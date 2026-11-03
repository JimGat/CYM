# Staged Wiki proposal — not published

Parent: reconcile with current live Wiki before publication; do not replace a
newer page blindly. No Wiki checkout/remote is modified by this integration.

Proposed Wardriving troubleshooting addition:
Development v3.0.44 integrates co-developer @birolt29's Patch24. Topbar Home/Back
retire the cached GPS prompt/wait and timer instead of leaving screen-parented
UI over the destination. JimGat lifecycle corrections include DELETE identity,
owned no-data backdrop/OK scheduling and Clock-deferred-start cancellation.
The no-data modal blocks touch navigation; its orphan was not reproduced in the
supplied device report. Use Now/Wait/Cancel and fresh GPS retain their behavior.

The supplied NM-CYD-C5 report and four builds are contributor-reported, not
independent final-artifact hardware acceptance or all-nine coverage. Installed-
LVGL host tests and the final nine-profile build/package evidence are software
qualification only. Repeat both layouts/all rotations and exact-artifact bench
checks before acceptance. Stable/main and existing board statuses are unchanged.

Review source docs/releases/v3.0.44-dev.md and
 docs/testing/wardrive-gps-prompt-v3.0.44.txt for exact commands and limitations.
