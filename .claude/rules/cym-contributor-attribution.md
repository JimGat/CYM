# CYM-NM28C5 contributor attribution rules

## Birol Tellioglu — always use @birolt29

Any reference to contributor **Birol** or **Birol Tellioglu** in any content written
or edited in this repository **must use the GitHub handle `@birolt29`** instead.

This applies to ALL repo content:
- README.md
- Release notes (GitHub Releases body text)
- Wiki pages
- CLAUDE.md and .claude/rules/*.md
- Changelog / commit messages that credit contributors
- In-code comments that credit contributors
- Any other documentation

**Rule:** If you are about to write "Birol" or "Birol Tellioglu", write `@birolt29` instead.

```
// WRONG
"Thanks to Birol for the DMA patch"
"Birol Tellioglu contributed the wardrive GPS fix"

// CORRECT
"Thanks to @birolt29 for the DMA patch"
"@birolt29 contributed the wardrive GPS fix"
```

**Also apply retroactively** when editing any existing file that contains "Birol" or
"Birol Tellioglu" — replace all occurrences with `@birolt29` in the same edit.

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
