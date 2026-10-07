"""Dominio: convierte un PDF en Markdown.

Se divide en dos pasos con responsabilidades separadas:
``reader`` (PDF → líneas con estilo, usa MuPDF) y
``markdown`` (líneas con estilo → Markdown, lógica pura).
"""

from __future__ import annotations

from dataclasses import dataclass

from .markdown import to_markdown
from .reader import InvalidPdfError, read_pdf

__all__ = ["Extraction", "InvalidPdfError", "extract_markdown"]


@dataclass(frozen=True, slots=True)
class Extraction:
    content: str
    page_count: int


def extract_markdown(pdf: bytes) -> Extraction:
    """Extrae el texto del PDF en formato Markdown.

    Raises:
        InvalidPdfError: si el archivo no es un PDF legible.
    """
    text = read_pdf(pdf)
    return Extraction(content=to_markdown(text.blocks), page_count=text.page_count)
