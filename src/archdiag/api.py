from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from archdiag.parse import interpret_notes
from archdiag.schema import ArchitectureDiagram

STATIC_DIR = Path(__file__).parent / "static"
EXAMPLE_PATH = Path(__file__).resolve().parents[2] / "sample_notes" / "exercise_example.txt"

app = FastAPI(
    title="Architecture Diagram Generator",
    description=(
        "Use Case 2: turn unstructured technical notes into a visual architecture diagram. "
        "Components and connections are taken only from the notes."
    ),
    version="0.1.0",
)


class NotesRequest(BaseModel):
    notes: str = Field(min_length=20)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/example")
def example() -> dict[str, str]:
    if EXAMPLE_PATH.exists():
        return {"notes": EXAMPLE_PATH.read_text(encoding="utf-8")}
    return {"notes": ""}


@app.post("/generate", response_model=ArchitectureDiagram)
def generate(payload: NotesRequest) -> ArchitectureDiagram:
    try:
        return interpret_notes(payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/generate.svg")
def generate_svg(payload: NotesRequest) -> Response:
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
