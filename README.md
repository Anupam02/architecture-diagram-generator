# Architecture Diagram Generator

**Use Case 2** of the AI Engineer Technical Exercise: turn unstructured technical notes into a clear, downloadable network / solution architecture diagram.

This app is **Python only**, with a small web UI. It is **not** a notebook, a prompt, or a standalone model call.

Use Case 1 (CV AI competency review) lives in a separate repository.

---

## What this application does

You paste raw notes (the kind an engineer might scribble after a design conversation). The application:

1. Identifies **infrastructure and application components** that are actually named (firewalls, load balancers, application servers, databases, zones, external systems, APIs, clients, and similar).
2. Identifies **connections and dependencies** between those components.
3. Captures **ports and protocols** when the notes include them (for example HTTPS on port 443, PostgreSQL on 5432).
4. Organises components into **logical zones** (external, edge, application, data, internal).
5. Draws a **visual architecture diagram** (SVG) in the browser.
6. Lets you **download** that diagram.
7. **Does not invent** boxes, products, or arrows that the notes do not support.
8. Lists **ambiguous or insufficient information** instead of guessing (for example “monitoring ports” with no numbers).

Every box and arrow is tied to an **evidence sentence** from the notes so you can see why it was drawn. The UI also shows:

- the **matched phrase** (the catalog span)
- the **connection rule** (`through_chain`, `then_chain`, `access_from`, …)
- an **extraction trace** — ordered decisions from notes → diagram
- click-through from a diagram node or table row to the source sentence

That is application-level traceability (why this architecture was drawn). It is separate from APM traces you might send to SigNoz or Grafana (see below).

---

## Are we using an LLM?

**By default, no.** Extraction is a deterministic catalog. Tests do not need an API key.

An **optional constrained LLM pass** can propose extra components. A separate `VerbatimSpanGate` is the authority: a proposal is kept **only if that phrase already appears as a contiguous quote in the notes**. Invented names (Redis when the notes never say Redis) are rejected and recorded on the extraction trace as `llm_rejected`.

```
catalog matches
    → optional LLM proposals
    → verbatim gate (accept / reject)
    → connection rules
    → ambiguities
    → SVG
```

Enable an OpenAI-compatible API:

```bash
export ARCHDIAG_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
# optional:
export ARCHDIAG_LLM_MODEL=gpt-4o-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
```

`GET /health` reports `llm`: `off`, `missing_api_key`, or `openai`. CLI: `--no-llm` forces catalog-only.

The model is never trusted to add a box. That is the SOLID split: `SpanProposer` (OpenAI or a test double) vs `ConstrainedLlmMerger` (policy).

---

## Sample example to try

This is the example from the exercise. In the UI click **Load exercise example**, or paste the text below.

```
External users connect through a firewall to a load balancer using HTTPS on port 443.
The load balancer distributes traffic to two application servers.
The application servers communicate with a PostgreSQL database on port 5432.
The application servers also connect to an external authentication service using HTTPS.
An external monitoring platform connects to the application servers on the required monitoring ports.
Administrative access to the application servers is permitted only from the internal network.
```

### What you should see

| Kind | Expected result |
| --- | --- |
| Components | External users, firewall, load balancer, application servers, PostgreSQL, external authentication service, external monitoring platform, internal network |
| Flows | users → firewall → load balancer → app servers; app servers → PostgreSQL (5432); app servers → auth (HTTPS); monitoring → app servers; internal network → app servers (admin) |
| Ports / protocols | HTTPS and port **443** on the user/firewall/load-balancer path; port **5432** on the database path |
| Must **not** appear | Redis, Kafka, CDN, WAF, extra VPCs, unnamed “cloud” boxes |
| Ambiguities | Monitoring ports are mentioned but not numbered; two app servers are not named individually; admin access has no named workstation |

A second, shorter sample is in `sample_notes/api_gateway_cache.txt` (API gateway, Redis, MySQL). Use it to check that components appear **only when named**.

---

## How to run (UI)

Python 3.11+.

```bash
python -m pip install --upgrade "pip>=24.2"
python -m pip install -r requirements.txt
python -m uvicorn archdiag.api:app --port 8001
```

Open **http://127.0.0.1:8001**

1. Click **Load exercise example** (or paste your own notes).
2. Click **Generate diagram**.
3. Read the diagram, the component table, the connection table, the sentence links, the extraction trace, and the ambiguity list.
4. Click **Download SVG** to save `architecture.svg`.

That is the intended user experience: paste notes → run → inspect evidence → download the picture.

---

## How to test

### Automated tests

```bash
python -m pytest
```

