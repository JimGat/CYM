# Evidence corrections and superseded-input handling

This record captures corrections supplied by co-developer @birolt29 through Jim.
It is not an independent re-execution of the historical reports. No new report
attachments or kit v2 were supplied with this correction message. The historical
findings below have not been revalidated on v3.0.44.

## Technical corrections

- Package D's claim that HAT inhibition was unwired in v3.0.43 was incorrect.
  `main.c` includes `hat_tx_runtime.inc`; its UI callback invokes
  `hat_tx_inhibit()`. It is a runtime-only four-HAT control, not a global or
  persisted TX-off policy. The D design review already corrects this premise.
- Patch24's submitted mutant accepted any nonzero exit, its no-data orphan prose
  contradicted the covering report, and its reported builds covered four profiles,
  not nine. The v3.0.44 integration `d11dc2ce94c9ba994c6e1cc970724d048058fd50`
  corrected lifecycle/navigation handling and test acceptance. The no-data modal
  was not reported orphaned through touch navigation. Final integration software
  gates include all nine profiles; contributor bench observations remain separate.
- The earlier Package A test lacked mutation sensitivity and used a modeled
  BLE_HS_EINVAL value of -6 rather than installed SDK value 3. It was not accepted
  as adequate regression protection. The maintained corrected test and
  `package-a-corrected-coverage.md` describe the actual evidence boundaries.
- Package G v1 did not include mutation sensitivity and did not establish safe
  partial-deinit readiness/re-entry. The integration separated readiness from
  retained ownership and tested failure/retry sequences. Do not cite the original
  v1 test as proof of the corrected complete lifecycle.

## Historical FSD findings — reported, current status unknown

The following correction describes the reports dated 2026-10-28. Entries in one
report are not assumed to share a root cause merely because they appear together.

| Report | Corrected interpretation | Required follow-up |
|---|---|---|
| A, NM-CYD-C5 landscape | One crash and Bluetooth row NOK were reported | Inspect original trace; reproduce on exact current artifact |
| D, Hosyond S3-35 | One crash, Infrared row NOK and 13 INCOMPLETE rows were reported | Inspect trace and incomplete reasons; do not call the run fully proven |
| All four | Blackout reportedly entered its TX screen without a warning popup | Open consent-path finding; verify before any authorized active test |
| B | NFC/RFID Home check failed | Trace actual route and destination; rerun both navigation layouts |
| All four | Start Wardrive TX-warning failures were false findings: Wardrive is passive | Contributor reports later FSD correction; verify the actual supplied tool version before claiming it installed |
| Clock screenshot | `proof-A-landscape-Clock-popup-CRIT.png` depicts Clock Settings, not the Clock Mode popup described in the mail | Do not use that image as evidence about the other popup |

Neither historical crash nor the Blackout finding is declared fixed or confirmed
present in v3.0.44. INCOMPLETE is not PASS. A mail's general confidence statement
does not supersede raw failure/incomplete rows. Do not perform uncontrolled RF
operations while investigating consent; use source review and instrumented
non-transmitting paths first, with separately authorized physical testing.

## Superseded inputs and publication exclusions

- Discard the incoming Patch22 local version suffix `v3.0.41-12` and its supplied
  generated memory-budget files as release authority. They are not the canonical
  version/build evidence and must not be reintroduced.
- FSD kit v1 is withdrawn; kit v2 supersedes it. Do not integrate, quote, or reuse
  v1. An actual local copy must be identified by provenance before deleting it;
  an older unrelated FSD archive must not be mistaken for this kit.
- Do not reuse real device MAC addresses from the withdrawn diagnostic mail or
  personal addresses from quoted mail headers. No such identifiers are repeated here.
- Do not publish duplicated old/new Package G decision sections as a single
  current specification. Preserve the accepted implementation and corrected tests
  as authority, not the duplicated incoming text.
- Before publishing the supplied English enclosure HTML manuals, translate the
  reported 125 Turkish alt/aria-label strings into English and validate the exact
  document inventory. This is a reported count, not a newly verified count.
  Do not silently alter already archived licensed originals or assume the source
  manuals have been received/published without checking their provenance.

## Attribution, communication and evidence policy

- Use only @birolt29 for public/person-facing attribution and the established
  GitHub noreply identity for Git authorship; no first/full name or personal email.
- @birolt29's Package A/B/D/G decisions and other work described in the correction
  are his alone. Do not infer joint authorship from plural wording. Separately
  attribute JimGat's actual integration corrections.
- Email is his only contact channel. The earlier messenger offer is withdrawn.
- Unsolicited offers of additional work are not obligations or assigned backlog.
- Bench reports for patches #09–#24 without attached logs are author observations,
  not independently reviewable test evidence. Keep the observations useful but
  distinguish them from attached captures and exact-final-artifact acceptance.

No firmware, package, version, board classification or Stable promotion is implied
by this documentation correction.
