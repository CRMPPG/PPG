"""Merge recorded document findings onto property records."""

from datetime import date


def merge_recorder_documents(
    properties: list[dict], recorder_results: dict[str, list[dict]]
) -> list[dict]:
    """Merge recorder document findings onto property dicts.

    Args:
        properties: List of property dicts (from CSV import).
        recorder_results: Dict mapping parcel_number -> list of document dicts.
            Each document dict has: document_type, recording_date, grantor,
            grantee, instrument_number, document_amount, etc.

    Returns:
        Updated property dicts with recorder-derived distress flags set.
    """
    for prop in properties:
        parcel = prop.get("parcel_number", "")
        if not parcel or parcel not in recorder_results:
            continue

        docs = recorder_results[parcel]
        if not docs:
            continue

        prop["recorder_document_count"] = len(docs)
        prop["_recorded_documents"] = docs

        most_recent_nod_date = None
        total_lien_amount = 0

        for doc in docs:
            doc_type = doc.get("document_type", "").lower()

            if "notice of default" in doc_type:
                prop["notice_of_default"] = True
                prop["in_foreclosure"] = True
                rec_date = doc.get("recording_date")
                if rec_date and (most_recent_nod_date is None or rec_date > most_recent_nod_date):
                    most_recent_nod_date = rec_date

            if "lis pendens" in doc_type:
                prop["lis_pendens"] = True
                prop["in_foreclosure"] = True

            if "trustee" in doc_type and "sale" in doc_type:
                prop["trustee_sale_scheduled"] = True
                prop["in_foreclosure"] = True

            if "lien" in doc_type:
                prop["has_liens"] = True
                amount = doc.get("document_amount")
                if amount and isinstance(amount, (int, float)):
                    total_lien_amount += amount

        if most_recent_nod_date:
            prop["nod_date"] = most_recent_nod_date

        if total_lien_amount > 0:
            existing = prop.get("lien_amount", 0) or 0
            prop["lien_amount"] = existing + total_lien_amount

    return properties
