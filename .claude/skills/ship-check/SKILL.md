---
name: ship-check
description: "Pre-ship checklist for any script, tool, or repo the agent writes or packages, run before code leaves the session and before the handback is written: path traversal, command injection, secrets and names, placeholders, .gitignore, license, atomic writes, and proof that every guard has been seen to fail. Use it whenever a session is about to hand back a change that ships executable code, and name the sections that did not apply."
---

# Ship check

Run this before any script, tool, or repo you wrote leaves your hands, and before the
handback is written. State the result in the handback, never as a bare "clean": what was
fixed, or "clean" followed by which sections did not apply and why. A check run silently is
indistinguishable from one skipped. The reasoning behind each item is in `SHIP-CHECK.md` at
the root of the claude-code-discipline package
(https://github.com/fightingforsidewalk/claude-code-discipline).

1. INPUT THAT BECOMES SOMETHING ELSE. Paths: allow-list the characters AND resolve-and-contain
   the final path, tested with `../../x`, `x/../../y`, `..`. Shell: argument lists, never a
   string built from input. Format strings, regex, SQL, HTML: ask of every input what language
   it lands in, and escape or parameterise for that language. File content that is also
   syntax (comment delimiters, fences, front-matter): refuse or escape.

2. NOT IN THE FILES. Secrets, referenced by location and rotation path, never by value; grep
   for `key`, `token`, `secret`, `password`, `://`. Names, when the artefact is for others:
   people, companies, products, internal roles, local paths. Unresolved placeholders (`TODO`,
   `TBD`, `<your-handle>`, `example.com`): fill, remove, or name as the human's to fill.
   Session-specific paths. Invisible characters: scan the final bytes for anything below
   `0x20` that is not newline or tab, plus `0x7F`, U+2028 and U+2029, and write them in
   source as escape sequences rather than literals.

3. REPO HYGIENE. `.gitignore` present and not ignoring folders the human's data will live in.
   `LICENSE` present and its holder intentional. Every referenced file exists, README links
   resolve, the layout section matches the tree's visible files — dotfiles and repo
   housekeeping (`.gitignore`, `.editorconfig`, `.github/` and the like) are not listed there
   — a section number cited in one file exists in the other. Front-matter parses: a Markdown
   file with YAML front-matter goes through a parser before packaging, never an eyeball, and a
   `description:` value carrying a colon-space is quoted, or YAML reads the colon as a nested
   key and a strict loader refuses the file. Help text and docstrings match current
   behaviour.

4. WRITES AND FAILURE. Atomic writes: temp file then replace. Assert invariants before
   mutating, so a failed assertion leaves the file untouched. Fail loudly with a reason a
   human can act on. Refuse the dangerous case rather than warn, when refusing is free.

5. PROVE THE GUARDS, IN ORDER. Feed every refusal the input it should refuse and show the
   refusal in the handback; then run the happy path once more. When FIXING a defect:
   reproduce it against the unfixed code and show it, then fix, then show it refused.
   Verifying only after the fix cannot distinguish "the guard works" from "the defect was
   never there". If reproduction is impractical, say so and say what was checked instead.
   Applies to correctness and security claims, not to docs, copy or renames. A comment
   asserting a verification is itself a claim and carries who established it and how.

6. BEFORE PACKAGING. Run sections 1, 2 and 5 on the final tree, not the draft. List every file
   going out. Name any section that did not apply and why. If a second reviewer exists
   (another chat, a linter, a scanner), say so and invite it.
