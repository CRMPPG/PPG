"""Tests for distress scoring logic."""

from datetime import date, timedelta

from ppg.analysis.distress_scorer import score_property, rank_properties


def test_clean_property_scores_zero():
    prop = {"address": "123 Main St", "list_price": 300000, "assessed_value": 280000}
    breakdown = score_property(prop)
    assert breakdown.total == 0


def test_tax_delinquent_scores_high():
    prop = {
        "address": "456 Elm St",
        "tax_delinquent": True,
        "tax_delinquent_years": 3,
    }
    breakdown = score_property(prop)
    assert breakdown.tax_delinquency_score >= 12
    assert breakdown.total >= 12


def test_price_below_assessed_value():
    prop = {
        "address": "789 Oak Ave",
        "list_price": 150000,
        "assessed_value": 300000,
    }
    breakdown = score_property(prop)
    assert breakdown.price_discount_score > 0
    assert prop["price_to_assessed_ratio"] == 0.5


def test_deep_discount_gets_max_score():
    prop = {
        "address": "789 Oak Ave",
        "list_price": 100000,
        "assessed_value": 300000,
    }
    breakdown = score_property(prop)
    assert breakdown.price_discount_score == 15  # below 0.7 ratio


def test_foreclosure_and_reo():
    prop = {"address": "321 Pine Rd", "in_foreclosure": True, "is_bank_owned": True}
    breakdown = score_property(prop)
    assert breakdown.foreclosure_score == 10


def test_vacancy_scores():
    prop = {"address": "111 Cedar Ln", "is_vacant": True}
    breakdown = score_property(prop)
    assert breakdown.vacancy_score == 10


def test_code_violations():
    prop = {"address": "222 Birch Ct", "code_violations": 5}
    breakdown = score_property(prop)
    assert breakdown.code_violation_score == 5  # capped at 5


def test_days_on_market():
    prop = {"address": "333 Maple Dr", "days_on_market": 200}
    breakdown = score_property(prop)
    assert breakdown.days_on_market_score == 10


def test_rank_properties_sorts_descending():
    props = [
        {"address": "A", "distress_score": 0},
        {"address": "B", "tax_delinquent": True, "in_foreclosure": True, "is_vacant": True},
        {"address": "C", "days_on_market": 100},
    ]
    ranked = rank_properties(props)
    scores = [p["distress_score"] for p in ranked]
    assert scores == sorted(scores, reverse=True)


def test_recorded_doc_nod():
    prop = {"address": "100 NOD St", "notice_of_default": True}
    breakdown = score_property(prop)
    assert breakdown.recorded_doc_score == 8


def test_recorded_doc_lis_pendens():
    prop = {"address": "200 LP Ave", "lis_pendens": True}
    breakdown = score_property(prop)
    assert breakdown.recorded_doc_score == 6


def test_recorded_doc_trustee_sale():
    prop = {"address": "300 TS Rd", "trustee_sale_scheduled": True}
    breakdown = score_property(prop)
    assert breakdown.recorded_doc_score == 6


def test_recorded_doc_all_plus_recency():
    prop = {
        "address": "400 All Docs Ln",
        "notice_of_default": True,
        "lis_pendens": True,
        "trustee_sale_scheduled": True,
        "nod_date": date.today() - timedelta(days=30),
    }
    breakdown = score_property(prop)
    assert breakdown.recorded_doc_score == 20  # capped at 20


def test_recorded_doc_nod_old_no_recency_bonus():
    prop = {
        "address": "500 Old NOD Ct",
        "notice_of_default": True,
        "nod_date": date.today() - timedelta(days=365),
    }
    breakdown = score_property(prop)
    assert breakdown.recorded_doc_score == 8  # no recency bonus


def test_heavily_distressed_property():
    prop = {
        "address": "999 Disaster Blvd",
        "list_price": 80000,
        "assessed_value": 250000,
        "tax_delinquent": True,
        "tax_delinquent_years": 4,
        "notice_of_default": True,
        "lis_pendens": True,
        "nod_date": date.today() - timedelta(days=60),
        "in_foreclosure": True,
        "is_bank_owned": True,
        "has_liens": True,
        "lien_amount": 60000,
        "is_vacant": True,
        "code_violations": 3,
        "days_on_market": 365,
    }
    breakdown = score_property(prop)
    assert breakdown.total >= 70  # heavily distressed
    top = breakdown.top_factors
    assert top[0][1] > 0  # top factor has nonzero score
