# PRISM — Unified Commerce Intelligence Platform

**The intelligence layer for luxury commerce.**

PRISM sits above Planet Payment's Unified Commerce Protocol (UCP) as a full-stack intelligence and commerce orchestration platform. It transforms raw product data into richly enriched, AI-indexed catalogues; exposes those catalogues through multimodal discovery experiences; powers intelligent CX agents capable of acting as personal stylists; and orchestrates payment flows through FlowRoute with intelligent multi-PSP routing.

**Live Demo:** [https://prism-demo-dtdgdsahka-uc.a.run.app](https://prism-demo-dtdgdsahka-uc.a.run.app)

---

## Architecture

PRISM is built as 8 bounded contexts following DDD, hexagonal architecture, and MCP-native orchestration — conforming to [skill2026](skill2026.md) architectural standards.

```
                        ┌─────────────────────────────────────┐
                        │           API Gateway               │
                        │    Auth · Rate Limiting · Tenants   │
                        └──────────┬──────────────────────────┘
                                   │
        ┌──────────┬───────────┬───┴────┬───────────┬──────────┬──────────┐
        │          │           │        │           │          │          │
   Catalogue  Intelligence  Discovery  Try-On   Commerce   Payment  Agentic CX
   ─────────  ────────────  ─────────  ──────   ────────   ───────  ──────────
   UCP Ingest  Vertex AI    Vector     Gemini   UCP Sync   FlowRoute Personal
   PUPS Schema Enrichment   Search     Vision   Google     Multi-PSP  Stylist
   BigQuery    Gemini Pro   Hybrid     Imagen   Shopping   FX Rates  Concierge
   Quality     Embeddings   Facets     GDPR     Pub/Sub    BNPL      MCP Tools
        │          │           │        │           │          │          │
        └──────────┴───────────┴────────┴───────────┴──────────┴──────────┘
                                   │
                        ┌──────────┴──────────────────────────┐
                        │         Shared Kernel               │
                        │  Entities · Events · DAG · DI · MCP │
                        └─────────────────────────────────────┘
```

### Bounded Contexts

| Context | Purpose | MCP Server | Key Technologies |
|---------|---------|------------|------------------|
| **Catalogue** | Product ingestion, PUPS schema, quality scoring | `catalogue-service` | BigQuery, UCP adapter |
| **Intelligence** | AI enrichment pipeline with parallel DAG orchestration | `intelligence-service` | Gemini Vision, Gemini Pro, Vertex AI Embeddings |
| **Discovery** | Multimodal semantic search (text, image, hybrid) | `discovery-service` | Vertex AI Vector Search, ContextOps |
| **Try-On** | Virtual try-on with GDPR-compliant image processing | `tryon-service` | Gemini Vision, Imagen |
| **Commerce** | Bidirectional UCP sync, Google Shopping feed | `commerce-service` | Pub/Sub, Apigee, Content API |
| **Payment** | FlowRoute multi-PSP routing, FX optimisation, BNPL | `payment-service` | Stripe, Planet Payment, Adyen |
| **Agentic CX** | Personal Stylist + Commerce Concierge agents | `agentic-cx-service` | Gemini, MCP orchestration, Firestore |
| **Gateway** | API auth, rate limiting, tenant config, PIM connectors | — | Apigee, Redis, Akeneo/Contentserv/Salsify |

### Architectural Principles (skill2026)

- **Frozen domain models** — All entities are immutable dataclasses with event-sourced state transitions
- **Protocol-based ports** — Infrastructure adapters implement domain ports via Python `Protocol`
- **MCP-native integration** — Each bounded context exposes an MCP server (tools = writes, resources = reads)
- **Parallelism-first** — DAG orchestrator runs independent steps concurrently via `asyncio.gather`
- **Multi-tenant isolation** — All data scoped by `TenantId` at the domain level
- **Domain events** — Cross-context communication via Pub/Sub event bus

---

## Quick Start

### Run Locally

```bash
# Clone
git clone https://github.com/asmeyatsky/prism.git
cd prism

# Install
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run
python -m prism.demo.run
```

Open [http://localhost:8000](http://localhost:8000) and click **Begin Guided Demo**.

The demo runs entirely with in-memory mocks — no GCP credentials required. It walks through all 7 bounded contexts step-by-step with real API calls, AI enrichment simulation, and a conversation with Aria (the Personal Stylist agent).

### Run with Docker

```bash
docker build -t prism .
docker run -p 8000:8080 prism
```

---

## Project Structure

```
prism/
├── src/prism/
│   ├── shared/                  # Shared kernel
│   │   ├── domain/              #   Base entities, value objects, events, ports
│   │   ├── application/         #   DAG orchestrator, DTOs, result types
│   │   └── infrastructure/      #   DI container, MCP registry, Pub/Sub event bus
│   ├── catalogue/               # Catalogue Intelligence
│   ├── intelligence/            # AI Intelligence Engine
│   ├── discovery/               # Multimodal Discovery
│   ├── tryon/                   # Virtual Try-On
│   ├── commerce/                # Commerce Protocol (UCP)
│   ├── payment/                 # Payment Orchestration (FlowRoute)
│   ├── agentic_cx/              # Agentic CX (Personal Stylist)
│   ├── gateway/                 # API Gateway
│   ├── demo/                    # Demo application
│   │   ├── api/                 #   FastAPI app with 11 REST endpoints
│   │   ├── mocks/               #   In-memory mock adapters for all ports
│   │   ├── seed_data/           #   15 luxury products, 3 brands, 3 customers
│   │   └── static/              #   Frontend UI
│   └── bootstrap.py             # Composition root
├── tests/                       # ~330 tests across all contexts
├── infrastructure/
│   └── mcp_servers/
│       └── server_config.json   # MCP server registry
├── Dockerfile
├── .github/workflows/
│   └── deploy.yml               # CI/CD → Cloud Run
├── pyproject.toml
├── skill2026.md                 # Architectural standards
└── PRISM-PRD-v0.1-clean.docx    # Product Requirements Document
```

Each bounded context follows the same internal structure:

```
context/
├── domain/
│   ├── entities/       # Aggregates and entities (frozen dataclasses)
│   ├── value_objects/  # Immutable value types
│   ├── events/         # Domain events
│   ├── services/       # Domain services (pure business logic)
│   └── ports/          # Protocol-based interfaces
├── application/
│   ├── commands/       # Write use cases (one class per use case)
│   ├── queries/        # Read use cases
│   ├── orchestration/  # DAG workflows
│   └── dtos/           # Pydantic data transfer objects
├── infrastructure/
│   ├── adapters/       # Port implementations (GCP, PSP, etc.)
│   ├── mcp_servers/    # MCP server for this context
│   └── repositories/   # Data persistence
└── presentation/
    └── api/            # REST/gRPC controllers
```

---

## Demo Features

The guided demo walks through the full PRISM platform:

| Step | Context | What Happens |
|------|---------|-------------|
| 1 | **Catalogue** | 15 luxury products loaded from UCP feed (Gucci, Louis Vuitton, Burberry) with real product photography |
| 2 | **Intelligence** | AI enrichment pipeline: parallel attribute extraction + image quality → description generation → embedding. Before/after comparison shows raw vs enriched data |
| 3 | **Discovery** | Semantic search for "black evening bag for a winter gala" with relevance-scored results |
| 4 | **Try-On** | Virtual try-on processing pipeline with animated pose skeleton, body keypoints, and confidence scoring |
| 5 | **Commerce** | Bidirectional UCP sync with schema diff view (raw UCP → PRISM enriched) |
| 6 | **Payment** | FlowRoute routes EUR 2,450 across 3 PSPs with FX rate comparison table |
| 7 | **Stylist** | Conversation with Aria (Personal Stylist) — typewriter responses, visible MCP tool calls |

After the guided demo, an interactive chat bar lets you continue the conversation with Aria.

---

## API Endpoints

| Method | Path | Context |
|--------|------|---------|
| `GET` | `/api/health` | System health check |
| `POST` | `/api/catalogue/ingest` | Ingest products |
| `GET` | `/api/catalogue/products` | List products (tenant-scoped) |
| `GET` | `/api/catalogue/products/{id}` | Product detail |
| `POST` | `/api/intelligence/enrich/{id}` | AI enrichment |
| `POST` | `/api/discovery/search` | Multimodal search |
| `POST` | `/api/tryon/process` | Virtual try-on |
| `POST` | `/api/payment/process` | Process payment |
| `POST` | `/api/agent/conversation` | Start agent conversation |
| `POST` | `/api/agent/conversation/{id}/message` | Send message to agent |
| `GET` | `/api/agent/conversation/{id}` | Get conversation history |

Swagger UI available at `/docs`.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.12+ | All bounded contexts |
| Framework | FastAPI | REST API |
| AI/ML | Vertex AI, Gemini, Imagen | Enrichment, search, try-on, agents |
| Data | BigQuery | Catalogue store, analytics |
| Search | Vertex AI Vector Search | Semantic product discovery |
| Messaging | Cloud Pub/Sub | Event-driven communication |
| Agent | Model Context Protocol (MCP) | Agentic orchestration |
| Memory | Firestore + Memorystore | Session context, cache |
| Gateway | Apigee | API management |
| Compute | Cloud Run | Stateless services |
| CI/CD | GitHub Actions | Build → Artifact Registry → Cloud Run |
| Validation | Pydantic | DTOs, structured AI output schemas |

---

## Deployment

Auto-deploys to Cloud Run on every push to `main` via GitHub Actions.

```
Push to main → Build Docker image → Push to Artifact Registry → Deploy to Cloud Run
```

- **Project:** `boreal-gravity-490707-i2`
- **Region:** `us-central1`
- **Service:** `prism-demo`
- **Scaling:** 0–3 instances, 512Mi, 1 CPU

---

## Delivery Phases (per PRD)

| Phase | Name | Duration | Status |
|-------|------|----------|--------|
| 0 | Discovery & Architecture | 4 weeks | Architecture complete |
| 1 | Catalogue Foundation | 8 weeks | Domain + mock demo ready |
| 2 | AI Intelligence | 8 weeks | Pipeline designed, mock enrichment working |
| 3 | Agentic CX | 6 weeks | Stylist agent with MCP orchestration working |
| 4 | Managed Services | Ongoing | — |

---

## Brands (Demo)

| Brand | Tenant ID | Products | Tone |
|-------|-----------|----------|------|
| Gucci | `gucci` | 5 (bags, dress, sneakers, belt) | Sophisticated, Italian heritage |
| Louis Vuitton | `louis-vuitton` | 5 (bags, sneakers, scarf, keepall) | Iconic, art of travel |
| Burberry | `burberry` | 5 (trench, bags, scarf, shirt) | British, heritage check |

---

## Architectural Rules — 2026 Compliance

PRISM is built to the `Architectural Rules — 2026.md` standard. Each rule
section maps to a concrete enforcement mechanism in the repo — *not just a
convention*. Per Rules §2: "Rule not in CI = rule not real."

| Rules § | Obligation | How PRISM enforces it |
|--------|------------|-----------------------|
| §1 | Canonical stack (Python 3.12, FastAPI, GCP, MCP) | `pyproject.toml`; ADR [0001](docs/decisions/0001-canonical-stack.md) for the all-Python v0.1 choice. |
| §2 | Layer direction (`domain ← application ← infrastructure ← presentation`) | `.importlinter` contract `layers`, run as `lint-imports` in `.github/workflows/ci.yml`. |
| §2 | Domain SDK-free | `.importlinter` contract `domain-purity` forbids `fastapi`, `httpx`, `google.*`, `pydantic`, etc. from every domain module. |
| §3 | Bounded-context isolation | `.importlinter` contract `bounded-contexts` (`independence` rule) blocks cross-context imports — they must go through the shared kernel. |
| §3 | Immutable aggregates, invariants in factories | `@dataclass(frozen=True)` everywhere; `__post_init__` invariants; `Product.create(...)`, `Payment.create(...)` factories. |
| §3 | One MCP server per bounded context | `src/prism/<context>/infrastructure/mcp_servers/<context>_server.py` × 7. Round-trip tested by `tests/mcp/test_mcp_schema_round_trip.py`. |
| §4 | No secrets in repo | No literal secrets; Cloud Run injects via Secret Manager + Workload Identity. |
| §4 | Input validation at boundaries | Pydantic models on every gateway endpoint and DTO. |
| §4 | Audit event on every write (actor, action, before/after hash, append-only, separate IAM) | `prism.shared.domain.audit.AuditSinkPort` + `InMemoryAuditSink` / `StructlogAuditSink` (Cloud Logging → BigQuery with deny-delete IAM). ADR [0004](docs/decisions/0004-audit-sink.md). |
| §4 | Timeouts + circuit breaker on external calls | `httpx` timeouts in every adapter; circuit-breaker scoped per context. |
| §4 | AI output validated against explicit schema | Pydantic schemas on every AI adapter output (`intelligence`, `tryon`, `agentic_cx`). |
| §4 | Supply chain — lockfile, dep scan, SBOM | `requirements.lock` (pip-tools); `pip-audit` + CycloneDX SBOM in CI. ADR [0002](docs/decisions/0002-pinned-lockfile.md). |
| §5 | Coverage floors (domain ≥95%, application ≥85%, overall ≥80%) | `pytest --cov-fail-under=80` plus `scripts/check_layer_coverage.py` gates per layer in CI. |
| §5 | MCP schema + round-trip tests | `tests/mcp/test_mcp_schema_round_trip.py`. |
| §6 | OpenTelemetry tracing | `TracerPort` (domain) + `NoopTracer`/OTel adapter (infrastructure); contextvar propagation across `await`. |
| §6 | RED metrics per endpoint and MCP tool | `ObservabilityMiddleware` + `InMemoryMetrics` adapter (Prometheus exporter pluggable). |
| §6 | Structured JSON logs with correlation IDs, zero PII | `configure_logging()` in `prism.shared.infrastructure.observability`; correlation IDs via contextvar — ADR [0005](docs/decisions/0005-correlation-ids.md). |
| §6 | Per-AI-call log (model id, version, prompt hash, tokens, latency, cost) | `AICallLog` + `LoggingAICallRecorder` writing to `prism.aicall`; prompts are SHA-256 hashed, never stored raw. |
| §7 | Anti-patterns rejected | Aggregates have real behaviour (`Product.enrich`, `Payment.capture`, `Conversation.append_message`); CI contracts above mechanically reject violations. |

ADR index lives in [`docs/decisions/`](docs/decisions/). New deviations
require a one-paragraph ADR before merge.

---

*PRISM — Unified Commerce Intelligence Platform | Searce / Planet Payment | Confidential*
