# CYM regression gates and evidence limits

These maintained tests are intended for co-developer @birolt29 and other reviewers
to reproduce, challenge, and improve **before future Stable promotion**. They do
not retrospectively demote any board or certify hardware. The original test-only consolidation retained historical v3.0.42 packages.
The Package G ownership candidate is a separate v3.0.43 firmware cycle; see
[its operator and acceptance record](../docs/testing/package-g-ownership.md).

See [contribution/review instructions](../CONTRIBUTING.md), the
[complete module/runner inventory](inventory.md), the machine-readable
[inventory](inventory.json), and [future qualification policy](../.claude/rules/cym-qualification-policy.md).
The [manifest](regression-manifest.json) is the explicit gate membership, not a
claim that every committed test or production path is covered.

## Operator commands (from the checkout root)

Use Python 3.12 or newer on Linux with a GNU-style C compiler, glibc, pthreads,
ASan and UBSan. The portable gate needs only Python's standard library plus `cc`;
it needs no ESP-IDF, managed components, serial port, private capture, or network.
Every output directory must be **new**, including on reruns. Relative output paths
are relative to the caller's working directory. Source paths come from `__file__`.

```sh
python3 -B tests/run_regression.py --suite portable --output tests/_generated/pr-001
```

Expected: each manifest entry reports PASS; `results.json` records exact unittest
counts, standalone invocation counts, optional skips, and exit status. Host harness
invocations are NOT individual assertion counts. No serial/RF/flash operations
occur. Counted native checks and semantic mutation kills are reported separately
from unittest cases and uncounted legacy harness invocations. `dependency-provenance.json` records Python/compiler and manifest provenance.
The runner is fail-fast: later selected entries remain NOT_RUN after a failure.

Installed-library/native tests are explicitly selected, never silently skipped:

```sh
export IDF_PATH="${HOME}/esp/esp-idf"  # actual installed SDK, not a serial port
python3 -B tests/run_regression.py --suite sdk-native --output tests/_generated/native-001
# Both gates in one fail-fast report:
python3 -B tests/run_regression.py --suite portable --suite sdk-native --output tests/_generated/both-001
# Focused reproduction (ID must belong to the selected suite):
python3 -B tests/run_regression.py --suite sdk-native --only ble_spam_sdk --output tests/_generated/ble-001
```

The SDK-native gate also includes the legacy BLE tick-matrix contract, which reads
existing generated config/sdkconfig.h files for its eight enumerated build directories.
These build outputs must already exist; absence reports NOT_RUN, not SKIP or PASS.
This legacy matrix is not the complete nine-profile release build gate.

Native prerequisites: installed ESP-IDF v6.0.2, with its NimBLE submodule, and the
managed components resolved for ESP32C5 from the repository's existing
`ESP32C5/dependencies.lock`: LVGL 8.4.0 and esp_codec_dev 1.5.11. This gate does not
install/update components or run CMake firmware configuration; provision these
separately in an authorized development setup. Missing prerequisites are NOT_RUN
and exit 2, never PASS. Current reproduced reference SDK: ESP-IDF commit
`7101770dc6db2667b3c477cc31365dd1acd6db4e`, NimBLE commit
`5d8b70207a6324f45d9f548ff57ec3b154afccdd`. LVGL package metadata identifies
`4495f428630cc1741bd8bfd977f080e8460e8e8d`; the lock's registry component hash is
`d7c1ac037ae6e85d94897f807d6e7ba0946a83e720074fc95a4f6241da9f9f53`.
Reports hash the actual installed inputs; a matching version string alone is not
proof that an SDK or managed tree is unmodified.

The added GitHub workflow runs only the portable gate on GitHub-hosted Linux.
Native qualification remains the above explicit gate: the full resolved managed
component/SDK provisioning has not been implemented or validated on hosted CI.
Local execution of CI commands is host verification, not evidence a hosted run passed.
Never run untrusted PR code on self-hosted development hardware, use privileged
`pull_request_target` to run fork code, supply secrets, or automatically flash.

Optional private GATT captures are never committed or fetched. To run the private
method with your own authorized fixtures, use a full-history checkout and:

```sh
# Set CYM_GATT23_FIXTURES only to an existing authorized private capture directory.
python3 -B tests/run_regression.py --suite portable --suite private-optional --output tests/_generated/private-001
```

Without that environment variable the optional entry records SKIP. An all-skip or
empty selection exits 3, not green. A configured but invalid/missing capture is a
failure. Private outputs/logs may be sensitive: do not upload that suite's output
to public CI or attach raw captures in bug reports. The default portable gate
records the unrequested private suite as an optional SKIP; no invented fixtures.

