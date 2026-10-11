# GATT metadata correlation hint v1 (shared CYM integration)

Issue: https://github.com/JimGat/CYM/issues/23#issuecomment-6109001088

This adds a second, optional fingerprint. The original FNV32 layout algorithm,
JSON `fingerprint`, SD directory and fingerprint-first filename remain unchanged.
Neither numeric FNV32 nor metadata SHA256 proves identity, ownership, authenticity
or security. Different devices can share metadata; a device can rename itself,
spoof metadata or change its layout. Use as a correlation hint only.

## Selection and uncertainty

Production code is `ESP32C5/main/gatt_metadata.h`, a header-only pure bounded C
helper used by `gatt_walker.c`. Header-only avoids changing shared-board source
lists. All eight release profiles compile this helper and the SDK PSA adapter.
The existing result screen renders copied metadata labels on the main owner;
filename capacity, legacy hash and read callback remain unchanged.

- DeviceName: raw successfully observed 2A00 bytes in Generic Access 1800.
- Fallback: stored advertised `gw_result_t.name` only when no nonempty readable
  GATT DeviceName exists. The stored name has at most 31 bytes, ending at first
  NUL. Advertising completeness cannot be reconstructed from this result.
- ManufacturerName: readable 2A29 in Device Information 180A only.
- ModelNumber: readable 2A24 in Device Information 180A only.
- UUID match accepts actual NimBLE `0xNNNN` and standardized Bluetooth-base
  `0000NNNN-0000-1000-8000-00805f9b34fb`, case-insensitive hex. It rejects
  malformed suffixes and vendor UUIDs with superficially similar prefixes.
- Bound GATT bytes to the stored 512-byte array. Strip only trailing 0x00 bytes;
  retain embedded NUL, UTF8, controls, whitespace and case. Never hash the ASCII
  display's replacement dots, UUID display names or top-level OUI manufacturer.
- Duplicates: prefer any nonempty observed value; then unsigned bytewise lexical
  minimum, shorter prefix first, smaller state on ties. Without nonempty bytes,
  higher state wins (cap uncertainty, observed empty, unreadable, absent).
  Equivalent candidates do not depend on discovery or handle order. The original
  layout hash still intentionally depends on its original UUID/property order;
  different layout hashes remain different enriched hashes. Non-selected duplicate
  values do not contribute to the digest.
- Exclude MAC/address type, RSSI, GPS, timestamp, OUI convenience strings, serial
  number, battery values, notification/probe frames and all other attribute data.
  UUIDs/properties remain part of the unchanged embedded layout fingerprint.

The legacy callback sets read_ok after positive chunks, including when a later
chunk errors, and silently caps storage at 512. We deliberately do NOT add or
claim read-complete/truncated flags. All positive GATT values are observed bytes
with completion unknown. A stored read_len >=512 marks cap/truncation uncertainty
(not proof of truncation). This uncertainty is encoded and exported. Host tests
execute the unchanged production callback for multiple chunks, EDONE, later error,
cap, and unreadable error. Partial-prefix collisions remain possible and documented.

## Canonical ABI (all lengths count bytes, not characters)

Algorithm/domain/version string: `cym-gatt-metadata-v1`.
Hash: SHA-256, full 64 lowercase hex characters. No truncation in JSON/result.
Target streaming adapter uses the SDK public psa/crypto.h API: crypto_init,
hash_setup(PSA_ALG_SHA_256), hash_update, hash_finish, and unconditional hash_abort
cleanup. Exactly 32 output bytes are required. No private mbedTLS header or host
hashing core is substituted into firmware. SHA failure leaves the digest
unavailable/empty/null while retaining the metadata-presence markers. Host tests
exercise init/setup/update/finish and incorrect digest-length failures.

TLV envelope: tag:u8, body_length:u16 big endian, body bytes, no alignment/padding.
Exactly these records in this order, no final terminator:

| Tag | Body |
| --- | --- |
| 0 | ASCII domain string above, WITHOUT terminating NUL |
| 1 | original layout fingerprint u32 BIG ENDIAN (4 bytes) |
| 2 | source:u8, state:u8, name_gatt_state:u8, selected DeviceName bytes |
| 3 | source:u8, state:u8, zero:u8, selected ManufacturerName bytes |
| 4 | source:u8, state:u8, zero:u8, selected ModelNumber bytes |

Sources: 0 none, 1 GATT, 2 advertised.
States: 0 absent, 1 unreadable (read_ok false), 2 empty after padding removal,
3 observed/completion unknown, 4 cap/truncation unknown.
Unselected absent fields have source 0; empty/unreadable observed GATT fields
retain source 1. Zero-length fields still carry their markers. The name's GATT
state is preserved separately when falling back to advertising, so absent,
unreadable and observed-empty are not conflated.

The mask is derived from nonempty selected bytes: bit0 name, bit1 manufacturer,
bit2 model. If mask==0, emit no canonical payload/digest; gm_canonical returns 1.
Return 0 means streamed successfully, -1 means invalid selection or sink error.
Selection bounds discovery counts. Serializer additionally rejects lengths >512
or nonempty NULL data. Sink prefixes emitted before failure must be discarded.

