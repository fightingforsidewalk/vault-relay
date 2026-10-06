---
name: vault-relay
description: Runs the vault relay when the person says "relay for you", "relay this to <code>", "who's in the relay", "relay help" or "set up the relay", or uses /vault-relay (alone, or with who, help, setup or to <code>); sends messages to other chats or AI agents through a RELAY folder. Uses the bundled relay tool for every edit.
---

# Vault relay

The relay lets chats that share a vault pass messages through a folder, so the person running them doesn't carry text between them. The rules are in the folder's `README.md`; read it once per session and follow it wherever it says more than this skill. The tool, `relay.py`, does every edit and checks the folder's protocol version itself. Never edit, move, create or delete a relay message, receipt or README by hand, and never write your own script for it.

The tool ships with this skill at `scripts/relay.py` in this skill's folder (the base directory shown when the skill loads). Below, `<bundled>` is that file and `<RELAY>` is the vault's RELAY folder.

## What the person can say

| Say | Or | What happens |
|---|---|---|
| relay for you | /vault-relay | This chat reads what's waiting for it, acts on each message, closes it with a receipt, and reports in one line (section 3). |
| relay this to `<code>` (or relay this for `<code>`) | /vault-relay to `<code>` | Sends what the person just asked for to that sender, as one message that says what done looks like (section 5). The recipient can be another Claude chat or another AI agent working in the same folder. |
| who's in the relay | /vault-relay who | Lists the folder's owner, who may send, and what's waiting, in plain words. Changes nothing (section 4). |
| relay help | /vault-relay help | Shows this list. |
| set up the relay | /vault-relay setup | Asks which folder, which chat owns it and who else joins, sets the folder up, then gives a ready-to-paste block for each chat and a short checklist (section 1). If the relay already exists, says so and shows who's in it. |

For "relay help", reply with a bulleted list and nothing else: one bullet per row of that table, the phrase and its slash form in bold, then what it does in one plain sentence. Like this:

- **relay for you** (or **/vault-relay**): reads what's waiting for this chat, acts on each message, closes it with a receipt, and reports in one line.
- **relay this to `<code>`** (or **/vault-relay to `<code>`**): sends what you just asked for to that sender as one message.
- **who's in the relay** (or **/vault-relay who**): shows the owner, who may send, and what's waiting. Changes nothing.
- **relay help** (or **/vault-relay help**): shows this list.
- **set up the relay** (or **/vault-relay setup**): walks you through setting up a new relay folder.

## 1. Know who you are and where the folder is

Your project instructions should hold one line like this:

```
Relay: sender code <code>; RELAY folder <path>. "Relay for you" or /vault-relay runs the vault-relay skill there.
```

For everything except "set up the relay": if that line is missing, don't guess. Give the person the line in one copyable block, with what you can fill in (the folder path if you can see it; the code is his choice), say it goes in this project's instructions, and stop.

**"Set up the relay"** works with or without the line. Never assume a chat exists or a folder is connected: ask, then check what you can.

- If the folder already has a relay (`README.md`, `pending/` and `done/` are there), say so, run `who` (section 4), and give the line if it's missing. Stop there.
- Otherwise, ask the person in one message:
  1. Which folder should hold the relay? Suggest `00-System/RELAY` in the vault you can see, as a full path.
  2. Which chat owns it? Suggest this one, with a short code (lower-case letters and digits).
  3. Which other chats are joining? A code and a few words for each.
  4. Which time zone should the relay's dates use? Suggest their own, as an IANA name such as America/New_York.
- When he answers, check that you can reach the folder's parent. If you can't, say which folder to connect to this chat and stop.
- Run init, dry run first: `init --relay <RELAY> --owner <code> --time-zone <zone> --senders "code=a few words; code=a few words" --dry-run`, then without `--dry-run`.
  - Same machine (section 2): run it with `python3 <bundled>`.
  - Different machines: first copy `<bundled>` byte for byte to `<RELAY>/relay.py` with the host's file-transfer tool. Then, where the folder is, `python3 <RELAY>/relay.py --version` must print exactly what `python3 <bundled> --version` prints; if it doesn't, stop and tell the person. Then run init with `python3 <RELAY>/relay.py`.
- Then give one ready-to-paste block per chat, each with that chat's code, the folder path and the trigger:
  ```
  Relay: sender code <code>; RELAY folder <path>. "Relay for you" or /vault-relay runs the vault-relay skill there.
  ```
- End with this checklist for the person:
  1. Connect the RELAY folder to each of those chats in the app.
  2. Paste each block into that chat's project instructions.
  3. Say "who's in the relay" in any of them to confirm it's working.

## 2. Pick which copy of the tool to run

