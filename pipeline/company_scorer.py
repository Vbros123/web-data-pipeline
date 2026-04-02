"""
company_scorer.py — combines news + job signals into a single company dict.
This is meant to be the simple entry point for the pipeline.
"""

import asyncio
from typing import Optional

from .news_collector import NewsCollector
from .job_signal import JobSignalCollector


async def score_company(company_name: str, max_news: int = 10) -> dict:
    """
    Runs news and job signal collection for a company concurrently,
    returns a structured dict with both signals.

    Args:
        company_name: Name to search for (e.g. "Apple", "Stripe")
        max_news: Max number of news items to return

    Returns:
        dict with keys: company, news, job_signal, summary
    """
    collector = NewsCollector()
    job_collector = JobSignalCollector()

    # run news fetch async, job signal is sync so run it in executor
    loop = asyncio.get_event_loop()

    news_task = collector.fetch_for_company(company_name)
    job_task = loop.run_in_executor(None, job_collector.get_signal, company_name)

    news_items, job_signal = await asyncio.gather(news_task, job_task)

    news_items = news_items[:max_news]

    # compute a rough "momentum score" — not scientific, just directional
    news_count = len(news_items)
    job_count = job_signal.posting_count

    # normalize to 0-10 scale (arbitrary thresholds based on what felt right)
    news_score = min(news_count / 5, 10)
    job_score = min(job_count / 100, 10) if job_count > 0 else 0

    return {
        "company": company_name,
        "news": [item.to_dict() for item in news_items],
        "job_signal": job_signal.to_dict(),
        "summary": {
            "news_article_count": news_count,
            "job_posting_count": job_count,
            "news_score_0_10": round(news_score, 2),
            "job_score_0_10": round(job_score, 2),
            "combined_score_0_10": round((news_score + job_score) / 2, 2),
            "notes": "scores are rough proxies, not meant to be precise",
        },
    }


if __name__ == "__main__":
    import json
    import sys

    company = sys.argv[1] if len(sys.argv) > 1 else "Apple"
    result = asyncio.run(score_company(company))
    print(json.dumps(result, indent=2, default=str))