These checks include: the exercise example extracts the supported components and ports; Redis/Kafka are not invented; a second sample picks up API gateway / Redis / MySQL; the HTTP API returns SVG.

### CLI

```bash
python -m archdiag sample_notes/exercise_example.txt --pretty --svg architecture.svg
```

Prints JSON (components, connections, ambiguities) and writes `architecture.svg`.

### API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web UI |
| `GET` | `/health` | Liveness |
| `GET` | `/example` | Returns the exercise sample notes |
| `POST` | `/generate` | JSON body `{ "notes": "..." }` → structured model + inline SVG |
| `POST` | `/generate.svg` | Same body; response is an SVG file download |

```bash
curl -s http://127.0.0.1:8001/health

curl -s -X POST http://127.0.0.1:8001/generate \
  -H 'Content-Type: application/json' \
  -d '{"notes":"External users connect through a firewall to a load balancer using HTTPS on port 443. The load balancer distributes traffic to two application servers."}'
```

---

## How the extractor works

```
raw notes
    → split into sentences
    → match catalog phrases (only if they occur in the text)
    → optional LLM proposals, kept only as verbatim spans
    → if a sentence has connection language and two+ known components,
      add an arrow (word order + named rules such as through_chain)
    → attach protocol/port from that sentence when present
    → collect ambiguities (missing ports, unnamed duplicates, …)
    → render a left-to-right zoned SVG
```

### Component catalog (drawn only if the notes mention them)

Examples: external users, firewall, load balancer, application servers, PostgreSQL, MySQL, generic database, authentication service, monitoring platform, internal network, API gateway, Redis/Memcached/cache, S3/object storage, VPN.

A generic “database” box is dropped if PostgreSQL or MySQL is already identified, so the example does not show two database nodes.

### Connection patterns

| Notes language | How it is interpreted |
| --- | --- |
| `connect through A to B` with three components | chain in order of appearance (users → firewall → load balancer) |
| `distributes` / `connects to` / `communicate with` / `route` | first mentioned component → last mentioned component |
| `access to Y … from X` | X → Y (admin from internal network) |

If a sentence has no connection verb, no arrow is created from that sentence.

---

## Project layout

```
sample_notes/               fictional notes used for the demo
src/archdiag/ports.py       interfaces (SOLID: depend on abstractions)
src/archdiag/pipeline.py    orchestrates finder → LLM gate → linker → SVG
src/archdiag/catalog.py     phrases recognised only when they appear
src/archdiag/components.py  catalog matching
src/archdiag/connections.py named connection rules (open for extension)
src/archdiag/ambiguities.py missing-detail flags
src/archdiag/llm.py         proposer + verbatim gate
src/archdiag/parse.py       public facade (`interpret_notes`)
src/archdiag/schema.py      API models and extraction trace
src/archdiag/render.py      SVG layout
src/archdiag/telemetry.py   optional OpenTelemetry (OTLP) spans
src/archdiag/api.py         FastAPI + UI
src/archdiag/static/        HTML page
tests/
```

---

## Mapping to the exercise brief

| Brief item | Status |
| --- | --- |
| Implemented primarily in Python | Yes |
| Usable UI (not only a script) | Yes — paste, generate, review, download |
| Firewalls, load balancers, app servers, databases, zones, ports, external systems, APIs, clients, flows | Recognised when present in the notes |
| Visual diagram that can be downloaded | SVG on the page and as a file |
| Do not invent unsupported architecture | Catalog + evidence sentences; no default extra boxes |
| Flag ambiguous / insufficient information | Explicit list under the diagram |
| Small fictional samples are enough | Two note files; realism of the dataset is not the point |

---

## Technical decisions and trade-offs

| Decision | Why |
| --- | --- |
| Catalog by default | Explainable, offline, no invented infrastructure, tests without keys |
| Optional LLM behind a verbatim gate | Recall for names outside the catalog without letting the model invent boxes |
| Injected ports (`SpanProposer`, `ConnectionLinker`, …) | SOLID: swap OpenAI, a stub, or a new connection rule without rewriting the pipeline |
| SVG rather than PNG-only | Vector download, no extra rendering binary |
| FastAPI + one HTML page | Meets “usable application” without a heavy frontend |
| Heuristic arrow direction | Good enough for the exercise example; odd wording can reverse an arrow |

---

## Limitations

- Names that are not in the catalog are not drawn unless the optional LLM pass is on **and** the phrase is a verbatim quote.
- Unusual sentence structure can attach the wrong direction to an arrow.
- Two unnamed application servers become **one logical group**, with an ambiguity note.
- Layout is a simple column grid, not a polished network drawing tool.
- The catalog is English-oriented and phrase-based (`load balancer`, not every vendor synonym).

## What I would change for production

