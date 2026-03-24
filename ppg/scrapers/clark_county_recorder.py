"""Clark County NV Recorder scraper using Selenium.

Scrapes the AcclaimWeb system at recorderecomm.clarkcountynv.gov for
recorded documents (Notices of Default, Lis Pendens, Liens, Trustee Sales).

Uses Selenium because AcclaimWeb generates JS-based hash+timestamp
parameters for anti-scraping protection.
"""

import random
import re
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ppg.scrapers.recorder_base import BaseRecorderScraper

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
    """Scrape Clark County NV Recorder (AcclaimWeb) for recorded documents."""

    county_name = "Clark"
    state = "NV"
    base_url = "https://recorderecomm.clarkcountynv.gov/AcclaimWeb"

    SEARCH_URL = f"{base_url}/Search/SearchTypeParcel"

    def __init__(self, headless=True, delay_seconds=3, timeout=20):
        self.headless = headless
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self._driver = None

    def _get_driver(self):
        """Initialize a Selenium Chrome driver."""
        if self._driver is not None:
            return self._driver

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Reduce automation detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self._driver = webdriver.Chrome(options=options)
        self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        return self._driver

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

        driver = self._get_driver()
        self._rate_limit()

        # Navigate to parcel search page (lets JS generate hash/timestamp)
        driver.get(self.SEARCH_URL)
        wait = WebDriverWait(driver, self.timeout)

        # Wait for and fill the parcel number input
        parcel_input = self._find_parcel_input(wait)
        parcel_input.clear()
        parcel_input.send_keys(normalized)

        # Submit the search
        self._submit_search(driver, wait)

        # Wait for results
        time.sleep(2)

        # Parse all result pages
        all_docs = []
        all_docs.extend(self._parse_results_page(driver))

        # Handle pagination
        while self._has_next_page(driver):
            self._click_next_page(driver)
            time.sleep(1.5)
            all_docs.extend(self._parse_results_page(driver))

        return all_docs

    def search_by_name(self, name: str) -> list[dict]:
        """Search recorded documents by party name."""
        driver = self._get_driver()
        self._rate_limit()

        name_search_url = f"{self.base_url}/Search/SearchTypeName"
        driver.get(name_search_url)
        wait = WebDriverWait(driver, self.timeout)

        # Look for name input fields
        try:
            name_input = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[id*='Name'], input[name*='name'], input[id*='Party']")
                )
            )
            name_input.clear()
            name_input.send_keys(name)
            self._submit_search(driver, wait)
            time.sleep(2)
            return self._parse_results_page(driver)
        except Exception:
            return []

    def _find_parcel_input(self, wait: WebDriverWait):
        """Find the parcel number input field on the search page."""
        selectors = [
            "input[id*='arcel']",
            "input[name*='arcel']",
            "input[id*='Parcel']",
            "input[name*='Parcel']",
            "input[id*='APN']",
            "input[type='text']",
        ]
        for selector in selectors:
            try:
                el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                return el
            except Exception:
                continue
        raise RuntimeError("Could not find parcel number input on search page")

    def _submit_search(self, driver, wait: WebDriverWait):
        """Submit the search form."""
        # Try clicking a search button
        button_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button[id*='earch']",
            "a[id*='earch']",
            ".btn-search",
            "#btnSearch",
        ]
        for selector in button_selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                btn.click()
                return
            except Exception:
                continue

        # Fallback: press Enter on the active element
        driver.switch_to.active_element.send_keys(Keys.RETURN)

    def _parse_results_page(self, driver) -> list[dict]:
        """Parse the current results page for document records."""
        docs = []

        # AcclaimWeb typically renders results in a table or grid
        # Try multiple strategies to find results

        # Strategy 1: Look for result table rows
        try:
            rows = driver.find_elements(
                By.CSS_SELECTOR,
                "table.SearchResults tr, .search-results tr, "
                "#SearchResultsGrid tr, .grid tr, table[role='grid'] tr, "
                "#searchResultsTable tr, .result-row"
            )
            if rows:
                headers = self._extract_headers(rows[0]) if rows else []
                for row in rows[1:]:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        doc = self._map_cells_to_doc(headers, cells)
                        if doc.get("document_type"):
                            docs.append(doc)
                return docs
        except Exception:
            pass

        # Strategy 2: Look for any table on the page
        try:
            tables = driver.find_elements(By.TAG_NAME, "table")
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) < 2:
                    continue
                headers = self._extract_headers(rows[0])
                for row in rows[1:]:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        doc = self._map_cells_to_doc(headers, cells)
                        if doc.get("document_type") or doc.get("instrument_number"):
                            docs.append(doc)
                if docs:
                    return docs
        except Exception:
            pass

        # Strategy 3: Look for div-based result rows
        try:
            result_divs = driver.find_elements(
                By.CSS_SELECTOR,
                ".search-result, .result-item, .document-row, [class*='result']"
            )
            for div in result_divs:
                text = div.text
                if text.strip():
                    doc = self._parse_result_text(text)
                    if doc:
                        docs.append(doc)
        except Exception:
            pass

        return docs

    def _extract_headers(self, header_row) -> list[str]:
        """Extract column headers from the first table row."""
        headers = []
        for cell in header_row.find_elements(By.CSS_SELECTOR, "th, td"):
            headers.append(cell.text.strip().lower())
        return headers

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
                    text = cell.text.strip()
                    if field == "recording_date":
                        doc[field] = self._parse_date(text)
                    elif field == "document_amount":
                        doc[field] = self._parse_amount(text)
                    else:
                        doc[field] = text

        # If no headers matched, try positional mapping (common AcclaimWeb layout)
        if not doc and len(cells) >= 4:
            doc = {
                "recording_date": self._parse_date(cells[0].text.strip()),
                "document_type": cells[1].text.strip() if len(cells) > 1 else "",
                "grantor": cells[2].text.strip() if len(cells) > 2 else "",
                "grantee": cells[3].text.strip() if len(cells) > 3 else "",
                "instrument_number": cells[4].text.strip() if len(cells) > 4 else "",
            }

        return doc

    def _parse_result_text(self, text: str) -> dict | None:
        """Parse a text block into a document dict (fallback for non-table layouts)."""
        doc = {}
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            lower = line.lower()
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

    def _has_next_page(self, driver) -> bool:
        """Check if there's a next page of results."""
        try:
            next_links = driver.find_elements(
                By.CSS_SELECTOR,
                "a.next, a[rel='next'], .pagination .next:not(.disabled), "
                "a[title='Next'], a[aria-label='Next'], .pager .next a"
            )
            return any(link.is_displayed() and link.is_enabled() for link in next_links)
        except Exception:
            return False

    def _click_next_page(self, driver):
        """Click the next page link."""
        next_links = driver.find_elements(
            By.CSS_SELECTOR,
            "a.next, a[rel='next'], .pagination .next a, "
            "a[title='Next'], a[aria-label='Next'], .pager .next a"
        )
        for link in next_links:
            if link.is_displayed() and link.is_enabled():
                link.click()
                return
        raise RuntimeError("Next page link not clickable")

    def close(self):
        """Shut down the Selenium driver."""
        if self._driver:
            self._driver.quit()
            self._driver = None
