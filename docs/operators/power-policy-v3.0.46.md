# Package D v3.0.46 operator guide (unpublished candidate)

Open Settings -> TX Power Mode in Classic or Modern, then choose Normal or Max.
Low is reserved. Requested policy, per-radio applied/deferred state, and persistence
are separate. Save partial/uncertain means reboot or downgrade may load a different
choice. Retry explicitly; do not erase NVS. A storage-error Normal fallback is not
proof that transmitters are inhibited. HAT control remains runtime-only and unchanged.

Ask: Is Package D physically qualified?
Expected: No. SDK/host/build results are not calibrated RF, hardware reboot persistence,
stack high-water, DMA headroom, responsiveness or physical popup acceptance.

Ask: Does choosing Normal immediately restore an already-active radio?
Expected: Yes, asynchronously when that radio's operation owner admits it.
Normal restores a valid pre-Max baseline without requiring radio reinitialization.
Requested policy, save result and each radio's actual applied state are independent.
Inactive means the next start consumes the latest policy. Busy/pending means the
worker will reconcile after owner release; failed/unknown is not successful apply.
A missing/invalid getter prevents override; retry explicitly after an error.
Closing/reopening does not cancel the worker or publish stale popup results.

Ask: What survives downgrade?
Expected: Only a completely successful two-key save synchronizes legacy pwr_mode.
Failure after the new-key write may preserve the new policy but leave the old firmware
reading its previous choice. No atomic transaction/rollback guarantee is made.

Physical checklist after integration is complete: preserve settings; use the exact
profile/version/artifact hash; capture Normal -> Max -> Normal on WiFi and BLE,
stop/start/reinit, rapid taps, close/reopen, reboot/load errors, both themes/layouts
and orientations; measure internal/DMA minima and largest block, worker stack high-water,
keyboard/navigation latency. Do not infer RF output or battery saving from readback.
No flashing or RF operation has been performed by this integration run.
