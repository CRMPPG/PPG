"""Clark County NV Recorder scraper using requests + BeautifulSoup.

Scrapes the AcclaimWeb system at recorderecomm.clarkcountynv.gov for
recorded documents (Notices of Default, Lis Pendens, Liens, Trustee Sales).

Uses requests with session cookies instead of Selenium for portability.
"""

import random
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ppg.scrapers.recorder_base import BaseRecorderScraper
from ppg.utils.http import ScraperSession

# Standard Clark County: XXX-XX-XXX-XXX (e.g. 179-34-712-030)
PARCEL_STANDARD = re.compile(r"^(\d{3})-?(\d{2})-?(\d{3})-?(\d{3})$")
# Older area parcels: XX-XXX-XX (e.g. 18-305-18) or XXX-XXX-XX (e.g. 003-132-22)
PARCEL_SHORT = re.compile(r"^(\d{2,3})-(\d{2,4})-(\d{2,4})$")
# Lettered prefix: X-XXXX-XXXX-XXXX (e.g. C-0645-0160-0000)
PARCEL_LETTER = re.compile(r"^([A-Z])-(\d{4})-(\d{4})-(\d{4})$", re.I)


def normalize_parcel(raw: str) -> str | None:
    """Normalize a Clark County parcel number, preserving its original format.

    Accepts multiple Clark County formats:
    - Standard: 179-34-712-030 or 17934712030
    - Short: 18-305-18, 003-132-22
    - Letter prefix: C-0645-0160-0000
    """
    cleaned = raw.strip().replace(" ", "").replace(".", "")
    if not cleaned:
        return None

    # Standard 11-digit format
    m = PARCEL_STANDARD.match(cleaned)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}-{m.group(4)}"

    # Try undashed 11-digit
    if re.match(r"^\d{11}$", cleaned):
        return f"{cleaned[:3]}-{cleaned[3:5]}-{cleaned[5:8]}-{cleaned[8:11]}"

    # Short format (already dashed)
    m = PARCEL_SHORT.match(cleaned)
    if m:
        return cleaned  # keep as-is

    # Letter prefix
    m = PARCEL_LETTER.match(cleaned)
    if m:
        return cleaned.upper()

    return None


