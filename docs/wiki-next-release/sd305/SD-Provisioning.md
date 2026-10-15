# SD provisioning (staged for v3.0.5 Development)

NOT PUBLISHED. Reconcile with current Wiki before separately authorized publication.
Stable remains v3.0.2 and retains its no-PSRAM manual-only behavior.

Development v3.0.5 integrates co-developer @birolt29 Patch #11 with lifecycle and
failure-reporting corrections. Both PSRAM and no-PSRAM devices can explicitly
choose Provision at startup, or Settings → SD Card → Validate & Provision
(Modern: Tools → Settings). Existing files are preserved during normal validation.
Format + Provision still requires two destructive confirmations.

The 4096-byte stack uses PSRAM when registered, internal 8-bit RAM only when no
PSRAM is registered. There is no internal fallback for exhausted PSRAM. Stack and
queue resources are reserved before formatting; resource/start failure shows a
truthful Failed status, usable Back and OK-only manual guidance. Storage failures
can leave partial work; never assume the card was unchanged after work started.

Manual setup copies CYM-SD-Assets `sdcard/` contents to the card root while preserving
user files: https://github.com/JimGat/CYM-SD-Assets . Provisioning does not download
all external assets. Exact-v3.0.5 physical heap, high-water and repeat-run checks
remain pending. Jim accepted both v3.0.4 Classic/HackerBox landscape builds, not
this new provisioning lifecycle. Development source checklist:
`docs/testing/sd-no-psram-v3.0.5.md`.
