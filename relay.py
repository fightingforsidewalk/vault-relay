#!/usr/bin/env python3
"""relay.py: plain-file mail for AI chats that share a folder.

A relay folder holds README.md (the rules, a protocol version, a sender list and the
folder's owner),
pending/ (one file per unread message) and done/ (consumed messages, each ending
in its receipt). A message's file name is its ID: date-sender-to-recipient-letter.md.

    relay.py list    --me CODE [--full]
    relay.py post    --from CODE --to CODE --done-when TEXT --body FILE [--fyi CODE]... [--re ID] [--add]
    relay.py consume ID --me CODE --seen HASH --receipt TEXT
    relay.py check
    relay.py prune   --me CODE [--days 14]
    relay.py install-plan --me CODE (--relay PATH | --readme FILE [--folder-copy FILE])
    relay.py who     [--me CODE]
    relay.py init    --relay PATH --owner CODE --senders "code=description; ..."

Every command takes --relay PATH (default: $RELAY_DIR, else the folder this file
sits in). post, consume and prune take --dry-run, which shows what would happen
and changes nothing.

What it will never do: overwrite a name that already exists or a file the caller
doesn't own, guess at a file it can't read, or delete anything, with one
exception: prune, run by the folder's owner, deletes consumed messages from done/
once they are past the hold (and, in a git repository, only once they are
committed unchanged, so a copy stays in history). Every write goes
to a dot-named temporary file and is renamed into place, so nobody ever reads
half a message. Standard library only; no network.

Exit status: 0 done, 1 refused or problems found, 2 bad arguments.
"""

import argparse
import datetime as dt
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TOOL_VERSION = "1.3"
PROTOCOL_VERSION = "2.2"
HOLD_DAYS = 14
TZ = "America/New_York"

CODE = r"[a-z0-9]+"
DATE = r"\d{4}-\d{2}-\d{2}"
NAME_RE = re.compile(rf"(?P<date>{DATE})-(?P<from>{CODE})-to-(?P<to>{CODE})-(?P<letter>[a-z]+)\.md")
ID_RE = re.compile(rf"{DATE}-{CODE}-to-{CODE}-[a-z]+")
CODE_RE = re.compile(CODE)
MONTH_RE = re.compile(r"\d{4}-\d{2}")
PROP_RE = re.compile(r"([a-z_]+):(?: (.*))?")
FYI_RE = re.compile(rf"\[\s*(?:{CODE}(?:\s*,\s*{CODE})*)?\s*\]")
RECEIPT_RE = re.compile(rf"RECEIPT ({CODE}) ({DATE}) · (\S.*)")
VERSION_RE = re.compile(r"RELAY PROTOCOL v(\d+)\.(\d+)")
TZ_RE = re.compile(r"\s*(?:[-*]\s+)?(?:\*\*)?Time zone:(?:\*\*)?\s*`?([A-Za-z][A-Za-z0-9_+\-]*(?:/[A-Za-z0-9_+\-]+)*)`?\s*\.?\s*")
OWNER_RE = re.compile(rf"\s*(?:[-*]\s+)?(?:\*\*)?Owner:(?:\*\*)?\s*`?({CODE})`?\s*\.?\s*")
KEYS = ["from", "to", "fyi", "sent", "re", "done_when"]


class Refused(Exception):
    """The tool declined to act. The message says why, in words a person can act on."""


# ── the protocol text init writes into README.md ──────────────────────────────
# Copied from the relay protocol standard (protocol v2.2): "Getting to done" through
# rule 18. Replace it whole when the protocol changes; never edit it here by hand.
PROTOCOL_RULES = """## Getting to done (these come first)

"The person" below is whoever runs the chats and decides when they check the relay.

1. Every message aims at completion. It says what done looks like and carries everything the recipient needs to finish in one pass, with any decisions asked as a short numbered list.

2. The receipt is the only acknowledgement. No thank-you, "received", "noted" or status-only messages.

3. Reply only when the message asks for something back, or when the answer changes what the sender will do. FYI never prompts a reply.

4. One round trip, then the person. If a thread has not closed after one message and one reply, the next word goes to the person, in the chat's reply to them, as a decision with options, not back to the other chat. Two chats never trade more than two messages on one thread without the person ruling. The tool enforces this: it refuses a third message on one thread, and its override is used only after the person has ruled.

5. Batch. A sender has at most one message pending for any one recipient; anything new for a recipient who has not yet consumed your last message is added to that message, not sent separately. Beyond that, at most one new message per recipient per session, unless something is live (security, cost, a deadline that day).

6. When the person says "relay for you" (or invokes /vault-relay), the chat ends that turn with every message addressed to it as ACTION consumed, or with one note to the person, in its reply, naming what blocks it.

## How it works

7. Every message is its own file: unread in the RELAY folder's `pending/`, consumed in its `done/`. Nothing else goes in either folder. Each holds an empty `.keep` so it survives when empty.

8. The file name is the message ID: date, sender, "to", recipient, letter, as in `2026-10-03-planner-to-builder-a.md`. Exactly one ACTION recipient, the one in the name; FYI recipients are listed inside. Take the next free letter; never reuse a name that exists anywhere under `RELAY/`.

9. A message opens with properties (from, to, fyi, sent, re, done_when), then the body in plain prose, with asks of the recipient as a short numbered list at the end. Property values stay on one line; quote any that contain a colon.

10. To send, write the whole file under a temporary name starting with a dot in `pending/`, then rename it to its real name, so nobody ever reads half a message. Adding to your own pending message (rule 5) is done the same way, whole file. Never overwrite a file that is not yours.

11. To consume (ACTION recipient only): first do or decide what the message asks and record the outcome in your own documents. Read the file again; if the sender has added to it since, deal with the addition first. Then add your receipt as the last line, after a blank line, written the same way as rule 10, and move the file into `done/`. A file in `pending/` that already ends in a receipt is finished by moving it. Never delete a message and never half-consume: if you cannot finish, leave it in `pending/` and tell the person what blocks you (rule 4).

12. FYI recipients read and never edit or move a message. Once consumed it is in `done/`, so a sender who needs an FYI reader to keep something sends that reader its own message.

13. Replies, when rule 3 allows one, are new messages with re set to the ID they answer. Nobody edits a message they did not send, except the ACTION recipient adding its receipt.

14. Never in a message: secrets, credentials, keys or recovery codes; personal data; anything from another venture's vault. A chat from outside the vault carries only what is meant for that vault.

15. A chat whose own work lives outside the vault reaches the folder through a connection the person makes to that folder alone, reads only the RELAY folder, writes only its own messages and its receipts, and keeps its own record in its own vault.

16. Dates are in the time zone the README names (America/New_York if it names none).

17. One chat owns each vault's RELAY folder: its `README.md`, which carries this protocol verbatim with a sender list. A protocol change is one edit to that README; message files carry no protocol text. A new sender needs only a line in the sender list. `done/` is a short hold, not an archive: what a message decided lives in the documents of the chat that acted on it (rule 11) and in the vault's history. The owner prunes consumed messages older than 14 days with the tool; nothing else is ever deleted.

18. Every relay edit goes through the relay tool via the vault-relay plugin: its bundled copy where the chat runs on the same machine as the folder, otherwise the copy of `relay.py` in the RELAY folder, which the owner keeps current. A chat that cannot run it tells the person and stops; nobody edits, moves or creates a relay file by hand or with a script of their own.
"""


