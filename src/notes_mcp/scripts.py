"""JXA-Skripte für die Notizen-App.

Alle Skripte sind feste Konstanten. Parameter kommen als JSON über argv[0]
(siehe osa.py). Jedes Skript gibt einen JSON-String zurück; Fehler, die der
Server verständlich melden soll, werden als {"error": "<code>"} zurückgegeben.
"""

_COMMON = r"""
const DELETED_NAMES = ["recently deleted", "zuletzt gelöscht"];

function isDeletedName(name) {
  return DELETED_NAMES.indexOf(String(name || "").trim().toLowerCase()) !== -1;
}

function iso(d) {
  try { return d ? d.toISOString() : null; } catch (e) { return null; }
}

function norm(s) {
  s = String(s || "");
  try { s = s.normalize("NFC"); } catch (e) {}
  return s.toLowerCase();
}

// Alle Ordner aller Accounts (inkl. Unterordner), jeweils nur einmal.
function allFolders(Notes, includeDeleted) {
  const out = [];
  const seen = {};
  const accounts = Notes.accounts();
  for (let a = 0; a < accounts.length; a++) {
    const acc = accounts[a];
    let accName = "";
    try { accName = acc.name(); } catch (e) {}
    let stack = [];
    try { stack = acc.folders(); } catch (e) {}
    while (stack.length) {
      const f = stack.shift();
      let fid;
      try { fid = f.id(); } catch (e) { continue; }
      if (seen[fid]) continue;
      seen[fid] = true;
      let fname = "";
      try { fname = f.name(); } catch (e) {}
      const deleted = isDeletedName(fname);
      if (deleted && !includeDeleted) continue;
      out.push({ ref: f, id: fid, name: fname, account: accName, deleted: deleted });
      try { const subs = f.folders(); for (let i = 0; i < subs.length; i++) stack.push(subs[i]); } catch (e) {}
    }
  }
  return out;
}

function selectFolders(Notes, folderName) {
  const folders = allFolders(Notes, false);
  if (folderName === null || folderName === undefined || folderName === "") return folders;
  const wanted = norm(folderName).trim();
  return folders.filter(function (f) { return norm(f.name).trim() === wanted; });
}

// Metadaten aller Notizen eines Ordners per Sammelabfrage (schnell).
function folderMeta(fo) {
  const n = fo.ref.notes;
  let ids = [];
  try { ids = n.id(); } catch (e) { return []; }
  if (!ids.length) return [];
  const names = n.name();
  const cd = n.creationDate();
  const md = n.modificationDate();
  let locked;
  try { locked = n.passwordProtected(); } catch (e) { locked = ids.map(function () { return false; }); }
  return ids.map(function (id, i) {
    return {
      id: id,
      title: names[i],
      folder: fo.name,
      account: fo.account,
      created: iso(cd[i]),
      modified: iso(md[i]),
      locked: !!locked[i]
    };
  });
}

function preview(text, title) {
  let t = String(text || "");
  // Die erste Zeile ist bei Notizen der Titel – nicht doppelt anzeigen.
  const nl = t.indexOf("\n");
  if (nl !== -1 && t.slice(0, nl).trim() === String(title || "").trim()) t = t.slice(nl + 1);
  t = t.replace(/\s+/g, " ").trim();
  return t.length > 160 ? t.slice(0, 160) + "…" : t;
}

function byModifiedDesc(a, b) {
  return (b.modified || "").localeCompare(a.modified || "");
}

function run(argv) {
  const params = argv.length ? JSON.parse(argv[0]) : {};
  const Notes = Application("Notes");
  return JSON.stringify(main(Notes, params));
}
"""

LIST_FOLDERS = _COMMON + r"""
function main(Notes, p) {
  const folders = allFolders(Notes, false);
  const accounts = {};
  const order = [];
  folders.forEach(function (f) {
    let count = null;
    try { count = f.ref.notes.length; } catch (e) {}
    if (!accounts[f.account]) { accounts[f.account] = []; order.push(f.account); }
    accounts[f.account].push({ id: f.id, name: f.name, note_count: count });
  });
  return { accounts: order.map(function (a) { return { account: a, folders: accounts[a] }; }) };
}
"""

LIST_NOTES = _COMMON + r"""
function main(Notes, p) {
  const folders = selectFolders(Notes, p.folder);
  if (p.folder && !folders.length) return { error: "folder_not_found" };
  let all = [];
  folders.forEach(function (fo) { all = all.concat(folderMeta(fo)); });
  if (p.modified_since) {
    const since = new Date(p.modified_since).toISOString();
    all = all.filter(function (m) { return m.modified && m.modified >= since; });
  }
  all.sort(byModifiedDesc);
  const total = all.length;
  const page = all.slice(0, p.limit);
  page.forEach(function (m) {
    if (m.locked) { m.preview = null; return; }
    try { m.preview = preview(Notes.notes.byId(m.id).plaintext(), m.title); } catch (e) { m.preview = null; }
  });
  return { total: total, notes: page };
}
"""

