## Prerequisites

- **Docker Desktop** (for Cassandra + Spark)
- **Python 3.12+** (developed/tested on CPython **3.14**, Windows)
- **Node.js 18+** (for the React frontend in `frontend/`)
- *(optional)* **Ollama** with a tool-calling model, for the LLM assistant

> **Windows + Python ≥3.12 note:** `cassandra-driver`'s default reactors are
> unavailable there (no libev wheel; `asyncore` removed in 3.12). The DAL
> transparently uses the **asyncio reactor** with a `SelectorEventLoop`
> (see `acme_dwh/dal/_compat.py`). No action needed — it just works.

---

## Setup

```powershell
# 1. venv + dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .

# 2. (optional) configuration — defaults work out of the box
copy .env.example .env

# 3. Start Cassandra and apply the schema
docker compose up -d cassandra          # wait ~60-90s until healthy
acme-init-db # equivalently: python -m acme_dwh.db.init_db
```

---

## Run the platform

### 1) Ingest live market data (UC1)

```powershell
acme-ingest BTCUSD ETHUSD --start 2021-01-01 # Bitfinex public API (default, no key). Uses provider pagination under the hood.
acme-ingest BTCUSD --provider nasdaq_data_link # Nasdaq Data Link instead (needs a free key in .env: NDL_API_KEY=...)
```

### 2) Explore via the REST API (UC2)

```powershell
uvicorn acme_dwh.api.main:app # http://127.0.0.1:8000
```

Open **http://127.0.0.1:8000/docs** for interactive OpenAPI docs. Examples:

```
GET /api/v1/assets?limit=20&offset=0
GET /api/v1/assets/BTCUSD
GET /api/v1/assets/BTCUSD?history=true
GET /api/v1/data-sources
GET /api/v1/data-sources/BITFINEX
GET /api/v1/data?assetId=BTCUSD&dataSourceId=BITFINEX&startBusinessDate=2024-01-01&endBusinessDate=2024-02-01&includeAttributes=true
```

`/data` returns records **newest-first**, one **latest version per business date**,
over the **half-open** interval `[start, end)`; `asOf` reproduces a historical view.

### 3) Spark analytics + ML

```powershell
docker compose up -d --build spark      # builds a small image with numpy + starts Spark

# Aggregation -> writes the `totals` table (count/min/max/avg close per year)
docker compose exec spark /opt/spark/bin/spark-submit --master "local[*]" `
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.1 `
  --conf spark.jars.ivy=/tmp/.ivy2 --conf spark.cassandra.connection.host=cassandra `
  --conf spark.log.level=WARN /opt/jobs/aggregation_job.py

# ML regression -> writes the `regression_results` table (predicts daily open)
docker compose exec -e ASSET_ID=BTCUSD spark /opt/spark/bin/spark-submit --master "local[*]" `
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.1 `
  --conf spark.jars.ivy=/tmp/.ivy2 --conf spark.cassandra.connection.host=cassandra `
  --conf spark.log.level=WARN /opt/jobs/regression_job.py
```

### 4) LLM assistant via MCP

The **MCP server** is read-only and works with any MCP client.
The bundled **assistant** uses a local Ollama model that tool-calls the server.

```powershell
ollama pull llama3.2 # one-time: pull a tool-calling-capable model

# keep the REST API running (the MCP server calls it), then:
acme-assistant "What crypto assets do we have, and how did BTCUSD move recently?"
```

The assistant prints each `[tool] ...` call it makes and then a grounded answer.
Run the MCP server standalone with `acme-mcp` (or `python -m acme_dwh.mcp.server`).

### 5) Web UI (React) — *Acme Terminal*

```powershell
# keep the API running (uvicorn acme_dwh.api.main:app), then in frontend/:
npm install --prefix frontend
npm run dev --prefix frontend        # http://localhost:5173
```

The Vite dev server proxies `/api` and `/health` to the backend on port 8000, so no
CORS setup is needed. The **Assistant** view needs Ollama running; the others need only
the API + Cassandra (the **Analytics** view needs the Spark jobs to have run).

---

## Testing

```powershell
pytest
```

- **Unit tests** (no Cassandra): bi-temporal logic, ingestion transform/parsing
  (mocked HTTP), MCP tool validation.
- **Integration tests**: DAL, ingestion, and API against a live Cassandra — they
  **auto-skip** if Cassandra isn't running. Start it (`docker compose up -d cassandra`
  + `acme-init-db`) to run them.

---

## Troubleshooting

- **Cassandra not ready:** it needs ~60–90s after `docker compose up`. Check with
  `docker compose ps` (status `healthy`) or `docker compose logs cassandra`.
- **API/MCP can't reach Cassandra:** ensure the schema is applied (`python db/init_db.py`)
  and `CASSANDRA_HOSTS`/`CASSANDRA_PORT` in `.env` match.
- **MCP assistant errors:** the REST API must be running first, and Ollama must serve a
  **tool-calling-capable** model (`ollama list` to verify `llama3.2` is present).
- **Spark connector download:** the first `spark-submit` downloads the connector from
  Maven Central (needs internet from the container); subsequent runs are cached.
