from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from archdiag.llm import llm_status
from archdiag.parse import interpret_notes
from archdiag.schema import ArchitectureDiagram
from archdiag.telemetry import init_telemetry, span as otel_span

STATIC_DIR = Path(__file__).parent / "static"
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "sample_notes"

_EXAMPLES = (
    ("exercise", "Exercise example", "exercise_example.txt"),
    ("api-cache", "API gateway + cache", "api_gateway_cache.txt"),
    ("fresh", "Fresh vocabulary", "fresh_vocabulary.txt"),
    ("eks", "EKS (needs LLM or verbatim span)", "eks_cluster.txt"),
)

_telemetry_status = init_telemetry()

app = FastAPI(
    title="Architecture Diagram Generator",
    description=(
        "Use Case 2: turn unstructured technical notes into a visual architecture diagram. "
        "Components and connections are taken only from the notes."
    ),
    version="0.4.0",
)


class NotesRequest(BaseModel):
    notes: str = Field(min_length=20)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "telemetry": _telemetry_status, "llm": llm_status()}


@app.get("/example")
def example() -> dict[str, str]:
    path = SAMPLES_DIR / "exercise_example.txt"
    if path.exists():
        return {"notes": path.read_text(encoding="utf-8")}
    return {"notes": ""}


@app.get("/examples")
def examples() -> dict[str, list[dict[str, str]]]:
    items: list[dict[str, str]] = []
    for ident, title, filename in _EXAMPLES:
        path = SAMPLES_DIR / filename
        if path.exists():
            items.append({"id": ident, "title": title, "notes": path.read_text(encoding="utf-8")})
    return {"examples": items}


@app.post("/generate", response_model=ArchitectureDiagram)
def generate(payload: NotesRequest) -> ArchitectureDiagram:
    with otel_span("archdiag.http.generate", notes_chars=len(payload.notes)):
        try:
            return interpret_notes(payload.notes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/generate.svg")
def generate_svg(payload: NotesRequest) -> Response:
    with otel_span("archdiag.http.generate_svg", notes_chars=len(payload.notes)):
        try:
            model = interpret_notes(payload.notes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=model.svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": "attachment; filename=architecture.svg"},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
