"""Tests der MCP-Tools mit gemockten JXA-Antworten."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from notes_mcp import osa, scripts, server


def meta(**kw):
    base = {
        "id": "x-coredata://ABC/ICNote/p1",
        "title": "Notiz",
        "folder": "Notizen",
        "account": "iCloud",
        "created": "2026-09-01T08:00:00.000Z",
        "modified": "2026-09-27T10:30:00.000Z",
        "locked": False,
        "preview": "Vorschau",
    }
    base.update(kw)
    return base


@pytest.mark.anyio
async def test_list_tools_registered():
    tools = {t.name for t in await server.mcp.list_tools()}
    assert tools == {"list_folders", "list_notes", "search_notes", "get_note", "create_note", "append_to_note"}


@pytest.mark.anyio
async def test_list_notes_clamps_limit_and_formats(fake_jxa):
    fake_jxa.response = {"total": 1, "notes": [meta()]}
    res = await server.list_notes(limit=500)
    script, payload = fake_jxa.calls[0]
    assert script is scripts.LIST_NOTES
    assert payload["limit"] == 100
    assert res["notes"][0]["title"] == "Notiz"
    assert "T" in res["notes"][0]["modified"]  # lokale ISO-Zeit


@pytest.mark.anyio
async def test_list_notes_modified_since(fake_jxa):
    fake_jxa.response = {"total": 0, "notes": []}
    await server.list_notes(modified_since="2026-09-01T00:00+00:00")
    assert fake_jxa.calls[0][1]["modified_since"] == "2026-09-01T00:00:00Z"


@pytest.mark.anyio
async def test_list_notes_invalid_date(fake_jxa):
    with pytest.raises(ToolError, match="Datum"):
        await server.list_notes(modified_since="letzte Woche")


@pytest.mark.anyio
async def test_locked_note_in_list_has_no_preview(fake_jxa):
    fake_jxa.response = {"total": 1, "notes": [meta(locked=True, preview="geheim")]}
    res = await server.list_notes()
    note = res["notes"][0]
    assert note["locked"] is True
    assert note["preview"] is None
    assert "Gesperrt" in note["hinweis"]


@pytest.mark.anyio
async def test_search_with_special_characters(fake_jxa):
    query = 'Müller\'s "Rezept" & <Kuchen> `$(whoami)`'
    fake_jxa.response = {"total": 1, "locked_body_not_searched": 2, "notes": [meta(title="Rezept")]}
    res = await server.search_notes(query, limit=0)
    script, payload = fake_jxa.calls[0]
    assert script is scripts.SEARCH_NOTES
    assert query not in script
    assert payload == {"query": query, "folder": None, "limit": 1}
    assert res["total"] == 1
    assert "2 gesperrte" in res["hinweis"]


@pytest.mark.anyio
async def test_search_requires_query(fake_jxa):
    with pytest.raises(ToolError):
        await server.search_notes("   ")
    assert fake_jxa.calls == []


@pytest.mark.anyio
async def test_get_note_converts_html_to_markdown(fake_jxa):
    fake_jxa.response = meta(html="<div><h1>Titel</h1></div><div>Hallo <b>Welt</b></div>", attachments=0)
    res = await server.get_note("x-coredata://ABC/ICNote/p1")
    assert fake_jxa.calls[0][1] == {"id": "x-coredata://ABC/ICNote/p1"}
    assert res["content_markdown"] == "# Titel\n\nHallo **Welt**"
    assert "preview" not in res


@pytest.mark.anyio
async def test_get_note_locked(fake_jxa):
    fake_jxa.response = meta(locked=True, html=None, attachments=0)
    res = await server.get_note("id")
    assert res["content_markdown"] is None
    assert "gesperrt" in res["hinweis"]


@pytest.mark.anyio
async def test_get_note_not_found(fake_jxa):
    fake_jxa.response = {"error": "not_found"}
    with pytest.raises(ToolError, match="Keine Notiz"):
        await server.get_note("gibt-es-nicht")


@pytest.mark.anyio
async def test_notes_error_becomes_tool_error(fake_jxa):
    fake_jxa.response = osa.NotesError("Keine Berechtigung …")
    with pytest.raises(ToolError, match="Berechtigung"):
        await server.list_folders()


@pytest.mark.anyio
async def test_create_note_defaults_to_claude_folder(fake_jxa):
    fake_jxa.response = {"id": "n1", "title": "Idee", "folder": "Claude", "account": "iCloud", "created_folder": True}
    res = await server.create_note("Idee <1>", "Punkt **eins**")
    payload = fake_jxa.calls[0][1]
    assert payload["folder"] == "Claude"
    assert payload["html"].startswith("<h1>Idee &lt;1&gt;</h1>")
    assert "<strong>eins</strong>" in payload["html"]
    assert res["ordner_neu_angelegt"] is True


@pytest.mark.anyio
async def test_append_refuses_locked(fake_jxa):
    fake_jxa.response = {"error": "locked"}
    with pytest.raises(ToolError, match="gesperrt"):
        await server.append_to_note("id", "mehr Text")


@pytest.mark.anyio
async def test_append_sends_html(fake_jxa):
    fake_jxa.response = {"id": "id", "title": "T", "folder": "Claude", "account": "iCloud", "modified": None}
    res = await server.append_to_note("id", "- neu")
    assert "<li>neu</li>" in fake_jxa.calls[0][1]["html"]
    assert res["status"] == "ergänzt"


def test_no_destructive_tools():
    names = " ".join(dir(server)).lower()
    for word in ("delete", "remove", "move_note", "overwrite"):
        assert word not in names
