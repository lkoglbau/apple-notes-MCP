"""MCP-Server für Apple Notizen (Notes.app).

Bewusst NICHT enthalten: Löschen, Verschieben oder Überschreiben von Notizen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from . import osa, scripts
from .convert import html_to_markdown, markdown_to_html, title_html

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_FOLDER = "Claude"

mcp = FastMCP(
    "apple-notes",
    instructions=(
        "Zugriff auf Apple Notizen. Listen und Suchen liefern nur Metadaten und eine kurze "
        "Vorschau; den vollständigen Inhalt gibt es mit get_note. Notizen können angelegt "
        "und ergänzt, aber nicht gelöscht, verschoben oder überschrieben werden."
    ),
)

_ERRORS = {
    "not_found": "Keine Notiz mit dieser ID gefunden. Hole die ID am besten neu über list_notes oder search_notes.",
    "folder_not_found": "Diesen Ordner gibt es nicht. Mit list_folders siehst du alle vorhandenen Ordner.",
    "locked": "Diese Notiz ist gesperrt (passwortgeschützt) und kann nicht bearbeitet werden.",
    "deleted": "Diese Notiz liegt in „Zuletzt gelöscht“ und wird nicht bearbeitet.",
    "attachments": (
        "Diese Notiz enthält Anhänge (z. B. Bilder oder Dateien). Um sie nicht zu beschädigen, "
        "wird nichts angehängt. Tipp: Lege stattdessen mit create_note eine neue Notiz an."
    ),
    "verify_failed": (
        "Beim Anhängen konnte nicht bestätigt werden, dass der bisherige Inhalt erhalten bleibt. "
        "Die Änderung wurde rückgängig gemacht."
    ),
    "folder_create_failed": "Der Zielordner konnte nicht angelegt werden.",
}


async def _call(script: str, payload: dict[str, Any] | None = None) -> Any:
    try:
        result = await osa.run_jxa(script, payload)
    except osa.NotesError as exc:
        raise ToolError(str(exc)) from exc
    if isinstance(result, dict) and "error" in result:
        raise ToolError(_ERRORS.get(result["error"], f"Fehler: {result['error']}"))
    return result


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def _local_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return dt.astimezone().isoformat(timespec="minutes")


def _parse_since(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolError(
            "modified_since bitte als Datum angeben, z. B. „2026-09-01“ oder „2026-09-01T08:00“."
        ) from exc
    if dt.tzinfo is None:
        dt = dt.astimezone()  # als lokale Zeit interpretieren
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_meta(note: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": note.get("id"),
        "title": note.get("title"),
        "folder": note.get("folder"),
        "account": note.get("account"),
        "created": _local_time(note.get("created")),
        "modified": _local_time(note.get("modified")),
        "preview": note.get("preview"),
    }
    if note.get("locked"):
        out["locked"] = True
        out["preview"] = None
        out["hinweis"] = "Gesperrte Notiz – Inhalt wird übersprungen."
    return out


# ---------------------------------------------------------------- Lesen


@mcp.tool()
async def list_folders() -> dict[str, Any]:
    """Listet alle Accounts (z. B. iCloud, „Auf meinem Mac“) mit ihren Ordnern und der
    Anzahl Notizen pro Ordner. „Zuletzt gelöscht“ wird ausgeblendet."""
    return await _call(scripts.LIST_FOLDERS)


@mcp.tool()
async def list_notes(
    folder: str | None = None,
    limit: int = DEFAULT_LIMIT,
    modified_since: str | None = None,
) -> dict[str, Any]:
    """Listet Notizen, neueste zuerst (nur Metadaten + kurze Vorschau).

    Args:
        folder: Optional nur diesen Ordner (Name, ohne Groß-/Kleinschreibung).
        limit: Anzahl Ergebnisse (Standard 20, höchstens 100).
        modified_since: Optional nur Notizen, die seit diesem Datum geändert wurden
            (z. B. "2026-09-01").
    """
    payload = {"folder": folder, "limit": _clamp_limit(limit), "modified_since": _parse_since(modified_since)}
    result = await _call(scripts.LIST_NOTES, payload)
    notes = [_format_meta(n) for n in result.get("notes", [])]
    return {"total": result.get("total", len(notes)), "shown": len(notes), "notes": notes}


@mcp.tool()
async def search_notes(query: str, folder: str | None = None, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Sucht in Titel und Inhalt aller Notizen (ohne Groß-/Kleinschreibung), neueste zuerst.
    Liefert Metadaten und einen Textausschnitt um den Treffer. Gesperrte Notizen werden nur
    im Titel durchsucht.

    Args:
        query: Suchbegriff.
        folder: Optional nur in diesem Ordner suchen.
        limit: Anzahl Ergebnisse (Standard 20, höchstens 100).
    """
    if not query or not query.strip():
        raise ToolError("Bitte einen Suchbegriff angeben.")
    payload = {"query": query, "folder": folder, "limit": _clamp_limit(limit)}
    result = await _call(scripts.SEARCH_NOTES, payload)
    notes = [_format_meta(n) for n in result.get("notes", [])]
    out: dict[str, Any] = {"total": result.get("total", len(notes)), "shown": len(notes), "notes": notes}
    locked = result.get("locked_body_not_searched", 0)
    if locked:
        out["hinweis"] = f"{locked} gesperrte Notiz(en): nur der Titel wurde durchsucht."
    return out