This schema is versioned. Any change to normalization, markers, selection policy,
field ordering or serialization requires an explicit algorithm/version decision.

## Additive export / result API

Existing export version remains 1; existing fields and probe export paths remain.
New JSON top-level fields:

- metadata_fingerprint: full SHA256 string, or null when unavailable/error.
- metadata_algorithm: cym-gatt-metadata-v1, even when unavailable.
- metadata object: available; identifying_metadata_present; name_source
  (gatt/advertised/none); fields array of contributing field identifiers;
  device_name/manufacturer_name/model_number state labels; name_gatt_state;
  completeness and meaning limitation strings.

No new raw metadata strings are exported. Existing read_data hex is authoritative.
The existing JSON string builder now escapes controls/preserves valid UTF8 and the
ASCII display escapes quotes/backslashes, preventing names from breaking JSON.
This is an escaping correction, not new hashing input. A hostile invalid-UTF8
advertised string is not validated by this helper; canonical hashing is bytewise.

Result extension: metadata_fingerprint[65], metadata_available, metadata_name_source,
metadata_fields, metadata_states[3], metadata_name_gatt_state. In-memory struct
size/offsets change; recompile all consumers together. It is not a persistent or
cross-process binary ABI. filepath remains 80 bytes. Legacy SD filenames do NOT
incorporate the metadata digest. Existing same-layout/time/MAC overwrite semantics
are not changed by this patch.

## Operator: what to ask and expect

Ask: "Run host-only GATT metadata tests using the private issue23 fixtures."
As dev on ESP32-Dev, from /home/dev/projects/CYM-NM28C5-jarvis-ws35-docs:

    CYM_GATT23_FIXTURES=/home/dev/ws-c5-35-fixes/gatt23-private-fixtures python3 -m unittest discover -s tests -p test_gatt23_metadata.py -v

Expect 12 passing tests under ASan/UBSan and a quiet count-only summary: 9 actual
captures, 9 unchanged layout values, 9 distinct metadata digests, all GATT names.
Private values must never be printed/copied into tracked data. Directory 700 and
files 600 remain outside git. Without the environment variable, private regression
is explicitly skipped, NOT claimed as tested; synthetic tests still run.

Ask: "Run the shared integration host regression suite without firmware builds."
The existing patch0506 tests need their untracked scratch directory first:

    mkdir -p .hermes/patch0506
    CYM_GATT23_FIXTURES=/home/dev/ws-c5-35-fixes/gatt23-private-fixtures python3 -m unittest discover -s tests

Expect 415 tests, OK with the private fixture environment enabled.
Host prerequisites: cc with ASan/UBSan, Python3, OpenSSL EVP headers and libcrypto.
Tests extract actual production legacy, SHA adapter, JSON serializer and callback;
OpenSSL supplies real host SHA256, checked against the abc standard vector.
Python hashlib independently verifies C-produced canonical bytes, not a parallel
Python implementation of selection/serialization. Real captures additionally
compare every legacy exported field against the original production serializer.

Ask after parent integration: "Compare layout and metadata hints in exported JSON."
Expect the original fingerprint/filename unchanged, full metadata digest when
nonempty metadata exists, correct source/presence/state markers, and null when
no identifying bytes exist. This does not authenticate rotating-MAC devices.

## Integration and physical acceptance

The shared result screen preserves the original FP row and appends three copied,
wrapped, scrollable labels using the existing theme text color: a 16-hex digest
preview (or unavailable), metadata source/presence, and correlation/read limitations.
SD JSON keeps all 64 hex digits. Labels retain no result pointer, callback or timer;
no LVGL call occurs in NimBLE context. Classic and Modern use this same feature
screen. Light/dark rendering and small/large viewport bounds are host-tested.

The authoritative cycle is v2.15.80: the first .79 attempt failed before any changed
application; the repaired .79 attempt produced NM-CYD-C5, then failed the WS audio
archive's missing timer include dependency. The next changed build therefore uses
.80 on all eight boards. A build/source version alone is not publication proof:
verify all board descriptors/manifests/packages, exact Git commit and live Beta pin.

Tester: open https://jimgat.github.io/CYM/beta/ (or the ordinary flasher ?beta=1),
select the correct board and Development, and confirm v2.15.80 after publication.
Perform a fresh authorized GATT walk, open the result, then compare SD JSON:

    fingerprint                 unchanged legacy layout hint
    metadata_algorithm          cym-gatt-metadata-v1
    metadata_fingerprint        64 lowercase hex, or null
    metadata.name_source        gatt / advertised / none
    metadata.fields             contributing field names
    metadata.completeness       observed bytes, read completion unknown

Walk the test devices again with a new advertising MAC when possible. Compare both
hints and inspect the contributing fields. Missing manufacturer/model is normal.
Matching hints do not prove identity; differences can result from renamed metadata,
read availability or layout changes. Do not publish raw identifying captures.
Physical BLE/UI/SD qualification remains a tester gate, not a compiler result.
