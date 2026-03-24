"""Base class for county recorder scrapers."""

from abc import ABC, abstractmethod

DISTRESS_DOCUMENT_TYPES = {
    "notice of default",
    "lis pendens",
    "trustee sale",
    "notice of trustee",
    "notice of trustee's sale",
    "lien",
    "tax lien",
    "mechanics lien",
    "mechanic's lien",
    "federal tax lien",
    "state tax lien",
    "judgment lien",
    "abstract of judgment",
}


class BaseRecorderScraper(ABC):
    """Abstract base class for county recorder document scrapers."""

    county_name: str = ""
    state: str = ""
    base_url: str = ""

    @abstractmethod
    def search_by_parcel(self, parcel_number: str) -> list[dict]:
        """Search recorded documents by parcel number.

        Returns list of dicts with keys: document_type, instrument_number,
        recording_date, grantor, grantee, document_amount, book, page.
        """

    @abstractmethod
    def search_by_name(self, name: str) -> list[dict]:
        """Search recorded documents by party name."""

    def get_distress_documents(self, parcel_number: str) -> list[dict]:
        """Filter search results to only distress-related document types."""
        all_docs = self.search_by_parcel(parcel_number)
        return [
            d
            for d in all_docs
            if any(
                dt in d.get("document_type", "").lower()
                for dt in DISTRESS_DOCUMENT_TYPES
            )
        ]

    def close(self):
        """Clean up resources. Override in subclasses."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
