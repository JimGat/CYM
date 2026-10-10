# Official Cases — Wiki updates staged for the next release

**Not published to the live Wiki yet.** Jim requested that the Official Cases documentation ship with the next release. The edited Wiki pages here are tracked on `Jimgat_Dev` so the changes can be reviewed without prematurely updating the live Wiki.

## Baselines

- Case package import: `6f39934b5bd68354e63006015dc40b0695859599`.
- Wiki source baseline: `73bc709628b6d4682cb5b0abf9b9ec5fa3dce953` (`JimGat/CYM.wiki`, `master`).
- Original case files remain under `docs/cases/birolt29/`; their hashes are recorded in `SOURCES.json` and `SHA256SUMS`.

## Included pages

- `Official-Cases.md` — new official catalog, all 12 manuals, models, original photos, licenses, source links and separate assembly caveats.
- `Home.md` — official collection prominently before Supported Hardware.
- `Where-To-Get-It.md` — official collection first; three older RF-HAT/community designs retained as alternatives.
- `Getting-Started.md` — official-case/manual entry point before assembly/setup.
- `Contributors.md` — co-developer credit with preserved original joint design attribution.
- `Classic-CYD-Support.md`, `Waveshare-WS-C5-28-Support.md`, `Hosyond-ESP32-S3-Family.md` — board-specific case entry points and caveats.

## Release operator procedure

1. Obtain Jim’s explicit release authorization; do not merge `main`, publish a release or push the Wiki as part of this documentation-only integration.
2. Verify `sha256sum --check docs/cases/birolt29/SHA256SUMS` from the CYM repository root.
3. Promote the case packages and repository documentation to `main` through the normal authorized release workflow. The staged Wiki catalog’s `blob/main/` file links intentionally target that release, not a pre-release Wiki publication.
4. Fetch the Wiki and compare its latest `master` with `73bc709628b6d4682cb5b0abf9b9ec5fa3dce953`. If it changed, merge **only the official-case edits** into the new Wiki pages; do not blindly overwrite newer content with these snapshots. Preserve unrelated page fixes.
5. Reconcile existing Classic GPS / S3 support statements against that release’s actual qualified profiles. The official-case edits do not certify the case manual’s Classic CN1 IO22/IO27 wiring; preserve the separate GPIO1/P3 caution until exact-board verification resolves it.
6. Verify the official collection is first and all old case links still appear under Alternatives. Check all 12 PDF links, model/image links and attribution/license text. Do not claim separately promised HTML/CAD files were received.
7. Commit the Wiki updates using the project’s normal authorship policy, push `master` only after release authorization, then read back the exact remote head and rendered pages. Record both project and Wiki commit IDs.
