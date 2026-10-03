"""Tests for relay.py.  Run from this folder:  python3 -B -m unittest discover -s tests

Each test copies tests/fixtures/relay into a temporary folder and works on the copy.
The six Guard classes each show one of the tool's promises being kept by watching it
refuse; tests/guard_mutations.py then switches each guard off in turn and confirms
its tests fail without it.
"""
import builtins
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(os.environ.get("RELAY_TOOL_DIR", HERE.parent))))
import relay  # noqa: E402

FIXTURE = HERE / "fixtures" / "relay"
TODAY = "2026-10-03"
TO_SITE = "2026-10-02-studio-to-site-a"
TO_STUDIO = "2026-10-02-site-to-studio-a"


class Case(unittest.TestCase):
    def setUp(self):
        os.environ["RELAY_TODAY"] = TODAY
        os.environ.pop("RELAY_DIR", None)
        self.tmp = Path(tempfile.mkdtemp(prefix="relay-test-"))
        self.r = self.tmp / "RELAY"
        shutil.copytree(FIXTURE, self.r)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = relay.main([str(a) for a in args])
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def snapshot(self):
        return {p.relative_to(self.r).as_posix(): p.read_bytes() for p in sorted(self.r.rglob("*")) if p.is_file()}

    def body(self, text="The weekly numbers are in.\n\n1. Read them."):
        p = self.tmp / f"body-{len(list(self.tmp.iterdir()))}.txt"
        p.write_text(text)
        return p

    def post(self, sender="ops", to="studio", *extra, done_when="studio has read the numbers", body=None):
        args = ["post", "--relay", self.r, "--from", sender, "--to", to, "--body", body or self.body()]
        if done_when is not None:
            args += ["--done-when", done_when]
        return self.run_tool(*args, *extra)

    def seen(self, mid):
        return relay.short_hash((self.r / "pending" / f"{mid}.md").read_bytes())

    def consume(self, mid, me, *extra, seen=None, receipt="done it"):
        return self.run_tool("consume", mid, "--relay", self.r, "--me", me,
                             "--seen", seen or self.seen(mid), "--receipt", receipt, *extra)

    def assertRefused(self, result, says):
        code, out, err = result
        self.assertEqual(code, 1, out + err)
        self.assertIn("refused:", err)
        self.assertIn(says, err)

    def check_ok(self):
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 0, out)


# ── the six guards ────────────────────────────────────────────────────────────

class Guard1NeverOverwrites(Case):
    def test_post_refuses_a_name_that_appears_while_writing(self):
        taken = self.r / "pending" / "2026-10-03-ops-to-studio-a.md"
        real = os.fsync

        def racing(fd):  # another chat claims the name while our temp file is being written
            taken.write_text("someone else's message\n")
            return real(fd)
        with mock.patch.object(os, "fsync", racing):
            self.assertRefused(self.post(), "appeared while writing")
        self.assertEqual(taken.read_text(), "someone else's message\n")

    def test_post_refuses_an_existing_name_before_writing_anything(self):
        with mock.patch.object(relay, "next_name", lambda *a: f"{TO_SITE}.md"):
            before = self.snapshot()
            self.assertRefused(self.post("studio", "ops"), "already exists")
        self.assertEqual(before, self.snapshot())   # not even a temp file

    def test_consume_refuses_a_name_already_in_a_done_month_folder(self):
        (self.r / "done" / "2026-10").mkdir()
        (self.r / "done" / "2026-10" / f"{TO_SITE}.md").write_text("an older copy\n")
        before = self.snapshot()
        self.assertRefused(self.consume(TO_SITE, "site"), "already exists in done/")
        self.assertEqual(before, self.snapshot())

    def test_consume_stops_if_done_gains_the_name_while_it_works(self):
        real = os.fsync
        clash = self.r / "done" / f"{TO_SITE}.md"

        def racing(fd):
            clash.write_text("another chat's copy\n")
            return real(fd)
        with mock.patch.object(os, "fsync", racing):
            self.assertRefused(self.consume(TO_SITE, "site"), "appeared in done/")
        self.assertEqual(clash.read_text(), "another chat's copy\n")
        self.assertTrue((self.r / "pending" / f"{TO_SITE}.md").read_text().rstrip().endswith("· done it"))

    def test_post_never_reuses_a_name_already_in_done(self):
        self.consume(TO_SITE, "site")
        os.environ["RELAY_TODAY"] = "2026-10-01"   # done/ already holds 2026-10-01-studio-to-site-a
        code, out, _ = self.post("studio", "site", body=self.body("Another note."))
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "2026-10-01-studio-to-site-b")

    def test_consume_refuses_when_done_already_has_the_name(self):
        (self.r / "done" / f"{TO_SITE}.md").write_text("an older copy\n")
        before = self.snapshot()
        self.assertRefused(self.consume(TO_SITE, "site"), "already exists in done/")
        self.assertEqual(before, self.snapshot())

    def test_add_only_touches_the_callers_own_message(self):
        self.post("ops", "studio")
        before = (self.r / "pending" / f"{TO_SITE}.md").read_bytes()
        code, _, _ = self.post("ops", "site", "--add")
        self.assertEqual(code, 1)          # ops has nothing pending for site; studio's message is not ops's to change
        self.assertEqual(before, (self.r / "pending" / f"{TO_SITE}.md").read_bytes())

    def test_a_file_whose_sender_disagrees_with_its_name_is_not_added_to(self):
        p = self.r / "pending" / f"{TO_STUDIO}.md"
        p.write_text(p.read_text().replace("from: site", "from: ops"))
        before = self.snapshot()
        self.assertRefused(self.post("site", "studio", "--add"), "malformed")
        self.assertEqual(before, self.snapshot())

    def test_only_the_action_recipient_consumes(self):
        before = self.snapshot()
        self.assertRefused(self.consume(TO_SITE, "ops"), "only on FYI")
        self.assertRefused(self.consume(TO_SITE, "studio"), "not its recipient")
        self.assertEqual(before, self.snapshot())


