"""Umwandlung zwischen dem HTML der Notizen-App und Markdown."""

from __future__ import annotations

import html
import re

import markdown as md_lib
from markdownify import MarkdownConverter


_BLANK = "⁣LEERZEILE⁣"


class _NotesConverter(MarkdownConverter):
    """Notizen speichert jede Zeile als <div>. Daraus sollen einfache Zeilen
    werden, keine Absätze mit Leerzeile dazwischen."""

    def convert_div(self, el, text, parent_tags):
        if "_inline" in parent_tags:
            return text
        content = text.strip("\n")
        if not content.strip():
            # <div><br></div> = Leerzeile in Notizen. markdownify würde sie
            # verschlucken, daher Platzhalter (wird in html_to_markdown ersetzt).
            return f"\n{_BLANK}\n"
        # Überschriften, Listen usw. behalten ihren Absatzabstand.
        suffix = "\n\n" if text.endswith("\n\n") else "\n"
        return content.rstrip() + suffix

    def convert_img(self, el, text, parent_tags):
        # Bilder sind oft riesige data:-URLs – nur einen Platzhalter ausgeben.
        alt = (el.get("alt") or "").strip()
        return f"[Bild: {alt}]" if alt else "[Bild]"


_converter = _NotesConverter(heading_style="ATX", bullets="-", escape_underscores=False)


def html_to_markdown(body_html: str | None) -> str:
    if not body_html:
        return ""
    text = _converter.convert(body_html)
    text = re.sub(rf"\n*{_BLANK}\n*", "\n\n", text)
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)  # Leerzeichen am Zeilenende (von <br>)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_html(text: str) -> str:
    """Einfaches HTML für Notizen. Rohes HTML in der Eingabe wird maskiert."""
    escaped = html.escape(text or "", quote=False)
    return md_lib.markdown(escaped, extensions=["sane_lists", "nl2br"])


def title_html(title: str) -> str:
    return f"<h1>{html.escape(title.strip())}</h1>"