Exit codes: 0 = nonempty selected gates pass, with explicit optional skips allowed;
1 = test/compile/runtime failure; 2 = missing required dependency, invalid request,
or hardware NOT_RUN; 3 = no executed passing gate. Read counts and reasons, not
just the last PASS line. A fail-fast report is incomplete, not overall acceptance.
The runner refuses existing output directories and `.hermes` or legacy `tests/_out`
locations. It never moves private files, restores stale binaries, or overwrites
preexisting `_out`. Standalone legacy commands may not have these protections;
use the manifest runner rather than unrestricted `unittest discover`.

## What the promoted tests actually execute

`run_ble_spam_sdk_host.py` extracts the production AirTag address construction,
Windows manufacturer/name field construction and flags initialization, and the
production allocation/serialization/set_data caller tail. It extracts the installed
NimBLE address validator, data validator and ownership wrapper, serializer helpers,
and flags/name/manufacturer branches. Numeric constants and `ble_addr_t` are
extracted from installed headers, with per-file SHA256 provenance (EINVAL is 3 in
the reference SDK, not -6). The accepted extraction and both in-memory mutants
are compiled and actually run with ASan+UBSan:

- Missing production address-type initialization must fail with initialized
  test-only 0xa5 poison. This is **not** an uninitialized-memory experiment;
  ASan/UBSan do not detect every uninitialized read.
- Restoring the name cap to `%6` must fail when actual serialized bytes exceed 31.
- Accepted output checks actual AD types, flags, company bytes, both name copies,
  all 30 deterministic RNG fixtures, 31-byte acceptance/32-byte rejection,
  deterministic invalid addresses, error propagation, and one-free accounting
  through extracted SDK and production caller success/failure paths.

Mbuf storage, HCI, locks, random input, allocator and abort endpoint are instrumented
boundaries. Only selected serializer branches are extracted; MYNEWT feature paths
are disabled in the scaffold. This is not a full NimBLE/controller integration,
not a physical mbuf pool/heap test, and not RF or embedded timing evidence.
`nimble-start-source.txt` preserves a source observation, not an executed start
path: S_ADV allows re-enable, while another active GAP operation can return
EALREADY. Firmware error policy/retry behavior is not changed by these tests.

`run_display_layout_host.py` promotes the accepted expanded v3.0.42 LVGL harness:
production layout/pagination/callbacks plus installed LVGL, 3 base panel sizes,
4 rotations, Classic/Modern routes, real font bounds, first/last reachability,
scroll-release behavior, wallpaper coverage, pagination refresh/selection, and
ATK callback routing. The combined candidate reports 1961 checks on the reference inputs, including
HAT topbar state text/click/deletion bounds. SDK/radio/
unrelated endpoints are stubbed. The native gate also compiles/runs an in-memory
fixed 280x250 Clock-card mutation and requires semantic bounds failures (not a
compile error) before reporting the mutation killed. Host allocation/timing printouts are diagnostic,
not device heap budgets or latency measurements; this is not physical touch proof.

The runner self-tests exercise real failing subprocesses and timeouts, missing SDK,
optional skips, empty/all-skip rejection, fail-fast reporting and exact preservation
of a preexisting output sentinel. Mutant FAIL diagnostics are expected only within
the mutation verifier: compilation failure or sanitizer startup failure does not
count as a semantic mutation kill. Accepted-path failures are blockers.

## Hardware is a separate, explicit owner gate

```sh
python3 -B tests/run_regression.py --suite hardware --output tests/_generated/hardware-unavailable-001
```

Expected here: NOT_RUN, exit 2, and **no hardware operation**. This is a reporting
placeholder, not a hardware runner or a route to acceptance. FSD already exists in
[firmware](../ESP32C5/main/fsd.h) and [tools/fsd.py](../tools/fsd.py), with synthetic
PC and installed-LVGL tests. Physical serial access from the development VM is
currently absent: FSD hardware tests are unavailable, not missing software.
No fictitious port is configured. Remote Pi/Bit-Pirate access remains separate
owner planning, not part of this integration. Inhibited TX lifecycle behavior
cannot prove actual RF emission or silence; each promoted board needs scoped real
hardware evidence and owner approval under the qualification policy.

## Package G PN532 ownership regression

Co-developer @birolt29 supplied the bounded handle-retention patch and original
native harness. The maintained harness extends it to distinguish ready from
cleanup-pending ownership and rejects the original patch's partial-deinit false
ready state. Integration corrections, manager/shared-pin callers and installed
SDK scaffolding are separately attributed in the operator record.

- `pn532_ownership` (portable): verbatim lifecycle/public guard extraction,
  failed new bus/add/remove/delete combinations, cached-ready control,
  re-init during both device+bus and bus-only retained ownership, repeated
  refusal/recovery, no command/field-off I/O after cleanup starts, unsupported
  WS-S3-5B before GPIO reset; ASan/UBSan. Four semantic mutations must fail on
  assertions (not compilation or sanitizer startup). Six scenario groups are
  not six exhaustive hardware tests; assertion count is not reported.