class ClarkCountyRecorderScraper(BaseRecorderScraper):
    """Scrape Clark County NV Recorder (AcclaimWeb) for recorded documents.

    Uses requests + BeautifulSoup instead of Selenium for portability.
    """

    county_name = "Clark"
    state = "NV"
    base_url = "https://recorderecomm.clarkcountynv.gov/AcclaimWeb"

    SEARCH_URL = f"{base_url}/Search/SearchTypeParcel"
    NAME_SEARCH_URL = f"{base_url}/Search/SearchTypeName"

    def __init__(self, headless=True, delay_seconds=3, timeout=30):
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self._session = None
        # headless kept for API compatibility but not used (no browser)

    def _get_session(self) -> requests.Session:
        """Initialize an HTTP session with proper headers."""
        if self._session is not None:
            return self._session

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })

        # Visit the base URL first to get session cookies
        try:
            resp = self._session.get(self.base_url, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Warning: could not initialize session: {e}")

        return self._session

    def _rate_limit(self):
        """Wait between requests with jitter."""
        jitter = random.uniform(0.5, 1.5)
        time.sleep(self.delay_seconds + jitter)

    def search_by_parcel(self, parcel_number: str) -> list[dict]:
        """Search the recorder by parcel number.

        Returns list of document dicts with: document_type, instrument_number,
        recording_date, grantor, grantee, book, page, document_amount.
        """
        normalized = normalize_parcel(parcel_number)
        if not normalized:
            raise ValueError(f"Invalid Clark County parcel format: {parcel_number}")

        session = self._get_session()
        self._rate_limit()

        # Load the search page to get any hidden form fields / tokens
        try:
            page_resp = session.get(self.SEARCH_URL, timeout=self.timeout)
            page_resp.raise_for_status()
        except Exception as e:
            print(f"  Warning: could not load search page: {e}")
            return []

        soup = BeautifulSoup(page_resp.text, "lxml")

        # Extract form fields (hidden inputs like __RequestVerificationToken)
        form_data = self._extract_form_data(soup)
        form_data.update(self._build_parcel_form_data(soup, normalized))

        # Determine form action URL
        form_action = self._get_form_action(soup, self.SEARCH_URL)

        # Submit search
        self._rate_limit()
        try:
            search_resp = session.post(
                form_action,
                data=form_data,
                timeout=self.timeout,
                headers={"Referer": self.SEARCH_URL},
            )
            search_resp.raise_for_status()
        except Exception as e:
            print(f"  Warning: search request failed: {e}")
            return []

        # Parse results
        results_soup = BeautifulSoup(search_resp.text, "lxml")
        all_docs = self._parse_results_page(results_soup)

        # Handle pagination
        page_num = 1
        while True:
            next_url = self._get_next_page_url(results_soup)
            if not next_url:
                break
            page_num += 1
            self._rate_limit()
            try:
                next_resp = session.get(next_url, timeout=self.timeout)
                next_resp.raise_for_status()
                results_soup = BeautifulSoup(next_resp.text, "lxml")
                page_docs = self._parse_results_page(results_soup)
                if not page_docs:
                    break
                all_docs.extend(page_docs)
            except Exception:
                break

        return all_docs

    def search_by_name(self, name: str) -> list[dict]:
        """Search recorded documents by party name."""
        session = self._get_session()
        self._rate_limit()

        try:
            page_resp = session.get(self.NAME_SEARCH_URL, timeout=self.timeout)
            page_resp.raise_for_status()
        except Exception:
            return []

        soup = BeautifulSoup(page_resp.text, "lxml")
        form_data = self._extract_form_data(soup)

        # Find name input fields and populate
        name_inputs = soup.find_all("input", attrs={
            "type": "text",
            "id": re.compile(r"(name|party)", re.I),
        })
        if not name_inputs:
            name_inputs = soup.find_all("input", attrs={"type": "text"})

        if name_inputs:
            form_data[name_inputs[0].get("name", "Name")] = name

        form_action = self._get_form_action(soup, self.NAME_SEARCH_URL)

        self._rate_limit()
        try:
            resp = session.post(
                form_action,
                data=form_data,
                timeout=self.timeout,
                headers={"Referer": self.NAME_SEARCH_URL},
            )
            resp.raise_for_status()
            return self._parse_results_page(BeautifulSoup(resp.text, "lxml"))
        except Exception:
            return []

    def _extract_form_data(self, soup: BeautifulSoup) -> dict:
        """Extract hidden form fields (CSRF tokens, etc.)."""
        data = {}
        form = soup.find("form")
        if form:
            for hidden in form.find_all("input", attrs={"type": "hidden"}):
                name = hidden.get("name")
                if name:
                    data[name] = hidden.get("value", "")
        return data

    def _build_parcel_form_data(self, soup: BeautifulSoup, parcel: str) -> dict:
        """Build the form data dict for a parcel search."""
        data = {}

        # Find parcel input by ID or name patterns
        parcel_input = (
            soup.find("input", attrs={"id": re.compile(r"arcel|APN", re.I)})
            or soup.find("input", attrs={"name": re.compile(r"arcel|APN", re.I)})
        )

        if parcel_input:
            data[parcel_input.get("name", "ParcelNumber")] = parcel
        else:
            # Fallback: find all text inputs and use the first one
            text_inputs = soup.find_all("input", attrs={"type": "text"})
            if text_inputs:
                data[text_inputs[0].get("name", "ParcelNumber")] = parcel
            else:
                data["ParcelNumber"] = parcel

        return data

    def _get_form_action(self, soup: BeautifulSoup, fallback_url: str) -> str:
        """Get the form's action URL."""
        form = soup.find("form")
        if form and form.get("action"):
            action = form["action"]
            if action.startswith("http"):
                return action
            if action.startswith("/"):
                return f"https://recorderecomm.clarkcountynv.gov{action}"
            return f"{self.base_url}/{action}"
        return fallback_url

    def _parse_results_page(self, soup: BeautifulSoup) -> list[dict]:
        """Parse the results page for document records."""
        docs = []

        # Strategy 1: Look for result tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            headers = [
                th.get_text(strip=True).lower()
                for th in rows[0].find_all(["th", "td"])
            ]

            # Check if this looks like a results table
            header_text = " ".join(headers)
            if not any(
                kw in header_text
                for kw in ["type", "instrument", "date", "record", "doc", "grantor"]
            ):
                continue

            for row in rows[1:]:
                cells = row.find_all("td")
                if cells:
                    doc = self._map_cells_to_doc(headers, cells)
                    if doc.get("document_type") or doc.get("instrument_number"):
                        docs.append(doc)
            if docs:
                return docs

        # Strategy 2: Look for div-based results
        result_divs = soup.find_all(
            "div", class_=re.compile(r"result|search-result|document", re.I)
        )
        for div in result_divs:
            text = div.get_text()
            if text.strip():
                doc = self._parse_result_text(text)
                if doc:
                    docs.append(doc)

        # Strategy 3: Look for any structured data in definition lists
        dl_elements = soup.find_all("dl")
        for dl in dl_elements:
            doc = {}
            terms = dl.find_all("dt")
            values = dl.find_all("dd")
            for dt, dd in zip(terms, values):
                key = dt.get_text(strip=True).lower()
                val = dd.get_text(strip=True)
                if "type" in key:
                    doc["document_type"] = val
                elif "date" in key or "record" in key:
                    doc["recording_date"] = self._parse_date(val)
                elif "instrument" in key:
                    doc["instrument_number"] = val
                elif "grantor" in key:
                    doc["grantor"] = val
                elif "grantee" in key:
                    doc["grantee"] = val
            if doc.get("document_type"):
                docs.append(doc)

        return docs

    def _map_cells_to_doc(self, headers: list[str], cells) -> dict:
        """Map table cells to a document dict using header names."""
        doc = {}
        header_field_map = {
            "doc type": "document_type",
            "document type": "document_type",
            "type": "document_type",
            "instrument": "instrument_number",
            "instrument #": "instrument_number",
            "instrument number": "instrument_number",
            "inst #": "instrument_number",
            "recording date": "recording_date",
            "record date": "recording_date",
            "rec date": "recording_date",
            "date": "recording_date",
            "recorded": "recording_date",
            "grantor": "grantor",
            "grantee": "grantee",
            "party 1": "grantor",
            "party 2": "grantee",
            "book": "book",
            "page": "page",
            "consideration": "document_amount",
            "amount": "document_amount",
        }

        for i, cell in enumerate(cells):
            if i < len(headers):
                header = headers[i]
                field = header_field_map.get(header)
                if field:
                    text = cell.get_text(strip=True)
                    if field == "recording_date":
                        doc[field] = self._parse_date(text)
                    elif field == "document_amount":
                        doc[field] = self._parse_amount(text)
                    else:
                        doc[field] = text

        # If no headers matched, try positional mapping (common AcclaimWeb layout)
        if not doc and len(cells) >= 4:
            doc = {
                "recording_date": self._parse_date(cells[0].get_text(strip=True)),
                "document_type": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                "grantor": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                "grantee": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                "instrument_number": cells[4].get_text(strip=True) if len(cells) > 4 else "",
            }

        return doc

    def _parse_result_text(self, text: str) -> dict | None:
        """Parse a text block into a document dict (fallback for non-table layouts)."""
        doc = {}
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if "type" in key or "doc" in key:
                    doc["document_type"] = value
                elif "date" in key or "record" in key:
                    doc["recording_date"] = self._parse_date(value)
                elif "instrument" in key or "inst" in key:
                    doc["instrument_number"] = value
                elif "grantor" in key:
                    doc["grantor"] = value
                elif "grantee" in key:
                    doc["grantee"] = value
        return doc if doc.get("document_type") else None

    def _parse_date(self, text: str):
        """Parse a date string into a date object."""
        if not text:
            return None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y", "%b %d, %Y"):
            try:
                return datetime.strptime(text.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _parse_amount(self, text: str) -> float | None:
        """Parse a currency amount."""
        if not text:
            return None
        cleaned = re.sub(r"[^\d.]", "", text)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _get_next_page_url(self, soup: BeautifulSoup) -> str | None:
        """Find the URL for the next page of results."""
        next_selectors = [
            {"rel": "next"},
            {"title": "Next"},
            {"aria-label": "Next"},
        ]
        for attrs in next_selectors:
            link = soup.find("a", attrs=attrs)
            if link and link.get("href"):
                href = link["href"]
                if href.startswith("http"):
                    return href
                if href.startswith("/"):
                    return f"https://recorderecomm.clarkcountynv.gov{href}"
                return f"{self.base_url}/{href}"

        # Look for "Next" text in pagination links
        for a in soup.find_all("a"):
            if a.get_text(strip=True).lower() in ("next", "next »", "next >", "»"):
                href = a.get("href")
                if href:
                    if href.startswith("http"):
                        return href
                    if href.startswith("/"):
                        return f"https://recorderecomm.clarkcountynv.gov{href}"
                    return f"{self.base_url}/{href}"

        return None

    def close(self):
        """Close the HTTP session."""
        if self._session:
            self._session.close()
            self._session = None
