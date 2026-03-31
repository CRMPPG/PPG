"""Tests for fix-and-flip calculator."""

from ppg.analysis.flip_calculator import (
    FlipAssumptions,
    FlipBreakdown,
    calculate_flip,
    analyze_flip_from_csv,
    _get_float,
)


# ── Single deal calculation ──────────────────────────────────────────

def test_basic_profitable_deal():
    b = calculate_flip(200_000, 320_000, 40_000)
    assert b.purchase_price == 200_000
    assert b.after_repair_value == 320_000
    assert b.rehab_cost == 40_000
    assert b.net_profit > 0
    assert b.roi_pct > 0
    assert b.is_profitable


def test_unprofitable_deal():
    b = calculate_flip(300_000, 310_000, 50_000)
    assert b.net_profit < 0
    assert not b.is_profitable


def test_purchase_costs():
    a = FlipAssumptions(buyer_closing_pct=0.02, inspection_cost=500, loan_to_value=0.80, loan_points=2.0)
    b = calculate_flip(200_000, 300_000, 30_000, assumptions=a)
    assert b.buyer_closing == 200_000 * 0.02  # 4000
    assert b.inspection == 500
    assert b.loan_amount == 160_000  # 80% LTV
    assert b.loan_points_cost == 160_000 * 0.02  # 3200
    assert b.total_purchase_costs == 4000 + 500 + 3200


def test_holding_costs():
    a = FlipAssumptions(
        holding_months=6,
        loan_to_value=0.80,
        annual_interest_rate=0.12,
        monthly_insurance=100,
        monthly_utilities=150,
        monthly_hoa=50,
        monthly_taxes=200,
    )
    b = calculate_flip(100_000, 200_000, 20_000, assumptions=a)
    loan = 80_000
    monthly_interest = loan * (0.12 / 12)  # 800
    assert b.interest_cost == monthly_interest * 6  # 4800
    assert b.insurance_cost == 100 * 6
    assert b.utilities_cost == 150 * 6
    assert b.hoa_cost == 50 * 6
    assert b.taxes_cost == 200 * 6
    expected_total = (monthly_interest + 100 + 150 + 50 + 200) * 6
    assert b.total_holding_costs == expected_total


def test_selling_costs():
    a = FlipAssumptions(agent_commission_pct=0.06, seller_closing_pct=0.01)
    b = calculate_flip(200_000, 300_000, 30_000, assumptions=a)
    assert b.agent_commission == 300_000 * 0.06
    assert b.seller_closing == 300_000 * 0.01
    assert b.total_selling_costs == b.agent_commission + b.seller_closing


def test_mao_calculation():
    a = FlipAssumptions(profit_margin_pct=0.30)
    b = calculate_flip(200_000, 300_000, 40_000, assumptions=a)
    expected_mao = 300_000 * 0.70 - 40_000  # 170,000
    assert b.mao == expected_mao


def test_total_project_cost():
    a = FlipAssumptions(
        buyer_closing_pct=0.0, inspection_cost=0, loan_to_value=0.0,
        loan_points=0, annual_interest_rate=0, monthly_insurance=0,
        monthly_utilities=0, monthly_hoa=0, monthly_taxes=0,
        agent_commission_pct=0, seller_closing_pct=0,
    )
    b = calculate_flip(100_000, 200_000, 30_000, assumptions=a)
    # With zero costs, total = purchase + rehab
    assert b.total_project_cost == 130_000
    assert b.net_profit == 70_000


def test_property_tax_used_from_prop():
    """annual_tax_amount from property dict overrides assumption."""
    prop = {"address": "123 Main", "annual_tax_amount": 2400}
    a = FlipAssumptions(holding_months=6, monthly_taxes=0)
    b = calculate_flip(200_000, 300_000, 30_000, assumptions=a, prop=prop)
    assert b.taxes_cost == 200 * 6  # 2400/12 * 6


def test_flip_results_attached_to_prop():
    prop = {"address": "456 Elm"}
    calculate_flip(200_000, 300_000, 30_000, prop=prop)
    assert "flip_net_profit" in prop
    assert "flip_roi_pct" in prop
    assert "flip_mao" in prop
    assert "flip_purchase_price" in prop


def test_cash_out_of_pocket():
    a = FlipAssumptions(
        loan_to_value=0.80, buyer_closing_pct=0, inspection_cost=0,
        loan_points=0, annual_interest_rate=0, monthly_insurance=0,
        monthly_utilities=0, monthly_hoa=0, monthly_taxes=0,
    )
    b = calculate_flip(100_000, 200_000, 20_000, assumptions=a)
    # Down payment = 20k, rehab = 20k, no other costs
    assert b.cash_out_of_pocket == 40_000


def test_annualized_roi():
    a = FlipAssumptions(
        holding_months=3, loan_to_value=0, buyer_closing_pct=0,
        inspection_cost=0, loan_points=0, annual_interest_rate=0,
        monthly_insurance=0, monthly_utilities=0, monthly_hoa=0,
        monthly_taxes=0, agent_commission_pct=0, seller_closing_pct=0,
    )
    b = calculate_flip(100_000, 150_000, 0, assumptions=a)
    # profit=50k, cash=100k, ROI=50%, annualized = 50% * (12/3) = 200%
    assert b.roi_pct == 50.0
    assert b.annualized_roi_pct == 200.0


def test_summary_lines():
    b = calculate_flip(200_000, 300_000, 30_000)
    lines = b.summary_lines
    assert len(lines) == 12
    assert any("Purchase Price" in l for l in lines)
    assert any("Net Profit" in l for l in lines)


# ── Batch CSV analysis ───────────────────────────────────────────────

def test_analyze_flip_from_csv_basic():
    records = [
        {"address": "A", "purchase_price": 200_000, "arv": 320_000, "rehab_cost": 30_000},
        {"address": "B", "purchase_price": 150_000, "arv": 250_000, "rehab_cost": 40_000},
    ]
    results = analyze_flip_from_csv(records)
    assert len(results) == 2
    assert all(r.get("flip_net_profit") is not None for r in results)
    # Sorted by profit descending
    assert results[0]["flip_net_profit"] >= results[1]["flip_net_profit"]


def test_analyze_flip_uses_list_price_fallback():
    records = [
        {"address": "C", "list_price": 180_000, "arv": 280_000, "rehab_cost": 25_000},
    ]
    results = analyze_flip_from_csv(records)
    assert results[0]["flip_purchase_price"] == 180_000


def test_analyze_flip_missing_arv():
    records = [{"address": "D", "purchase_price": 200_000}]
    results = analyze_flip_from_csv(records)
    assert results[0].get("flip_net_profit") is None


def test_analyze_flip_string_dollar_amounts():
    records = [
        {"address": "E", "purchase_price": "$200,000", "arv": "$300,000", "rehab_cost": "$25,000"},
    ]
    results = analyze_flip_from_csv(records)
    assert results[0]["flip_purchase_price"] == 200_000


# ── _get_float helper ────────────────────────────────────────────────

def test_get_float_with_dollar_sign():
    assert _get_float({"price": "$1,234.56"}, "price") == 1234.56


def test_get_float_with_int():
    assert _get_float({"x": 42}, "x") == 42.0


def test_get_float_missing_key():
    assert _get_float({}, "x") is None


def test_get_float_garbage():
    assert _get_float({"x": "N/A"}, "x") is None