- `pn532_manager` (portable): production teardown extraction, active poll and
  emulation, repeated release errors, failed-init ownership, eventual retry,
  card-buffer retention and repeated cleanup. RTOS/driver boundaries mocked.
- `pn532_claims` (portable): six actual production claim/raw-GPIO entry functions,
  retained-ownership refusal and recovered normal entry; all GPIO/radio endpoints
  mocked, not a physical test or real LVGL gesture test.
- `pn532_idf_contract` (sdk-native, `IDF_PATH`, `cc`): installed I2C
  remove/delete/destroy bodies extracted verbatim, busy-state/nonempty-list/pin
  deinit errors and eventual success. Hardware, RTOS and allocator boundaries
  are scaffolded. Creation/add-device semantics are source-audited, not executed
  from the installed SDK by this test. Record actual source hashes in provenance.

```sh
export IDF_PATH="$HOME/esp/esp-idf"
python3 -B tests/run_regression.py --suite portable --suite sdk-native   --only pn532_ownership --only pn532_manager --only pn532_claims   --only pn532_idf_contract --output /path/to/new/task-owned-output
```

Output isolation requires `CYM_TEST_OUT` for direct standalone commands; use the
manifest runner to set this and `TMPDIR` safely. No physical card detection,
I2C fault reproduction, RF silence or stop-latency qualification is implied.

## Package C HAT TX regression

`hat_tx`, `hat_emitters`, and `hat_runtime` are maintained portable production-extracted ASAN/UBSAN gates. They cover synchronized admission/cancellation and stale tickets, the real four-emitter SDK/GPIO request boundaries, raw diagnostic and timer ownership, checked stop errors and retained resources/retry, copied-signal/mailbox lifetime, stale UI epochs and aggregate state/no restart. Seven semantic mutants require assertion failures, not compiler failures. `display_layout` additionally uses installed LVGL and exact production topbar geometry for both layouts/all rotations. See [operator and physical limits](../docs/testing/package-c-hat-tx.md); no physical RF/optical or timing qualification is implied.

## Wardrive GPS prompt navigation (Patch24, Development v3.0.44)

`wardrive_gps_prompt_nav` is @birolt29's readable portable cleanup extraction,
extended with semantic mutation validation and behavior wiring rather than an
exact call-site count. `wardrive_gps_prompt_lvgl` is SDK-native (`cc`, installed
LVGL 8.4), executes the production prompt/Use Now/Wait/Cancel/no-data callbacks,
wait timer, Home/Back and GPS admission prefix. The post-admission UI/radio task
endpoint and Clock admission boundary are mocked; actual Clock cancellation is
extracted. Direct Home uses the production entry prefix; FSD overlay rejection
is source-checked and full FSD tests separately exercise installed LVGL.

The native runner covers OK before/after timer handling, pending OK followed by X,
repeated cleanup, unrelated overlay survival, timer-after-departure, normal fresh/
cached/lock/cancel and deferred cancellation. Its layout loop repeats shared
callbacks; full geometry is the separate display_layout gate. ASan/UBSan are on;
LeakSanitizer alone is disabled for LVGL process-global display allocations.
Explicit popup/backdrop child counts remain required. Both runners reject a
compiled mutant semantically, never by accepting a crash/compile/startup failure.
No-data blocks touch navigation and was NOT reported orphaned on the device.
See [cycle/operator evidence limits](../docs/testing/wardrive-gps-prompt-v3.0.44.txt).

```sh
python3 -B tests/run_regression.py --suite portable --suite sdk-native --only wardrive_gps_prompt_nav --only wardrive_gps_prompt_lvgl --output /path/to/new/wardrive-proof
```

## Package B AP lifecycle (Development v3.0.45)

`run_ap_owner_lifecycle_host.py`, `run_ap_owner_queue_host.py` and
`run_ap_admit_host.py` are portable pure decision-helper extractions only.
`run_ap_worker_host.py` extracts the production admission, lazy allocation,
queue/cancellation and worker step with scheduled SDK-boundary interleavings;
requires installed IDF esp_err.h (IDF_PATH). `run_ap_services_host.py` extracts
production HTTP/DNS start/stop/socket-owner exit, fault-injects every acquisition,
and checks timeout retention; requires installed IDF esp_err/http_parser headers.
`run_ap_controls_lvgl_host.py` compiles actual controls against installed LVGL8.4,
checks callbacks, rejection/status, DELETE timer cleanup and scroll reachability
in flex parents across five panel sizes/all rotations/both compositions. It does
not instantiate complete running screens or prove physical input/legibility.
All require CC; all generated output uses CYM_TEST_OUT and TMPDIR. Native tests
use ASAN/UBSAN and strict semantic mutant classifications (86 + assertion or
explicit RESULT failures), never compilation errors or random crashes. No SMP,
real SDK operations, device stack/heap minima or RF proof is claimed.
