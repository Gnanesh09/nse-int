# NSE AI Alerts — small FastAPI backend

This MVP monitors NSE corporate announcements, filters them to user-selected NSE symbols,
extracts filing PDFs when present, sends the content to an LLM for structured analysis,
stores the result in MongoDB, and emails the watcher.

## Architecture

NSE public announcement API
        ↓
browser-like HTTP session + retry/backoff
        ↓
normalize + MongoDB unique dedupe
        ↓
only watched symbols
        ↓
optional PDF text extraction
        ↓
Groq Responses API (OpenAI-compatible)
        ↓
structured analysis stored in MongoDB
        ↓
SMTP email to every matching watcher

## Why this does not scrape the HTML table

The page is a dynamic UI. The backend should consume the underlying corporate-announcements
API rather than repeatedly rendering/scrolling the browser table. The API is date-based, so
the worker polls a small recent window and deduplicates by NSE announcement identity.

## Run locally

1. Copy `.env.example` to `.env`.
2. Add MongoDB and SMTP credentials.
3. Add `GROQ_API_KEY`.
4. Start:

    docker compose up --build

5. Open:

    http://localhost:8000/docs

6. Add a watcher:

    curl -X POST http://localhost:8000/watch \
      -H "Content-Type: application/json" \
      -d '{"email":"you@example.com","symbols":["RELIANCE","TCS","HDFCBANK"]}'

7. Force a poll:

    curl -X POST http://localhost:8000/poll

## Important production notes

- Run exactly one scheduler instance for this MVP. If you scale the web service horizontally,
  move polling to a dedicated worker/cron/queue and use a MongoDB distributed lock.
- Keep NSE request volume low. Polling once per minute with a date window and MongoDB dedupe
  is much safer than opening hundreds of browser pages.
- Analyze only watched symbols and only download PDFs for those announcements.
- Add rate limiting/authentication before exposing `/watch` publicly.
- Add an email verification/unsubscribe flow before production.
- The exchange states that corporate information is uploaded by companies and is disseminated
  by NSE without verification of adequacy, accuracy, or veracity. Treat AI output as
  summarization/analysis, not verified facts or investment advice.

## Next upgrade: RAG

Do not add a vector database on day one. MongoDB is already the system of record.

When enough historical announcements accumulate:
1. Create embeddings for normalized announcement + extracted filing text.
2. Store the embedding in MongoDB.
3. Create a MongoDB Atlas Vector Search index.
4. For each new filing, retrieve the nearest historical filings for the same symbol.
5. Give those snippets to the LLM as "historical context" and explicitly label them as context,
   never as current facts.

This makes the system useful for questions such as "Is this order unusually large for this
company?" without making the ingestion path unnecessarily complex.

## API

- `GET /health`
- `POST /watch` — set a user's watchlist
- `GET /watch/{email}`
- `GET /announcements/{symbol}`
- `POST /poll`

Example watch payload:

    {
      "email": "investor@example.com",
      "symbols": ["RELIANCE", "INFY", "TCS"]
    }

The analyzer returns:

- headline
- summary
- event_type
- importance 0–100
- impact
- why_it_matters
- key_numbers
- watch_items
- confidence

The current backend uses the NSE corporate-announcements endpoint documented in public
examples as:

`https://www.nseindia.com/api/corporate-announcements?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY`

NSE also provides an official corporate-data subscription product; this MVP uses the public
website endpoint instead, so production deployment should respect NSE's current terms,
rate limits, and access policies.
