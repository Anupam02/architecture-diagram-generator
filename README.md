# Architecture Diagram Generator (Use Case 2)

Python web app that turns **unstructured technical notes** into a **downloadable architecture diagram**.

This repository is **Use Case 2 only** from the AI Engineer Technical Exercise. Use Case 1 (CV competency review) is a separate repo.

The extractor **does not invent** components or connections. If a port, hostname, or box is not in the notes, it is omitted or listed as ambiguous.

---

## What has been done

| Exercise requirement | How this app meets it |
| --- | --- |
| Paste unstructured technical notes | Text area in the UI, file/CLI, or JSON API |
| Identify infrastructure and application components | Catalog match only when the phrase appears in the notes |
| Identify connections and dependencies | Sentence-level flows (`through`, `connects to`, `distributes`, `from`/`access`) |
| Capture ports and protocols when provided | e.g. HTTPS, port 443, port 5432 |
| Organize into a logical architecture | Zones: external, edge, application, data, internal |
| Visual diagram | SVG rendered in the page |
| Download the diagram | **Download SVG** in the UI, `POST /generate.svg`, or CLI `--svg` |
| Do not invent unsupported boxes or links | No default VPC/WAF/CDN unless named |
| Flag ambiguous / insufficient information | Listed under the diagram and in JSON |

The exercise example notes are included in `sample_notes/exercise_example.txt`.

---

## How to install

```bash
python -m pip install --upgrade "pip>=24.2"
python -m pip install -r requirements.txt
```

---

## How to test

### Automated tests

```bash
python -m pytest
```

### UI

```bash
python -m uvicorn archdiag.api:app --port 8001
```

Open http://127.0.0.1:8001

1. Click **Load exercise example**.
2. Click **Generate diagram**.
3. Confirm boxes for users, firewall, load balancer, application servers, PostgreSQL, auth, monitoring, internal network.
4. Confirm there is **no** Redis/Kafka/CDN box.
5. Confirm ambiguities mention unnumbered monitoring ports and unnamed app servers.
6. Click **Download SVG**.

### CLI

```bash
python -m archdiag sample_notes/exercise_example.txt --pretty --svg /tmp/architecture.svg
```

### API

```bash
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8001/example
curl -s -X POST http://127.0.0.1:8001/generate \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF'
{"notes":"External users connect through a firewall to a load balancer using HTTPS on port 443. The load balancer distributes traffic to two application servers."}
EOF
```

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | UI |
| GET | `/health` | Liveness |
| GET | `/example` | Exercise sample notes |
| POST | `/generate` | JSON model + inline SVG |
| POST | `/generate.svg` | SVG file download |

---

## How it works

```
notes
  → split sentences
  → match known component phrases (only if present)
  → extract connections from connection language in those sentences
  → attach ports/protocols found in the same sentence
  → list ambiguities
  → draw zoned SVG
```

This is a deterministic extractor, not an LLM call, so it is explainable in a technical discussion: every box and arrow has an evidence sentence. A catalog can be extended; unknown product names that are not in the catalog are reported rather than guessed.

---

## Limitations

- Components outside the catalog are not drawn (by design: no invention).
- Connection direction uses word order plus a few patterns (`through`, `from`/`access`). Unusual wording can reverse an arrow.
- Two unnamed application servers are one logical box.
- Layout is a simple left-to-right zone grid, not a visio-quality drawing.

## If this were production

- Optional LLM extraction **constrained** to spans that appear in the notes
- Human edit of the graph before export
- PNG/PDF export, richer layout, and a larger validated catalog
