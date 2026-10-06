# Release notes

## vault-relay 1.3.1

*Released 2026-10-06 · relay protocol v2.2 · Python 3.9+ · standard library only · MIT License*

Plain-file mail for AI chats that share a folder, with rules that stop them chatting. You decide when anyone checks it.

vault-relay 1.3.1 changes how sending works, and nothing else. "Relay for you" is now said only to the chat that should pick up its messages. Sending never needs a phrase.

### Highlights

- **Sending needs no phrase.** Ask a chat to send something, in any words, or say yes to a message it drafted, and it posts it straight away. It then tells you in one line which chat to prompt, by sender code and plain name, for example "Posted 2026-10-06-studio-to-marcel-b; tell the Marcel chat (marcel) 'relay for you'."
- **"Relay for you" is for the receiving chat only.** A chat will never ask you to say it so that it can send something.
- **"Relay this to `<code>`" still works** as one way of asking a chat to send.

### Commands you can say

| Say | Or type | What happens |
|---|---|---|
| relay for you | `/vault-relay` | Said to the chat that should pick up its messages. It reads what's waiting, acts on each message, closes each one with a receipt, and reports in one line. |
| (no phrase needed) | `/vault-relay to <code>` | Ask for a message to go, or approve one the chat drafted. It's posted straight away and the chat tells you which chat to say "relay for you" to. **Changed in 1.3.1.** |
| who's in the relay | `/vault-relay who` | Lists the owner, the senders and what's waiting. Changes nothing. |
| relay help | `/vault-relay help` | Lists these phrases and what they do. |
| set up the relay | `/vault-relay setup` | Walks you through setting up a new relay folder. |

Other agents learn the same behaviour from `AGENTS.md`.

### Upgrading from 1.3

Install the 1.3.1 plugin. Only the skill's instructions, `AGENTS.md` and the README changed; `relay.py` is still 1.3, so nothing is reinstalled into relay folders. Agents that use `AGENTS.md` need the new copy. Message files, receipts, the README format and the folder layout are unchanged.

### Known limitations

Unchanged from 1.3.

### Getting it

- **As a plugin, for Claude:** install `vault-relay.plugin` from this release.
- **For other agents:** download `AGENTS.md` from this release and replace your copy. `relay.py` is unchanged from 1.3.
- **Build it yourself:** `python3 packaging/build.py` packs the plugin from this repository.

### License

vault-relay is released under the MIT License. See `LICENSE`. Developed through Fighting For Sidewalk.

---

## vault-relay 1.3

*Released 2026-10-05 · relay protocol v2.2 · Python 3.9+ · standard library only · MIT License*

Plain-file mail for AI chats that share a folder, with rules that stop them chatting. You decide when anyone checks it.

vault-relay 1.3 opens the relay to AI agents beyond Claude. Any agent that can work on files in the relay folder and run `python3` can now take part, with its own instructions file, and a Claude chat can send work to it with one phrase.

### Highlights

- **Works with other AIs.** A new `AGENTS.md` gives any agent (Codex, Gemini CLI, Copilot or Cursor in agent mode, and others like them) the same routine Claude follows: its sender code and relay folder, "relay for you", "relay this to", "who's in the relay" and "relay help", with every edit going through `relay.py`. Many agents read `AGENTS.md` on their own.
- **Send with one phrase.** "Relay this to `<code>`" (or "relay this for `<code>`") turns what you just asked for into one message to that sender, with what done looks like and everything needed to finish. The recipient can be another Claude chat or another agent.
- **Easier help.** "Relay help" now answers with a short bulleted list, each phrase in bold with what it does.

### Commands you can say

| Say | Or type | What happens |
|---|---|---|
| relay for you | `/vault-relay` | The chat reads what's waiting for it, acts on each message, closes each one with a receipt, and reports in one line. |
| relay this to `<code>` | `/vault-relay to <code>` | Sends what you just asked for to that sender as one message. **New in 1.3.** |
| who's in the relay | `/vault-relay who` | Lists the owner, the senders and what's waiting. Changes nothing. |
| relay help | `/vault-relay help` | Lists these phrases and what they do. |
| set up the relay | `/vault-relay setup` | Walks you through setting up a new relay folder. |

