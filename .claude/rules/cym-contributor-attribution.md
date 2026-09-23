# CYM-NM28C5 contributor attribution rules

## Birol Tellioglu — always use @birolt29, NEVER his real name or personal email

Any reference to contributor **Birol** or **Birol Tellioglu** in any content written
or edited in this repository **must use the GitHub handle `@birolt29`** instead.
This applies to his **personal email address too** — never write it anywhere in this
repo (commit author/committer field, Co-Authored-By trailer, comments, docs, release
notes). If a commit needs a machine-readable attribution trailer for him, use his
GitHub noreply address (`birolt29@users.noreply.github.com`) — never his real email.

This is a standing, emphasized instruction from Jim (2026-09-23): "That maut be a rule
when giving credit for development or patches" — apply it every time a patch, commit,
or piece of content credits @birolt29, not just when explicitly reminded.

This applies to ALL repo content:
- README.md
- Release notes (GitHub Releases body text)
- Wiki pages
- CLAUDE.md and .claude/rules/*.md
- Changelog / commit messages that credit contributors
- In-code comments that credit contributors
- Any other documentation
- Patch files / diffs he submits — when writing the commit that applies one of his
  patches, credit him as `@birolt29` in the commit message body, never his real name,
  and never put his personal email in the commit's author/committer/trailer fields.

**Rule:** If you are about to write "Birol", "Birol Tellioglu", or his personal email
address, write `@birolt29` (or the GitHub noreply address, for a machine trailer) instead.

```
// WRONG
"Thanks to Birol for the DMA patch"
"Birol Tellioglu contributed the wardrive GPS fix"
Co-Authored-By: Birol Tellioglu <his.real@email.example>

// CORRECT
"Thanks to @birolt29 for the DMA patch"
"@birolt29 contributed the wardrive GPS fix"
Co-Authored-By: @birolt29 <birolt29@users.noreply.github.com>
```

**Also apply retroactively** when editing any existing file that contains "Birol" or
"Birol Tellioglu" — replace all occurrences with `@birolt29` in the same edit. Note:
per Jim (2026-09-23), this retroactive cleanup does NOT extend to rewriting historical
git commits that already picked up the real-name/email line — only new content and new
commits going forward need to get this right.

## @birolt29 is a co-developer, not "a contributor" (as of v2.15.00)

As of the v2.15.00 screen-orientation patch, @birolt29's role has been formally
upgraded from contributor to **co-developer**, reflecting the scope of the landscape
mode feature, WiFi list redesign, dual-band Handshaker, and the many crash/navigation
fixes shipped alongside it — on top of the substantial prior patch history already
credited in `Contributors.md` and `README.md`.

**Rule:** When introducing or describing @birolt29 in any new content (README,
release notes, wiki, commit messages), use "co-developer" — not "contributor" —
as the primary descriptor. Existing prose that already lists specific
contributions in detail does not need to be rewritten purely to insert the word,
but the section/tier heading and any summary line should say co-developer.

```
// WRONG (as of v2.15.00)
"@birolt29, an extraordinary contributor..."
"Thanks to contributor @birolt29 for the screen orientation feature"

// CORRECT
"@birolt29, co-developer of CYM..."
"Thanks to co-developer @birolt29 for the screen orientation feature"
```

This applies to the same content list above (README, release notes, wiki, CLAUDE.md
and rules, changelog/commit messages, in-code comments).
