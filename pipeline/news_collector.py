"""
news_collector.py — async RSS news fetcher.
Pulls headlines and summaries from financial news RSS feeds.
Structured output via dataclass so it's easy to work with downstream.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from email.utils import parsedate_to_datetime

import aiohttp
import feedparser


# RSS feeds that are actually useful and free
RSS_FEEDS = {
    "reuters_business": "https://feeds.reuters.com/reuters/businessNews",
    "reuters_markets": "https://feeds.reuters.com/reuters/companyNews",
    "ft_companies": "https://www.ft.com/companies?format=rss",
    "seeking_alpha": "https://seekingalpha.com/market_currents.xml",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
}


@dataclass
class NewsItem:
    """A single news article / headline."""
    title: str
    summary: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tags": self.tags,
        }


def _parse_date(entry) -> Optional[datetime]:
    """Try to get a proper datetime out of a feedparser entry."""
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return None


def _parse_feed(raw_content: str, source_name: str) -> List[NewsItem]:
    """Parse raw RSS XML into a list of NewsItems."""
    feed = feedparser.parse(raw_content)
    items = []
    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        summary = getattr(entry, "summary", "").strip()
        url = getattr(entry, "link", "").strip()
        tags = [t.get("term", "") for t in getattr(entry, "tags", [])]

        if not title or not url:
            continue

        items.append(NewsItem(
            title=title,
            summary=summary[:500],  # cap summary length
            url=url,
            source=source_name,
            published_at=_parse_date(entry),
            tags=tags,
        ))
    return items


class NewsCollector:
    """
    Async news collector. Fetches multiple RSS feeds concurrently
    and optionally filters results for a keyword (company name).
    """

    def __init__(self, feeds: dict = None, timeout: int = 10):
        self.feeds = feeds or RSS_FEEDS
        self.timeout = timeout

    async def _fetch_feed(
        self,
        session: aiohttp.ClientSession,
        name: str,
        url: str,
    ) -> List[NewsItem]:
        """Fetch and parse a single RSS feed."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                if resp.status != 200:
                    return []
                content = await resp.text()
                return _parse_feed(content, name)
        except Exception:
            return []

    async def fetch_all(self, keyword: str = None) -> List[NewsItem]:
        """
        Fetch all configured feeds concurrently.
        If keyword is given, only returns items where the title or summary
        contains the keyword (case-insensitive).
        """
        connector = aiohttp.TCPConnector(limit=10)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; research-pipeline/1.0)"}

        async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
            tasks = [
                self._fetch_feed(session, name, url)
                for name, url in self.feeds.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for r in results:
            if isinstance(r, list):
                all_items.extend(r)

        if keyword:
            kw_lower = keyword.lower()
            all_items = [
                item for item in all_items
                if kw_lower in item.title.lower() or kw_lower in item.summary.lower()
            ]

        # sort newest first
        all_items.sort(key=lambda x: x.published_at or datetime.min, reverse=True)
        return all_items

    async def fetch_for_company(self, company_name: str) -> List[NewsItem]:
        """Convenience wrapper — fetch news filtered to a specific company."""
        return await self.fetch_all(keyword=company_name)
