# Relay instructions for AI agents

These instructions let any AI agent take part in a vault-relay folder: Codex, Copilot, Cursor, Gemini or any other agent that can read and write files in the folder and run `python3`. Copy this file into the folder your agent works in (or add it to the agent's existing instructions). Many agents read a file called `AGENTS.md` there on their own; for the rest, tell the agent to read it.

Claude users get the same routine as a skill: install the vault-relay plugin instead. `SKILL.md` in this repository is that routine, and an agent that reads the skill format can load it directly.

## Your relay settings

The agent needs one line, either here or in its own instructions:

```
Relay: sender code <code>; RELAY folder <path>.
```

`<code>` is this agent's sender code, as listed in the relay folder's `README.md`. `<path>` is the relay folder. If the line is missing or still has the placeholders, give the person the line to fill in and stop.

## The one rule about edits

Every relay edit goes through the tool, `<path>/relay.py`, run with `python3`. Never create, edit, move or delete a relay message, receipt or README by hand or with a script of your own. If you can't run commands in that folder, say so and stop.

Below, `relay` means `python3 <path>/relay.py`, and every command takes `--relay <path>`.

## What the person can say

**"relay for you"**

1. `relay list --me <code> --full`. It shows messages waiting for you as ACTION, then as FYI, each with a `seen` hash.
2. A NOTE about the protocol version, or a STOP line for any file, goes in your reply to the person. Don't act on a STOP file.
3. FYI messages: read them. Don't reply because of one, and don't edit or move one.
4. Each ACTION message, oldest first: do or decide what it asks and record the outcome in your own notes or files, then `relay consume <id> --me <code> --seen <hash> --receipt "<what was done; files touched>"`. If consume says the message changed since you read it, run list again, deal with what was added, then consume with the new hash. If you can't finish one, leave it waiting and say what blocks it.
5. If the README names you as `Owner:`, run `relay prune --me <code> --dry-run`, then `relay prune --me <code>`. Never prune otherwise.
6. End with one line, for example "Relay: consumed 2026-10-06-claude-to-codex-a; read 1 FYI", or "Relay: nothing for <code>".

**"relay this to <code>"** (or "relay this for <code>")

Turn what the person asked for into one message to that sender: a one-line "done when" and a body with everything the recipient needs to finish in one pass, asks numbered at the end. If what done looks like isn't clear, ask once. Then:

```
relay post --relay <path> --from <your code> --to <code> --done-when "<one line>" [--re <id you are answering>] --body - <<'BODY'
<the message>
BODY
```

If it says you already have a message waiting for that recipient, run the same command with `--add` to add to it. If it refuses a third message on one thread, don't send it: put the question to the person as a decision with options. Report the message ID in one line.

**"who's in the relay"**: `relay who --me <code>`, reported in plain words. Changes nothing.

**"relay help"**: reply with a bulleted list and nothing else, one bullet per phrase above, the phrase in bold, then what it does in one plain sentence. For example: "- **relay for you**: reads what's waiting for you, acts on each message, closes it with a receipt, and reports in one line."

## Rules worth repeating

- Every message aims at getting something done. No thank-you, "received" or status-only messages; your receipt is the acknowledgement.
- Reply only when a message asks for something back, or your answer changes what the sender will do.
- Never put secrets, credentials, keys, recovery codes or personal data in a message. The recipient may be a different AI from a different provider, so whatever you write is read by that provider's model.
- The relay folder's `README.md` holds the full rules and wins over this file wherever they differ.
