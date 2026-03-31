"""Fix-and-flip deal calculator.

Calculates profitability for distressed property flips including:
- Purchase costs (closing costs, inspection)
- Rehab / repair budget
- Holding costs (loan interest, taxes, insurance, utilities, HOA)
- Selling costs (agent commissions, seller closing)
- Profit, ROI, and Maximum Allowable Offer (MAO)
"""

from dataclasses import dataclass, field


@dataclass
class FlipAssumptions:
    """Default assumptions for flip analysis.  Override per-deal as needed."""

    # Purchase-side closing costs as % of purchase price
    buyer_closing_pct: float = 0.02
    inspection_cost: float = 500.0

    # Financing
    loan_to_value: float = 0.80  # 80% LTV hard-money / conventional
    annual_interest_rate: float = 0.10  # 10% hard-money default
    loan_points: float = 2.0  # origination points (%)

    # Holding period
    holding_months: int = 6

    # Monthly holding costs (estimated if not provided per-property)
    monthly_taxes: float = 0.0  # derived from annual_tax_amount when available
    monthly_insurance: float = 150.0
    monthly_utilities: float = 200.0
    monthly_hoa: float = 0.0

    # Selling costs
    agent_commission_pct: float = 0.05  # 5% total (buyer + seller agent)
    seller_closing_pct: float = 0.02

    # Profit target for MAO calculation (the "70% rule" margin)
    profit_margin_pct: float = 0.30  # investor wants 30% of ARV as margin


@dataclass
class FlipBreakdown:
    """Full financial breakdown of a fix-and-flip deal."""

    # Inputs
    address: str = ""
    purchase_price: float = 0
    after_repair_value: float = 0
    rehab_cost: float = 0

    # Purchase costs
    buyer_closing: float = 0
    inspection: float = 0
    loan_amount: float = 0
    loan_points_cost: float = 0
    total_purchase_costs: float = 0

    # Holding costs
    holding_months: int = 0
    interest_cost: float = 0
    taxes_cost: float = 0
    insurance_cost: float = 0
    utilities_cost: float = 0
    hoa_cost: float = 0
    total_holding_costs: float = 0

    # Selling costs
    agent_commission: float = 0
    seller_closing: float = 0
    total_selling_costs: float = 0

    # Summary
    total_project_cost: float = 0
    cash_out_of_pocket: float = 0
    net_profit: float = 0
    roi_pct: float = 0
    annualized_roi_pct: float = 0
    mao: float = 0  # Maximum Allowable Offer

    @property
    def is_profitable(self) -> bool:
        return self.net_profit > 0

    @property
    def summary_lines(self) -> list[str]:
        """Human-readable summary."""
        return [
            f"Purchase Price:    ${self.purchase_price:>12,.0f}",
            f"ARV:               ${self.after_repair_value:>12,.0f}",
            f"Rehab:             ${self.rehab_cost:>12,.0f}",
            f"Purchase Costs:    ${self.total_purchase_costs:>12,.0f}",
            f"Holding Costs:     ${self.total_holding_costs:>12,.0f}  ({self.holding_months} mo)",
            f"Selling Costs:     ${self.total_selling_costs:>12,.0f}",
            f"Total Project:     ${self.total_project_cost:>12,.0f}",
            f"Cash Out-of-Pocket:${self.cash_out_of_pocket:>12,.0f}",
            f"Net Profit:        ${self.net_profit:>12,.0f}",
            f"ROI:               {self.roi_pct:>12.1f}%",
            f"Annualized ROI:    {self.annualized_roi_pct:>12.1f}%",
            f"MAO (70% rule):    ${self.mao:>12,.0f}",
        ]


