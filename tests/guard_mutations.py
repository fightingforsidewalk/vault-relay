"""Switch each of relay.py's guards and build.py's upload checks off in turn and confirm its tests fail.

    python3 -B tests/guard_mutations.py

A guard test that still passes with its guard removed proves nothing, so this
copies relay.py (or packaging/build.py) to a temporary folder, breaks one guard
in the copy, and runs that guard's test class against the broken copy. Every
line should read 'caught'. Neither file is ever changed.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parent / "relay.py").read_text(encoding="utf-8")
BUILD_SOURCE = (HERE.parent / "packaging" / "build.py").read_text(encoding="utf-8")

MUTATIONS = {
    "Guard1NeverOverwrites": [
        ("    if target.exists() and not may_replace:", "    if False:"),
        ("    if not may_replace and target.exists():", "    if False:"),
        ("    if taken_in_done(relay, path):", "    if False:"),
        ("    if taken_in_done(relay, src):", "    if False:"),
        ('    if msg.props["to"] != me:', "    if False:"),
        ("    _agree(msg)\n    return msg", "    return msg"),
        ("    used = [NAME_RE", "    used = [] and [NAME_RE"),
    ],
    "Guard2NeverDeletes": [
        ("    os.rename(src, dest)", "    dest.write_bytes(src.read_bytes())\n    os.unlink(src)"),
    ],
    "Guard2PruneIsTheOnlyDelete": [
        ("    if me != readme.owner:", "    if False:"),
        ('    if readme.owner is None:\n        raise Refused("README.md names no owner',
         '    if False:\n        raise Refused("README.md names no owner'),
        ("            if m.receipt and m.receipt[1] < cutoff:", "            if m.receipt:"),
        ("    folders = [done] + sorted(", '    folders = [done, relay / "pending"] + sorted('),
        ('            if m.errors:\n                raise Refused(f"done/', '            if False:\n                raise Refused(f"done/'),
        ("    if status is not None:\n        for p, _ in list(candidates):", "    if False:\n        for p, _ in list(candidates):"),
        ("        except PermissionError:", "        except ZeroDivisionError:"),
        ("    if a.dry_run:\n        for p, d in candidates:", "    if False:\n        for p, d in candidates:"),
        ("    if a.days < 1:", "    if False:"),
    ],
    "TestInstallPlan": [
        ("    elif theirs is not None and theirs > mine:", "    elif False:"),
        ("    elif owner:", "    elif True:"),
        ("    same_bytes = theirs == mine and short_hash(theirs_bytes) == self_hash()", "    same_bytes = theirs == mine"),
    ],
    "TestInit": [
        ('    taken = [n for n in ("README.md", "pending", "done")', '    taken = [] and [n for n in ("README.md", "pending", "done")'),
        ("    if owner not in [c for c, _ in senders]:", "    if False:"),
    ],
    "Guard3ConsumeMovesOnlyOne": [
        ("    move_into_done(relay, path)\n",
         "    move_into_done(relay, path)\n    [move_into_done(relay, q) for q in sorted((relay / 'pending').glob('*.md'))[:1]]\n"),
        ("    if after != before - {path.name}:", "    if False:"),
    ],
    "Guard4TempThenRename": [
        ('        tmp = target.parent / f".{target.name}.{os.getpid()}.{n}.tmp"', "        tmp = target"),
        ("os.O_WRONLY | os.O_CREAT | os.O_EXCL", "os.O_WRONLY | os.O_CREAT | os.O_TRUNC"),
    ],
    "Guard5MalformedStops": [
        ("    _agree(msg)\n    return msg", "    _agree(msg)\n    msg.errors.clear()\n    return msg"),
    ],
    "Guard6VersionMismatch": [
        ("    if readme.version_text != PROTOCOL_VERSION:", "    if False:"),
    ],
}

# build.py refuses to pack what claude.ai's plugin upload would reject.
BUILD_MUTATIONS = {
    "PluginPackaging": [
        ('        if "<" in d or ">" in d:', "        if False:"),
        ("        if len(d) > 1024:", "        if False:"),
        ("        if not manifest.get(key):", "        if False:"),
    ],
}

# Guard 1 has several independent checks; each is broken on its own so every one is seen to matter.
SPLIT = {"Guard1NeverOverwrites": True, "Guard2PruneIsTheOnlyDelete": True, "TestInstallPlan": True, "TestInit": True,
         "PluginPackaging": True}

# Which file a set of mutations breaks, and the variable the tests read to load the broken copy.
TARGETS = {"relay.py": (SOURCE, "RELAY_TOOL_DIR"), "build.py": (BUILD_SOURCE, "BUILD_TOOL_DIR")}


def run(guard: str, edits, target: str = "relay.py") -> int:
    src, variable = TARGETS[target]
    for old, new in edits:
        if src.count(old) != 1:
            print(f"  cannot apply mutation for {guard}: {old.strip()[:50]!r} found {src.count(old)} times")
            return 2
        src = src.replace(old, new)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / target).write_text(src, encoding="utf-8")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **{variable: d})
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", f"test_relay.{guard}"],
                           cwd=HERE, env=env, capture_output=True, text=True)
    return r.returncode


def main() -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    base = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_relay"], cwd=HERE, env=env,
                          capture_output=True, text=True)
    if base.returncode:
        print("the unmodified tool fails its own tests; fix that first")
        return 1
    missed = 0
    jobs = [(g, e, "relay.py") for g, e in MUTATIONS.items()] + [(g, e, "build.py") for g, e in BUILD_MUTATIONS.items()]
    for guard, edits, target in jobs:
        groups = [[e] for e in edits] if SPLIT.get(guard) else [edits]
        for group in groups:
            code = run(guard, group, target)
            what = group[0][0].strip().splitlines()[0][:60]
            if code == 1:
                print(f"caught   {guard}: switched off '{what}'")
            else:
                missed += 1
                print(f"MISSED   {guard}: switched off '{what}' and its tests still pass")
    print("every guard is seen to fail without its check" if not missed else f"{missed} mutation(s) not caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
