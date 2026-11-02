# Package A: corrected reusable coverage note for @birolt29

Thank you to co-developer @birolt29 for the Package A contribution and the push for
reusable, challengeable regression evidence. No firmware correction is proposed by
this test integration; the bounded accepted v3.0.42 bytes remain unchanged.

The supplied standalone script was **not accepted as production-extracted proof**:
its hardcoded name-expression assertion/copy passed even after the production
AirTag type initializer was removed. Its address gate and serializer were
handwritten, no mbuf operation ran, and it used EINVAL=-6 whereas the installed
NimBLE header defines BLE_HS_EINVAL=3. Its zeroed invalid-type fixture was initialized
invalid memory, not a deterministic demonstration of uninitialized behavior.
Original scripts, logs and review mutations remain preserved outside the repo;
none of those incorrect claims is promoted as accepted evidence.

The [maintained harness](../../tests/run_ble_spam_sdk_host.py) now extracts the
production address-building, flags and Windows payload fields, production caller
serialization/ownership tail, and installed NimBLE validation/ownership/serialization
paths with actual header constants, type layout and hashes. It checks real AD bytes,
31-byte limits, deterministic negative fixtures, one-free accounting and errors.
Both requested production-input mutations must fail a semantic runtime assertion:
missing AirTag type initialization (initialized test-only poison), and `%6` name cap
(32 actual serialized bytes). All three variants are actually run under ASan+UBSan;
no canonical firmware mutation, flash, RF activity or new retry policy is involved.

Limitations: mbuf storage/allocator, HCI, locks, random source and abort endpoint are
instrumented; only selected serializer branches and feature settings are tested.
ASan/UBSan do not prove absence of every uninitialized read. The installed start
semantics observation is source-only: S_ADV can re-enable; other GAP operations can
produce EALREADY. Controller timing, repeated on-device operation, embedded heap,
and actual RF emission/reception remain untested hardware gates, not implied PASS.
Use [reproduction and dispute instructions](../../CONTRIBUTING.md) to submit a
counterexample with source/SDK provenance rather than relying on an all-green label.
