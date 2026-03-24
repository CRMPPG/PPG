"""Score properties by distress level.

Distress score ranges from 0-100. Higher = more distressed = more opportunity.

Scoring factors and weights:
- Tax delinquency (0-20 pts)
- Price vs assessed value discount (0-15 pts)
- Foreclosure / bank-owned status (0-10 pts)
- Recorded distress documents (0-20 pts)
- Liens (0-10 pts)
- Vacancy (0-10 pts)
- Code violations (0-5 pts)
- Days on market (0-10 pts)
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class DistressBreakdown:
    """Breakdown of distress score components."""

    tax_delinquency_score: float = 0
    price_discount_score: float = 0
    foreclosure_score: float = 0
    recorded_doc_score: float = 0
    lien_score: float = 0
    vacancy_score: float = 0
    code_violation_score: float = 0
    days_on_market_score: float = 0
    total: float = 0

    @property
    def top_factors(self) -> list[tuple[str, float]]:
        """Return scoring factors sorted by contribution, descending."""
        factors = [
            ("Tax Delinquency", self.tax_delinquency_score),
            ("Price Discount", self.price_discount_score),
            ("Foreclosure/REO", self.foreclosure_score),
            ("Recorded Documents", self.recorded_doc_score),
            ("Liens", self.lien_score),
            ("Vacancy", self.vacancy_score),
            ("Code Violations", self.code_violation_score),
            ("Days on Market", self.days_on_market_score),
        ]
        return sorted(factors, key=lambda x: x[1], reverse=True)


def score_property(prop: dict) -> DistressBreakdown:
    """Calculate distress score for a property dict.

    Args:
        prop: Dict with property fields (matching the Property model).

    Returns:
        DistressBreakdown with individual component scores and total.
    """
    breakdown = DistressBreakdown()

    # --- Tax delinquency (max 20 pts) ---
    if prop.get("tax_delinquent"):
        breakdown.tax_delinquency_score = 12  # base for any delinquency
        years = prop.get("tax_delinquent_years", 0) or 0
        breakdown.tax_delinquency_score += min(years * 2, 8)  # up to 8 more

    # --- Price vs assessed value discount (max 15 pts) ---
    list_price = prop.get("list_price")
    assessed = prop.get("assessed_value") or prop.get("market_value")
    if list_price and assessed and assessed > 0:
        ratio = list_price / assessed
        prop["price_to_assessed_ratio"] = round(ratio, 3)
        if ratio < 0.7:
            breakdown.price_discount_score = 15
        elif ratio < 1.0:
            discount_pct = (1.0 - ratio) * 100
            breakdown.price_discount_score = min(discount_pct * 0.5, 15)

    # --- Foreclosure / bank-owned (max 10 pts) ---
    if prop.get("in_foreclosure"):
        breakdown.foreclosure_score += 7
    if prop.get("is_bank_owned"):
        breakdown.foreclosure_score += 3
    breakdown.foreclosure_score = min(breakdown.foreclosure_score, 10)

    # --- Recorded distress documents (max 20 pts) ---
    recorded_doc_score = 0
    if prop.get("notice_of_default"):
        recorded_doc_score += 8
    if prop.get("lis_pendens"):
        recorded_doc_score += 6
    if prop.get("trustee_sale_scheduled"):
        recorded_doc_score += 6
    # Recency bonus: NOD within last 6 months
    nod_date = prop.get("nod_date")
    if nod_date:
        if isinstance(nod_date, date):
            days_since = (date.today() - nod_date).days
            if days_since <= 180:
                recorded_doc_score = min(recorded_doc_score + 4, 20)
    breakdown.recorded_doc_score = min(recorded_doc_score, 20)

    # --- Liens (max 10 pts) ---
    if prop.get("has_liens"):
        breakdown.lien_score = 5
        lien_amt = prop.get("lien_amount", 0) or 0
        if lien_amt > 50000:
            breakdown.lien_score = 10
        elif lien_amt > 10000:
            breakdown.lien_score = 8
        elif lien_amt > 0:
            breakdown.lien_score = 6

    # --- Vacancy (max 10 pts) ---
    if prop.get("is_vacant"):
        breakdown.vacancy_score = 10
    elif prop.get("owner_occupied") is False:
        breakdown.vacancy_score = 3  # absentee owner, slight signal

    # --- Code violations (max 5 pts) ---
    violations = prop.get("code_violations", 0) or 0
    if violations > 0:
        breakdown.code_violation_score = min(violations * 2, 5)

    # --- Days on market (max 10 pts) ---
    dom = prop.get("days_on_market", 0) or 0
    if dom > 180:
        breakdown.days_on_market_score = 10
    elif dom > 120:
        breakdown.days_on_market_score = 7
    elif dom > 90:
        breakdown.days_on_market_score = 5
    elif dom > 60:
        breakdown.days_on_market_score = 3

    breakdown.total = round(
        breakdown.tax_delinquency_score
        + breakdown.price_discount_score
        + breakdown.foreclosure_score
        + breakdown.recorded_doc_score
        + breakdown.lien_score
        + breakdown.vacancy_score
        + breakdown.code_violation_score
        + breakdown.days_on_market_score,
        1,
    )

    prop["distress_score"] = breakdown.total
    return breakdown


def rank_properties(properties: list[dict]) -> list[dict]:
    """Score and sort properties by distress level, most distressed first."""
    for prop in properties:
        score_property(prop)
    return sorted(properties, key=lambda p: p.get("distress_score", 0), reverse=True)
