"""Tests für den osascript-Aufruf (subprocess wird gemockt)."""

import json
import subprocess

import pytest

from notes_mcp import osa, scripts


class Recorder:
    def __init__(self, returncode=0, stdout="{}", stderr=""):
        self.cmd = None
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)

    def __call__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs
        return self.result


TRICKY = 'O\'Brien "Zitat" `rm -rf ~` ${x} \\n"); doShellScript("ls'


@pytest.mark.anyio
async def test_user_input_is_passed_as_argv_not_in_script(monkeypatch):
    rec = Recorder(stdout='{"total": 0, "notes": []}')
    monkeypatch.setattr(subprocess, "run", rec)

    await osa.run_jxa(scripts.SEARCH_NOTES, {"query": TRICKY, "limit": 5})

    assert rec.cmd[:5] == ["osascript", "-l", "JavaScript", "-e", scripts.SEARCH_NOTES]
    # Das Skript bleibt unverändert, der Suchbegriff steht nur im JSON-Argument.
    assert TRICKY not in rec.cmd[4]
    assert len(rec.cmd) == 6
    assert json.loads(rec.cmd[5]) == {"query": TRICKY, "limit": 5}
    assert rec.cmd[5].startswith("{")
    assert "timeout" in rec.kwargs


@pytest.mark.anyio
async def test_permission_error_is_translated(monkeypatch):
    rec = Recorder(
        returncode=1,
        stdout="",
        stderr="execution error: Error: Error: Not authorized to send Apple events to Notes. (-1743)",
    )
    monkeypatch.setattr(subprocess, "run", rec)
    with pytest.raises(osa.NotesError, match="Automation"):
        await osa.run_jxa(scripts.LIST_FOLDERS)


@pytest.mark.anyio
async def test_timeout_is_translated(monkeypatch):
    def boom(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(osa.NotesError, match="Zeitüberschreitung"):
        await osa.run_jxa(scripts.LIST_FOLDERS, timeout=1)


@pytest.mark.anyio
async def test_invalid_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", Recorder(stdout="kaputt"))
    with pytest.raises(osa.NotesError, match="JSON"):
        await osa.run_jxa(scripts.LIST_FOLDERS)


def test_scripts_contain_no_python_placeholders():
    # Schutz davor, dass jemand später doch Werte per format()/f-String einbaut.
    for name in ["LIST_FOLDERS", "LIST_NOTES", "SEARCH_NOTES", "GET_NOTE", "CREATE_NOTE", "APPEND_TO_NOTE"]:
        script = getattr(scripts, name)
        assert "JSON.parse(argv[0])" in script
