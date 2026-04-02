"""
job_signal.py — job posting signal collector.
Estimates a company's hiring velocity from job posting counts.
Uses search result counts as a proxy — not perfectly accurate but directionally useful.
"""

import re
import time
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 10


@dataclass
class JobSignal:
    """Result from a job posting lookup."""
    company: str
    posting_count: int
    source: str
    is_estimated: bool = False  # True if we couldn't get exact count
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "posting_count": self.posting_count,
            "source": self.source,
            "is_estimated": self.is_estimated,
            "notes": self.notes,
        }


def _extract_number(text: str) -> Optional[int]:
    """Pull the first integer-ish number out of a string like '1,234 jobs'."""
    text = text.replace(",", "").replace(".", "")
    match = re.search(r"\b(\d{1,7})\b", text)
    if match:
        return int(match.group(1))
    return None


class JobSignalCollector:
    """
    Fetches job posting counts for a company from public job boards.
    Tries multiple sources and returns the best result it can get.

    Note: HTML parsing against live pages is fragile. If this breaks,
    the sites probably changed their markup. TODO: find a stable API.
    """

    def __init__(self, session: requests.Session = None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def _fetch_indeed_count(self, company: str) -> Optional[int]:
        """
        Try to get job count from Indeed search results page.
        Fragile — depends on their HTML structure.
        """
        query = company.replace(" ", "+")
        url = f"https://www.indeed.com/jobs?q={query}&from=searchOnHP&vjk=&l="
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")

            # indeed shows something like "Page 1 of 1,234 jobs"
            for tag in soup.find_all(["div", "span"], string=re.compile(r"\d.*job", re.I)):
                count = _extract_number(tag.get_text())
                if count and count > 0:
                    return count

            # fallback: count individual job cards
            cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|tapItem"))
            if cards:
                return len(cards)  # just page count, not total — mark as estimated

        except Exception as e:
            logger.debug(f"indeed fetch failed for {company}: {e}")
        return None

    def _fetch_linkedin_count(self, company: str) -> Optional[int]:
        """
        Try LinkedIn job search count. Even more fragile than Indeed
        but sometimes works.
        """
        query = company.replace(" ", "%20")
        url = f"https://www.linkedin.com/jobs/search/?keywords={query}"
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")

            # LinkedIn often has a results count span
            for tag in soup.find_all(["span", "h1"], string=re.compile(r"\d")):
                text = tag.get_text(strip=True)
                if "result" in text.lower() or "job" in text.lower():
                    count = _extract_number(text)
                    if count:
                        return count

        except Exception as e:
            logger.debug(f"linkedin fetch failed for {company}: {e}")
        return None

    def get_signal(self, company: str) -> JobSignal:
        """
        Main method. Tries Indeed first, falls back to LinkedIn,
        returns a JobSignal with whatever we managed to get.
        """
        # try Indeed
        count = self._fetch_indeed_count(company)
        if count is not None:
            return JobSignal(
                company=company,
                posting_count=count,
                source="indeed",
                is_estimated=False,
            )

        time.sleep(0.5)

        # try LinkedIn
        count = self._fetch_linkedin_count(company)
        if count is not None:
            return JobSignal(
                company=company,
                posting_count=count,
                source="linkedin",
                is_estimated=True,
                notes="count from LinkedIn search results page, may not be exact",
            )

        # couldn't get anything
        return JobSignal(
            company=company,
            posting_count=0,
            source="none",
            is_estimated=True,
            notes="could not fetch job count — site may have blocked request or changed markup",
        )
