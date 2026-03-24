"""Tests for property matching/comparison."""

from ppg.analysis.comparator import normalize_address, match_properties, find_discrepancies


def test_normalize_address():
    assert normalize_address("123 North Main Street") == "123 N MAIN ST"
    assert normalize_address("456 S. Oak Avenue, Apt 2") == "456 S OAK AVE APT 2"


def test_match_by_parcel():
    listings = [{"address": "123 Main St", "parcel_number": "ABC-123", "list_price": 200000}]
    assessor = [{"address": "123 Main Street", "parcel_number": "ABC-123", "assessed_value": 250000}]
    matched = match_properties(listings, assessor)
    assert len(matched) == 1
    assert matched[0]["match_method"] == "parcel_number"
    assert matched[0]["assessed_value"] == 250000
    assert matched[0]["list_price"] == 200000


def test_match_by_address():
    listings = [{"address": "456 Oak Avenue", "list_price": 150000}]
    assessor = [{"address": "456 Oak Ave", "assessed_value": 180000}]
    matched = match_properties(listings, assessor)
    assert len(matched) == 1
    assert "address" in matched[0]["match_method"]


def test_find_discrepancies_flags_price_gap():
    merged = [{
        "address": "789 Elm St",
        "list_price": 100000,
        "assessed_value": 200000,
        "listing_status": "Active",
        "tax_delinquent": True,
    }]
    result = find_discrepancies(merged)
    assert len(result[0]["discrepancies"]) >= 1
    assert any("below assessed" in d for d in result[0]["discrepancies"])
    assert any("delinquent" in d for d in result[0]["discrepancies"])
