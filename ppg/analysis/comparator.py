"""Compare listing data against assessor data to find discrepancies and opportunities."""

import re
from difflib import SequenceMatcher


def normalize_address(address: str) -> str:
    """Normalize an address for fuzzy matching."""
    addr = address.upper().strip()
    replacements = {
        r"\bSTREET\b": "ST",
        r"\bAVENUE\b": "AVE",
        r"\bBOULEVARD\b": "BLVD",
        r"\bDRIVE\b": "DR",
        r"\bLANE\b": "LN",
        r"\bROAD\b": "RD",
        r"\bCOURT\b": "CT",
        r"\bPLACE\b": "PL",
        r"\bCIRCLE\b": "CIR",
        r"\bNORTH\b": "N",
        r"\bSOUTH\b": "S",
        r"\bEAST\b": "E",
        r"\bWEST\b": "W",
        r"\bAPARTMENT\b": "APT",
        r"\bSUITE\b": "STE",
        r"\bUNIT\b": "UNIT",
        r"[.,#]": "",
    }
    for pattern, repl in replacements.items():
        addr = re.sub(pattern, repl, addr)
    addr = re.sub(r"\s+", " ", addr)
    return addr


def match_properties(
    listings: list[dict], assessor_records: list[dict], threshold: float = 0.85
) -> list[dict]:
    """Match listing records to assessor records by address or parcel number.

    Returns merged records with data from both sources.
    """
    matched = []
    unmatched_listings = []

    # Index assessor records by parcel number for fast lookup
    parcel_index = {}
    for rec in assessor_records:
        pn = rec.get("parcel_number", "").strip()
        if pn:
            parcel_index[pn] = rec

    # Index by normalized address
    addr_index = {}
    for rec in assessor_records:
        addr = rec.get("address", "")
        if addr:
            addr_index[normalize_address(addr)] = rec

    for listing in listings:
        merged = None

        # Try parcel number match first (exact)
        pn = listing.get("parcel_number", "").strip()
        if pn and pn in parcel_index:
            merged = {**parcel_index[pn], **listing, "match_method": "parcel_number"}

        # Try exact normalized address match
        if not merged:
            listing_addr = normalize_address(listing.get("address", ""))
            if listing_addr and listing_addr in addr_index:
                merged = {**addr_index[listing_addr], **listing, "match_method": "address_exact"}

        # Try fuzzy address match
        if not merged and listing_addr:
            best_score = 0
            best_match = None
            for norm_addr, rec in addr_index.items():
                score = SequenceMatcher(None, listing_addr, norm_addr).ratio()
                if score > best_score:
                    best_score = score
                    best_match = rec
            if best_score >= threshold and best_match:
                merged = {
                    **best_match,
                    **listing,
                    "match_method": f"address_fuzzy({best_score:.2f})",
                }

        if merged:
            matched.append(merged)
        else:
            unmatched_listings.append(listing)

    return matched


def find_discrepancies(merged: list[dict]) -> list[dict]:
    """Flag properties where listing data conflicts with assessor data.

    Returns the input list with added 'discrepancies' field.
    """
    for prop in merged:
        flags = []

        list_price = prop.get("list_price")
        assessed = prop.get("assessed_value")
        if list_price and assessed and assessed > 0:
            ratio = list_price / assessed
            if ratio < 0.7:
                flags.append(f"List price is {(1-ratio)*100:.0f}% below assessed value")
            elif ratio > 1.5:
                flags.append(f"List price is {(ratio-1)*100:.0f}% above assessed value")

        listing_sqft = prop.get("sqft")
        if listing_sqft and prop.get("assessed_sqft"):
            diff_pct = abs(listing_sqft - prop["assessed_sqft"]) / prop["assessed_sqft"]
            if diff_pct > 0.15:
                flags.append(f"Sqft discrepancy: listing={listing_sqft}, assessor={prop['assessed_sqft']}")

        if prop.get("tax_delinquent") and prop.get("listing_status") == "Active":
            flags.append("Active listing with delinquent taxes")

        prop["discrepancies"] = flags

    return merged