@mcp.tool()
async def get_note(note_id: str) -> dict[str, Any]:
    """Liefert den vollständigen Inhalt einer Notiz als Markdown plus Metadaten.

    Args:
        note_id: Die ID aus list_notes oder search_notes.
    """
    note = await _call(scripts.GET_NOTE, {"id": note_id})
    out = _format_meta(note)
    out.pop("preview", None)
    out["attachments"] = note.get("attachments", 0)
    if note.get("in_recently_deleted"):
        out["in_recently_deleted"] = True
    if note.get("locked"):
        out["content_markdown"] = None
        out["hinweis"] = "Diese Notiz ist gesperrt (passwortgeschützt). Ihr Inhalt kann nicht gelesen werden."
    else:
        out["content_markdown"] = html_to_markdown(note.get("html"))
        if out["attachments"]:
            out["hinweis"] = "Anhänge (Bilder, Dateien) sind nur als Platzhalter enthalten."
    return out


# ---------------------------------------------------------------- Schreiben


@mcp.tool()
async def create_note(title: str, body_markdown: str, folder: str = DEFAULT_FOLDER) -> dict[str, Any]:
    """Legt eine neue Notiz an (im Standard-Account). Der Ordner wird angelegt, falls er fehlt.

    Args:
        title: Titel der Notiz.
        body_markdown: Inhalt als Markdown.
        folder: Zielordner (Standard „Claude“).
    """
    if not title or not title.strip():
        raise ToolError("Bitte einen Titel angeben.")
    folder = (folder or DEFAULT_FOLDER).strip()
    html = title_html(title) + markdown_to_html(body_markdown or "")
    result = await _call(scripts.CREATE_NOTE, {"html": html, "folder": folder})
    return {
        "status": "angelegt",
        "id": result.get("id"),
        "title": result.get("title"),
        "folder": result.get("folder"),
        "account": result.get("account"),
        "ordner_neu_angelegt": bool(result.get("created_folder")),
    }


@mcp.tool()
async def append_to_note(note_id: str, text_markdown: str) -> dict[str, Any]:
    """Hängt Text unten an eine bestehende Notiz an. Bestehender Inhalt bleibt unverändert.
    Gesperrte Notizen, Notizen mit Anhängen und Notizen in „Zuletzt gelöscht“ werden nicht
    verändert.

    Args:
        note_id: Die ID aus list_notes oder search_notes.
        text_markdown: Anzuhängender Text als Markdown.
    """
    if not text_markdown or not text_markdown.strip():
        raise ToolError("Bitte einen Text zum Anhängen angeben.")
    html = markdown_to_html(text_markdown)
    result = await _call(scripts.APPEND_TO_NOTE, {"id": note_id, "html": html})
    return {
        "status": "ergänzt",
        "id": result.get("id"),
        "title": result.get("title"),
        "folder": result.get("folder"),
        "modified": _local_time(result.get("modified")),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
