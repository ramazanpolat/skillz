#!/usr/bin/env python3
"""Unit tests for claude-ai-archive's project writer and harvest script.

No browser and no network: archive.py's write_project runs against a temporary
archive root, and harvest.py runs against a fake browser-harness (new_tab, js,
cdp, ...) that answers the claude.ai API calls from a table. All data is
synthetic.

  python3 plugins/skillz/skills/claude-ai-archive/tests/test_archive.py
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
HARVEST = SCRIPTS / "harvest.py"

spec = importlib.util.spec_from_file_location("archive", SCRIPTS / "archive.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
project_folder_by_uuid = sys.modules["common"].project_folder_by_uuid

U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
U3 = "00000000-0000-4000-8000-000000000003"
U4 = "00000000-0000-4000-8000-000000000004"


def project(uuid, name, docs=None, description=""):
    return {"uuid": uuid, "name": name, "docs": docs or [], "description": description,
            "created_at": "2000-01-01T00:00:00Z", "updated_at": "2000-01-01T00:00:00Z"}


def uuid_of(folder):
    m = re.search(r"^uuid:\s*(\S+)", (folder / "CLAUDE.md").read_text(), re.M)
    return m.group(1) if m else None


class WriteProjectDocs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "archive"
        (self.root / "projects").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_doc_filenames_with_a_path_stay_flat_inside_docs(self):
        docs = [{"filename": "notes/plan.md", "content": "a"},
                {"filename": "notes\\win.md", "content": "b"},
                {"filename": "../outside.md", "content": "c"},
                {"filename": "..", "content": "d"},
                {"filename": None, "content": "e"},
                {"filename": "plain.md", "content": "f"}]
        pdir = archive.write_project(project(U1, "Alpha", docs), "", self.root, {})
        got = {p.name: p.read_text() for p in (pdir / "docs").iterdir()}
        self.assertEqual(got, {"notes__plan.md": "a", "notes__win.md": "b", "..__outside.md": "c",
                               "untitled.txt": "d", "untitled_2.txt": "e", "plain.md": "f"})
        self.assertTrue(all(p.is_file() for p in (pdir / "docs").iterdir()))
        # nothing escaped the project folder
        outside = [p for p in Path(self.tmp.name).rglob("*") if p.is_file() and pdir not in p.parents]
        self.assertEqual(outside, [])

    def test_a_resync_drops_docs_the_export_no_longer_has(self):
        pdir = archive.write_project(project(U1, "Alpha", [{"filename": "a/one.md", "content": "1"},
                                                           {"filename": "two.md", "content": "2"}]),
                                     "", self.root, {})
        archive.write_project(project(U1, "Alpha", [{"filename": "a/one.md", "content": "1b"}]),
                              "", self.root, project_folder_by_uuid(self.root))
        self.assertEqual({p.name: p.read_text() for p in (pdir / "docs").iterdir()}, {"a__one.md": "1b"})


class WriteProjectDocNameLength(unittest.TestCase):
    """Flattening lengthens a name; the name written must still fit in 255 bytes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "projects").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, *filenames):
        docs = [{"filename": fn, "content": str(i)} for i, fn in enumerate(filenames)]
        return archive.write_project(project(U1, "Alpha", docs), "", self.root, project_folder_by_uuid(self.root))

    def names(self, pdir):
        got = {p.name: p.read_text() for p in (pdir / "docs").iterdir()}
        self.assertTrue(all(len(n.encode()) <= 255 for n in got), [len(n.encode()) for n in got])
        return got

    def test_backslash_name_at_the_limit_still_writes(self):
        # 255 bytes as exported, 256 once the backslash becomes "__"
        fn = "a" * 126 + "\\" + "b" * 125 + ".md"
        self.assertEqual(len(fn.encode()), 255)
        self.assertEqual(self.names(self.write(fn)), {"a" * 126 + "__" + "b" * 124 + ".md": "0"})

    def test_slash_name_at_the_limit(self):
        fits = "d/" + "x" * 249 + ".md"   # 255 bytes once flattened: kept whole
        over = "e/" + "y" * 250 + ".md"   # 256 once flattened: one stem byte trimmed
        self.assertEqual(self.names(self.write(fits, over)),
                         {"d__" + "x" * 249 + ".md": "0", "e__" + "y" * 249 + ".md": "1"})

    def test_a_multibyte_stem_is_cut_on_a_character_boundary(self):
        two = "notes/" + "ç" * 124 + ".md"    # 2-byte characters, 258 bytes flattened
        four = "p/" + "😀" * 63 + ".md"       # 4-byte characters, 258 bytes flattened
        got = self.names(self.write(two, four))
        # 255 would split a character, so both stop at 254
        self.assertEqual(got, {"notes__" + "ç" * 122 + ".md": "0", "p__" + "😀" * 62 + ".md": "1"})
        self.assertEqual(sorted(len(n.encode()) for n in got), [254, 254])

    def test_a_collision_suffix_stays_inside_the_limit(self):
        same = "z" * 252 + ".md"                                # exactly 255 bytes
        long1, long2 = "w" * 260 + "1.md", "w" * 260 + "2.md"   # equal once trimmed
        want = {"z" * 252 + ".md": "0", "z" * 250 + "_2.md": "1", "w" * 252 + ".md": "2", "w" * 250 + "_2.md": "3"}
        pdir = self.write(same, same, long1, long2)
        self.assertEqual(self.names(pdir), want)
        # a re-sync of the same docs lands on the same names and keeps all four
        self.write(same, same, long1, long2)
        self.assertEqual(self.names(pdir), want)


