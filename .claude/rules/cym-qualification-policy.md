# Future supported / Stable board qualification (owner-approved)

This standard governs **future** support/Stable promotions. It does not demote,
relabel, or retrospectively recertify any current board. Existing owner-approved
Stable classifications and their narrower capability limits are grandfathered.
The current seven Stable profiles and two Development-only profiles remain as
recorded in the canonical workflow. Newly added boards stay **Development** until
explicit, scoped hardware qualification and owner approval.

## Required review package before future promotion

- An owner-approved board matrix: exact board/vendor/profile/hardware revision,
  peripherals/wiring, enabled and unsupported functions, source commit, build
  configuration, and exact artifact/manifest SHA256s. Record the scope and who
  operated/observed each test; do not generalize a clone or peripheral result.
- Readable, reviewable, reusable regression tests in the repository, available to
  co-developer @birolt29 and other reviewers to reproduce and challenge **before**
  future Stable. Include commands, source/SDK provenance, dependency prerequisites,
  fixture origin, mocks, limitations, and mutation/red-green sensitivity evidence.
  Private captures may remain optional and must not be misrepresented as public
  reproduction coverage. See [test instructions](../../tests/README.md).
- All **nine current compatibility build checks** remain required and distinct:
  `nm-cyd-c5`, `ws-c5-28`, `ws-c5-35`, `cyd-2432s028`, `cyd-2432s028-l`,
  `hackerbox-cyd`, `hosyond-s3-35`, `pancake-c5`, `ws-s3-5b`. Record affected
  source/configuration and exact artifacts; an added board also needs its own
  build evidence. This is cross-board build compatibility, not nine hardware
  acceptances or automatic promotion of the two Development targets.
- Explicit hardware acceptance **for each board being promoted**, on the exact
  artifacts and approved functional scope: startup/navigation/display/touch,
  supported peripheral functions, lifecycle/start-stop/cancel/error cases,
  sustained/soak behavior, heap/memory behavior and recovery. Set the functional
  matrix, test duration, repetitions, heap thresholds and pass criteria in the
  owner-approved scope rather than inventing universal numbers after the test.
- No unresolved CRIT/crash defect within the promoted scope. Track warnings with
  evidence-based disposition (fixed, accepted with reason/owner, or blocking).
  Intentional scrolling is not automatically a layout defect: demonstrate readable,
  reachable first/last content, exit/cancel access and correct gesture behavior.
- Enumerate unsupported, not-run and unavailable cases and their acceptance impact;
  do not claim all paths proven. Build success, static assertions, simulation,
  an inhibited-TX lifecycle test, or a controller's accepted command is not actual
  RF emission/silence proof. Use scoped physical measurements where required.
- Preserve raw serial/screenshots/functional/soak/memory/error evidence privately
  where necessary and provide a reviewable sanitized summary. FSD software exists;
  current development-VM physical serial access is absent, so FSD hardware runs
  are **unavailable** here. No invented port or external latest-FSD completeness
  claim. Alternate remote hardware arrangements require separate owner planning.
- Obtain Jim's explicit approval of the board's evidence and exact promotion scope.
  A green host/CI run, no objection, or a version number alone cannot grant Stable.

Documentation/tests/CI-only integration with verified unchanged firmware inputs
and packaged hashes does not require rebuilding the nine historical packages.
Record that exemption and unchanged hashes explicitly; it is not a waiver of the
nine-build gate for future changed firmware. Historical v3.0.42 packages remain
v3.0.42 and gain no new hardware acceptance from this consolidation.

This policy imposes no blanket feature freeze or automatic all-path/RF guarantee.
It does not authorize hardware work, publication, repository settings changes,
or demotion of existing labels.
