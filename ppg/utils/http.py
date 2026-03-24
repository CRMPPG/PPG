"""HTTP utilities for scraping with rate limiting and retries."""

import random
import time

import requests
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential


class ScraperSession:
    """A requests session with rate limiting, random user agents, and retries."""

    def __init__(self, delay_seconds=2, max_retries=3):
        self.session = requests.Session()
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self._last_request_time = 0

        try:
            ua = UserAgent()
            self.session.headers["User-Agent"] = ua.random
        except Exception:
            self.session.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay_seconds:
            jitter = random.uniform(0.5, 1.5)
            time.sleep(self.delay_seconds - elapsed + jitter)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def get(self, url, **kwargs):
        self._rate_limit()
        response = self.session.get(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    def post(self, url, **kwargs):
        self._rate_limit()
        response = self.session.post(url, timeout=30, **kwargs)
        response.raise_for_status()
        return response