class WriteProjectFolders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "projects").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_name_projects_never_share_a_folder(self):
        first = archive.write_project(project(U1, "Alpha", description="first"), "", self.root, {})
        before = (first / "CLAUDE.md").read_text()
        # a later sync: the archive already holds U1; U2 and U3 have the same name
        folders = project_folder_by_uuid(self.root)
        second = archive.write_project(project(U2, "Alpha", description="second"), "", self.root, folders)
        third = archive.write_project(project(U3, "Alpha", description="third"), "", self.root, folders)
        self.assertEqual([first.name, second.name, third.name], ["alpha", "alpha-2", "alpha-3"])
        self.assertEqual((first / "CLAUDE.md").read_text(), before)
        self.assertEqual([uuid_of(first), uuid_of(second), uuid_of(third)], [U1, U2, U3])

    def test_an_existing_project_keeps_its_folder(self):
        archive.write_project(project(U1, "Alpha"), "", self.root, {})
        archive.write_project(project(U2, "Alpha"), "", self.root, project_folder_by_uuid(self.root))
        again = archive.write_project(project(U2, "Alpha", description="edited"), "", self.root,
                                      project_folder_by_uuid(self.root))
        self.assertEqual(again.name, "alpha-2")
        self.assertEqual(sorted(p.name for p in (self.root / "projects").iterdir()), ["alpha", "alpha-2"])

    def test_a_folder_that_is_not_a_project_is_left_alone(self):
        own = self.root / "projects" / "beta"
        own.mkdir()
        (own / "notes.md").write_text("mine")
        pdir = archive.write_project(project(U4, "Beta"), "", self.root, project_folder_by_uuid(self.root))
        self.assertEqual(pdir.name, "beta-2")
        self.assertEqual(sorted(p.name for p in own.iterdir()), ["notes.md"])


class FakeBrowser:
    """browser-harness stand-in: claude.ai API answers come from `routes`."""

    def __init__(self, routes, login_redirect=False):
        self.routes, self.login_redirect = routes, login_redirect
        self.opened, self.closed, self.result = [], [], None

    def new_tab(self, url="about:blank"):
        self.opened.append(url)
        return f"tab-{len(self.opened)}"

    def wait_for_load(self):
        pass

    def ensure_real_tab(self):
        raise AssertionError("harvest must not adopt the current tab")

    def cdp(self, method, **params):
        if method == "Target.closeTarget":
            self.closed.append(params["targetId"])
        return {}

    def js(self, expr):
        m = re.search(r'fetch\((".*?")\)', expr)
        if m:
            answer = self.routes.get(json.loads(m.group(1)))
            self.result = answer if answer is not None else {"__error": "HTTP 404"}
            return None
        if "location.pathname" in expr:
            return self.login_redirect
        if "window.__r" in expr:
            return self.result
        raise AssertionError(f"unexpected js: {expr}")


class Harvest(unittest.TestCase):
    ROUTES = {
        "/api/organizations": [{"uuid": "org-1"}],
        "/api/organizations/org-1/projects": [{"uuid": U1, "name": "Alpha"}],
        "/api/organizations/org-1/chat_conversations?limit=100&offset=0": [
            {"uuid": "c-1", "name": "first", "project_uuid": U1},
            {"uuid": "c-2", "name": "second", "project_uuid": None}],
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        archive.write_project(project(U1, "Alpha"), "", self.root, {})

    def tearDown(self):
        self.tmp.cleanup()

    def run_harvest(self, browser):
        g = {"__name__": "__main__", "new_tab": browser.new_tab, "wait_for_load": browser.wait_for_load,
             "js": browser.js, "cdp": browser.cdp, "ensure_real_tab": browser.ensure_real_tab}
        with mock.patch.dict(os.environ, {"CLAUDE_AI_ARCHIVE": str(self.root)}), \
                mock.patch.object(time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            exec(compile(HARVEST.read_text(), str(HARVEST), "exec"), g)

    def test_opens_its_own_tab_and_closes_it(self):
        b = FakeBrowser(self.ROUTES)
        self.run_harvest(b)
        self.assertEqual(b.opened, ["https://claude.ai/recents"])
        self.assertEqual(b.closed, ["tab-1"])
        out = json.loads((self.root / "_phase2_mapping.json").read_text())
        self.assertEqual(out["mapping"][U1]["chats"], [{"uuid": "c-1", "title": "first"}])

    def test_closes_its_tab_when_a_fetch_fails(self):
        b = FakeBrowser({k: v for k, v in self.ROUTES.items() if "chat_conversations" not in k})
        with self.assertRaises(RuntimeError):
            self.run_harvest(b)
        self.assertEqual(b.closed, ["tab-1"])
        self.assertFalse((self.root / "_phase2_mapping.json").exists())

    def test_closes_its_tab_on_a_login_redirect(self):
        b = FakeBrowser(self.ROUTES, login_redirect=True)
        with self.assertRaises(SystemExit):
            self.run_harvest(b)
        self.assertEqual(b.closed, ["tab-1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
