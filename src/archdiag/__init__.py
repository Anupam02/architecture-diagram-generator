"""Evidence-only architecture extraction from unstructured technical notes."""

from archdiag.parse import interpret_notes
from archdiag.schema import ArchitectureDiagram

__all__ = ["interpret_notes", "ArchitectureDiagram"]
__version__ = "0.1.0"