def calculate_flip(
    purchase_price: float,
    after_repair_value: float,
    rehab_cost: float,
    assumptions: FlipAssumptions | None = None,
    prop: dict | None = None,
) -> FlipBreakdown:
    """Run a full fix-and-flip analysis.

    Args:
        purchase_price: Agreed or proposed acquisition price.
        after_repair_value: Estimated ARV after rehab.
        rehab_cost: Estimated total repair / renovation budget.
        assumptions: Override default assumptions.
        prop: Optional property dict (from PPG pipeline) — used to pull
              annual_tax_amount and other fields automatically.

    Returns:
        FlipBreakdown with every cost line-item and profit metrics.
    """
    a = assumptions or FlipAssumptions()
    prop = prop or {}

    b = FlipBreakdown(
        address=prop.get("address", ""),
        purchase_price=purchase_price,
        after_repair_value=after_repair_value,
        rehab_cost=rehab_cost,
        holding_months=a.holding_months,
    )

    # --- Purchase costs ---
    b.buyer_closing = purchase_price * a.buyer_closing_pct
    b.inspection = a.inspection_cost
    b.loan_amount = purchase_price * a.loan_to_value
    b.loan_points_cost = b.loan_amount * (a.loan_points / 100)
    b.total_purchase_costs = b.buyer_closing + b.inspection + b.loan_points_cost

    # --- Holding costs ---
    monthly_interest = b.loan_amount * (a.annual_interest_rate / 12)
    b.interest_cost = monthly_interest * a.holding_months

    # Use property tax data if available, else fall back to assumption
    annual_tax = prop.get("annual_tax_amount") or (a.monthly_taxes * 12)
    monthly_tax = annual_tax / 12 if annual_tax else 0
    b.taxes_cost = monthly_tax * a.holding_months

    b.insurance_cost = a.monthly_insurance * a.holding_months
    b.utilities_cost = a.monthly_utilities * a.holding_months
    b.hoa_cost = a.monthly_hoa * a.holding_months

    b.total_holding_costs = (
        b.interest_cost + b.taxes_cost + b.insurance_cost
        + b.utilities_cost + b.hoa_cost
    )

    # --- Selling costs ---
    b.agent_commission = after_repair_value * a.agent_commission_pct
    b.seller_closing = after_repair_value * a.seller_closing_pct
    b.total_selling_costs = b.agent_commission + b.seller_closing

    # --- Totals ---
    b.total_project_cost = (
        purchase_price + rehab_cost
        + b.total_purchase_costs + b.total_holding_costs + b.total_selling_costs
    )

    # Cash out-of-pocket = down payment + rehab + purchase costs + holding costs
    down_payment = purchase_price - b.loan_amount
    b.cash_out_of_pocket = (
        down_payment + rehab_cost
        + b.total_purchase_costs + b.total_holding_costs
    )

    b.net_profit = after_repair_value - b.total_project_cost

    if b.cash_out_of_pocket > 0:
        b.roi_pct = (b.net_profit / b.cash_out_of_pocket) * 100
        if a.holding_months > 0:
            b.annualized_roi_pct = b.roi_pct * (12 / a.holding_months)
    else:
        b.roi_pct = 0
        b.annualized_roi_pct = 0

    # --- MAO: Maximum Allowable Offer (70% rule variant) ---
    # MAO = ARV * (1 - profit_margin) - rehab - purchase_costs_estimate - holding_estimate - selling_estimate
    b.mao = (
        after_repair_value * (1 - a.profit_margin_pct)
        - rehab_cost
    )

    # Attach flip results to the property dict so downstream pipeline can use them
    if prop is not None:
        prop["flip_purchase_price"] = purchase_price
        prop["flip_arv"] = after_repair_value
        prop["flip_rehab_cost"] = rehab_cost
        prop["flip_net_profit"] = round(b.net_profit, 2)
        prop["flip_roi_pct"] = round(b.roi_pct, 1)
        prop["flip_mao"] = round(b.mao, 2)
        prop["flip_total_project_cost"] = round(b.total_project_cost, 2)

    return b


def analyze_flip_from_csv(records: list[dict], assumptions: FlipAssumptions | None = None) -> list[dict]:
    """Batch-analyze flips from CSV records.

    Expects each record to have at minimum:
      - purchase_price (or list_price as fallback)
      - arv (or after_repair_value)
      - rehab_cost (or rehab or repair_cost)

    Returns records sorted by net profit descending.
    """
    a = assumptions or FlipAssumptions()

    for rec in records:
        purchase = _get_float(rec, "purchase_price") or _get_float(rec, "list_price") or 0
        arv = _get_float(rec, "arv") or _get_float(rec, "after_repair_value") or 0
        rehab = _get_float(rec, "rehab_cost") or _get_float(rec, "rehab") or _get_float(rec, "repair_cost") or 0

        if purchase > 0 and arv > 0:
            calculate_flip(purchase, arv, rehab, assumptions=a, prop=rec)
        else:
            rec["flip_net_profit"] = None
            rec["flip_roi_pct"] = None
            rec["flip_mao"] = None

    return sorted(
        records,
        key=lambda r: r.get("flip_net_profit") or float("-inf"),
        reverse=True,
    )


def _get_float(rec: dict, key: str) -> float | None:
    """Safely extract a float from a record, stripping $ and commas."""
    val = rec.get(key)
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
