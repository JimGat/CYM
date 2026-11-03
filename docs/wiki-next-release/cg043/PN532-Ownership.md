# PN532 ownership correction (staged, not published)

Development candidate v3.0.43 incorporates co-developer @birolt29's Package G
retained-handle patch, with JimGat integration corrections for cleanup-pending
readiness and shared-pin reuse. Failed cleanup blocks competing pin owners until
an explicit retry succeeds; do not equate initialized=false with released pins.
The original NM no-card problem remains open. Host fault injection and compilation
are not physical acceptance.

Package C's four-emitter HAT TX design originates with @birolt29 and is now implemented as a separate four-emitter runtime control; see
HAT-TX-Control.md. Wi-Fi, BLE, 802.15.4 and utility traffic are not inhibited.

Before publication, merge this proposal against the then-current live Wiki.
Link to the repository's docs/testing/package-g-ownership.md operator procedure.