# ── dates and hashes ──────────────────────────────────────────────────────────

def zone(name: str):
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        raise Refused("relay.py needs Python 3.9 or later for time zones")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise Refused(f"no time-zone data for {name!r}: check the README's 'Time zone:' line is an IANA name "
                      f"such as America/New_York (on Windows, also run: pip install tzdata)")


def today(tz: str = TZ, now: Optional[dt.datetime] = None) -> str:
    """The date in the relay's time zone (the README's 'Time zone:' line, default America/New_York)."""
    where = zone(tz)  # a bad time-zone name is refused even when the date is fixed for tests
    fixed = os.environ.get("RELAY_TODAY")
    if fixed and now is None:
        try:
            return dt.date.fromisoformat(fixed).isoformat()
        except ValueError:
            raise Refused(f"RELAY_TODAY is {fixed!r}, not a YYYY-MM-DD date")
    moment = now or dt.datetime.now(dt.timezone.utc)
    return moment.astimezone(where).date().isoformat()


def short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


# ── the README ────────────────────────────────────────────────────────────────

@dataclass
class Readme:
    version: Tuple[int, int]
    senders: List[str]
    owner: Optional[str] = None
    descriptions: Dict[str, str] = field(default_factory=dict)
    tz: str = TZ

    @property
    def version_text(self) -> str:
        return f"{self.version[0]}.{self.version[1]}"


def read_readme(relay: Path, path: Optional[Path] = None) -> Readme:
    path = path or relay / "README.md"
    if not path.is_file() or path.is_symlink():
        raise Refused(f"no README.md at {path}; is this the RELAY folder?")
    lines = path.read_text(encoding="utf-8").splitlines()
    version = None
    for line in lines:
        m = VERSION_RE.search(line)
        if m:
            version = (int(m.group(1)), int(m.group(2)))
            break
    if version is None:
        raise Refused("README.md has no 'RELAY PROTOCOL v<major>.<minor>' line")
    start = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("senders and codes:")), None)
    if start is None:
        raise Refused("README.md has no 'Senders and codes:' line")
    entries: List[str] = []
    rest = lines[start].split(":", 1)[1].strip()
    if rest:
        entries = [e for e in rest.split(",")]
    else:  # one sender per list line below the heading
        for line in lines[start + 1:]:
            s = line.strip()
            if not s:
                if entries:
                    break
                continue
            if not s.startswith(("- ", "* ")):
                break
            entries.append(s[2:])
    senders = []
    descriptions: Dict[str, str] = {}
    for e in entries:
        m = re.match(rf"\s*`?({CODE})`?\s*(?:$|[=:(]|\s[-=:(])", e)
        if not m:
            raise Refused(f"README.md sender entry {e.strip()!r} doesn't start with a sender code (lower-case letters and digits)")
        senders.append(m.group(1))
        desc = e[m.end(1):].strip().lstrip("`").strip().lstrip("=:-").strip()
        if desc.startswith("(") and desc.endswith(")"):
            desc = desc[1:-1].strip()
        descriptions[m.group(1)] = desc
    if not senders:
        raise Refused("README.md's sender list is empty")
    owners = {m.group(1) for m in (OWNER_RE.fullmatch(l) for l in lines) if m}
    if len(owners) > 1:
        raise Refused(f"README.md names more than one owner ({', '.join(sorted(owners))})")
    owner = owners.pop() if owners else None
    if owner and owner not in senders:
        raise Refused(f"README.md's owner {owner!r} isn't in its sender list")
    zones = {m.group(1) for m in (TZ_RE.fullmatch(l) for l in lines) if m}
    if len(zones) > 1:
        raise Refused(f"README.md names more than one time zone ({', '.join(sorted(zones))})")
    return Readme(version, senders, owner, descriptions, zones.pop() if zones else TZ)


def version_note(readme: Readme) -> Optional[str]:
    if readme.version_text != PROTOCOL_VERSION:
        return (f"README.md is protocol v{readme.version_text}; this tool is written for v{PROTOCOL_VERSION}. "
                f"Check with the person running the relay before relying on it.")
    return None


# ── message files ─────────────────────────────────────────────────────────────

@dataclass
class Message:
    path: Path
    raw: bytes
    props: Dict[str, object] = field(default_factory=dict)
    body: List[str] = field(default_factory=list)
    receipt: Optional[Tuple[str, str, str]] = None
    errors: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.path.name[:-3]

    @property
    def hash(self) -> str:
        return short_hash(self.raw)

    @property
    def name_parts(self) -> Dict[str, str]:
        m = NAME_RE.fullmatch(self.path.name)
        return m.groupdict() if m else {}


