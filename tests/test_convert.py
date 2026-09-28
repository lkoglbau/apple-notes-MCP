from notes_mcp.convert import html_to_markdown, markdown_to_html, title_html

NOTES_HTML = (
    "<div><h1>Einkaufsliste</h1></div>"
    "<div>Milch &amp; Brot</div>"
    "<div><br></div>"
    "<div><b>Wichtig:</b> Äpfel &quot;Boskoop&quot;</div>"
    "<ul><li>eins</li><li>zwei</li></ul>"
    '<div><img src="data:image/png;base64,AAAA"></div>'
)


def test_html_to_markdown_notes_style():
    md = html_to_markdown(NOTES_HTML)
    assert md == (
        "# Einkaufsliste\n\n"
        "Milch & Brot\n\n"
        '**Wichtig:** Äpfel "Boskoop"\n\n'
        "- eins\n- zwei\n\n"
        "[Bild]"
    )


def test_html_to_markdown_consecutive_lines_stay_together():
    assert html_to_markdown("<div>Zeile 1</div><div>Zeile 2</div>") == "Zeile 1\nZeile 2"


def test_html_to_markdown_empty():
    assert html_to_markdown(None) == ""
    assert html_to_markdown("") == ""


def test_markdown_to_html_basic():
    html = markdown_to_html("**fett**\n\n- a\n- b")
    assert "<strong>fett</strong>" in html
    assert "<li>a</li>" in html


def test_markdown_to_html_escapes_raw_html():
    html = markdown_to_html('<script>alert("x")</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_title_html_escapes():
    assert title_html('Tom & "Jerry" <3') == "<h1>Tom &amp; &quot;Jerry&quot; &lt;3</h1>"