Other agents learn the same phrases from `AGENTS.md`.

### Safety

The tool's behaviour is unchanged from 1.2, and so are its six promises: it never overwrites a name or a file the caller doesn't own; it deletes nothing except what the owner prunes past the hold; consuming moves exactly one file; every write goes through a temporary file and a rename; malformed files stop the run; and protocol version mismatches are flagged. The same 91 tests and the mutation check run against 1.3.

A message to another AI is read by that provider's model, so the rule against putting secrets, credentials or personal data in a message matters even more once the relay crosses providers. `AGENTS.md` says so to every agent that reads it.

### Upgrading from 1.2

1. Install the 1.3 plugin. In a folder whose owner is a Claude chat on another machine, the owner's next "relay for you" installs `relay.py` 1.3 into the relay folder and says so.
2. To add a non-Claude agent: put its code in the relay folder's README sender list, copy `AGENTS.md` into the folder the agent works in, and fill in its Relay line.

Message files, receipts, the README format and the folder layout are unchanged.

### Known limitations

- Only agents that can work on files in the relay folder on your machine can take part. A chat that lives only in a browser tab can't.
- The routine in `AGENTS.md` has been run end to end as written, in both directions, but not yet by a non-Claude agent. Reports of what worked are welcome as issues.
- A sender code is taken on trust, not proved, and the relay is built for one chat at a time. Both as in 1.2.

### Getting it

- **As a plugin, for Claude:** install `vault-relay.plugin` from this release.
- **For other agents:** download `relay.py` and `AGENTS.md` from this release, put `relay.py` in your relay folder, and `AGENTS.md` where the agent works.
- **Build it yourself:** `python3 packaging/build.py` packs the plugin from this repository.

See the README's "Works with other AIs" section for setup.

### License

vault-relay is released under the MIT License. See `LICENSE`. Developed through Fighting For Sidewalk.

---

## vault-relay 1.2

*Released 2026-10-03 · relay protocol v2.2 · Python 3.9+ · standard library only · MIT License*

Plain-file mail for AI chats that share a folder, with rules that stop them chatting. You decide when anyone checks it.

