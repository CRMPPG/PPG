"""Base scraper class for county assessor sites."""

from abc import ABC, abstractmethod

from ppg.utils.http import ScraperSession


class BaseAssessorScraper(ABC):
    """Abstract base class for county assessor scrapers.

    Each county has a different assessor website. Subclass this to add
    support for a specific county.
    """

    county_name: str = ""
    state: str = ""
    base_url: str = ""

    def __init__(self, delay_seconds=2):
        self.http = ScraperSession(delay_seconds=delay_seconds)

    @abstractmethod
    def search_by_address(self, address: str) -> list[dict]:
        """Search assessor records by street address.

        Returns a list of dicts with keys matching Property model fields.
        """

    @abstractmethod
    def search_by_parcel(self, parcel_number: str) -> dict | None:
        """Search assessor records by parcel/APN number.

        Returns a dict with keys matching Property model fields, or None.
        """

    @abstractmethod
    def get_tax_status(self, parcel_number: str) -> dict:
        """Get current tax payment status for a parcel.

        Returns dict with keys: tax_delinquent, tax_delinquent_amount,
        tax_delinquent_years, annual_tax_amount, tax_year.
        """

    def get_delinquent_properties(self) -> list[dict]:
        """Scrape the tax delinquency list if the county publishes one.

        Override in subclasses where this data is available.
        Returns list of dicts with parcel_number, address, delinquent_amount, etc.
        """
        raise NotImplementedError(
            f"{self.county_name} scraper doesn't support delinquency list scraping"
        )

    def get_liens(self, parcel_number: str) -> list[dict]:
        """Get lien records for a parcel. Override where available."""
        return []