def _value(key: str, raw: Optional[str]) -> object:
    v = (raw or "").strip()
    if key == "fyi":
        if not FYI_RE.fullmatch(v):
            raise ValueError("fyi must be a bracketed list of codes, such as [ops] or []")
        return [c.strip() for c in v[1:-1].split(",") if c.strip()]
    if not v:
        raise ValueError(f"{key} is empty")
    if v.startswith('"'):
        if len(v) < 2 or not v.endswith('"'):
            raise ValueError(f"{key} has an unbalanced double-quoted value")
        out, inner, i = [], v[1:-1], 0
        while i < len(inner):
            ch = inner[i]
            if ch == "\\":
                if i + 1 >= len(inner) or inner[i + 1] not in '"\\':
                    raise ValueError(f"{key} has a backslash escape other than \\\" or \\\\")
                out.append(inner[i + 1])
                i += 2
                continue
            if ch == '"':
                raise ValueError(f"{key} has an unescaped quote inside a double-quoted value")
            out.append(ch)
            i += 1
        if not out:
            raise ValueError(f"{key} is empty")
        return "".join(out)
    if v.startswith("'"):
        inner = v[1:-1]
        if len(v) < 2 or not v.endswith("'") or "'" in inner.replace("''", ""):
            raise ValueError(f"{key} has an unbalanced single-quoted value")
        if not inner:
            raise ValueError(f"{key} is empty")
        return inner.replace("''", "'")
    if ": " in v or v.endswith(":") or " #" in v or v[0] in "[]{}&*!|>%@`,?#":
        raise ValueError(f"{key} needs quotes (it contains a colon or a character YAML treats specially)")
    return v