- Human graph editor (delete/rename a node before download).
- PNG/PDF export, collision-free layout, and grouping of identical nodes.
- A labelled eval set (precision/recall of catalog vs gated LLM).

---

## Presentation demo (about two minutes)

1. `python -m pytest`
2. Start the UI, load the exercise example, generate.
3. Point at HTTPS/443 and PostgreSQL/5432 on the arrows.
4. Point at the ambiguity list (monitoring ports, two unnamed app servers).
5. Click a box or table row and show the matching sentence plus the extraction trace.
6. Show that Redis/CDN are absent.
7. Download the SVG.
8. State clearly: **the catalog is the default**; an LLM cannot add a box unless the phrase is a verbatim quote (`llm_accepted` / `llm_rejected` on the trace).
9. Optional: load `sample_notes/eks_cluster.txt` with a stub/LLM to show EKS accepted and Redis rejected.

---

## How you can improve this further

Keep precision first: do not invent boxes. Useful next steps:

1. **Human graph editor** — drag, drop, or delete a node before download.
2. **Evaluation set** — 10–20 labelled notes; precision/recall for catalog vs gated LLM.
3. **Richer layout** — Graphviz if SVG arrows overlap.
4. **Catalog growth from failures** — add a tested synonym rather than loosening regexes globally.
5. **Observability of the app** — OpenTelemetry to SigNoz/Grafana (below).

## SOLID and clean code

| Principle | How it shows up |
| --- | --- |
| **S**ingle responsibility | Catalog matching, connection rules, ambiguity flags, verbatim gate, SVG, and HTTP are separate modules |
| **O**pen/closed | Add a `ConnectionRule` (see `tests/test_connections.py`) without editing the linker loop |
| **L**iskov | `NullProposer`, `StaticProposer`, and `OpenAiCompatibleProposer` all return `ProposedComponent` lists; the gate treats them the same |
| **I**nterface segregation | Small ports in `ports.py` (`ComponentFinder`, `SpanProposer`, `ConnectionLinker`, `DiagramRenderer`) instead of one “engine” interface |
| **D**ependency inversion | `ArchitecturePipeline` depends on ports. Tests inject `StaticProposer`; production may inject OpenAI |

The previous design put finding, linking, and SVG in one `parse.py` procedure. That made the LLM gate hard to test without calling a vendor. The pipeline constructor is the seam.

## Traceability (already in this repo)

There are two different “traces”:

| Kind | What it answers | Where |
| --- | --- | --- |
| Extraction trace | Why is this box/arrow on the diagram? | `extraction_trace`, evidence spans, UI sentence list |
| APM / distributed trace | How long did `/generate` take? Did OTLP export fail? | OpenTelemetry → SigNoz / Grafana / Jaeger |

Do not mix them in the demo. Use the extraction trace for the architecture story. Use OTLP only if you want to show you can operate the service.

## Open-source alternatives similar to Datadog

Datadog is a hosted APM + metrics + logs + service-map product. You do not need it for this exercise. If you want the same *job* (see request traces, latency, errors) with open source:

| Tool | Closest Datadog feature | Why it fits |
| --- | --- | --- |
| **[SigNoz](https://signoz.io/)** | APM UI, traces, logs, metrics in one product | Strongest “Datadog-like” OSS option; native OpenTelemetry |
| **Grafana LGTM** ([Tempo](https://grafana.com/oss/tempo/) + Loki + Prometheus + Grafana) | Dashboards, trace-to-logs | Very common in industry; slightly more assembly |
| **[Jaeger](https://www.jaegertracing.io/)** | Distributed tracing | Simple if you only need traces |
| **[Uptrace](https://uptrace.dev/)** | APM on OpenTelemetry | Lightweight OTLP backend |
| **[Apache SkyWalking](https://skywalking.apache.org/)** | Service maps, APM | Useful if you later draw live service maps from traffic, not from notes |

This app speaks **OpenTelemetry (OTLP HTTP)**. Install extras and point at any of the backends above (or Datadog’s OTLP intake, if you had a key):

```bash
python -m pip install -e ".[otel]"
export OTEL_SERVICE_NAME=architecture-diagram-generator
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
python -m uvicorn archdiag.api:app --port 8001
```

`GET /health` reports `telemetry`: `disabled`, `packages_missing`, or `otlp`.

SigNoz local example: run their Docker install, use OTLP port **4318**, generate a diagram, then open the `architecture-diagram-generator` service and the `archdiag.http.generate` span.

A live Datadog/SigNoz **service map** is not a substitute for Use Case 2. Service maps come from runtime traffic. This exercise must draw architecture from **unstructured notes**, including boxes that have never emitted a span.