class Guard2NeverDeletes(Case):
    def test_no_command_deletes_anything(self):
        def forbidden(*a, **k):
            raise AssertionError("the tool tried to delete something")
        patches = [mock.patch.object(os, "unlink", forbidden), mock.patch.object(os, "remove", forbidden),
                   mock.patch.object(os, "rmdir", forbidden), mock.patch.object(shutil, "rmtree", forbidden),
                   mock.patch.object(Path, "unlink", forbidden), mock.patch.object(Path, "rmdir", forbidden)]
        for p in patches:
            p.start()
        try:
            self.assertEqual(self.post()[0], 0)
            self.assertEqual(self.post("ops", "studio", "--add")[0], 0)
            self.assertEqual(self.consume(TO_SITE, "site")[0], 0)
            self.assertEqual(self.consume(TO_STUDIO, "studio", seen="000000000000")[0], 1)
            with mock.patch.object(os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    self.post("site", "ops")
            self.run_tool("list", "--relay", self.r, "--me", "studio")
            self.run_tool("check", "--relay", self.r)
        finally:
            for p in patches:
                p.stop()

    def test_a_failed_write_leaves_its_temp_file_for_check_to_report(self):
        with mock.patch.object(os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.post()
        temps = [p.name for p in (self.r / "pending").iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(len(temps), 1)
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 1)
        self.assertIn("leftover temp file", out)


class Guard2PruneIsTheOnlyDelete(Case):
    """prune deletes consumed messages in done/ past the hold, for the owner only, and nothing else."""

    def setUp(self):
        super().setUp()
        os.environ["RELAY_TODAY"] = "2026-10-20"           # 14-day hold: receipts before 2026-10-06 go
        self.old = self.r / "done" / "2026-10-01-studio-to-site-a.md"          # receipt 2026-10-01
        month = self.r / "done" / "2026-09"
        month.mkdir()
        self.old_month = month / "2026-09-20-site-to-ops-a.md"
        self.old_month.write_text(self.msg("site", "ops", "2026-09-20") + "\nRECEIPT ops 2026-09-21 · read\n")
        self.recent = self.r / "done" / "2026-10-15-ops-to-studio-a.md"
        self.recent.write_text(self.msg("ops", "studio", "2026-10-15") + "\nRECEIPT studio 2026-10-15 · read\n")
        self.unreceipted = self.r / "done" / "2026-09-01-ops-to-site-a.md"
        self.unreceipted.write_text(self.msg("ops", "site", "2026-09-01"))
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nRECEIPT site 2026-10-01 · done, not yet moved\n")
        (self.r / "done" / "notes.txt").write_text("not a message\n")
        (self.r / "relay.py").write_text("# a copy of the tool\n")

    @staticmethod
    def msg(frm, to, date):
        return (f"---\nfrom: {frm}\nto: {to}\nfyi: []\nsent: {date}\nre: none\n"
                f'done_when: "read it"\n---\nA message.\n')

    def prune(self, me="studio", *extra):
        return self.run_tool("prune", "--relay", self.r, "--me", me, *extra)

    def test_prunes_only_consumed_messages_in_done_past_the_hold(self):
        before = self.snapshot()
        code, out, err = self.prune()
        self.assertEqual(code, 0, err)
        after = self.snapshot()
        gone = set(before) - set(after)
        self.assertEqual(gone, {"done/2026-10-01-studio-to-site-a.md", "done/2026-09/2026-09-20-site-to-ops-a.md"})
        self.assertEqual(set(after) - set(before), set())
        for name in after:
            self.assertEqual(after[name], before[name], name)
        self.assertIn("pruned 2 consumed message(s) with receipts before 2026-10-06", out)

    def test_the_hold_can_be_set(self):
        self.prune("studio", "--days", "30")   # cutoff 2026-09-20: only the 2026-09-20 one... receipt 09-21 is not before it
        self.assertTrue(self.old.exists())
        self.assertTrue(self.old_month.exists())
        self.assertRefused(self.prune("studio", "--days", "0"), "at least 1")

    def test_only_the_owner_prunes(self):
        before = self.snapshot()
        self.assertRefused(self.prune("site"), "only the folder's owner (studio)")
        readme = self.r / "README.md"
        readme.write_text(readme.read_text().replace("Owner: studio\n", ""))
        self.assertRefused(self.prune("studio"), "names no owner")
        readme.write_text(readme.read_text() + "\nOwner: site\nOwner: ops\n")
        self.assertRefused(self.prune("site"), "more than one owner")
        self.assertEqual({k: v for k, v in before.items() if k != "README.md"},
                         {k: v for k, v in self.snapshot().items() if k != "README.md"})

    def test_dry_run_deletes_nothing(self):
        before = self.snapshot()
        code, out, _ = self.prune("studio", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would prune done/2026-10-01-studio-to-site-a.md (receipt 2026-10-01)", out)
        self.assertEqual(before, self.snapshot())

    def test_a_malformed_message_in_done_stops_the_prune(self):
        self.recent.write_text(self.recent.read_text().replace("fyi: []", "fyi: ops"))
        before = self.snapshot()
        self.assertRefused(self.prune(), "malformed")
        self.assertEqual(before, self.snapshot())

    def test_blocked_deletes_stop_cleanly(self):
        before = self.snapshot()
        with mock.patch.object(os, "unlink", side_effect=PermissionError(1, "Operation not permitted")):
            code, out, err = self.prune()
        self.assertEqual(code, 1)
        self.assertIn("deleting isn't permitted in this folder", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(before, self.snapshot())

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_in_a_git_repository_only_committed_unchanged_files_go(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.tmp), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                           check=True, capture_output=True)
        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "relay")
        self.old_month.write_text(self.old_month.read_text().replace("A message.", "A message, edited."))
        late = self.r / "done" / "2026-10-02-site-to-studio-a.md"
        late.write_text(self.msg("site", "studio", "2026-10-02") + "\nRECEIPT studio 2026-10-02 · ok\n")
        code, out, err = self.prune()
        self.assertEqual(code, 0, err)
        self.assertFalse(self.old.exists())
        self.assertTrue(self.old_month.exists())
        self.assertTrue(late.exists())
        self.assertIn("kept done/2026-09/2026-09-20-site-to-ops-a.md: changed since it was committed", out)
        self.assertIn("kept done/2026-10-02-site-to-studio-a.md: not committed yet", out)
        self.assertFalse((self.tmp / ".git" / "index.lock").exists())

    def test_check_warns_when_no_owner_is_named(self):
        readme = self.r / "README.md"
        readme.write_text(readme.read_text().replace("Owner: studio\n", ""))
        _, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertIn("no 'Owner: <code>' line", out)
        readme.write_text(readme.read_text() + "\nOwner: legal\n")
        _, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertIn("owner 'legal' isn't in its sender list", out)


class Guard3ConsumeMovesOnlyOne(Case):
    def test_consume_moves_exactly_the_named_file(self):
        self.post("ops", "site", body=self.body("Third pending message."))
        before = self.snapshot()
        code, _, err = self.consume(TO_SITE, "site")
        self.assertEqual(code, 0, err)
        after = self.snapshot()
        moved_from, moved_to = f"pending/{TO_SITE}.md", f"done/{TO_SITE}.md"
        self.assertNotIn(moved_from, after)
        self.assertIn(moved_to, after)
        for name, data in before.items():
            if name != moved_from:
                self.assertEqual(after.get(name), data, f"{name} changed or vanished")
        self.assertEqual(set(after) - set(before), {moved_to})

    def test_consume_reports_if_pending_changes_under_it(self):
        real = relay.move_into_done

        def and_another(relay_path, src):
            dest = real(relay_path, src)
            (relay_path / "pending" / TO_STUDIO).with_suffix(".md").rename(relay_path / "done" / f"{TO_STUDIO}.md")
            return dest
        with mock.patch.object(relay, "move_into_done", and_another):
            self.assertRefused(self.consume(TO_SITE, "site"), "changed unexpectedly")


class Guard4TempThenRename(Case):
    def test_an_interrupted_write_never_shows_half_a_message(self):
        target = self.r / "pending" / f"{TO_SITE}.md"
        before = target.read_bytes()
        real_open = os.fdopen

        class HalfWriter:
            def __init__(self, fh):
                self.fh = fh

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.fh.close()

            def write(self, data):
                self.fh.write(data[: len(data) // 2])
                raise OSError("power cut")

            def __getattr__(self, name):
                return getattr(self.fh, name)

        with mock.patch.object(os, "fdopen", lambda fd, mode: HalfWriter(real_open(fd, mode))):
            with self.assertRaises(OSError):
                self.consume(TO_SITE, "site")
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse((self.r / "done" / f"{TO_SITE}.md").exists())
        with mock.patch.object(os, "fdopen", lambda fd, mode: HalfWriter(real_open(fd, mode))):
            with self.assertRaises(OSError):
                self.post()
        self.assertFalse((self.r / "pending" / "2026-10-03-ops-to-studio-a.md").exists())

    def test_writes_land_by_rename_from_a_dot_temp_in_the_same_folder(self):
        seen = []
        real = os.replace

        def spy(src, dst):
            seen.append((Path(src), Path(dst)))
            return real(src, dst)
        with mock.patch.object(os, "replace", spy):
            self.post()
            self.consume(TO_SITE, "site")
        self.assertEqual(len(seen), 2)
        for src, dst in seen:
            self.assertTrue(src.name.startswith(".") and src.name.endswith(".tmp"), src)
            self.assertEqual(src.parent, dst.parent)


class Guard5MalformedStops(Case):
    BAD = {
        "no closing rule": lambda t: t.replace("---\nPlease", "Please", 1),
        "unquoted colon": lambda t: t.replace('done_when: "the contact form shows the new privacy line: deployed and checked"',
                                              "done_when: the contact form shows the new privacy line: deployed and checked"),
        "fyi not a list": lambda t: t.replace("fyi: [ops]", "fyi: ops"),
        "unknown property": lambda t: t.replace("re: none", "re: none\npriority: high"),
        "missing property": lambda t: t.replace("sent: 2026-10-02\n", ""),
        "two-line value": lambda t: t.replace("re: none", "re: none\n  continued"),
        "bad receipt": lambda t: t + "\nRECEIPT site · done\n",
        "empty quoted value": lambda t: t.replace('done_when: "the contact form shows the new privacy line: deployed and checked"', 'done_when: ""'),
    }

    def test_consume_stops_on_each_kind_of_malformed_file(self):
        for label, breaker in self.BAD.items():
            with self.subTest(label):
                self.setUp()
                p = self.r / "pending" / f"{TO_SITE}.md"
                p.write_text(breaker(p.read_text()))
                before = self.snapshot()
                self.assertRefused(self.consume(TO_SITE, "site"), "malformed")
                self.assertEqual(before, self.snapshot())
                code, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site")
                self.assertEqual(code, 1)
                self.assertIn(f"STOP   {TO_SITE}.md", out)
                self.assertNotIn(f"ACTION {TO_SITE}", out)
                self.assertEqual(self.run_tool("check", "--relay", self.r)[0], 1)
                self.tearDown()

    def test_a_malformed_readme_stops_everything(self):
        readme = self.r / "README.md"
        readme.write_text(readme.read_text().replace("- site = ", "- Site Chat = "))
        self.assertRefused(self.post(), "doesn't start with a sender code")
        readme.write_text("no version here\n")
        self.assertRefused(self.run_tool("list", "--relay", self.r, "--me", "site"), "RELAY PROTOCOL")


class Guard6VersionMismatch(Case):
    def set_version(self, v):
        readme = self.r / "README.md"
        readme.write_text(readme.read_text().replace("v2.2", f"v{v}"))

    def test_minor_mismatch_is_flagged_by_check_and_list(self):
        self.set_version("2.3")
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 0)
        self.assertIn("warning README.md is protocol v2.3; this tool is written for v2.2", out)
        _, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site")
        self.assertIn("NOTE  README.md is protocol v2.3", out)
        self.assertEqual(self.post()[0], 0)   # same major version: writes still go ahead

    def test_major_mismatch_stops_writes(self):
        self.set_version("3.0")
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 1)
        self.assertIn("ERROR   README.md is protocol v3.0", out)
        before = self.snapshot()
        self.assertRefused(self.post(), "protocol v3.0")
        self.assertRefused(self.consume(TO_SITE, "site"), "protocol v3.0")
        self.assertEqual(before, self.snapshot())


# ── the commands ──────────────────────────────────────────────────────────────

class TestList(Case):
    def test_action_then_fyi_with_hashes(self):
        code, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site")
        self.assertEqual(code, 0)
        self.assertIn(f"ACTION {TO_SITE}  seen {self.seen(TO_SITE)}  from studio", out)
        self.assertIn("done when: the contact form shows the new privacy line: deployed and checked", out)
        _, out, _ = self.run_tool("list", "--relay", self.r, "--me", "ops")
        self.assertTrue(out.startswith(f"FYI    {TO_SITE}"))

    def test_full_prints_the_message(self):
        _, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site", "--full")
        self.assertIn("2. Deploy and check it.", out)

    def test_nothing_pending(self):
        self.consume(TO_STUDIO, "studio")
        _, out, _ = self.run_tool("list", "--relay", self.r, "--me", "studio")
        self.assertEqual(out.strip(), "nothing pending for studio")

    def test_flags_receipted_and_disagreeing_files(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nRECEIPT site 2026-10-03 · done\n")
        _, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site")
        self.assertIn("ALREADY RECEIPTED", out)
        q = self.r / "pending" / f"{TO_STUDIO}.md"
        q.write_text(q.read_text().replace("to: studio", "to: ops"))
        code, out, _ = self.run_tool("list", "--relay", self.r, "--me", "site")
        self.assertEqual(code, 1)
        self.assertIn("name says to 'studio' but the to property says 'ops'", out)

    def test_unknown_me(self):
        self.assertRefused(self.run_tool("list", "--relay", self.r, "--me", "nobody"), "isn't in README.md's sender list")


class TestPost(Case):
    def test_posts_a_new_message(self):
        code, out, _ = self.post("ops", "studio", "--fyi", "site", done_when="studio confirms: numbers read")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "2026-10-03-ops-to-studio-a")
        text = (self.r / "pending" / "2026-10-03-ops-to-studio-a.md").read_text()
        self.assertTrue(text.startswith('---\nfrom: ops\nto: studio\nfyi: [site]\nsent: 2026-10-03\nre: none\n'
                                        'done_when: "studio confirms: numbers read"\n---\nThe weekly numbers are in.'))
        self.check_ok()

    def test_second_message_to_the_same_recipient_points_to_add(self):
        self.post()
        self.assertRefused(self.post(), "Add to it with --add")
        code, out, _ = self.post("ops", "studio", "--add", "--fyi", "site", done_when=None, body=self.body("One more thing."))
        self.assertEqual(code, 0)
        text = (self.r / "pending" / "2026-10-03-ops-to-studio-a.md").read_text()
        self.assertIn("Read them.\n\nAdded 2026-10-03:\n\nOne more thing.\n", text)
        self.assertIn("fyi: [site]", text)
        self.check_ok()

    def test_add_with_nothing_pending(self):
        self.assertRefused(self.post("ops", "studio", "--add"), "post without --add")

    def test_a_receipted_message_no_longer_blocks_a_new_one(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nRECEIPT site 2026-10-03 · done\n")
        self.assertEqual(self.post("studio", "site")[0], 0)

    def test_refusals(self):
        before = self.snapshot()
        self.assertRefused(self.post("nobody", "studio"), "--from 'nobody'")
        self.assertRefused(self.post("ops", "nobody"), "--to 'nobody'")
        self.assertRefused(self.post("ops", "ops"), "the same code")
        self.assertRefused(self.post("ops", "studio", "--fyi", "x/y"), "isn't a sender code")
        self.assertRefused(self.post(done_when=None), "--done-when is required")
        self.assertRefused(self.post(done_when="two\nlines"), "one line")
        self.assertRefused(self.post(body=self.body("   \n")), "the body is empty")
        self.assertRefused(self.post(body=self.body("---\nfrom: x")), "can't start with '---'")
        self.assertRefused(self.post(body=self.body("ok\n\nRECEIPT ops 2026-10-03 · x")), "already consumed")
        self.assertRefused(self.post(body=self.tmp / "missing.txt"), "couldn't read --body")
        self.assertRefused(self.post("ops", "studio", "--re", "not-an-id"), "isn't a message ID")
        self.assertRefused(self.post("ops", "studio", "--re", "2026-01-01-ops-to-studio-a"), "matches no message")
        self.assertEqual(before, self.snapshot())

    def test_third_message_on_a_thread_goes_to_the_person(self):
        # done/...studio-to-site-a, then pending/...site-to-studio-a replies to it: a reply to that is the third
        self.consume(TO_SITE, "site")   # clears studio's other pending message to site, so rule 5 doesn't fire first
        self.assertRefused(self.post("studio", "site", "--re", TO_STUDIO), "Rule 4")
        self.assertEqual(self.post("studio", "site", "--re", TO_STUDIO, "--ruled")[0], 0)

    def test_a_second_reply_to_the_first_message_also_counts(self):
        self.consume(TO_SITE, "site")
        # the thread already holds studio-to-site-a and site's reply to it; another reply to the first is the third
        self.assertRefused(self.post("studio", "site", "--re", "2026-10-01-studio-to-site-a"), "message 3 on one thread")

    def test_add_with_re_names_the_message_and_still_counts_the_thread(self):
        self.consume(TO_SITE, "site")
        self.post("studio", "site", body=self.body("Unrelated note."))
        self.assertRefused(self.post("studio", "site", "--add", "--re", TO_STUDIO), "Rule 4")
        self.assertEqual(self.post("studio", "site", "--add", "--re", TO_STUDIO, "--ruled", done_when=None)[0], 0)
        self.assertIn(f"Added 2026-10-03, answering {TO_STUDIO}:", (self.r / "pending" / "2026-10-03-studio-to-site-a.md").read_text())

    def test_a_reply_added_with_add_counts_toward_its_thread(self):
        self.post("ops", "site", body=self.body("First message."), done_when="site replies")
        self.post("site", "ops", body=self.body("Unrelated."), done_when="ops reads it")
        self.assertEqual(self.post("site", "ops", "--add", "--re", "2026-10-03-ops-to-site-a", done_when=None)[0], 0)
        self.consume("2026-10-03-ops-to-site-a", "site")
        self.assertRefused(self.post("ops", "site", "--re", "2026-10-03-ops-to-site-a"), "message 3 on one thread")

    def test_done_when_survives_quotes_colons_and_backslashes(self):
        tricky = 'see "C:\\new\\folder": it\'s ready'
        self.assertEqual(self.post(done_when=tricky)[0], 0)
        m = relay.parse(self.r / "pending" / "2026-10-03-ops-to-studio-a.md")
        self.assertEqual(m.errors, [])
        self.assertEqual(m.props["done_when"], tricky)
        self.check_ok()

    def test_first_reply_is_allowed(self):
        self.assertEqual(self.post("site", "studio", "--re", TO_SITE, body=self.body("Done; see link."))[0], 1)  # batch rule
        self.consume(TO_STUDIO, "studio")
        self.assertEqual(self.post("site", "studio", "--re", TO_SITE)[0], 0)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        code, out, _ = self.post("ops", "studio", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("dry run: would write pending/2026-10-03-ops-to-studio-a.md", out)
        self.assertEqual(before, self.snapshot())
        self.post()
        before = self.snapshot()
        code, out, _ = self.post("ops", "studio", "--add", "--dry-run")
        self.assertIn("would rewrite", out)
        self.assertEqual(before, self.snapshot())

    def test_body_from_standard_input(self):
        with mock.patch.object(sys, "stdin", io.StringIO("From a pipe.\n")):
            self.assertEqual(self.post(body="-")[0], 0)


class TestConsume(Case):
    def test_receipt_then_move(self):
        code, out, err = self.consume(TO_SITE, "site", receipt="privacy line live; site README v1.4")
        self.assertEqual(code, 0, err)
        text = (self.r / "done" / f"{TO_SITE}.md").read_text()
        self.assertTrue(text.endswith("2. Deploy and check it.\n\nRECEIPT site 2026-10-03 · privacy line live; site README v1.4\n"))
        self.assertFalse((self.r / "pending" / f"{TO_SITE}.md").exists())
        self.check_ok()

    def test_already_receipted_is_only_moved(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nRECEIPT site 2026-10-02 · done yesterday\n")
        code, _, err = self.consume(TO_SITE, "site")
        self.assertEqual(code, 0)
        self.assertIn("moving it without adding another", err)
        self.assertEqual((self.r / "done" / f"{TO_SITE}.md").read_text().count("RECEIPT"), 1)

    def test_changed_since_read(self):
        old = self.seen(TO_SITE)
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nAdded 2026-10-03:\n\nAlso the footer.\n")
        self.assertRefused(self.consume(TO_SITE, "site", seen=old), "has changed since you read it")

    def test_not_pending(self):
        self.assertRefused(self.consume("2026-10-01-studio-to-site-a", "site", seen="x"), "it's in done/")
        self.assertRefused(self.consume("../README", "site", seen="x"), "isn't a message ID")

    def test_needs_a_one_line_receipt(self):
        self.assertRefused(self.consume(TO_SITE, "site", receipt="two\nlines"), "one line")

    def test_keeps_windows_line_endings(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(self.consume(TO_SITE, "site")[0], 0)
        data = (self.r / "done" / f"{TO_SITE}.md").read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))

    def test_keeps_permissions(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.chmod(0o644)
        self.consume(TO_SITE, "site")
        self.assertEqual((self.r / "done" / f"{TO_SITE}.md").stat().st_mode & 0o777, 0o644)

    def test_dry_run_writes_nothing(self):
        before = self.snapshot()
        code, out, _ = self.consume(TO_SITE, "site", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("RECEIPT site 2026-10-03 · done it", out)
        self.assertEqual(before, self.snapshot())


class TestCheck(Case):
    def test_clean(self):
        self.check_ok()

    def expect(self, says):
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 1, out)
        self.assertIn(says, out)

    def test_missing_keep(self):
        (self.r / "pending" / ".keep").rename(self.tmp / "keep")
        self.expect("pending/.keep is missing")

    def test_stray_files(self):
        (self.r / "pending" / "notes.md").write_text("x")
        self.expect("pending/notes.md doesn't belong here")

    def test_month_folders_are_allowed_and_checked(self):
        (self.r / "done" / "2026-09").mkdir()
        (self.r / "done" / "2026-10-01-studio-to-site-a.md").rename(self.r / "done" / "2026-09" / "2026-10-01-studio-to-site-a.md")
        self.check_ok()
        (self.r / "done" / "2026-09" / "stray.txt").write_text("x")
        self.expect("done/2026-09/stray.txt doesn't belong here")

    def test_done_without_receipt(self):
        p = self.r / "done" / "2026-10-01-studio-to-site-a.md"
        p.write_text(p.read_text().split("\nRECEIPT")[0] + "\n")
        self.expect("is in done/ without a receipt")

    def test_two_pending_from_one_sender_to_one_recipient(self):
        src = self.r / "pending" / f"{TO_SITE}.md"
        (self.r / "pending" / "2026-10-02-studio-to-site-b.md").write_text(src.read_text())
        self.expect("rule 5 allows one")

    def test_same_name_in_pending_and_done(self):
        src = self.r / "done" / "2026-10-01-studio-to-site-a.md"
        (self.r / "pending" / src.name).write_text(src.read_text())
        self.expect("exists twice")

    def test_unknown_codes(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text().replace("fyi: [ops]", "fyi: [legal]"))
        self.expect("fyi 'legal' isn't in README.md's sender list")

    def test_receipt_by_someone_else(self):
        p = self.r / "done" / "2026-10-01-studio-to-site-a.md"
        p.write_text(p.read_text().replace("RECEIPT site", "RECEIPT ops"))
        self.expect("the receipt is by 'ops'")

    def test_mac_ds_store_is_ignored_and_a_folder_named_like_a_message_is_reported(self):
        (self.r / "pending" / ".DS_Store").write_bytes(b"\x00")
        self.check_ok()
        (self.r / "pending" / "2026-10-02-ops-to-site-a.md").mkdir()
        self.expect("pending/2026-10-02-ops-to-site-a.md doesn't belong here")

    def test_symlink(self):
        (self.r / "pending" / "2026-10-02-ops-to-site-a.md").symlink_to(self.r / "pending" / f"{TO_SITE}.md")
        self.expect("is a symbolic link")


class TestInstallPlan(Case):
    """The skill carries relay.py and installs it into the folder: owner only, never downgrading."""

    def plan(self, me, copy_version=None, *extra):
        args = ["install-plan", "--me", me, "--readme", self.r / "README.md", *extra]
        if copy_version:
            copy = self.tmp / "folder-relay.py"
            copy.write_text(f'#!/usr/bin/env python3\nTOOL_VERSION = "{copy_version}"\nPROTOCOL_VERSION = "2.1"\n')
            args += ["--folder-copy", copy]
        code, out, err = self.run_tool(*args)
        self.assertEqual(code, 0, err)
        return out.strip()

    def test_same_machine_runs_the_bundled_copy_directly(self):
        self.assertFalse((self.r / "relay.py").exists())
        out = self.run_tool("install-plan", "--me", "site", "--relay", self.r)[1]
        self.assertTrue(out.startswith("LOCAL:"), out)
        self.check_ok()                                    # no copy in the folder is needed

    def test_older_copy_and_owner_installs(self):
        out = self.plan("studio", "1.1")
        self.assertTrue(out.startswith(f"INSTALL 1.1 -> {relay.TOOL_VERSION}:"), out)
        self.assertEqual(out.splitlines()[-1],
                         f"EXPECT relay.py {relay.TOOL_VERSION} (protocol v{relay.PROTOCOL_VERSION}) sha256 {relay.self_hash()}")

    def test_missing_copy_and_owner_installs(self):
        self.assertTrue(self.plan("studio").startswith(f"INSTALL none -> {relay.TOOL_VERSION}:"))

    def test_newer_copy_is_never_replaced(self):
        for me in ("studio", "site"):
            out = self.plan(me, "9.0")
            self.assertTrue(out.startswith("NEWER: relay.py here is 9.0"), out)

    def test_identical_copy_is_current(self):
        copy = self.tmp / "identical.py"
        copy.write_bytes(Path(relay.__file__).read_bytes())
        out = self.run_tool("install-plan", "--me", "site", "--readme", self.r / "README.md", "--folder-copy", copy)[1]
        self.assertTrue(out.startswith("CURRENT"), out)

    def test_same_version_with_different_contents_is_replaced_by_the_owner_only(self):
        self.assertTrue(self.plan("studio", relay.TOOL_VERSION).startswith(
            f"INSTALL {relay.TOOL_VERSION} (different contents) -> {relay.TOOL_VERSION}:"))
        self.assertTrue(self.plan("site", relay.TOOL_VERSION).startswith("WAIT"))

    def test_non_owner_waits_for_the_owner(self):
        self.assertEqual(self.plan("site", "1.1").splitlines()[0],
                         f"WAIT: relay.py here is 1.1; the owner's next pass updates it to {relay.TOOL_VERSION}. "
                         f"Carry on with the folder's copy.")

    def test_non_owner_and_missing_copy(self):
        self.assertTrue(self.plan("site").startswith("MISSING:"))

    def test_unreadable_version_is_left_alone(self):
        copy = self.tmp / "odd.py"
        copy.write_text("print('hello')\n")
        self.assertRefused(self.run_tool("install-plan", "--me", "studio", "--readme", self.r / "README.md",
                                         "--folder-copy", copy), "can't tell which version")

    def test_version_reports_its_own_hash(self):
        out = self.run_tool("--version")[1]
        self.assertEqual(out.strip(), f"relay.py {relay.TOOL_VERSION} (protocol v{relay.PROTOCOL_VERSION}) sha256 {relay.self_hash()}")


class TestWho(Case):
    def test_owner_senders_and_pending(self):
        before = self.snapshot()
        code, out, _ = self.run_tool("who", "--relay", self.r, "--me", "site")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[:6], [
            "Owner: studio",
            "Time zone: America/New_York",
            "Senders:",
            "  studio (the studio chat): sending 1 (oldest 2026-10-02); receiving 1 (oldest 2026-10-02)",
            "  site (the website build chat): sending 1 (oldest 2026-10-02); receiving 1 (oldest 2026-10-02)  <- you",
            "  ops (the operations chat): sending none; receiving none",
        ])
        self.assertIn("Pending: 2026-10-02-studio-to-site-a (from studio to site, since 2026-10-02)", out)
        self.assertEqual(before, self.snapshot())          # read-only

    def test_one_line_sender_list_has_no_descriptions(self):
        readme = self.r / "README.md"
        text = readme.read_text().replace("- studio = the studio chat\n- site = the website build chat\n- ops = the operations chat\n", "")
        readme.write_text(text.replace("Senders and codes:\n", "Senders and codes: studio, site, ops\n"))
        out = self.run_tool("who", "--relay", self.r)[1]
        self.assertIn("  ops (no description): sending none; receiving none", out)
        readme.write_text(readme.read_text().replace("Senders and codes: studio, site, ops", "Senders and codes: studio (the studio chat), site, ops"))
        self.assertIn("  studio (the studio chat): sending", self.run_tool("who", "--relay", self.r)[1])
        self.assertNotIn("<- you", out)

    def test_unknown_me(self):
        self.assertRefused(self.run_tool("who", "--relay", self.r, "--me", "nobody"), "isn't in README.md's sender list")

    def test_a_receipted_message_is_not_counted_as_waiting(self):
        p = self.r / "pending" / f"{TO_SITE}.md"
        p.write_text(p.read_text() + "\nRECEIPT site 2026-10-03 · done\n")
        out = self.run_tool("who", "--relay", self.r)[1]
        self.assertIn("  site (the website build chat): sending 1 (oldest 2026-10-02); receiving none", out)
        self.assertIn(f"Receipted, not yet moved: {TO_SITE} (site's next pass moves it to done/)", out)
        self.assertNotIn(f"Pending: {TO_SITE}", out)


class TestInit(Case):
    SENDERS = "studio=the studio chat; site=the website build chat"

    def init(self, folder, *extra, owner="studio", senders=None):
        return self.run_tool("init", "--relay", folder, "--owner", owner, "--senders", senders or self.SENDERS, *extra)

    def test_sets_up_a_working_relay(self):
        new = self.tmp / "NEW"
        code, out, err = self.init(new)
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(p.relative_to(new).as_posix() for p in new.rglob("*")),
                         ["README.md", "done", "done/.keep", "pending", "pending/.keep"])
        text = (new / "README.md").read_text()
        self.assertTrue(text.startswith(f"# RELAY\n\nRELAY PROTOCOL v{relay.PROTOCOL_VERSION} · {TODAY}\n\nOwner: studio\n\n"
                                        "Time zone: America/New_York\n\n"
                                        "Senders and codes:\n- studio = the studio chat\n- site = the website build chat\n"))
        self.assertIn("## Getting to done", text)
        self.assertTrue(text.rstrip().endswith("with a script of their own."))
        self.assertNotIn("00-System", text)
        self.assertEqual(self.run_tool("check", "--relay", new)[0], 0)
        self.r = new
        self.assertEqual(self.post("site", "studio", done_when="studio reads it")[0], 0)
        self.assertEqual(self.consume("2026-10-03-site-to-studio-a", "studio")[0], 0)

    def test_refuses_a_folder_that_already_has_a_relay(self):
        for part in ("README.md", "pending", "done"):
            with self.subTest(part):
                folder = self.tmp / f"has-{part}"
                folder.mkdir()
                (folder / part).mkdir() if part != "README.md" else (folder / part).write_text("mine\n")
                before = sorted(p.name for p in folder.rglob("*"))
                self.assertRefused(self.init(folder), "init only sets up a folder with no relay yet")
                self.assertEqual(before, sorted(p.name for p in folder.rglob("*")))
        self.assertRefused(self.init(self.r), "already has README.md, pending, done")

    def test_refusals(self):
        new = self.tmp / "NEW"
        self.assertRefused(self.init(new, owner="ops"), "must be one of the senders")
        self.assertRefused(self.init(new, senders="studio"), "isn't 'code=description'")
        self.assertRefused(self.init(new, senders="Studio=x"), "isn't lower-case")
        self.assertRefused(self.init(new, senders="studio=x; studio=y"), "listed twice")
        self.assertRefused(self.init(new, senders="studio= "), "one-line description")
        self.assertRefused(self.init(self.tmp / "no" / "such"), "doesn't exist")
        self.assertFalse(new.exists())

    def test_time_zone(self):
        new = self.tmp / "NEW"
        self.assertRefused(self.init(new, "--time-zone", "Mars/Olympus"), "no time-zone data")
        self.assertFalse(new.exists())
        self.assertEqual(self.init(new, "--time-zone", "Europe/London")[0], 0)
        self.assertIn("\nTime zone: Europe/London\n", (new / "README.md").read_text())
        self.assertEqual(relay.read_readme(new).tz, "Europe/London")

    def test_dry_run(self):
        new = self.tmp / "NEW"
        code, out, _ = self.init(new, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Owner: studio", out)
        self.assertFalse(new.exists())


class TestTimeZone(Case):
    def test_dates_follow_the_zone(self):
        late = relay.dt.datetime(2026, 10, 4, 2, 30, tzinfo=relay.dt.timezone.utc)
        self.assertEqual(relay.today("America/New_York", late), "2026-10-03")
        self.assertEqual(relay.today("Asia/Tokyo", late), "2026-10-04")

    def test_readme_zone_is_used_and_defaults_to_new_york(self):
        self.assertEqual(relay.read_readme(self.r).tz, "America/New_York")
        readme = self.r / "README.md"
        readme.write_text(readme.read_text().replace("Owner: studio\n", "Owner: studio\n\nTime zone: Asia/Tokyo\n"))
        seen = []
        real = relay.today
        with mock.patch.object(relay, "today", lambda tz=relay.TZ, now=None: seen.append(tz) or real(tz, now)):
            self.post()
            self.consume(TO_SITE, "site")
        self.assertEqual(seen, ["Asia/Tokyo", "Asia/Tokyo"])

    def test_bad_or_doubled_zone(self):
        readme = self.r / "README.md"
        text = readme.read_text()
        readme.write_text(text.replace("Owner: studio\n", "Owner: studio\nTime zone: Mars/Olympus\n"))
        self.assertRefused(self.post(), "no time-zone data for 'Mars/Olympus'")
        code, out, _ = self.run_tool("check", "--relay", self.r)
        self.assertEqual(code, 1)
        self.assertIn("no time-zone data", out)
        readme.write_text(text.replace("Owner: studio\n", "Owner: studio\nTime zone: Europe/Paris\nTime zone: Asia/Tokyo\n"))
        self.assertRefused(self.post(), "more than one time zone")


class TestEdges(Case):
    def test_usage_errors_exit_two(self):
        self.assertEqual(self.run_tool()[0], 2)
        self.assertEqual(self.run_tool("consume", "--relay", self.r)[0], 2)

    def test_not_a_relay_folder(self):
        self.assertRefused(self.run_tool("check", "--relay", self.tmp), "isn't a RELAY folder")

    def test_relay_dir_from_environment(self):
        os.environ["RELAY_DIR"] = str(self.r)
        self.assertEqual(self.run_tool("check")[0], 0)

    def test_bad_today(self):
        os.environ["RELAY_TODAY"] = "soon"
        self.assertRefused(self.post(), "RELAY_TODAY")

    def test_letters_roll_past_z(self):
        self.assertEqual(relay.n_to_letters(27), "aa")
        self.assertEqual(relay.letters_to_n("aa"), 27)


if __name__ == "__main__":
    unittest.main()