- **Same machine.** If the shell that can run `<bundled>` can also see `<RELAY>`, run `<bundled>` directly with `--relay <RELAY>` for everything below. No copy in the folder is needed.
- **Different machines** (for example the skill in the cloud and the vault on the person's computer). Copy `<RELAY>/README.md` and, if it exists, `<RELAY>/relay.py` to where `<bundled>` is, using the host's file-transfer tool, and run `python3 <bundled> install-plan --me <code> --readme <copied README> [--folder-copy <copied relay.py>]`. Do what its first word says:
  - `CURRENT`: carry on with the folder's copy.
  - `INSTALL ...` (only ever said to the owner): copy `<bundled>` byte for byte to `<RELAY>/relay.py` with the host's file-transfer tool, never by retyping it. If that tool can refuse to write when the folder's file changed since you copied it, use that check. Then, where the folder is, run `python3 <RELAY>/relay.py --version`; it must print the text of the plan's last line after `EXPECT `, exactly. If it doesn't, stop, tell the person in one line, and run nothing else with that copy. If it does, add "installed relay.py `<old>` -> `<new>`" to your summary.
  - `WAIT`: repeat its sentence to the person in your summary and carry on with the folder's copy.
  - `NEWER`: the folder's copy is newer than this skill. Carry on with it, never replace it, and mention that the skill may need updating.
  - `MISSING`: there's no copy and you aren't the owner. Tell the person in one line and stop.

  Then run every command below with the folder's copy, on the machine where the folder is.

Below, `<tool>` means whichever copy this step chose: `python3 <bundled>` on the same machine, or `python3 <RELAY>/relay.py` otherwise. Always pass `--relay <RELAY>`. Installing the tool is the only time you write a file into the folder yourself; every message, receipt and move goes through `<tool>`.

## 3. "Relay for you" (or /vault-relay)

1. `<tool> list --me <code> --full`. It shows what's pending for you as ACTION, then as FYI, each with a `seen` hash.
2. If it prints a NOTE about the protocol version, or a STOP line for any file, put that in your reply to the person. Don't act on a STOP file.
3. FYI messages: read them. Never reply because of one, and never edit or move one.
4. Each ACTION message, oldest first:
   a. Do or decide what it asks, and record the outcome in your own documents.
   b. `<tool> consume <id> --me <code> --seen <hash> --receipt "<what was done; docs touched, with versions>"`. This adds your receipt and moves it to done/.
   c. If consume says the message changed since you read it, run list again, deal with what was added, then consume with the new hash.
   d. If you can't finish it, leave it pending and name what blocks it in your reply to the person.
5. Send at most one message to any one recipient, and only when the next section says to.
6. If you are the folder's owner (`Owner:` in its README): `<tool> prune --me <code> --dry-run`, then `<tool> prune --me <code>`. It deletes consumed messages past the 14-day hold, nothing else. If it stops because deleting isn't permitted, ask the host for delete permission on the RELAY folder once if it offers that, otherwise tell the person in one line. Never prune if you aren't the owner.
7. End the turn with nothing pending for you as ACTION, or with one line to the person naming the blocker. Summarise the pass in one line, for example "Relay: consumed 2026-10-03-planner-to-builder-a; read 1 FYI; pruned 2; installed relay.py 1.1 -> 1.2", or "Relay: nothing for `<code>`".

## 4. "Who's in the relay" (or /vault-relay who)

Run `<tool> who --me <code>` and report it in plain words, for example: "Owner planner. Senders: planner (planning chat), builder (build chat), reviewer (review chat). Pending: 1 from planner to builder, since 2026-10-02." Change nothing.

## 5. Sending a message

**"Relay this to `<code>`"** (or "relay this for `<code>`", or /vault-relay to `<code>`) is the person asking you to send something now. Turn what they asked for into one message to `<code>`: a one-line "done when" and a body with everything the recipient needs to finish in one pass, asks numbered at the end. If what done looks like isn't clear from the conversation, ask once. Then post it as below and report the message ID in one line. Check `<code>` against the README's sender list first; if it isn't there, say so and stop. The rules below still apply.

Otherwise, send only when the message you're answering asks for something back, or your answer changes what the sender will do. Never send thanks, "received", "noted" or a status update; your receipt already says it.

```
<tool> post --relay <RELAY> --from <code> --to <recipient> \
  --done-when "<one line: what finishes this>" [--fyi <code>] [--re <id you are answering>] --body - <<'BODY'
<Plain prose with everything the recipient needs to finish in one pass.>

1. <Ask.>
2. <Ask.>
BODY
```

- If the tool says you already have a message pending for that recipient, add `--add` (and drop `--done-when` unless it changes). That adds to the waiting message instead of sending a second; keep `--re` if you're answering something.
- If it refuses a third message on one thread, don't send it. Put the question to the person in your reply as a decision with options. Only use `--ruled` after they have ruled.
- Never put secrets, credentials, keys, recovery codes, personal data, or anything from another venture's vault in a message.

`--dry-run` on post, consume, prune or init shows what would happen without changing anything.

## When something looks wrong

`<tool> check --relay <RELAY>` checks the whole folder. Report what it finds to the person. Fix nothing by hand; only the folder's owner changes the README.
