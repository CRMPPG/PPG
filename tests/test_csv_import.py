"""Tests for CSV import functionality."""

import tempfile
from pathlib import Path

from ppg.scrapers.csv_import import import_csv


def _write_csv(rows: list[list[str]]) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    import csv
    writer = csv.writer(f)
    for row in rows:
        writer.writerow(row)
    f.close()
    return Path(f.name)


def test_basic_import():
    path = _write_csv([
        ["Address", "City", "State", "List Price", "Assessed Value"],
        ["123 Main St", "Springfield", "IL", "$250,000", "$230,000"],
        ["456 Oak Ave", "Springfield", "IL", "$180,000", "$200,000"],
    ])
    records = import_csv(path)
    assert len(records) == 2
    assert records[0]["address"] == "123 Main St"
    assert records[0]["list_price"] == 250000.0
    assert records[1]["assessed_value"] == 200000.0
    path.unlink()


def test_handles_alternate_headers():
    path = _write_csv([
        ["Street Address", "Bedrooms", "Bathrooms", "SqFt", "Year Built", "APN"],
        ["789 Elm Dr", "3", "2.5", "1800", "1995", "12-345-678"],
    ])
    records = import_csv(path)
    assert len(records) == 1
    assert records[0]["bedrooms"] == 3
    assert records[0]["bathrooms"] == 2.5
    assert records[0]["sqft"] == 1800
    assert records[0]["parcel_number"] == "12-345-678"
    path.unlink()


def test_boolean_fields():
    path = _write_csv([
        ["Address", "Tax Delinquent", "Foreclosure", "Vacant"],
        ["111 Test St", "Yes", "No", "Y"],
    ])
    records = import_csv(path)
    assert records[0]["tax_delinquent"] is True
    assert records[0]["is_vacant"] is True
    path.unlink()


def test_skips_empty_rows():
    path = _write_csv([
        ["Address", "List Price"],
        ["", ""],
        ["123 Real St", "$100,000"],
    ])
    records = import_csv(path)
    assert len(records) == 1
    path.unlink()
