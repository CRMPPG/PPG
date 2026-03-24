"""Import property data from CSV files (assessor exports, listing exports, etc.)

Many counties provide bulk data downloads as CSV. MLS exports and listing
platforms also export to CSV. This module handles importing those files.
Supports both comma-delimited and tab-delimited formats.
"""

import csv
import re
from pathlib import Path

COLUMN_MAP = {
    # Address
    r"^address$|street|situs": "address",
    r"^city$": "city",
    r"^state$": "state",
    r"zip|postal": "zip_code",
    r"county": "county",
    r"parcel|apn|pin|tax.?id": "parcel_number",
    # Characteristics
    r"prop.?type|land.?use|class|^sub$": "property_type",
    r"bed": "bedrooms",
    r"bath": "bathrooms",
    r"sq.?ft|liv(ing)?.?area|heated|approx.?liv": "sqft",
    r"lot.?(size|area|sq)": "lot_size_sqft",
    r"year.?built": "year_built",
    r"bldg.?des|building.?desc": "building_description",
    r"pool|pv.?pool": "has_pool",
    r"garage": "garage",
    # Listing
    r"(list|ask|current).?price": "list_price",
    r"list.?date": "list_date",
    r"^dom$|days.?on.?market": "days_on_market",
    r"^stat$|status|listing.?status": "listing_status",
    r"^mls$|mls.?(num|#|id)": "listing_source",
    r"close.?date": "close_date",
    # Assessor
    r"assess.*(val|worth)": "assessed_value",
    r"land.?val": "assessed_land_value",
    r"improv.?val": "assessed_improvement_value",
    r"market.?val": "market_value",
    # Tax
    r"tax.?(amount|due|total)": "annual_tax_amount",
    r"tax.?year": "tax_year",
    r"delinq": "tax_delinquent",
    r"lien": "has_liens",
    r"foreclos": "in_foreclosure",
    r"bank.?own|reo": "is_bank_owned",
    r"vacant": "is_vacant",
    r"code.?viol": "code_violations",
    r"owner.?occ": "owner_occupied",
}

CURRENCY_FIELDS = {
    "list_price",
    "assessed_value",
    "assessed_land_value",
    "assessed_improvement_value",
    "market_value",
    "annual_tax_amount",
}
INT_FIELDS = {"bedrooms", "sqft", "lot_size_sqft", "year_built", "days_on_market", "tax_year", "code_violations", "garage"}
FLOAT_FIELDS = {"bathrooms"}
BOOL_FIELDS = {"tax_delinquent", "has_liens", "in_foreclosure", "is_bank_owned", "is_vacant", "owner_occupied", "has_pool"}
# Fields we import but don't store directly on the Property model (kept in dict for reference)
PASSTHROUGH_FIELDS = {"building_description", "listing_source", "close_date", "garage", "has_pool"}


def _match_column(col_name: str) -> str | None:
    """Match a CSV column header to a model field name."""
    col_lower = col_name.strip().lower()
    for pattern, field in COLUMN_MAP.items():
        if re.search(pattern, col_lower):
            return field
    return None


def _parse_value(field: str, raw: str) -> object:
    """Convert a raw CSV value to the appropriate Python type."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw or raw.lower() in ("n/a", "none", "null", "-"):
        return None

    if field in CURRENCY_FIELDS:
        cleaned = re.sub(r"[^\d.]", "", raw)
        return float(cleaned) if cleaned else None
    if field in INT_FIELDS:
        cleaned = raw.replace(",", "")
        match = re.search(r"(\d+)", cleaned)
        return int(match.group(1)) if match else None
    if field in FLOAT_FIELDS:
        match = re.search(r"(\d+\.?\d*)", raw)
        return float(match.group(1)) if match else None
    if field in BOOL_FIELDS:
        return raw.lower() in ("true", "yes", "y", "1", "x")
    return raw


def _detect_delimiter(filepath: Path) -> str:
    """Detect whether a file is tab-delimited or comma-delimited."""
    with open(filepath, encoding="utf-8-sig") as f:
        first_line = f.readline()
        tab_count = first_line.count("\t")
        comma_count = first_line.count(",")
        return "\t" if tab_count > comma_count else ","


def import_csv(filepath: str | Path) -> list[dict]:
    """Import a CSV file and return a list of property dicts.

    Automatically maps CSV column headers to property model fields
    using fuzzy pattern matching. Supports tab and comma delimiters.
    """
    filepath = Path(filepath)
    records = []
    delimiter = _detect_delimiter(filepath)

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        # Build column mapping
        col_map = {}
        for col in reader.fieldnames or []:
            matched = _match_column(col)
            if matched:
                col_map[col] = matched

        for row in reader:
            record = {}
            for csv_col, model_field in col_map.items():
                val = _parse_value(model_field, row.get(csv_col, ""))
                if val is not None:
                    record[model_field] = val
            if record.get("address") or record.get("parcel_number"):
                records.append(record)

    return records
