"""Tests for Clark County Recorder scraper utilities."""

from ppg.scrapers.clark_county_recorder import normalize_parcel
from ppg.scrapers.recorder_base import DISTRESS_DOCUMENT_TYPES


# Standard format XXX-XX-XXX-XXX
def test_normalize_parcel_dashed():
    assert normalize_parcel("179-34-712-030") == "179-34-712-030"


def test_normalize_parcel_no_dashes():
    assert normalize_parcel("17934712030") == "179-34-712-030"


def test_normalize_parcel_spaces():
    assert normalize_parcel("179 34 712 030") == "179-34-712-030"


def test_normalize_parcel_with_whitespace():
    assert normalize_parcel("  179-34-712-030  ") == "179-34-712-030"


# Short format (older areas)
def test_normalize_parcel_short_2_3_2():
    assert normalize_parcel("18-305-18") == "18-305-18"


def test_normalize_parcel_short_3_3_2():
    assert normalize_parcel("003-132-22") == "003-132-22"


def test_normalize_parcel_short_3_3_2_alt():
    assert normalize_parcel("013-042-17") == "013-042-17"


# Letter prefix format
def test_normalize_parcel_letter_prefix():
    assert normalize_parcel("C-0645-0160-0000") == "C-0645-0160-0000"


def test_normalize_parcel_letter_prefix_lowercase():
    assert normalize_parcel("c-0645-0160-0000") == "C-0645-0160-0000"


# Invalid
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
