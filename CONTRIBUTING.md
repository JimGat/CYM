# Reproducing and challenging CYM regression evidence

Read [AGENTS.md](AGENTS.md) for the portable entry point and the
[canonical workflow](.claude/rules/cym-canonical-workflow.md) for binding project
rules. Tests and test results do not authorize firmware publication or hardware
operations. Follow [test operator commands](tests/README.md) and the
[gate inventory](tests/inventory.md) before making a coverage claim.

## Reproduce, dispute, and improve

1. Identify the exact source commit plus any uncommitted test patch. Use a fresh
   output directory and run the portable gate; run SDK-native explicitly when its
   prerequisites are installed. Preserve the complete `results.json`, per-entry
   logs, commands, source SHA256 and dependency provenance. Do not report only a
   count or a screenshot of a PASS line.
2. For a disputed assertion, submit a minimal failing fixture/case and its expected
   behavior, actual output, source SHA, installed SDK file hashes, compiler, and
   reproduction command. Distinguish structural source checks, execution of
   extracted production code, handwritten models, and hardware observations.
3. Establish red/green sensitivity. The fixture must fail on a controlled wrong
   behavior and pass on the reviewed behavior. Prefer safe in-memory source input
   mutations as in the BLE gate; never edit canonical firmware just to run a mutant
   or flash an intentionally broken image. Compilation failure, missing dependency,
   sanitizer startup trouble and a deliberate crash are not semantic mutation proof.
4. Keep reusable harnesses and fixtures readable/reviewable in `tests/`; never make
   private release-evidence directories prerequisites for a public regression gate.
   Declare every mock, extraction boundary, unsupported path and untested case.
   Add gate membership/prerequisites explicitly in the manifest and inventory.
5. Do not mask missing required dependencies as skips. Optional private captures
   may skip with a recorded reason. A required gate that did not run blocks its
   acceptance; an all-skipped suite is not success. Expected-failure mutant
   diagnostics must be distinguished from release-blocking accepted-path failures.

Public reports must redact private captures, device identifiers and serial logs.
No test execution grants permission for uncontrolled RF, serial operations, flashing,
secrets, or publication. Hardware qualification is per board and exact artifacts,
not inferred from the nine-board build gate or host tests. Submit reviewable tests
before requesting future supported/Stable promotion; see the
[qualification standard](.claude/rules/cym-qualification-policy.md).

## Human credit

Co-developer @birolt29's Package A and request for reusable, challengeable regression
evidence inspired the corrected BLE harness and consolidation. His supplied
standalone script was reviewed, not imported as accepted proof; see the
[corrected coverage note](docs/testing/package-a-corrected-coverage.md).
Preserve legitimate human authorship and handle/noreply privacy under the
[attribution rule](.claude/rules/cym-contributor-attribution.md). The default author
is JimGat; external patches retain their human author's GitHub noreply identity,
committer stays Jim. No AI attribution trailers or model/agent-name credits.
