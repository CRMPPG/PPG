"""Tests for document merger logic."""

from datetime import date

from ppg.analysis.document_merger import merge_recorder_documents


def test_nod_sets_flags():
    properties = [{"address": "123 Main St", "parcel_number": "139-16-813-026"}]
    recorder_results = {
        "139-16-813-026": [
            {
                "document_type": "Notice of Default",
                "recording_date": date(2025, 6, 15),
                "grantor": "Smith John",
                "grantee": "Big Bank NA",
            }
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["notice_of_default"] is True
    assert result[0]["in_foreclosure"] is True
    assert result[0]["nod_date"] == date(2025, 6, 15)
    assert result[0]["recorder_document_count"] == 1


def test_lis_pendens_sets_flags():
    properties = [{"address": "456 Oak Ave", "parcel_number": "100-20-300-040"}]
    recorder_results = {
        "100-20-300-040": [
            {"document_type": "Lis Pendens", "recording_date": date(2025, 8, 1)}
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["lis_pendens"] is True
    assert result[0]["in_foreclosure"] is True


def test_trustee_sale_sets_flags():
    properties = [{"address": "789 Elm Dr", "parcel_number": "200-30-400-050"}]
    recorder_results = {
        "200-30-400-050": [
            {"document_type": "Notice of Trustee's Sale", "recording_date": date(2025, 9, 1)}
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["trustee_sale_scheduled"] is True
    assert result[0]["in_foreclosure"] is True


def test_lien_accumulates_amount():
    properties = [{"address": "321 Pine Rd", "parcel_number": "300-40-500-060"}]
    recorder_results = {
        "300-40-500-060": [
            {"document_type": "Federal Tax Lien", "document_amount": 25000},
            {"document_type": "Mechanics Lien", "document_amount": 15000},
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["has_liens"] is True
    assert result[0]["lien_amount"] == 40000
    assert result[0]["recorder_document_count"] == 2


def test_no_matching_parcel_unchanged():
    properties = [{"address": "111 Cedar Ln", "parcel_number": "999-99-999-999"}]
    recorder_results = {
        "000-00-000-000": [
            {"document_type": "Notice of Default", "recording_date": date(2025, 1, 1)}
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0].get("notice_of_default") is None
    assert result[0].get("in_foreclosure") is None


def test_multiple_nods_uses_most_recent():
    properties = [{"address": "222 Birch Ct", "parcel_number": "400-50-600-070"}]
    recorder_results = {
        "400-50-600-070": [
            {"document_type": "Notice of Default", "recording_date": date(2024, 1, 1)},
            {"document_type": "Notice of Default", "recording_date": date(2025, 6, 1)},
            {"document_type": "Notice of Default", "recording_date": date(2025, 3, 1)},
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["nod_date"] == date(2025, 6, 1)


def test_existing_lien_amount_added_to():
    properties = [
        {"address": "333 Maple Dr", "parcel_number": "500-60-700-080", "lien_amount": 10000}
    ]
    recorder_results = {
        "500-60-700-080": [
            {"document_type": "Tax Lien", "document_amount": 5000},
        ]
    }
    result = merge_recorder_documents(properties, recorder_results)
    assert result[0]["lien_amount"] == 15000
