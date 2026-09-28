"""Kapselt alle Aufrufe von ``osascript`` (JXA).

Sicherheit: Die Skripte sind feste Konstanten. Nutzereingaben werden
ausschließlich als JSON in ``argv[0]`` übergeben und im Skript per
``JSON.parse`` gelesen – niemals per String-Interpolation ins Skript eingebaut.

In Tests wird ``run_jxa`` (bzw. ``subprocess.run``) gemockt.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from functools import partial
from typing import Any

import anyio

DEFAULT_TIMEOUT = float(os.environ.get("NOTES_MCP_TIMEOUT", "30"))


class NotesError(Exception):
    """Fehler mit verständlicher (deutscher) Meldung für die Nutzerin."""


_PERMISSION_HINT = (
    "Keine Berechtigung, die Notizen-App zu steuern. Öffne Systemeinstellungen → "
    "Datenschutz & Sicherheit → Automation und erlaube bei der aufrufenden App "
    "(z. B. Claude oder Terminal) den Zugriff auf „Notizen“. "
    "Danach die App neu starten und es erneut versuchen."
)


def _translate_error(stderr: str) -> str:
    code_match = re.search(r"\((-?\d+)\)\s*$", stderr.strip())
    code = int(code_match.group(1)) if code_match else None
    if code == -1743 or "Not authorized" in stderr or "nicht berechtigt" in stderr:
        return _PERMISSION_HINT
    if code == -1712:
        return (
            "Die Notizen-App hat nicht rechtzeitig geantwortet. "
            "Bitte später erneut versuchen oder das Ergebnis weiter eingrenzen."
        )
    if code in (-600, -609, -10810):
        return "Die Notizen-App ist nicht erreichbar. Bitte Notizen einmal öffnen und erneut versuchen."
    detail = stderr.strip().splitlines()[-1] if stderr.strip() else "unbekannter Fehler"
    return f"Fehler beim Zugriff auf die Notizen-App: {detail}"


def _run_sync(script: str, payload: dict[str, Any], timeout: float) -> Any:
    # Das JSON beginnt immer mit "{", wird von osascript also nie als Option gelesen.
    cmd = [
        "osascript",
        "-l",
        "JavaScript",
        "-e",
        script,
        json.dumps(payload, ensure_ascii=False),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise NotesError(
            f"Zeitüberschreitung: Die Notizen-App hat nicht innerhalb von {timeout:.0f} Sekunden "
            "geantwortet. Falls gerade ein macOS-Dialog zur Berechtigung angezeigt wird, "
            "bestätige ihn mit „OK“ und versuche es erneut. Bei sehr vielen Notizen hilft es, "
            "die Suche auf einen Ordner zu beschränken."
        ) from exc
    except FileNotFoundError as exc:
        raise NotesError("osascript wurde nicht gefunden – dieser Server läuft nur auf macOS.") from exc

    if proc.returncode != 0:
        raise NotesError(_translate_error(proc.stderr))

    out = proc.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise NotesError("Unerwartete Antwort der Notizen-App (kein gültiges JSON).") from exc


async def run_jxa(script: str, payload: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
    """Führt ein JXA-Skript in einem Worker-Thread aus und gibt das geparste JSON zurück."""
    return await anyio.to_thread.run_sync(
        partial(_run_sync, script, payload or {}, timeout or DEFAULT_TIMEOUT)
    )
