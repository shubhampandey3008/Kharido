# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All Python commands use the project's `.venv` directly (uv does not inject pip; use `uv sync --reinstall` if the venv appears empty).

```bash
# Install / refresh dependencies
uv sync --reinstall

# Run the Python backend (FastAPI)
uvicorn api.main:app --reload --port 8000

# Run the Next.js frontend
cd frontend && npm install && npm run dev   # served at localhost:3000

# CLI smoke test (runs the full pipeline with a hard-coded query)
.venv/bin/python -m kharido

# Tests
.venv/bin/pytest tests/ -v
.venv/bin/pytest tests/test_models.py -v              # single file
.venv/bin/pytest tests/ -v -k "test_set_and_get"      # single test by name

# Lint / format
.venv/bin/ruff check kharido/ api/ tests/
.venv/bin/ruff format kharido/ api/ tests/

# Type check
.venv/bin/mypy kharido/ api/
```

The frontend proxies `/api/*` to `localhost:8000` via `frontend/next.config.js`, so both servers must run simultaneously during development.

## Architecture

### Pipeline (LangGraph StateGraph)

The core logic is a 5-node pipeline assembled in `kharido/graph.py`. Every node reads from and writes partial updates into `GraphState` (`kharido/state.py`). LangGraph merges the dicts.

```
START → query_understanding → criteria_research → product_search
                                                        │
                                              ┌─ no candidates → error_node → END
                                              │
                                    review_analysis_fanout   ← emits list[Send]
                                    review_analysis_worker   ← runs per candidate (parallel)
                                    review_analysis_collect  ← fan-in
                                              │
                                        recommendation
                                              │  ← interrupt_after here
                                    ┌─────────┴──────────┐
                                  accept          show_alternative
                                    │                     │
                                   END                   END
```

**V1 is sequential** (criteria → product search, no parallelism). V2 upgrade: add two edges from `query_understanding` to both nodes and add a join node.

**Human-in-the-loop** is implemented via `interrupt_after=["recommendation"]` in `build_graph()`. After the recommendation node runs, the graph pauses. The frontend calls `GET /search/{thread_id}/alternative` to resume from the MemorySaver checkpoint.

**Fan-out pattern** (`review_analysis`): `review_analysis_fanout_node` returns `list[Send]` — not a state dict. LangGraph routes each Send to `review_analysis_worker`. Worker return values are accumulated into `state["evidence"]` via the `operator.add` reducer defined in `GraphState`.

### State and Models

- `kharido/state.py` — `GraphState` TypedDict. All fields are optional (`total=False`) except `raw_query`. The `evidence` field uses `Annotated[list[...], operator.add]` to accumulate worker results.
- `kharido/models.py` — all Pydantic v2 models. These are the source of truth for both LLM structured output schemas (`.with_structured_output(ParsedQuery)`) and API serialisation. Do not duplicate model definitions in `api/schemas.py`; API schemas wrap domain models.

### Services

Each service in `kharido/services/` is a class instantiated per-request (no global singletons except `get_settings()`):
- `ScraperClient` — calls Apify scrapers for Flipkart (product `TBFjma2NhVb30QONt`, reviews `MgqDrxBkXJGDF4P7I`) and Amazon (product `BG3WDrGdteHgZgbPK`, reviews `8vhDnIX6dStLlGVr7`) when `APIFY_API_TOKEN` is set; merges and deduplicates results; always falls back to `data/offline_dataset/{category}.json`.
- `TavilySearchClient` — web search for criteria research (stubbed in V1).
- `CriteriaCache` — SQLite table `criteria_cache`; `CriteriaCache.get(category)` returns `None` on miss or expiry.
- `ScraperCache` — diskcache for raw API responses; keyed via `make_key(source, params)`.
- `PreferenceMemoryService` — V1 returns cold-start defaults; logs accept/reject to `.cache/kharido/preference_log.jsonl` for V2 seeding.

### Configuration

`kharido/config.py` exposes a `get_settings()` singleton (LRU-cached). All env vars live in `.env` (copy `.env.example`). Key vars:
- `KHARIDO_REASONING_MODEL` — used for query parsing, criteria extraction, recommendation reasoning (default: `claude-sonnet-4-6`)
- `KHARIDO_EXTRACTION_MODEL` — used for per-review classification (default: `claude-haiku-4-5-20251001`)
- `APIFY_API_TOKEN` — Apify token for Flipkart product and review scrapers
- `KHARIDO_OFFLINE_DATASET_DIR` — path to the JSON fallback dataset

### API / Frontend boundary

`api/` is a thin FastAPI layer over the LangGraph graph. `api/schemas.py` defines request/response models; `api/routes/search.py` calls `build_graph()` once at module load and reuses it across requests. The frontend at `frontend/` is a Next.js 14 App Router project — all components are in `frontend/components/`, all routes in `frontend/app/`.

### Offline dataset

`data/offline_dataset/{category_slug}.json` — each file is a JSON array of `Product`-compatible dicts. Filename must match the snake_case category slug that `query_understanding_node` returns (e.g. `running_shoes`, `earbuds`, `backpacks`). `ScraperClient._load_offline_dataset(category)` picks the file by name.

## Key LangGraph version note

LangGraph 1.x removed `langgraph.graph.graph.CompiledGraph`. Use `from langgraph.graph.state import CompiledStateGraph` instead. `MemorySaver` is at `langgraph.checkpoint.memory`. `Send` is at `langgraph.types`.

## Build versions

- **V1** (current): all nodes are workflow stubs with `TODO` markers. No real LLM calls yet. Apify scraper calls use `APIFY_API_TOKEN` when set; otherwise the offline dataset is the data source. Tavily is stubbed.
- **V2**: replace node stubs with real LLM calls, upgrade `criteria_research` and `product_search` to agent loops, integrate Mem0.