def parse(path: Path) -> Message:
    raw = path.read_bytes()
    msg = Message(path, raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        msg.errors.append("not UTF-8 text")
        return msg
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        msg.errors.append("doesn't open with a '---' properties block")
        return msg
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if end is None:
        msg.errors.append("properties block is never closed with '---'")
        return msg
    for line in lines[1:end]:
        m = PROP_RE.fullmatch(line)
        if not m:
            msg.errors.append(f"property line {line!r} isn't 'key: value' on one line")
            continue
        key = m.group(1)
        if key not in KEYS:
            msg.errors.append(f"unknown property {key!r}")
            continue
        if key in msg.props:
            msg.errors.append(f"property {key!r} appears twice")
            continue
        try:
            msg.props[key] = _value(key, m.group(2))
        except ValueError as e:
            msg.errors.append(str(e))
    missing = [k for k in KEYS if k not in msg.props and not any(k in e for e in msg.errors)]
    if missing:
        msg.errors.append(f"missing properties: {', '.join(missing)}")
    body = lines[end + 1:]
    while body and not body[-1].strip():
        body.pop()
    if body and body[-1].startswith("RECEIPT"):
        m = RECEIPT_RE.fullmatch(body[-1].rstrip())
        if not m:
            msg.errors.append(f"last line looks like a receipt but isn't 'RECEIPT <code> <date> · <text>': {body[-1][:60]!r}")
        elif len(body) < 2 or body[-2].strip():
            msg.errors.append("the receipt needs a blank line above it")
        else:
            msg.receipt = (m.group(1), m.group(2), m.group(3))
            body = body[:-2]
    msg.body = body
    if not any(l.strip() for l in body):
        msg.errors.append("the message has no body")
    _agree(msg)
    return msg


def _agree(msg: Message) -> None:
    """Name and properties must tell the same story."""
    parts = msg.name_parts
    if not parts:
        msg.errors.append("file name isn't date-sender-to-recipient-letter.md")
        return
    p = msg.props
    for key, name_key in (("from", "from"), ("to", "to"), ("sent", "date")):
        if key in p and p[key] != parts[name_key]:
            msg.errors.append(f"name says {name_key} {parts[name_key]!r} but the {key} property says {p[key]!r}")
    if "re" in p and p["re"] != "none" and not ID_RE.fullmatch(str(p["re"])):
        msg.errors.append(f"re {p['re']!r} is neither 'none' nor a message ID")
    if "sent" in p:
        try:
            dt.date.fromisoformat(str(p["sent"]))
        except ValueError:
            msg.errors.append(f"sent {p['sent']!r} isn't a YYYY-MM-DD date")
    if msg.receipt and "to" in p and msg.receipt[0] != p["to"]:
        msg.errors.append(f"the receipt is by {msg.receipt[0]!r}, not the ACTION recipient {p['to']!r}")


# ── the folder ────────────────────────────────────────────────────────────────

def relay_dir(arg: Optional[str]) -> Path:
    candidate = arg or os.environ.get("RELAY_DIR") or str(Path(__file__).resolve().parent)
    p = Path(candidate)
    if not (p / "pending").is_dir() or not (p / "done").is_dir():
        raise Refused(f"{candidate} isn't a RELAY folder (no pending/ and done/); pass --relay PATH")
    return p.resolve()


def message_files(relay: Path) -> List[Path]:
    """Every message-named file under pending/, done/ and done/YYYY-MM/."""
    out = []
    for folder in [relay / "pending", relay / "done"] + sorted(
            d for d in (relay / "done").iterdir() if d.is_dir() and MONTH_RE.fullmatch(d.name)):
        out.extend(p for p in sorted(folder.iterdir()) if NAME_RE.fullmatch(p.name) and p.is_file())
    return out


def pending(relay: Path) -> List[Message]:
    return [parse(p) for p in sorted((relay / "pending").iterdir()) if NAME_RE.fullmatch(p.name) and p.is_file()]


def known_code(readme: Readme, code: str, label: str) -> str:
    if not CODE_RE.fullmatch(code or ""):
        raise Refused(f"{label} {code!r} isn't a sender code (lower-case letters and digits)")
    if code not in readme.senders:
        raise Refused(f"{label} {code!r} isn't in README.md's sender list ({', '.join(readme.senders)})")
    return code


def letters_to_n(s: str) -> int:
    n = 0
    for ch in s:
        n = n * 26 + (ord(ch) - 96)
    return n


def n_to_letters(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def next_name(relay: Path, date: str, sender: str, to: str) -> str:
    prefix = f"{date}-{sender}-to-{to}-"
    used = [NAME_RE.fullmatch(p.name).group("letter") for p in message_files(relay) if p.name.startswith(prefix)]
    return f"{prefix}{n_to_letters(max((letters_to_n(u) for u in used), default=0) + 1)}.md"


def exists_anywhere(relay: Path, name: str) -> Optional[Path]:
    return next((p for p in message_files(relay) if p.name == name), None)


ANSWERING_RE = re.compile(rf"Added {DATE}, answering ({DATE}-{CODE}-to-{CODE}-[a-z]+):")


def thread_length(relay: Path, re_id: str) -> int:
    """Messages on the thread a reply to re_id would join, counting the reply. A thread is
    every message linked to re_id through re properties or '--add --re' answers, in either direction."""
    links: Dict[str, set] = {}
    for p in message_files(relay):
        m = parse(p)
        links.setdefault(m.id, set())
        targets = [str(m.props.get("re", "none"))] + [x.group(1) for l in m.body for x in [ANSWERING_RE.fullmatch(l)] if x]
        for t in targets:
            if t != "none":
                links[m.id].add(t)
                links.setdefault(t, set()).add(m.id)
    thread, todo = set(), [re_id]
    while todo:
        cur = todo.pop()
        if cur in thread:
            continue
        thread.add(cur)
        todo.extend(links.get(cur, ()))
    return 1 + len([t for t in thread if exists_anywhere(relay, t + ".md")])


# ── writing ───────────────────────────────────────────────────────────────────

def write_via_temp(target: Path, data: bytes, may_replace: bool) -> None:
    """Write data to a dot-named temp file beside target, then rename it into place.
    Nothing is ever deleted: if something fails, the temp file stays and check reports it."""
    if target.is_symlink():
        raise Refused(f"{target.name} is a symbolic link; refusing to write it")
    if target.exists() and not may_replace:
        raise Refused(f"{target.name} already exists; the relay never overwrites a name")
    mode = (target.stat().st_mode & 0o7777) if target.exists() else None
    n = 0
    while True:
        tmp = target.parent / f".{target.name}.{os.getpid()}.{n}.tmp"
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
            break
        except FileExistsError:
            n += 1
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    if mode is not None:
        os.chmod(tmp, mode)
    if not may_replace and target.exists():  # someone took the name while we wrote
        raise Refused(f"{target.name} appeared while writing; left {tmp.name} for check to report")
    os.replace(tmp, target)


def taken_in_done(relay: Path, src: Path) -> bool:
    """True if src's name is already used in done/ or one of its month folders."""
    return (relay / "done" / src.name).exists() or any(
        p.name == src.name and p != src for p in message_files(relay))


def move_into_done(relay: Path, src: Path) -> Path:
    if taken_in_done(relay, src):  # checked again here in case another chat moved one in meanwhile
        raise Refused(f"{src.name} appeared in done/ while consuming; it now ends in your receipt "
                      f"but stays in pending/. Tell the person running the relay.")
    dest = relay / "done" / src.name
    os.rename(src, dest)
    return dest


def newline_of(raw: bytes) -> str:
    return "\r\n" if b"\r\n" in raw else "\n"


def one_line(label: str, value: Optional[str]) -> str:
    v = (value or "").strip()
    if not v:
        raise Refused(f"{label} is required")
    if "\n" in v or "\r" in v:
        raise Refused(f"{label} must be one line")
    return v


def quoted(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_body(arg: str) -> List[str]:
    try:
        text = sys.stdin.read() if arg == "-" else Path(arg).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Refused(f"couldn't read --body {arg}: {e}")
    lines = text.replace("\r\n", "\n").strip("\n").split("\n")
    if not any(l.strip() for l in lines):
        raise Refused("the body is empty")
    if lines[0] == "---":
        raise Refused("the body can't start with '---'; it would read as a second properties block")
    if lines[-1].startswith("RECEIPT"):
        raise Refused("the body can't end with a line starting RECEIPT; it would read as already consumed")
    return lines


def render(props: Dict[str, object], body: List[str]) -> str:
    fyi = "[" + ", ".join(props["fyi"]) + "]"  # type: ignore[arg-type]
    head = ["---", f"from: {props['from']}", f"to: {props['to']}", f"fyi: {fyi}", f"sent: {props['sent']}",
            f"re: {props['re']}", f"done_when: {quoted(str(props['done_when']))}", "---"]
    return "\n".join(head + body) + "\n"


def stop_if_malformed(msg: Message) -> None:
    if msg.errors:
        raise Refused(f"{msg.path.name} is malformed ({msg.errors[0]}); the relay won't guess at it. Tell the person running the relay.")


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_list(relay: Path, a: argparse.Namespace) -> int:
    readme = read_readme(relay)
    me = known_code(readme, a.me, "--me")
    note = version_note(readme)
    if note:
        print(f"NOTE  {note}")
    msgs = pending(relay)
    bad = [m for m in msgs if m.errors]
    action = [m for m in msgs if not m.errors and m.props["to"] == me]
    fyi = [m for m in msgs if not m.errors and me in m.props["fyi"]]  # type: ignore[operator]

    def show(m: Message, role: str) -> None:
        p = m.props
        extra = f"  re {p['re']}" if p["re"] != "none" else ""
        flag = "  ALREADY RECEIPTED: finish it with consume, which only moves it" if m.receipt else ""
        print(f"{role:6} {m.id}  seen {m.hash}  from {p['from']}{extra}{flag}")
        print(f"       done when: {p['done_when']}")
        if a.full:
            print("       " + "\n       ".join(m.raw.decode("utf-8").rstrip("\n").replace("\r", "").split("\n")))

    for m in action:
        show(m, "ACTION")
    for m in fyi:
        show(m, "FYI")
    if not action and not fyi:
        print(f"nothing pending for {me}")
    for m in bad:
        print(f"STOP   {m.path.name}: {'; '.join(m.errors)}. Don't act on it; tell the person running the relay.")
    return 1 if bad else 0


def check_reply(relay: Path, re_id: str, ruled: bool) -> str:
    if not ID_RE.fullmatch(re_id):
        raise Refused(f"--re {re_id!r} isn't a message ID")
    if exists_anywhere(relay, re_id + ".md") is None:
        raise Refused(f"--re {re_id} matches no message under RELAY/")
    n = thread_length(relay, re_id)
    if n >= 3 and not ruled:
        raise Refused(f"this would be message {n} on one thread. Rule 4: put it to the person running the "
                      f"relay as a decision with options. Once they have ruled, add --ruled.")
    return re_id


def cmd_post(relay: Path, a: argparse.Namespace) -> int:
    readme = read_readme(relay)
    note = version_note(readme)
    if note and readme.version[0] != int(PROTOCOL_VERSION.split(".")[0]):
        raise Refused(note)
    sender = known_code(readme, a.sender, "--from")
    to = known_code(readme, a.to, "--to")
    if sender == to:
        raise Refused("--from and --to are the same code")
    fyi: List[str] = []
    for f in a.fyi or []:
        known_code(readme, f, "--fyi")
        if f not in (sender, to) and f not in fyi:
            fyi.append(f)
    body = read_body(a.body)
    date = today(readme.tz)
    mine = [m for m in pending(relay) if m.name_parts.get("from") == sender and m.name_parts.get("to") == to]
    open_mine = [m for m in mine if m.receipt is None]

    if a.add:
        if not open_mine:
            raise Refused(f"{sender} has no unconsumed message pending for {to}; post without --add")
        target = open_mine[0]
        stop_if_malformed(target)  # a sender is found by file name, and name and properties must agree
        props = dict(target.props)
        props["fyi"] = list(dict.fromkeys(list(props["fyi"]) + fyi))  # type: ignore[arg-type]
        if a.done_when:
            props["done_when"] = one_line("--done-when", a.done_when)
        added = f"Added {date}:"
        if a.re:
            re_id = check_reply(relay, one_line("--re", a.re), a.ruled)
            added = f"Added {date}, answering {re_id}:"
        new_body = target.body + ["", added, ""] + body
        nl = newline_of(target.raw)
        data = render(props, new_body).replace("\n", nl).encode("utf-8")
        if a.dry_run:
            print(f"dry run: would rewrite pending/{target.path.name} with this content:\n{data.decode('utf-8')}")
            return 0
        write_via_temp(target.path, data, may_replace=True)
        print(f"added to {target.id}")
        return 0

    if open_mine:
        raise Refused(f"{sender} already has {open_mine[0].id} pending for {to}. Add to it with --add "
                      f"(rule 5: one pending message per sender and recipient).")
    done_when = one_line("--done-when", a.done_when)
    re_id = check_reply(relay, one_line("--re", a.re), a.ruled) if a.re else "none"
    name = next_name(relay, date, sender, to)
    props = {"from": sender, "to": to, "fyi": fyi, "sent": date, "re": re_id, "done_when": done_when}
    data = render(props, body).encode("utf-8")
    if a.dry_run:
        print(f"dry run: would write pending/{name}:\n{data.decode('utf-8')}")
        return 0
    write_via_temp(relay / "pending" / name, data, may_replace=False)
    print(name[:-3])
    return 0


def cmd_consume(relay: Path, a: argparse.Namespace) -> int:
    readme = read_readme(relay)
    note = version_note(readme)
    if note and readme.version[0] != int(PROTOCOL_VERSION.split(".")[0]):
        raise Refused(note)
    me = known_code(readme, a.me, "--me")
    mid = a.id[:-3] if a.id.endswith(".md") else a.id
    if not ID_RE.fullmatch(mid):
        raise Refused(f"{a.id!r} isn't a message ID")
    path = relay / "pending" / f"{mid}.md"
    if not path.is_file() or path.is_symlink():
        where = exists_anywhere(relay, f"{mid}.md")
        raise Refused(f"{mid} isn't in pending/" + (f" (it's in {where.parent.name}/)" if where else ""))
    msg = parse(path)
    stop_if_malformed(msg)
    if msg.props["to"] != me:
        role = "only on FYI, so read it and leave it" if me in msg.props["fyi"] else "not its recipient"  # type: ignore[operator]
        raise Refused(f"{me} is {role}; only {msg.props['to']} consumes {mid}")
    if msg.hash != a.seen:
        raise Refused(f"{mid} has changed since you read it (seen {a.seen}, now {msg.hash}). "
                      f"Run list --full again and deal with what was added first.")
    before = {p.name for p in (relay / "pending").iterdir()}
    receipt_text = one_line("--receipt", a.receipt)
    if msg.receipt:
        print(f"note: {mid} already ends in a receipt; moving it without adding another", file=sys.stderr)
        data = None
    else:
        nl = newline_of(msg.raw)
        text = msg.raw.decode("utf-8").rstrip("\r\n")
        data = (text + nl + nl + f"RECEIPT {me} {today(readme.tz)} · {receipt_text}" + nl).encode("utf-8")
    if taken_in_done(relay, path):
        raise Refused(f"{path.name} already exists in done/; the relay never overwrites a name")
    if a.dry_run:
        if data is not None:
            print(f"dry run: would add this last line to {mid}, then move it to done/:\n"
                  f"{data.decode('utf-8').rstrip().splitlines()[-1]}")
        else:
            print(f"dry run: would move {mid} to done/")
        return 0
    if data is not None:
        write_via_temp(path, data, may_replace=True)
    move_into_done(relay, path)
    after = {p.name for p in (relay / "pending").iterdir()}
    if after != before - {path.name}:
        raise Refused(f"pending/ changed unexpectedly during consume: lost {sorted(before - after - {path.name})}, "
                      f"gained {sorted(after - before)}. Tell the person running the relay.")
    print(f"consumed {mid}: receipt written, moved to done/")
    return 0


def cmd_check(relay: Path, a: argparse.Namespace) -> int:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        readme = read_readme(relay)
    except Refused as e:
        print(f"ERROR   {e}")
        return 1
    note = version_note(readme)
    if note:  # a later minor version keeps the same file formats; a different major version may not
        (errors if readme.version[0] != int(PROTOCOL_VERSION.split(".")[0]) else warnings).append(note)
    if readme.owner is None:
        warnings.append("README.md has no 'Owner: <code>' line, so nobody can prune done/")
    try:
        zone(readme.tz)
    except Refused as e:
        errors.append(str(e))
    for folder in ("pending", "done"):
        if not (relay / folder / ".keep").is_file():
            errors.append(f"{folder}/.keep is missing, so the folder can vanish when empty")
    for p in sorted(relay.rglob("*")):
        if p.is_symlink():
            errors.append(f"{p.relative_to(relay)} is a symbolic link")

    def stray(folder: Path, allow_months: bool) -> None:
        for p in sorted(folder.iterdir()):
            rel = p.relative_to(relay)
            if p.name == ".keep" and folder.name in ("pending", "done"):
                continue
            if p.name == ".DS_Store":  # macOS leaves these everywhere; harmless
                continue
            if p.is_dir() and allow_months and MONTH_RE.fullmatch(p.name):
                stray(p, False)
                continue
            if p.name.startswith(".") and p.name.endswith(".tmp"):
                errors.append(f"{rel} is a leftover temp file: a write was interrupted. Tell the person running the relay; don't guess which copy is right.")
            elif not (p.is_file() and NAME_RE.fullmatch(p.name)):
                errors.append(f"{rel} doesn't belong here; only messages named date-sender-to-recipient-letter.md")

    stray(relay / "pending", False)
    stray(relay / "done", True)

    seen: Dict[str, Path] = {}
    open_pairs: Dict[Tuple[str, str], List[str]] = {}
    all_ids = {p.name[:-3] for p in message_files(relay)}
    for p in message_files(relay):
        rel = p.relative_to(relay)
        if p.name in seen:
            errors.append(f"{p.name} exists twice: {seen[p.name].relative_to(relay)} and {rel}")
        seen[p.name] = p
        m = parse(p)
        for e in m.errors:
            errors.append(f"{rel}: {e}")
        if m.errors:
            continue
        for key in ("from", "to"):
            if m.props[key] not in readme.senders:
                errors.append(f"{rel}: {key} {m.props[key]!r} isn't in README.md's sender list")
        for f in m.props["fyi"]:  # type: ignore[union-attr]
            if f not in readme.senders:
                errors.append(f"{rel}: fyi {f!r} isn't in README.md's sender list")
        if m.props["re"] != "none" and m.props["re"] not in all_ids:
            warnings.append(f"{rel}: re {m.props['re']} matches no message under RELAY/")
        in_pending = p.parent.name == "pending"
        if in_pending and m.receipt:
            warnings.append(f"{rel} already ends in a receipt; {m.props['to']} should finish it by moving it to done/")
        if not in_pending and not m.receipt:
            errors.append(f"{rel} is in done/ without a receipt")
        if in_pending and not m.receipt:
            open_pairs.setdefault((str(m.props["from"]), str(m.props["to"])), []).append(m.id)
    for (s, t), ids in open_pairs.items():
        if len(ids) > 1:
            errors.append(f"{s} has {len(ids)} messages pending for {t} ({', '.join(ids)}); rule 5 allows one")
    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"warning {w}")
    n_pending = len([p for p in (relay / "pending").iterdir() if NAME_RE.fullmatch(p.name)])
    print(f"{'FAIL' if errors else 'ok'}: protocol v{readme.version_text}, {n_pending} pending, "
          f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def git_check(relay: Path, files: List[Path]) -> Optional[Dict[Path, str]]:
    """None if the folder isn't in a git repository. Otherwise, for each file, '' if it is
    committed and unchanged, or the reason it isn't. Only read-only git commands are used,
    with optional locks off, so this never leaves a lock file behind."""
    top = relay
    while not (top / ".git").exists():
        if top.parent == top:
            return None
        top = top.parent
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

    def git(*args: str) -> str:
        try:
            r = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, env=env, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            raise Refused(f"this folder is in a git repository but git couldn't be run ({e}); not pruning anything")
        if r.returncode:
            raise GitMiss(r.stderr.strip() or f"git {args[0]} failed")
        return r.stdout.strip()

    try:
        git("rev-parse", "--verify", "-q", "HEAD")
    except GitMiss:
        raise Refused("this folder is in a git repository with no commits yet; commit before pruning")
    out: Dict[Path, str] = {}
    for f in files:
        rel = os.path.relpath(f, top).replace(os.sep, "/")
        try:
            committed = git("rev-parse", "--verify", "-q", f"HEAD:{rel}")
        except GitMiss:
            out[f] = "not committed yet"
            continue
        try:
            now = git("hash-object", "--", rel)
        except GitMiss as e:
            raise Refused(f"git couldn't read {rel} ({e}); not pruning anything")
        out[f] = "" if now == committed else "changed since it was committed"
    return out


class GitMiss(Exception):
    pass


def cmd_prune(relay: Path, a: argparse.Namespace) -> int:
    readme = read_readme(relay)
    note = version_note(readme)
    if note and readme.version[0] != int(PROTOCOL_VERSION.split(".")[0]):
        raise Refused(note)
    me = known_code(readme, a.me, "--me")
    if readme.owner is None:
        raise Refused("README.md names no owner ('Owner: <code>'), so nobody may prune")
    if me != readme.owner:
        raise Refused(f"only the folder's owner ({readme.owner}) prunes done/")
    if a.days < 1:
        raise Refused("--days must be at least 1")
    cutoff = (dt.date.fromisoformat(today(readme.tz)) - dt.timedelta(days=a.days)).isoformat()

    done = relay / "done"
    folders = [done] + sorted(d for d in done.iterdir()
                              if d.is_dir() and not d.is_symlink() and MONTH_RE.fullmatch(d.name))
    candidates: List[Tuple[Path, str]] = []
    for folder in folders:
        for p in sorted(folder.iterdir()):
            if not NAME_RE.fullmatch(p.name) or not p.is_file() or p.is_symlink():
                continue  # only message files are ever considered
            m = parse(p)
            if m.errors:
                raise Refused(f"done/{p.relative_to(done)} is malformed ({m.errors[0]}); not pruning anything. "
                              f"Run check and tell the person running the relay.")
            if m.receipt and m.receipt[1] < cutoff:
                candidates.append((p, m.receipt[1]))

    kept: List[str] = []
    status = git_check(relay, [p for p, _ in candidates]) if candidates else None
    if status is not None:
        for p, _ in list(candidates):
            if status[p]:
                kept.append(f"kept {p.relative_to(relay)}: {status[p]}")
        candidates = [(p, d) for p, d in candidates if not status[p]]

    for line in kept:
        print(line)
    if not candidates:
        print(f"nothing to prune: no committed, consumed message in done/ has a receipt before {cutoff}")
        return 0
    if a.dry_run:
        for p, d in candidates:
            print(f"would prune {p.relative_to(relay)} (receipt {d})")
        print(f"dry run: would prune {len(candidates)} consumed message(s) with receipts before {cutoff}")
        return 0

    before_pending = {p.name for p in (relay / "pending").iterdir()}
    pruned = 0
    for p, d in candidates:
        try:
            os.unlink(p)
        except PermissionError:
            print(f"stopped: deleting isn't permitted in this folder from here, so {p.relative_to(relay)} and "
                  f"the rest were left alone. Some hosts block deletes in connected folders until the person "
                  f"allows them; once allowed, run prune again. Pruned {pruned} before stopping.", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"stopped: couldn't delete {p.relative_to(relay)} ({e.strerror}). Pruned {pruned} before stopping.",
                  file=sys.stderr)
            return 1
        print(f"pruned {p.relative_to(relay)} (receipt {d})")
        pruned += 1
    if {p.name for p in (relay / "pending").iterdir()} != before_pending:
        raise Refused("pending/ changed during prune. Tell the person running the relay.")
    print(f"pruned {pruned} consumed message(s) with receipts before {cutoff}")
    return 0


def cmd_who(relay: Path, a: argparse.Namespace) -> int:
    """Read-only: the owner, every sender with its description, and what each has pending."""
    readme = read_readme(relay)
    me = known_code(readme, a.me, "--me") if a.me else None
    sending: Dict[str, List[str]] = {}
    receiving: Dict[str, List[str]] = {}
    waiting, receipted = [], []
    for p in sorted((relay / "pending").iterdir()):
        parts = NAME_RE.fullmatch(p.name)
        if not (parts and p.is_file()):
            continue
        if parse(p).receipt:  # consumed, just not moved yet: not waiting on anyone
            receipted.append(parts)
            continue
        waiting.append(parts)
        sending.setdefault(parts.group("from"), []).append(parts.group("date"))
        receiving.setdefault(parts.group("to"), []).append(parts.group("date"))

    def summary(dates: List[str]) -> str:
        return f"{len(dates)} (oldest {min(dates)})" if dates else "none"

    print(f"Owner: {readme.owner or 'none named'}")
    print(f"Time zone: {readme.tz}")
    print("Senders:")
    for code in readme.senders:
        desc = readme.descriptions.get(code) or "no description"
        you = "  <- you" if code == me else ""
        print(f"  {code} ({desc}): sending {summary(sending.get(code, []))}; "
              f"receiving {summary(receiving.get(code, []))}{you}")
    for parts in waiting:
        print(f"Pending: {parts.group(0)[:-3]} (from {parts.group('from')} to {parts.group('to')}, "
              f"since {parts.group('date')})")
    for parts in receipted:
        print(f"Receipted, not yet moved: {parts.group(0)[:-3]} ({parts.group('to')}'s next pass moves it to done/)")
    return 0


def parse_senders(spec: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for item in [s for s in (spec or "").split(";") if s.strip()]:
        if "=" not in item:
            raise Refused(f"sender {item.strip()!r} isn't 'code=description'")
        code, desc = (x.strip() for x in item.split("=", 1))
        if not CODE_RE.fullmatch(code):
            raise Refused(f"sender code {code!r} isn't lower-case letters and digits")
        if not desc or "\n" in desc or "\r" in desc:
            raise Refused(f"sender {code!r} needs a one-line description")
        if code in [c for c, _ in out]:
            raise Refused(f"sender {code!r} is listed twice")
        out.append((code, desc))
    if not out:
        raise Refused("--senders lists nobody")
    return out


def cmd_init(a: argparse.Namespace) -> int:
    """Set up a RELAY folder that has no relay yet: README.md, pending/.keep and done/.keep."""
    if not a.relay:
        raise Refused("give --relay with the folder to set up")
    relay = Path(a.relay)
    if relay.is_symlink() or (relay.exists() and not relay.is_dir()):
        raise Refused(f"{relay} isn't a plain folder")
    if not relay.parent.is_dir():
        raise Refused(f"{relay.parent} doesn't exist; init only creates the RELAY folder itself")
    taken = [n for n in ("README.md", "pending", "done") if (relay / n).exists() or (relay / n).is_symlink()]
    if taken:
        raise Refused(f"{relay} already has {', '.join(taken)}; init only sets up a folder with no relay yet")
    senders = parse_senders(a.senders)
    owner = a.owner or ""
    if owner not in [c for c, _ in senders]:
        raise Refused(f"the owner {owner!r} must be one of the senders ({', '.join(c for c, _ in senders)})")
    tz = (a.time_zone or TZ).strip()
    zone(tz)  # refuses a name with no time-zone data
    text = (f"# RELAY\n\nRELAY PROTOCOL v{PROTOCOL_VERSION} · {today(tz)}\n\nOwner: {owner}\n\nTime zone: {tz}\n\n"
            f"Senders and codes:\n"
            + "".join(f"- {c} = {d}\n" for c, d in senders) + "\n" + PROTOCOL_RULES)
    if a.dry_run:
        print(f"dry run: would create {relay}/README.md, pending/.keep and done/.keep. README.md:\n\n{text}")
        return 0
    relay.mkdir(exist_ok=True)
    for sub in ("pending", "done"):
        (relay / sub).mkdir()
        write_via_temp(relay / sub / ".keep", b"", may_replace=False)
    write_via_temp(relay / "README.md", text.encode("utf-8"), may_replace=False)
    print(f"set up {relay}: README.md (protocol v{PROTOCOL_VERSION}, owner {owner}, time zone {tz}, "
          f"{len(senders)} sender(s)), pending/ and done/")
    return 0


TOOL_VERSION_RE = re.compile(r'^TOOL_VERSION = "(\d+)\.(\d+)"$', re.M)


def self_hash() -> str:
    return short_hash(Path(__file__).read_bytes())


def cmd_install_plan(a: argparse.Namespace) -> int:
    """Say whether this copy of relay.py (the one bundled with the skill) should be installed
    into the RELAY folder. It never copies anything itself: the chat's host moves the file,
    byte for byte. The first word of the answer is what to do: LOCAL, CURRENT, INSTALL,
    WAIT, NEWER or MISSING."""
    mine = tuple(int(x) for x in TOOL_VERSION.split("."))
    if a.relay:
        relay_dir(a.relay)
        print(f"LOCAL: this relay.py {TOOL_VERSION} can reach the RELAY folder; run it directly. Nothing to install.")
        return 0
    if not a.readme:
        raise Refused("give --relay (same machine) or --readme with the folder's README.md (copied here)")
    readme = read_readme(Path(a.readme).parent, Path(a.readme))
    me = known_code(readme, a.me, "--me")
    owner = readme.owner is not None and me == readme.owner
    theirs_bytes = b""
    if a.folder_copy:
        try:
            theirs_bytes = Path(a.folder_copy).read_bytes()
            text = theirs_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise Refused(f"couldn't read the folder's relay.py copy ({e}); leaving it alone")
        m = TOOL_VERSION_RE.search(text)
        if not m:
            raise Refused("can't tell which version the folder's relay.py is; leaving it alone. "
                          "Tell the person running the relay.")
        theirs: Optional[Tuple[int, int]] = (int(m.group(1)), int(m.group(2)))
    else:
        theirs = None
    old = f"{theirs[0]}.{theirs[1]}" if theirs else "none"
    expect = f"EXPECT relay.py {TOOL_VERSION} (protocol v{PROTOCOL_VERSION}) sha256 {self_hash()}"
    same_bytes = theirs == mine and short_hash(theirs_bytes) == self_hash()
    if same_bytes:
        print(f"CURRENT: relay.py here is {TOOL_VERSION}, identical to the skill's.")
    elif theirs == mine and owner:
        print(f"INSTALL {old} (different contents) -> {TOOL_VERSION}: the folder's copy has the same version but "
              f"isn't identical to the skill's. Copy this file ({Path(__file__).resolve()}) byte for byte into the "
              f"RELAY folder as relay.py, then check that relay.py --version there prints the EXPECT line below.")
        print(expect)
    elif theirs == mine:
        print(f"WAIT: relay.py here is {old} but isn't identical to the skill's copy; the owner's next pass "
              f"replaces it. Carry on with the folder's copy.")
    elif theirs is not None and theirs > mine:
        print(f"NEWER: relay.py here is {old}, newer than the skill's {TOOL_VERSION}. Leave it alone and use it; "
              f"the skill may need updating.")
    elif owner:
        print(f"INSTALL {old} -> {TOOL_VERSION}: copy this file ({Path(__file__).resolve()}) byte for byte into the "
              f"RELAY folder as relay.py, then check that relay.py --version there prints the EXPECT line below.")
        print(expect)
    elif theirs is not None:
        print(f"WAIT: relay.py here is {old}; the owner's next pass updates it to {TOOL_VERSION}. "
              f"Carry on with the folder's copy.")
    else:
        print(f"MISSING: there is no relay.py in the RELAY folder, and only its owner "
              f"({readme.owner or 'none named'}) installs it. Tell the person running the relay.")
    return 0


class VersionAction(argparse.Action):
    def __init__(self, option_strings, dest, **kw):
        super().__init__(option_strings, dest, nargs=0, help="print the version and this file's sha256")

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"relay.py {TOOL_VERSION} (protocol v{PROTOCOL_VERSION}) sha256 {self_hash()}")
        parser.exit()


# ── command line ──────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="relay.py", description=f"Relay tool {TOOL_VERSION}, for relay protocol v{PROTOCOL_VERSION}.")
    p.add_argument("--version", action=VersionAction)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--relay", help="the RELAY folder (default: $RELAY_DIR, else the folder relay.py is in)")
        return s

    li = add("list", "what is pending for you, as ACTION and as FYI")
    li.add_argument("--me", required=True)
    li.add_argument("--full", action="store_true", help="print each message in full")
    po = add("post", "send a message, or add to your pending one with --add")
    po.add_argument("--from", dest="sender", required=True)
    po.add_argument("--to", required=True)
    po.add_argument("--fyi", action="append")
    po.add_argument("--re")
    po.add_argument("--done-when")
    po.add_argument("--body", required=True, help="a file holding the body, or - for standard input")
    po.add_argument("--add", action="store_true", help="add to your message already pending for --to")
    po.add_argument("--ruled", action="store_true", help="send a third message on a thread after the person running the relay has ruled")
    po.add_argument("--dry-run", action="store_true")
    co = add("consume", "add your receipt to a message for you and move it to done/")
    co.add_argument("id")
    co.add_argument("--me", required=True)
    co.add_argument("--seen", required=True, help="the 'seen' hash list printed when you read it")
    co.add_argument("--receipt", required=True, help="one line: what was done; docs touched, with versions")
    co.add_argument("--dry-run", action="store_true")
    add("check", "check the whole folder against the protocol")
    pr = add("prune", "owner only: delete consumed messages in done/ past the hold")
    pr.add_argument("--me", required=True)
    pr.add_argument("--days", type=int, default=HOLD_DAYS, help=f"the hold in days (default {HOLD_DAYS})")
    pr.add_argument("--dry-run", action="store_true")
    wh = add("who", "who is in the relay, and what each has pending")
    wh.add_argument("--me")
    ini = sub.add_parser("init", help="set up a RELAY folder that has no relay yet")
    ini.add_argument("--relay", required=True)
    ini.add_argument("--owner", required=True)
    ini.add_argument("--senders", required=True, help='"code=description; code=description"')
    ini.add_argument("--time-zone", default=TZ, help=f"IANA time zone for the relay's dates (default {TZ})")
    ini.add_argument("--dry-run", action="store_true")
    ip = sub.add_parser("install-plan", help="should this relay.py be installed into the RELAY folder?")
    ip.add_argument("--me", required=True)
    ip.add_argument("--relay", help="the RELAY folder, if this machine can reach it")
    ip.add_argument("--readme", help="a copy of the RELAY folder's README.md")
    ip.add_argument("--folder-copy", help="a copy of the RELAY folder's relay.py, if it has one")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        if a.cmd == "install-plan":
            return cmd_install_plan(a)
        if a.cmd == "init":
            return cmd_init(a)
        relay = relay_dir(a.relay)
        return {"list": cmd_list, "post": cmd_post, "consume": cmd_consume, "check": cmd_check,
                "prune": cmd_prune, "who": cmd_who}[a.cmd](relay, a)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
