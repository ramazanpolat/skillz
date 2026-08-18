---
name: living-docs
description: Keep a repo's living documents in the root and retire stale ones into history/. Set up the convention in a project, retire a superseded doc, promote a draft to accepted, or show what is live vs retired. Use when a repo's design/spec/plan docs should have exactly one current version in the root and everything superseded moved aside — not deleted.
---

# /living-docs

A convention for repositories whose important documents evolve: **the root holds
what is true now; `history/` holds what used to be true.** A reader who opens the
repo sees only the current picture. Nothing is deleted — superseded documents are
moved aside, where they remain accurate records of what was believed when they
were written.

This skill explains the convention and performs its four operations. It is
document-type agnostic: it works for `DESIGN.md`, `SPEC-v*.md`, `RFC-*.md`,
`PLAN-*.md`, `ARCHITECTURE.md` — anything versioned.

## The convention

**One current version per document, in the root.** If a document has versions,
exactly one is *accepted* and lives in the root. Superseded versions live in
`history/`.

**A draft sits beside the accepted version, never on top of it.** Work in
progress is a draft — `SPEC-v3-draft.md` beside the accepted `SPEC-v2.md`. A
proposal that has already replaced the thing it proposes to replace cannot be
rejected, so the accepted version stays untouched until a human accepts the
draft. Multiple drafts of the same version may coexist in the root so any two
can be diffed.

**A current version stands alone — it never refers back to what it replaced.**
No "supersedes v2", no "what changed since", no changelog paragraph. Every
back-reference is a sentence the reader must resolve against a document they do
not have open, and they accumulate. `history/` keeps the old version and git
keeps the diff; the *story of the change belongs in the commit message*. The
test: a reader who has never seen an earlier version should notice nothing
missing.

**`history/` is read-only.** A retired document is not corrected, not repointed
when a path moves, not updated when a fact changes. Its whole value is being an
accurate record of what was true when written; editing it produces something
that is neither that nor current. The one edit it may receive is being marked
retired.

**Why not just delete.** A deleted document is gone from the working tree and
buried in git history nobody reads. A retired one is a browsable record: why a
decision was made, what was tried, what a path used to mean. Cheap to keep,
expensive to reconstruct.

## Operations

Determine intent from the user's words, then run the matching operation. All git
operations happen in the repository containing the current working directory;
confirm it is the intended repo if ambiguous.

### `init` — set the convention up in this repo

Triggered by "set up living docs", "add the root/history convention", "init
living-docs".

1. Create the retired-documents directory if absent:
   ```bash
   mkdir -p history
   ```
2. Add the convention to the repo's `CLAUDE.md` (create it if absent) so every
   agent working here follows it. Append the block in **The CLAUDE.md block**
   below, adapting `<DOC>` to the repo's actual document names if known.
3. If the repo has documents that are clearly superseded already, list them and
   offer to `retire` each — do not move anything without confirmation.
4. Report what was created and changed, with absolute paths.

### `retire <path>` — move a superseded document to history/

Triggered by "retire <file>", "this doc is stale", "move <file> to history".

1. Confirm the file is genuinely superseded, not merely old. If unsure, ask.
2. Move it with git so history is preserved as a rename:
   ```bash
   git mv <path> history/<basename>
   ```
   If the repo is not a git repo, `mkdir -p history && mv <path> history/`.
3. Optionally mark it retired inside the file — a single line near the top,
   e.g. `> Retired 2026-08-13 — superseded by <name>.` This is the *only* edit
   a retired document may receive.
4. Do **not** edit any other retired document, and do **not** update
   cross-references inside `history/` — retired paths are stale on purpose.
5. Repoint the **live** documents (README, index) that referenced the retired
   file, so nothing current points into `history/` by accident.

### `accept <draft> [<name>]` — promote a draft to the accepted version

Triggered by "accept <draft>", "make <draft> the current version", "promote".

1. Rename the draft to its accepted name, dropping the `draft` marker:
   ```bash
   git mv SPEC-v3-draft.md SPEC-v3.md
   ```
   If the user gave a target `<name>`, use it.
2. Flip any status marker in the file from `draft` to `accepted` (a
   `**Status:**` line, or similar). Leave the body untouched — the accepted
   version is byte-identical to the draft that was reviewed.
3. Retire the version it replaces (`retire` above): `git mv SPEC-v2.md history/`.
4. Decide, with the user, whether *other* drafts of the version retire now or
   stay in the root for diffing. Default: ask; do not sweep them silently.
5. Repoint the README/index at the newly accepted file.
6. The changelog — what changed and why — goes in the **commit message**, not in
   the accepted document.

### `status` — show what is live vs retired

Triggered by "living-docs status", "what's current here".

```bash
echo "=== live (root) ==="; ls *.md 2>/dev/null
echo "=== retired (history/) ==="; ls history/*.md 2>/dev/null
```
Then say, in one line, which document is the accepted current version and whether
any drafts are open beside it.

## The CLAUDE.md block

Append this to the target repo's `CLAUDE.md` on `init`. Adapt `<DOC>` to the
repo's real document family (e.g. `SPEC`, `DESIGN`, `RFC`).

```markdown
## The root holds what is current; history/ holds what used to be

Living documents (`<DOC>-*.md`, the README, and any open drafts) live in the
repository root. Everything superseded lives in `history/`, which is read-only.

- **One accepted version in the root.** If `<DOC>` is versioned, exactly one is
  accepted; superseded versions move to `history/`.
- **A draft sits beside the accepted version, never on top of it.** It carries a
  `draft` marker and does not displace the accepted version until a human accepts
  it. Drafts of the same version may coexist in the root for diffing.
- **A current version never references an older one** — no "supersedes", no
  changelog paragraph. `history/` keeps the old version and git keeps the diff;
  the story of the change goes in the commit message. Test: a reader who never
  saw an earlier version notices nothing missing.
- **`history/` is read-only.** A retired document is a record of what was true
  when written, not something to maintain. The only edit it may receive is being
  marked retired.
- **Retire, never delete.** A superseded document is moved aside, not removed —
  it is the browsable record of why a decision was made.
```

## Notes

- This skill governs *documents*, not code. Code lifecycle is git's job.
- It composes with heavier disciplines a project may add on top — an executable
  companion per document version that never itself gets edited (author a new
  revision instead), or a frozen set pairing a document with the evidence that
  proved it. Those are optional extensions of the same idea (the root is
  current, superseded things are moved aside and frozen), not part of this
  skill.
- Keep the accepted document's *own* record of what is unresolved inside it — an
  "Open questions" section that a new version carries forward — rather than in a
  separate tracker, so the picture and its gaps stay together.
</content>
</invoke>
