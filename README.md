# web-data-pipeline

started building this as the data layer for PrivateLens, a startup concept I've been thinking about. the idea is: give it any company name, and it aggregates job postings, recent news, and eventually public records into a structured signal about what that company is actually doing.

## what works right now

- **news aggregation** — pulls from Reuters, FT, and a few other RSS feeds asynchronously. pretty fast. gives you headlines, summaries, and timestamps structured into a dataclass.
- **job posting signal** — fetches job posting counts for a company from search results. returns a "hiring velocity" metric. rough but useful.
- **company scorer** — wrapper that runs both and returns a combined dict you can actually use.

## what's WIP

- public records / SEC filings integration is not done yet. placeholder is in the code but I haven't figured out the right data source. EDGAR API is on my list.
- the job signal scraper is fragile — it's doing HTML parsing against pages that change, so it breaks sometimes. need to find a more stable source.
- no persistence layer yet. everything is in-memory. want to add a simple SQLite cache.

## structure

```
pipeline/
  news_collector.py   — async RSS news fetcher
  job_signal.py       — job posting count scraper
  company_scorer.py   — combines both into a signal dict
  __init__.py
```

## quick start

```bash
pip install -r requirements.txt
python -c "
import asyncio
from pipeline.company_scorer import score_company
result = asyncio.run(score_company('Apple'))
print(result)
"
```

## why I built this

I want to build something that gives you a real-time picture of a private company's momentum — are they hiring aggressively? getting mentioned in the news? that kind of thing. this is the data collection layer. still early but the bones are there.
