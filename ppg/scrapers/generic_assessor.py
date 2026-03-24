"""Generic county assessor scraper using common page patterns.

Many county assessor sites share similar structures. This scraper uses
heuristic parsing to extract data from common layouts. For best results,
create a county-specific subclass.
"""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ppg.scrapers.base import BaseAssessorScraper


# Common field label patterns found on assessor sites
FIELD_PATTERNS = {
    "parcel_number": re.compile(
        r"(parcel|apn|pin|tax\s*id|account)\s*(number|no\.?|#)?", re.I
    ),
    "assessed_value": re.compile(r"(total\s*)?assess(ed)?\s*value", re.I),
    "assessed_land_value": re.compile(r"land\s*(assess(ed)?)?\s*value", re.I),
    "assessed_improvement_value": re.compile(
        r"(improvement|building|structure)\s*value", re.I
    ),
    "market_value": re.compile(r"(fair\s*)?market\s*value", re.I),
    "property_type": re.compile(r"(property|land\s*use)\s*(type|class|code)", re.I),
    "year_built": re.compile(r"year\s*built", re.I),
    "sqft": re.compile(r"(living|heated|total)\s*(area|sq\.?\s*ft|square\s*feet)", re.I),
    "lot_size_sqft": re.compile(r"lot\s*(size|area|sq\.?\s*ft)", re.I),
    "bedrooms": re.compile(r"bed(room)?s?", re.I),
    "bathrooms": re.compile(r"bath(room)?s?", re.I),
    "owner_name": re.compile(r"owner(\s*name)?", re.I),
    "tax_amount": re.compile(r"(total\s*)?tax(es)?\s*(amount|due)?", re.I),
    "tax_year": re.compile(r"tax\s*year", re.I),
    "tax_status": re.compile(r"(tax\s*)?(status|delinquen)", re.I),
}


def _parse_currency(text: str) -> float | None:
    """Extract a dollar amount from text like '$1,234.56'."""
    match = re.search(r"\$?\s*([\d,]+\.?\d*)", text.replace(",", "").strip())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _parse_int(text: str) -> int | None:
    match = re.search(r"(\d+)", text.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class GenericAssessorScraper(BaseAssessorScraper):
    """A heuristic scraper that attempts to parse common assessor page layouts.

    Configure by setting county_name, state, base_url, and search_path.
    """

    county_name = "Generic"
    state = ""
    base_url = ""
    search_path = "/search"  # path appended to base_url for searches
    search_param = "query"  # query parameter name for address searches

    def __init__(self, base_url=None, county_name=None, state=None, **kwargs):
        super().__init__(**kwargs)
        if base_url:
            self.base_url = base_url.rstrip("/")
        if county_name:
            self.county_name = county_name
        if state:
            self.state = state

    def search_by_address(self, address: str) -> list[dict]:
        url = urljoin(self.base_url, self.search_path)
        response = self.http.get(url, params={self.search_param: address})
        soup = BeautifulSoup(response.text, "lxml")
        return self._parse_search_results(soup)

    def search_by_parcel(self, parcel_number: str) -> dict | None:
        url = urljoin(self.base_url, self.search_path)
        response = self.http.get(url, params={self.search_param: parcel_number})
        soup = BeautifulSoup(response.text, "lxml")
        results = self._parse_search_results(soup)
        return results[0] if results else None

    def get_tax_status(self, parcel_number: str) -> dict:
        record = self.search_by_parcel(parcel_number)
        if not record:
            return {}
        return {
            k: record.get(k)
            for k in [
                "tax_delinquent",
                "tax_delinquent_amount",
                "annual_tax_amount",
                "tax_year",
            ]
            if record.get(k) is not None
        }

    def _parse_search_results(self, soup: BeautifulSoup) -> list[dict]:
        """Parse search result pages using heuristics."""
        results = []

        # Strategy 1: Look for result tables
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if cells:
                    record = self._match_fields(dict(zip(headers, cells)))
                    if record:
                        record["county"] = self.county_name
                        record["state"] = self.state
                        results.append(record)

        # Strategy 2: Look for label-value pairs (detail pages)
        if not results:
            record = {}
            for dt_dd in soup.find_all(["dt", "th", "label", "strong", "b"]):
                label = dt_dd.get_text(strip=True)
                value_el = dt_dd.find_next(["dd", "td", "span", "div"])
                if value_el:
                    value = value_el.get_text(strip=True)
                    matched = self._match_single_field(label, value)
                    record.update(matched)
            if record:
                record["county"] = self.county_name
                record["state"] = self.state
                results.append(record)

        return results

    def _match_fields(self, raw: dict) -> dict:
        """Match raw key-value pairs to our schema fields."""
        record = {}
        for raw_key, raw_value in raw.items():
            record.update(self._match_single_field(raw_key, raw_value))
        return record

    def _match_single_field(self, label: str, value: str) -> dict:
        """Match a single label-value pair to our schema."""
        result = {}
        for field_name, pattern in FIELD_PATTERNS.items():
            if pattern.search(label):
                if field_name in (
                    "assessed_value",
                    "assessed_land_value",
                    "assessed_improvement_value",
                    "market_value",
                    "tax_amount",
                ):
                    parsed = _parse_currency(value)
                    if parsed is not None:
                        if field_name == "tax_amount":
                            result["annual_tax_amount"] = parsed
                        else:
                            result[field_name] = parsed
                elif field_name in ("year_built", "bedrooms", "sqft", "lot_size_sqft", "tax_year"):
                    parsed = _parse_int(value)
                    if parsed is not None:
                        result[field_name] = parsed
                elif field_name == "bathrooms":
                    match = re.search(r"(\d+\.?\d*)", value)
                    if match:
                        result[field_name] = float(match.group(1))
                elif field_name == "tax_status":
                    is_delinquent = bool(re.search(r"delinquen", value, re.I))
                    result["tax_delinquent"] = is_delinquent
                else:
                    result[field_name] = value.strip()
                break
        return result
