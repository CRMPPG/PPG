"""Tests for Clark County Recorder scraper utilities."""

from ppg.scrapers.clark_county_recorder import normalize_parcel
from ppg.scrapers.recorder_base import DISTRESS_DOCUMENT_TYPES


def test_normalize_parcel_dashed():
    assert normalize_parcel("139-16-813-026") == "139-16-813-026"


def test_normalize_parcel_no_dashes():
    assert normalize_parcel("13916813026") == "139-16-813-026"


def test_normalize_parcel_spaces():
    assert normalize_parcel("139 16 813 026") == "139-16-813-026"


def test_normalize_parcel_with_whitespace():
    assert normalize_parcel("  139-16-813-026  ") == "139-16-813-026"


def test_normalize_parcel_invalid():
    assert normalize_parcel("ABC-123") is None
    assert normalize_parcel("12345") is None
    assert normalize_parcel("") is None


def test_distress_types_include_key_documents():
    assert "notice of default" in DISTRESS_DOCUMENT_TYPES
    assert "lis pendens" in DISTRESS_DOCUMENT_TYPES
    assert "trustee sale" in DISTRESS_DOCUMENT_TYPES
    assert "tax lien" in DISTRESS_DOCUMENT_TYPES
    assert "federal tax lien" in DISTRESS_DOCUMENT_TYPES
    assert "mechanics lien" in DISTRESS_DOCUMENT_TYPES
