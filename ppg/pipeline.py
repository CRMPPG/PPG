"""Main pipeline: ingest data, match, score, and store results."""

from pathlib import Path

from ppg.analysis.comparator import find_discrepancies, match_properties
from ppg.analysis.distress_scorer import rank_properties
from ppg.analysis.document_merger import merge_recorder_documents
from ppg.models.database import Property, RecordedDocument, get_session, init_db
from ppg.scrapers.csv_import import import_csv


def run_csv_pipeline(
    listing_csv: str | Path,
    assessor_csv: str | Path,
    database_url: str | None = None,
) -> list[dict]:
    """Run the full pipeline from CSV files.

    1. Import listings CSV
    2. Import assessor CSV
    3. Match records by address/parcel
    4. Find discrepancies
    5. Score distress
    6. Store in database
    7. Return ranked results
    """
    # Import
    listings = import_csv(listing_csv)
    assessor_records = import_csv(assessor_csv)

    # Match & analyze
    merged = match_properties(listings, assessor_records)
    merged = find_discrepancies(merged)
    ranked = rank_properties(merged)

    # Store
    init_db(database_url)
    session = get_session(database_url)
    _store_results(session, ranked)

    return ranked


def run_scraper_pipeline(
    scraper,
    listing_csv: str | Path,
    addresses: list[str] | None = None,
    database_url: str | None = None,
) -> list[dict]:
    """Run pipeline using a live scraper for assessor data + CSV for listings.

    1. Import listings CSV
    2. For each listing, scrape assessor data by address
    3. Match, score, store
    """
    listings = import_csv(listing_csv)

    assessor_records = []
    search_addresses = addresses or [l.get("address", "") for l in listings if l.get("address")]

    for addr in search_addresses:
        try:
            results = scraper.search_by_address(addr)
            assessor_records.extend(results)
        except Exception as e:
            print(f"  Warning: could not scrape assessor for '{addr}': {e}")

    merged = match_properties(listings, assessor_records)
    merged = find_discrepancies(merged)
    ranked = rank_properties(merged)

    init_db(database_url)
    session = get_session(database_url)
    _store_results(session, ranked)

    return ranked


def run_recorder_pipeline(
    listing_csv: str | Path,
    headless: bool = True,
    delay: float = 3.0,
    database_url: str | None = None,
) -> list[dict]:
    """Run pipeline: MLS CSV + Clark County Recorder scraping.

    1. Import MLS listings CSV
    2. Normalize parcel numbers
    3. For each parcel, search recorder for distress documents
    4. Merge document findings onto properties
    5. Score and rank
    6. Store properties + recorded documents in DB
    """
    from ppg.scrapers.clark_county_recorder import (
        ClarkCountyRecorderScraper,
        normalize_parcel,
    )

    listings = import_csv(listing_csv)

    # Normalize parcel numbers
    for listing in listings:
        pn = listing.get("parcel_number", "")
        if pn:
            normalized = normalize_parcel(pn)
            if normalized:
                listing["parcel_number"] = normalized

    # Scrape recorder for each parcel
    recorder_results = {}
    parcels = [l["parcel_number"] for l in listings if l.get("parcel_number")]

    with ClarkCountyRecorderScraper(headless=headless, delay_seconds=delay) as scraper:
        for i, parcel in enumerate(parcels):
            print(f"  [{i+1}/{len(parcels)}] Searching recorder for {parcel}...")
            try:
                docs = scraper.get_distress_documents(parcel)
                recorder_results[parcel] = docs
                if docs:
                    print(f"    Found {len(docs)} distress document(s)")
            except Exception as e:
                print(f"    Warning: search failed for {parcel}: {e}")

    # Merge and score
    merged = merge_recorder_documents(listings, recorder_results)
    ranked = rank_properties(merged)

    # Store
    init_db(database_url)
    session = get_session(database_url)
    _store_results(session, ranked)
    _store_recorded_documents(session, ranked)

    return ranked


def _store_results(session, ranked: list[dict]):
    """Upsert ranked property dicts into the database."""
    property_fields = {c.name for c in Property.__table__.columns}

    for data in ranked:
        filtered = {k: v for k, v in data.items() if k in property_fields and k != "id"}
        parcel = filtered.get("parcel_number")

        existing = None
        if parcel:
            existing = session.query(Property).filter_by(parcel_number=parcel).first()

        if existing:
            for k, v in filtered.items():
                setattr(existing, k, v)
        else:
            session.add(Property(**filtered))

    session.commit()


def _store_recorded_documents(session, ranked: list[dict]):
    """Store recorded document details in the database."""
    for data in ranked:
        docs = data.pop("_recorded_documents", [])
        if not docs:
            continue

        parcel = data.get("parcel_number")
        if not parcel:
            continue

        prop = session.query(Property).filter_by(parcel_number=parcel).first()
        if not prop:
            continue

        doc_fields = {c.name for c in RecordedDocument.__table__.columns}
        for doc in docs:
            filtered = {k: v for k, v in doc.items() if k in doc_fields and k != "id"}
            filtered["property_id"] = prop.id
            filtered["parcel_number"] = parcel
            session.add(RecordedDocument(**filtered))

    session.commit()
