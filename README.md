# Apple Notizen – MCP-Server für Claude

Mit diesem kleinen Server kann Claude (in Claude Desktop oder Claude Code) deine
Apple Notizen auf dem Mac **lesen, durchsuchen, neue Notizen anlegen und Text an
bestehende Notizen anhängen**.

Absichtlich **nicht** möglich: Notizen löschen, verschieben oder überschreiben.

## Was Claude damit kann

| Tool | Was es tut |
|---|---|
| `list_folders` | Zeigt alle Accounts (iCloud, „Auf meinem Mac“ …) und Ordner mit Anzahl Notizen |
| `list_notes` | Listet Notizen, neueste zuerst (optional nur ein Ordner / nur seit einem Datum) |
| `search_notes` | Sucht in Titel und Inhalt (Groß-/Kleinschreibung egal) |
| `get_note` | Liest eine Notiz vollständig (als Markdown) |
| `create_note` | Legt eine neue Notiz an – standardmäßig im Ordner **„Claude“** (wird bei Bedarf angelegt) |
| `append_to_note` | Hängt Text **unten** an eine Notiz an; bestehender Inhalt bleibt erhalten |

Gut zu wissen:
- Listen und Suche liefern höchstens 20 Ergebnisse (auf Wunsch bis 100) und nur eine kurze Vorschau. Den ganzen Text holt Claude dann gezielt mit `get_note`.
- **Gesperrte Notizen** (mit Passwort) werden erkannt und übersprungen – ihr Inhalt wird nie gelesen, nur der Titel ist sichtbar.
- Notizen in **„Zuletzt gelöscht“** werden ausgeblendet.
- An Notizen mit **Anhängen** (Bilder, Dateien) wird aus Sicherheitsgründen nichts angehängt, damit nichts kaputtgeht.
- Neue Notizen landen im **Standard-Account** der Notizen-App (meist iCloud).

## Einrichtung

Voraussetzung: macOS und [uv](https://docs.astral.sh/uv/) (`brew install uv`).

1. Repo klonen und im Projektordner einmal die Abhängigkeiten installieren (Pfade unten an deinen Rechner anpassen):
   ```bash
   cd "/Users/DEIN-NAME/Pfad/zu/apple-notes-MCP"
   uv sync
   ```
2. Kurz testen (siehe „Berechtigungen“ unten – hier kommt der erste macOS-Dialog):
   ```bash
   uv run python -c "import anyio, json; from notes_mcp import server; print(json.dumps(anyio.run(server.list_folders), ensure_ascii=False, indent=1))"
   ```
3. In Claude Desktop eintragen (nächster Abschnitt).

## Eintrag in `claude_desktop_config.json`

Die Datei liegt hier:
`~/Library/Application Support/Claude/claude_desktop_config.json`
(oder in Claude Desktop: Einstellungen → Entwickler → Konfiguration bearbeiten).

Füge unter `"mcpServers"` diesen Eintrag hinzu (Pfad zu uv mit `which uv` prüfen):

```json
{
  "mcpServers": {
    "apple-notes": {
      "command": "/opt/homebrew/bin/uv",
      "args": [
        "run",
        "--directory",
        "/Users/DEIN-NAME/Pfad/zu/apple-notes-MCP",
        "notes-mcp"
      ]
    }
  }
}
```

Wenn dort schon andere Server stehen, kommt `"apple-notes": { … }` einfach als
weiterer Eintrag dazu (mit Komma getrennt). Danach Claude Desktop **komplett
beenden** (⌘Q) und neu öffnen.

## Beispiel-Fragen an Claude

- „Welche Ordner habe ich in Apple Notizen?“
- „Zeig mir meine 10 zuletzt geänderten Notizen.“
- „Welche Notizen habe ich seit dem 1. September geändert?“
- „Such in meinen Notizen nach ‚Urlaub‘ und fass sie mir zusammen.“
- „Lege eine Notiz ‚Einkaufsliste‘ mit Milch, Brot und Äpfeln an.“
- „Häng an meine Notiz ‚Ideen‘ den Punkt ‚Mehr Wasser trinken‘ an.“

## Berechtigungen (wichtig!)

macOS schützt die Notizen-App. Jede App, die Notizen steuern will, muss einmal
erlaubt werden (Systemeinstellungen → Datenschutz & Sicherheit → **Automation**).

1. **Erster Test im Terminal:** Es erscheint ein Dialog wie
   *„Terminal“ möchte „Notizen“ steuern.* → **OK** klicken.
2. **Claude Desktop fragt separat:** Beim ersten Mal, wenn Claude Desktop auf
   Notizen zugreift, kommt derselbe Dialog noch einmal – diesmal für
   *„Claude“*. → Wieder **OK** klicken. (Die Erlaubnis gilt pro App.)
3. **Versehentlich „Nicht erlauben“ geklickt?**
   - Öffne **Systemeinstellungen → Datenschutz & Sicherheit → Automation**.
   - Klappe die betroffene App auf (z. B. „Claude“ oder „Terminal“) und schalte
     den Schalter bei **„Notizen“** ein.
   - Die App danach komplett beenden (⌘Q) und neu starten.
   - Steht die App dort gar nicht, kannst du die Entscheidung im Terminal
     zurücksetzen, dann kommt der Dialog beim nächsten Versuch erneut:
     ```bash
     tccutil reset AppleEvents
     ```
     (Das setzt die Automation-Erlaubnisse **aller** Apps zurück – sie fragen
     dann einfach neu.)

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| „Keine Berechtigung, die Notizen-App zu steuern“ | Siehe „Berechtigungen“ Punkt 3. |
| „Zeitüberschreitung“ | Oft wartet ein macOS-Dialog im Hintergrund auf „OK“. Sonst: Suche auf einen Ordner eingrenzen. Die Wartezeit (Standard 30 s) lässt sich mit der Umgebungsvariable `NOTES_MCP_TIMEOUT` ändern, z. B. `"env": {"NOTES_MCP_TIMEOUT": "60"}` im Config-Eintrag. |
| Server taucht in Claude Desktop nicht auf | JSON auf Tippfehler prüfen (Kommas!), Claude Desktop mit ⌘Q beenden und neu starten. Logs: `~/Library/Logs/Claude/mcp-server-apple-notes.log` |
| „uv: command not found“ in den Logs | In der Config den vollen Pfad von `which uv` verwenden. |
| Notiz wird nicht gefunden | IDs ändern sich nicht, aber gelöschte Notizen verschwinden. Einfach neu suchen lassen. |
| Notiz „gesperrt“ | Passwortgeschützte Notizen können nicht gelesen oder bearbeitet werden – das ist Absicht. |

## Für Entwickler

```bash
uv run pytest        # Tests (osascript wird gemockt, Notizen werden nicht berührt)
```

- `src/notes_mcp/osa.py` – alle `osascript`-Aufrufe (in Tests mockbar), Timeout, deutsche Fehlermeldungen
- `src/notes_mcp/scripts.py` – die JXA-Skripte (feste Konstanten)
- `src/notes_mcp/convert.py` – HTML ↔ Markdown
- `src/notes_mcp/server.py` – die MCP-Tools (FastMCP, `mcp[cli]>=1.2,<2`)

Sicherheit: Eingaben (Suchbegriffe, Titel, Text) werden nie in den Skript-Code
eingebaut, sondern als JSON-Argument an `osascript` übergeben und im Skript mit
`JSON.parse` gelesen. So ist keine Skript-Injection möglich.
