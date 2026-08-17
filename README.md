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

Every box and arrow is tied to an **evidence sentence** from the notes so you can see why it was drawn.

---

## Are we using an LLM?

**No.** Diagram generation does **not** call OpenAI, Anthropic, Gemini, or any other LLM.

There is no `OPENAI_API_KEY`, no chat completion, and no embedding model in this project.

The pipeline is a **deterministic extractor**:

- regular expressions against a **component catalog**
- connection language in the same sentence (`connect`, `through`, `distributes`, `communicate`, `access` / `from`, `route`, …)
- port/protocol tokens in that sentence
- a simple zoned SVG layout

That is a deliberate trade-off: the behaviour is explainable in a technical interview, tests are stable without API keys, and the system cannot “hallucinate” a Redis box that was never mentioned. The cost is that product names **outside the catalog** are not drawn; they are treated as unknown rather than invented.

If this were production, an optional LLM could propose extra spans **only if those exact phrases appear in the notes**, with a human edit step before export.

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
3. Read the diagram, the component table, the connection table, and the ambiguity list.
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
    → if a sentence has connection language and two+ known components,
      add an arrow (word order + patterns such as "through A to B"
      and "access to Y from X")
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
sample_notes/          fictional notes used for the demo
src/archdiag/parse.py  component + connection extraction
src/archdiag/render.py SVG layout
src/archdiag/api.py    FastAPI + UI
src/archdiag/cli.py    command line
src/archdiag/static/   HTML page
tests/                 pytest coverage of the example and API
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
| No LLM | Explainable, offline, no invented infrastructure, easy to test |
| Catalog + regex rather than a general NER model | Precision over recall for this exercise; missing a rare product is better than drawing a fake one |
| SVG rather than PNG-only | Vector download, no extra rendering binary |
| FastAPI + one HTML page | Meets “usable application” without a heavy frontend |
| Heuristic arrow direction | Good enough for the exercise example; odd wording can reverse an arrow (called out as a limitation) |

---

## Limitations

- Names that are not in the catalog are not drawn (by design).
- Unusual sentence structure can attach the wrong direction to an arrow.
- Two unnamed application servers become **one logical group**, with an ambiguity note.
- Layout is a simple column grid, not a polished network drawing tool.
- The catalog is English-oriented and phrase-based (`load balancer`, not every vendor synonym).

## What I would change for production

- Optional LLM pass **constrained** to verbatim spans from the notes, then a human graph editor.
- PNG/PDF export, collision-free layout, and grouping of identical nodes.
- A larger, tested catalog (cloud load balancers, Kubernetes, message buses) with evaluation notes.
- Audit log of which sentence produced which box and arrow.

---

## Presentation demo (about two minutes)

1. `python -m pytest`
2. Start the UI, load the exercise example, generate.
3. Point at HTTPS/443 and PostgreSQL/5432 on the arrows.
4. Point at the ambiguity list (monitoring ports, two unnamed app servers).
5. Show that Redis/CDN are absent.
6. Download the SVG.
7. State clearly: **no LLM was used**; every element is evidenced in the notes.