vault-relay is the successor to [skill-claude-relay](https://github.com/fightingforsidewalk/skill-claude-relay): a major revamp, rewritten from the ground up with expanded functionality. The original remains available.

Works with any folder of Markdown files (an Obsidian vault, a VS Code workspace, a plain folder) and any AI tool that can run a Python command. Claude gets a ready-made skill and plugin.

vault-relay 1.2 turns the tool into something you can set up, run and keep tidy by asking for it in plain words. Setup now takes one conversation, the folder cleans up after itself, and the skill carries its own copy of the tool and keeps the relay folder's copy current.

### Highlights

- **Guided setup.** Say "set up the relay" and the chat asks three questions: which folder, which chat owns it, and which other chats are joining. It creates the folder, then gives you a ready-to-paste block for each chat and a short checklist to finish.
- **See who's in the relay.** "Who's in the relay" lists the folder's owner, every sender with a short description, and what's waiting between whom, with the oldest date. It only reads.
- **Built-in help.** "Relay help" lists every phrase you can say and what each one does.
- **Automatic cleanup.** `done/` is now a short hold rather than an archive. The folder's owner clears consumed messages once they are 14 days old, and nothing else is ever deleted.
- **The skill keeps the tool up to date.** The skill ships with its own copy of `relay.py`. If the chat and the folder are on the same machine, it runs that copy directly. If they aren't, the owner's chat installs its copy into the relay folder whenever the two differ, never over a newer copy, and says so in its summary.

### Commands you can say

| Say | Or type | What happens |
|---|---|---|
| relay for you | `/vault-relay` | The chat reads what's waiting for it, acts on each message, closes each one with a receipt, and reports in one line. |
| who's in the relay | `/vault-relay who` | Lists the owner, the senders and what's waiting. Changes nothing. |
| relay help | `/vault-relay help` | Lists these phrases and what they do. |
| set up the relay | `/vault-relay setup` | Walks you through setting up a new relay folder. |

### New in the tool

- `who`: owner, time zone, senders with descriptions, and pending counts per sender and recipient. A message that has its receipt but hasn't been moved yet is shown separately rather than counted as waiting.
- `init`: sets up a folder with no relay yet. It writes `README.md` with the owner, the time zone, the sender list and the rules, plus `pending/` and `done/`, and refuses if any of them already exist.
- `prune`: owner only. It deletes messages in `done/` whose receipt is older than the hold (14 days by default, set with `--days`). It never touches `pending/`, the README or the tool. If the folder is in a git repository, it only removes files that are committed and unchanged, so a copy always stays in your history. If the host blocks deletes, it stops cleanly and says so.
- `install-plan`: tells the skill whether to install its copy of the tool into the relay folder, and how to check the result.
- `--version` now prints the file's own hash as well as the version, so an install can be checked byte for byte.
- The README now carries an `Owner: <code>` line, which prune and installs read, and a `Time zone: <IANA name>` line for the relay's dates (America/New_York when absent). Setup asks for both.
- `check` warns when no owner is named.

### Safety

Every promise the tool makes is covered by tests that watch it refuse. A mutation check then switches off each safeguard in turn and confirms the tests catch it. In 1.2 that covers:

1. It never overwrites a name or a file the caller doesn't own.
2. It deletes nothing, except that `prune`, run by the owner, removes consumed messages past the hold.
3. Consuming a message moves exactly that one file.
4. Every write goes through a temporary file and a rename, so nobody ever reads half a message.
5. A file with malformed properties stops the run instead of being guessed at.
6. A protocol version mismatch is flagged. A different major version stops every command that writes.

### Upgrading from 1.1

1. Install the 1.2 plugin, or replace `relay.py` with the 1.2 copy.
2. Add an `Owner: <code>` line to your relay folder's `README.md`, naming the chat that owns the folder. Without it, nobody can prune, and the skill won't install updates into the folder.
3. Change the README's header line to `RELAY PROTOCOL v2.2`. A README still at v2.1 keeps working, but `check` and `list` will flag it.
4. Optionally add a `Time zone: <IANA name>` line. Without one, dates stay in New York time, as before.

Message files, receipts and the folder layout are unchanged. Nothing needs converting.

### Known limitations

- A sender code is taken on trust, not proved. Any chat with the folder connected could claim another chat's code, so the real boundary is which folders you connect to which chats.
- The relay is built for one chat at a time. Two chats writing at the same instant aren't guarded against.
- Some hosts block deletes in connected folders until you allow them. `prune` stops and tells you when that happens.

### Getting it

- **As a plugin:** install `vault-relay.plugin` from this release. It contains the skill with the tool bundled.
- **The tool on its own:** download `relay.py`. There's nothing to install. On Windows, run `pip install tzdata` first.
- **Build it yourself:** `python3 packaging/build.py` packs the plugin from this repository.

See the README for the full rules, the folder layout and every command.

### License

vault-relay is released under the MIT License. See `LICENSE`. Developed through Fighting For Sidewalk.

---

## Earlier versions

### vault-relay 1.1

*Relay protocol v2.1*

- Support for protocol v2.1.
- A README on a later minor version is now a warning rather than an error, so a small rules change doesn't stop the relay. A different major version still stops every command that writes.

### vault-relay 1.0

*Relay protocol v2.0, first release*

- One file per message, in `pending/` until it's consumed and in `done/` afterwards with its receipt.
- `list`, `post`, `consume` and `check`, with `--dry-run` on every write.
- One waiting message per sender and recipient. More goes in with `--add`.
- The third message on a thread is refused until you've ruled.
- `consume` refuses a message that changed after the chat read it.
- `check` ignores macOS `.DS_Store` files.
- The six safety guarantees above, apart from prune, each tested and each test seen failing when its safeguard is switched off.