SEARCH_NOTES = _COMMON + r"""
function main(Notes, p) {
  const q = norm(p.query).trim();
  const folders = selectFolders(Notes, p.folder);
  if (p.folder && !folders.length) return { error: "folder_not_found" };
  let hits = [];
  let lockedCount = 0;
  folders.forEach(function (fo) {
    const metas = folderMeta(fo);
    if (!metas.length) return;
    let texts = null;
    try { texts = fo.ref.notes.plaintext(); } catch (e) { texts = null; }
    metas.forEach(function (m, i) {
      let text = "";
      if (m.locked) {
        lockedCount++;
      } else if (texts) {
        text = texts[i] || "";
      } else {
        try { text = Notes.notes.byId(m.id).plaintext(); } catch (e) { text = ""; }
      }
      const inTitle = norm(m.title).indexOf(q) !== -1;
      const pos = m.locked ? -1 : norm(text).indexOf(q);
      if (!inTitle && pos === -1) return;
      if (m.locked) {
        m.preview = null;
      } else if (pos !== -1) {
        const start = Math.max(0, pos - 60);
        let snip = text.slice(start, pos + q.length + 100).replace(/\s+/g, " ").trim();
        m.preview = (start > 0 ? "…" : "") + snip + (pos + q.length + 100 < text.length ? "…" : "");
      } else {
        m.preview = preview(text, m.title);
      }
      hits.push(m);
    });
  });
  hits.sort(byModifiedDesc);
  return { total: hits.length, locked_body_not_searched: lockedCount, notes: hits.slice(0, p.limit) };
}
"""

_NOTE_LOOKUP = r"""
function findNote(Notes, id) {
  const n = Notes.notes.byId(id);
  try { n.id(); } catch (e) { return null; }
  return n;
}

function noteLocation(Notes, n, id) {
  let folder = null, account = null;
  try { folder = n.container().name(); } catch (e) {}
  try {
    const accs = Notes.accounts();
    for (let i = 0; i < accs.length; i++) {
      if (accs[i].notes.byId(id).exists()) { account = accs[i].name(); break; }
    }
  } catch (e) {}
  return { folder: folder, account: account };
}

function attachmentCount(n) {
  try { return n.attachments.length; } catch (e) { return 0; }
}
"""

GET_NOTE = _COMMON + _NOTE_LOOKUP + r"""
function main(Notes, p) {
  const n = findNote(Notes, p.id);
  if (!n) return { error: "not_found" };
  const loc = noteLocation(Notes, n, p.id);
  let locked = false;
  try { locked = n.passwordProtected(); } catch (e) {}
  const res = {
    id: p.id,
    title: n.name(),
    folder: loc.folder,
    account: loc.account,
    created: iso(n.creationDate()),
    modified: iso(n.modificationDate()),
    locked: locked,
    in_recently_deleted: isDeletedName(loc.folder),
    attachments: attachmentCount(n),
    html: null
  };
  if (!locked) {
    try { res.html = n.body(); } catch (e) { res.html = null; }
  }
  return res;
}
"""

CREATE_NOTE = _COMMON + r"""
function main(Notes, p) {
  const acc = Notes.defaultAccount();
  function findFolder() {
    const fs = acc.folders();
    for (let i = 0; i < fs.length; i++) {
      if (fs[i].name() === p.folder) return fs[i];
    }
    return null;
  }
  let target = findFolder();
  let createdFolder = false;
  if (!target) {
    acc.folders.push(Notes.Folder({ name: p.folder }));
    target = findFolder();
    createdFolder = true;
    if (!target) return { error: "folder_create_failed" };
  }
  const note = Notes.Note({ body: p.html });
  target.notes.push(note);
  let id = null, title = null;
  try { id = note.id(); title = note.name(); } catch (e) {
    // Fallback: neueste Notiz im Zielordner
    const ids = target.notes.id();
    const cds = target.notes.creationDate();
    let best = -1;
    for (let i = 0; i < ids.length; i++) if (best === -1 || cds[i] > cds[best]) best = i;
    if (best !== -1) { id = ids[best]; title = target.notes.byId(id).name(); }
  }
  return { id: id, title: title, folder: target.name(), account: acc.name(), created_folder: createdFolder };
}
"""

APPEND_TO_NOTE = _COMMON + _NOTE_LOOKUP + r"""
function squash(s) { return String(s || "").replace(/\s+/g, " ").trim(); }

function main(Notes, p) {
  const n = findNote(Notes, p.id);
  if (!n) return { error: "not_found" };
  let locked = false;
  try { locked = n.passwordProtected(); } catch (e) {}
  if (locked) return { error: "locked" };
  const loc = noteLocation(Notes, n, p.id);
  if (isDeletedName(loc.folder)) return { error: "deleted" };
  const att = attachmentCount(n);
  if (att > 0) return { error: "attachments", attachments: att };

  const oldBody = n.body();
  const oldPlain = squash(n.plaintext());
  n.body = oldBody + p.html;

  // Sicherheitsprüfung: Der alte Inhalt muss vollständig erhalten sein.
  const newPlain = squash(n.plaintext());
  if (newPlain.indexOf(oldPlain) !== 0) {
    try { n.body = oldBody; } catch (e) {}
    return { error: "verify_failed" };
  }
  return { id: p.id, title: n.name(), folder: loc.folder, account: loc.account, modified: iso(n.modificationDate()) };
}
"""
