# vault-relay

Plain-file mail for AI chats that share a folder, with rules that stop them chatting. You decide when anyone checks it.

*The successor to [skill-claude-relay](https://github.com/fightingforsidewalk/skill-claude-relay): a major revamp, rebuilt from the ground up with much more in it. See [Where it came from](#where-it-came-from).*

## The problem

If you work with several AI chats on one project (one planning, one building, one reviewing), you soon become their message bus. You copy a handover out of one chat, paste it into another, and carry the reply back. Text drifts, things get dropped, and the chats can't see what the others already know.

This gives them a shared folder instead. Each message is a small Markdown file. A chat writes one; another picks it up when you tell it to, does the work, and files it with a one-line receipt. You can read everything in any Markdown editor, and nothing happens until you ask.

Left alone, chats will happily trade updates forever. So the rules start with getting things done.

## What it works with

**Any folder of Markdown files.** "Vault" here just means the folder where your notes live. Obsidian is a nice fit: each message's properties show as a tidy header, and you can watch the relay folder fill and empty as chats work. It isn't required. VS Code or any text editor works just as well, and so does a folder no editor ever opens.

**Any AI tool that can read files and run a command.** The rules are plain text and the tool is one Python file, so any chat or agent that can run `python3` in the folder can take part, and so can a person at a terminal. Different tools can share one relay, each with its own sender code.

**Claude gets the ready-made routine.** The `vault-relay` skill, shipped as a Claude plugin, teaches a Claude chat the whole routine and carries the tool with it. Other agents get the same routine from `AGENTS.md`; see [Works with other AIs](#works-with-other-ais).

## Getting to done

1. Every message aims at completion. It says what done looks like and carries everything the recipient needs to finish in one pass, with any decisions asked as a short numbered list.
2. The receipt is the only acknowledgement. No thank-you, "received", "noted" or status-only messages.
3. Reply only when the message asks for something back, or when the answer changes what the sender will do. Being copied (FYI) never prompts a reply.
4. One round trip, then you. If a thread hasn't closed after one message and one reply, the next word goes to you, as a decision with options, not back to the other chat. The tool refuses a third message on a thread until you've ruled.
5. Batch. A sender has at most one message waiting for any one recipient; anything new is added to that message. Beyond that, at most one new message per recipient per session, unless something is urgent.
6. When you say "relay for you", the chat ends that turn with every message addressed to it dealt with, or with one note to you naming what blocks it.

## Commands you can say

| Say | Or type | What happens |
|---|---|---|
| relay for you | /vault-relay | The chat reads what's waiting for it, acts on each message, closes each one with a receipt, and reports in one line. If it owns the folder, it also clears out old consumed messages. |
| relay this to <code> (or relay this for <code>) | /vault-relay to <code> | Sends what you just asked for to that sender as one message that says what done looks like. The recipient can be another Claude chat or another AI agent working in the same folder. |
| who's in the relay | /vault-relay who | Lists the folder's owner, who may send, and what's waiting between whom. Changes nothing. |
| relay help | /vault-relay help | Lists these phrases and what they do. |
| set up the relay | /vault-relay setup | Asks you which folder, which chat owns it and which other chats join, sets the folder up, then gives you a ready-to-paste block for each chat and a short checklist. |

The phrases work because the chat recognises them and loads the skill. Typing the slash form calls the skill directly, which is the surer route; both do the same thing. These are the Claude skill's phrases. `AGENTS.md` teaches other AI agents the same ones.

## Works with other AIs

The relay doesn't care which AI is on the other end. Any agent that can read and write files in the relay folder and run `python3` there can take part: Codex, Gemini CLI, Copilot or Cursor in agent mode, and others like them. A Claude chat and another agent can hand work back and forth through the same folder, each with its own sender code.

To add one:

1. Put its sender code in the relay folder's README sender list, for example `- codex = Codex CLI`.
2. Make sure `relay.py` sits in the relay folder. A Claude chat that owns the folder installs it there for you; otherwise copy it in from the release.
3. Copy `AGENTS.md` into the folder the agent works in, or add it to the agent's own instructions. Fill in its one line: `Relay: sender code <code>; RELAY folder <path>.` Many agents read `AGENTS.md` on their own; for the rest, tell the agent to read it.
4. Say "relay for you" to it, as you would to a Claude chat. "Relay this to <code>", "who's in the relay" and "relay help" work the same way.

An agent that reads the skill format can load `SKILL.md` directly instead.

**The limit.** The agent has to be able to work on files in that folder on your machine. A chat that only lives in a browser tab, with no access to your files, can't take part.

**What's been tested.** The tool is the same one Claude uses, with the same tests behind it. The routine in `AGENTS.md` has been run end to end as written: a message from a Claude sender to a second sender, consumed with a receipt, and a reply back the other way, also consumed. It hasn't yet been run by a non-Claude agent. If you try it with one, an issue saying what worked is very welcome.

**Mind what you send.** A message to another AI is read by that provider's model. The rule against putting secrets, credentials or personal data in a message matters even more when the relay crosses providers.

## Setting it up

Say "set up the relay" in the chat that will own the folder and it walks you through this. In order:

1. Connect the relay folder to each chat that will use it. A chat can only reach folders connected to it, and setup never assumes one is connected; it asks, then checks.
2. Run setup once, from the chat that will own the folder. It asks which folder (suggesting `00-System/RELAY` inside your vault or project folder), which chat owns it, which other chats join and which time zone the dates should use, then creates `README.md` (the rules, the owner and the list of senders), `pending/` and `done/`.
3. Add one line to every participating project's instructions:
   ```
   Relay: sender code <code>; RELAY folder <path>. "Relay for you" or /vault-relay runs the vault-relay skill there.
   ```
   Setup gives you one of these, filled in, for each chat. Without it, the skill gives you the line to add, and stops.
4. Say "who's in the relay" in any of the chats to confirm it's working.
5. To add a chat later, put it in the README's sender list before it posts. The tool refuses anyone who isn't listed.

## The layout

```
RELAY/
  README.md      the rules, a protocol version line, the owner and the sender list
  relay.py       the tool, installed here by the skill when the chat and folder are on different machines
  pending/       one file per unread message, plus an empty .keep
  done/          consumed messages, each ending in its receipt, plus .keep
```

A message's file name is its ID: date, sender, "to", recipient and a letter, as in `2026-10-03-planner-to-builder-a.md`. Exactly one chat is the ACTION recipient, the one in the name; others can be copied in with `fyi`. Sender codes are lower-case letters and digits.

```
---
from: planner
to: builder
fyi: [reviewer]
sent: 2026-10-03
re: none
done_when: "the signup page shows the new consent line, deployed and checked"
---
Please add the consent line under the signup form. The wording is in the brief.

1. Add the line.
2. Deploy, check it, and say where in your receipt.
```

When the builder has done it, the file moves to done/ with one last line, after a blank line:

```
RECEIPT builder 2026-10-03 · consent line live; signup page README v1.4
```

The tool reads four things from the README: a line containing `RELAY PROTOCOL v2.2`, an `Owner: <code>` line, a `Time zone: <IANA name>` line (America/New_York if there isn't one), and the sender list, either on one line (`Senders and codes: planner, builder, reviewer`) or as `- code = description` lines under `Senders and codes:`. Setup writes all four for you, followed by the rules.

Read messages in Obsidian or any editor, but leave their properties alone there: an editor that tidies properties (into a block list, say) produces a file the tool will refuse rather than guess at.

## Where it works

The skill can be loaded in any chat, but three things decide where it does anything:

- Each chat's own instructions give its sender code and the folder's path. Without them it asks and stops.
- The folder's README lists who may send. The tool refuses anyone else.
- A chat can only reach the folders connected to it.

Each vault or project folder keeps its own relay and its own rules.

## Trust

A sender code is taken on trust, not proved. Any chat with the folder connected could claim another chat's code. The real boundary is which folders you connect to which chats.

## Cleanup

`done/` is a short hold, not an archive. The folder's owner prunes consumed messages after 14 days. What a message decided should live in the documents of the chat that acted on it, and in your version history. If the folder is in a git repository, prune only removes files that are committed and unchanged, so a copy always stays in history. Some hosts block deletes in connected folders until you allow them; prune then stops and says so.

## The tool

`relay.py` is one Python file. It needs Python 3.9 or later, uses only the standard library, makes no network calls and only touches the relay folder you give it. Dates are in the time zone the README names, or New York time if it names none. On Windows, run `pip install tzdata` first.

```
python3 relay.py list    --relay RELAY --me CODE [--full]
python3 relay.py post    --relay RELAY --from CODE --to CODE --done-when TEXT --body FILE [--fyi CODE]... [--re ID] [--add] [--ruled]
python3 relay.py consume ID --relay RELAY --me CODE --seen HASH --receipt TEXT
python3 relay.py who     --relay RELAY [--me CODE]
python3 relay.py check   --relay RELAY
python3 relay.py prune   --relay RELAY --me CODE [--days 14]
python3 relay.py init    --relay RELAY --owner CODE --senders "code=description; code=description" [--time-zone ZONE]
python3 relay.py install-plan --me CODE (--relay RELAY | --readme FILE [--folder-copy FILE])
python3 relay.py --version
```

`--relay` can be left out if `RELAY_DIR` is set or `relay.py` sits in the relay folder. `post`, `consume`, `prune` and `init` take `--dry-run`, which shows what would happen and changes nothing.

**list** shows what's waiting for you as ACTION, then as FYI, each with a short `seen` hash of the file as you read it. `--full` prints each message. It flags a message that already ends in a receipt (consume will just move it). A file it can't read cleanly gets a STOP line instead of being listed, and list then exits 1.

**post** writes a new message with the next free letter. If you already have one waiting for that recipient, it refuses and points you to `--add`, which adds your text to the waiting message under an "Added" line (naming the message you're answering, if you give `--re`). It refuses a third message on one thread, counting every message linked back to the same first one, unless you pass `--ruled`. `--body -` reads the body from standard input.

**consume** is for the ACTION recipient only. It refuses if the file has changed since you read it, so a late addition from the sender can't slip past. Otherwise it adds your receipt and moves the file to done/.

**who** prints the owner, the time zone, each sender with its description, and how many messages each has waiting as sender and as recipient, with the oldest date. A message that already has its receipt but hasn't been moved yet is listed separately, not counted as waiting. It only reads.

**check** looks over the whole folder: names, properties, receipts, one waiting message per sender and recipient, nothing stray (macOS `.DS_Store` files are ignored), both `.keep` files, the owner line and the protocol version.

**prune** is for the folder's owner only. It deletes files in done/ (and any done/YYYY-MM/ folders) that end in a receipt dated before the hold, by default 14 days. It never touches pending/, the README, relay.py or anything else.

**init** sets up a folder with no relay yet, and refuses if a README, pending/ or done/ is already there. The owner must be one of the senders, and `--time-zone` (default America/New_York) must be a name the system knows.

**install-plan** tells the skill whether to install its own copy of the tool into the relay folder: `LOCAL` (same machine, nothing to install), `CURRENT` (the folder's copy is identical), `INSTALL <old> -> <new>` (owner only: the folder's copy is missing, older, or the same version with different contents), `WAIT` (the same cases for anyone but the owner), `NEWER` (the folder's copy is newer and is left alone) or `MISSING` (no copy, and not the owner). It never copies anything itself. `--version` prints the version and the file's own hash, so an install can be checked byte for byte.

Exit status is 0 when done, 1 when refused or check finds problems, and 2 for a bad command line.

### What it promises

1. It never overwrites a name that exists anywhere under the relay folder, or a file the caller doesn't own.
2. It deletes nothing, except that prune, run by the owner, deletes consumed messages past the hold. In a git repository those must also be committed and unchanged.
3. A consume moves exactly the one file named, and every other waiting message is still there afterwards.
4. Every write goes to a dot-named temporary file and is renamed into place, so nobody ever reads half a message.
5. A file with malformed properties stops the run rather than being guessed at.
6. A README whose protocol version differs from the tool's is flagged. A later minor version is a warning and everything still works; a different major version is an error in check and stops post, consume and prune.

Each promise has tests that watch it refuse, and `tests/guard_mutations.py` switches each check off in a copy of the tool to confirm the tests then fail.

```
python3 -m unittest discover -s tests
python3 tests/guard_mutations.py
```

## The skill (for Claude)

`SKILL.md` teaches a Claude chat the routines behind the phrases above. It calls the tool for every edit, so every chat runs the relay the same way.

The skill carries its own copy of `relay.py`. When the chat and the folder are on the same machine, it runs that copy directly. When they aren't (a chat running in the cloud, say, with the folder on your computer), the skill installs its copy into the relay folder whenever the two differ, but only when the chat is the folder's owner, and never over a newer copy. Other chats keep using the folder's copy and mention that the owner's next pass will update it. Every install is announced in the pass summary, from which version to which.

`python3 packaging/build.py` packs `SKILL.md`, `relay.py` and `packaging/plugin.json` into `vault-relay.plugin`, an installable plugin with the tool where the skill expects it.

## Limits

The tool checks form, not content. Whether a message really carries everything needed, or keeps secrets out, is up to whoever writes it. Two chats can't safely use the relay at the same instant; it's built for a person who wakes one chat at a time.

## Where it came from

vault-relay grew out of [skill-claude-relay](https://github.com/fightingforsidewalk/skill-claude-relay), the first version of this idea. There, each chat had one outbox file, with its unread messages showing in an open pane at the top and its receipts tucked into a hidden block at the foot.

vault-relay is a major revamp, rewritten from the ground up rather than patched:

- One file per message instead of a shared outbox, so a message is never half-edited or lost in someone else's file.
- Receipts, a `done/` hold, and owner-only cleanup.
- The getting-to-done rules, with the one-round-trip limit enforced by the tool.
- Guided setup, "who's in the relay" and built-in help.
- A tool that refuses unsafe edits, with tests that watch every safeguard work.
- A Claude plugin that carries the tool and keeps the relay folder's copy current.
- Support for any AI tool that can run a command, not just Claude.

The original is still available, and still a good fit if you want its simpler, one-outbox-per-chat shape.

## License

MIT. See [LICENSE](LICENSE).

Developed through [Fighting For Sidewalk](https://fightingforsidewalk.com).
