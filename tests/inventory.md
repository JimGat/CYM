# Test and runner inventory

This inventory distinguishes committed reusable tests from release-specific evidence.
The [JSON inventory](inventory.json) records module prerequisites/reasons; the
[manifest](regression-manifest.json) is authoritative automated gate membership.
Nothing here claims total production-path coverage. Do not run unrestricted discovery
on the development tree: legacy tests can write fixed `.hermes`, `_out`, or private
paths, require unavailable assets/history, or call other legacy runners.

## Taxonomy

- **Structural**: source/metadata assertions. These can catch contract drift, not
  prove runtime behavior. Version-named contracts are not all obsolete; only the
  reviewed explicit selection runs in portable CI.
- **Mocked-host native/simulation**: extracted or linked production C executed with
  synthetic SDK/RTOS/radio/storage boundaries. Portable on the documented host.
- **Installed SDK/library native**: real installed NimBLE, LVGL, codec or I2S source
  plus declared host stubs; explicit dependencies and provenance. Never RF proof.
- **Hardware**: real board/serial/screen/peripheral/RF/soak evidence, separately
  authorized and unavailable here; not replaced with mocked data.
- **Private optional**: authorized external captures/assets, explicitly recorded
  skips if unconfigured; configured invalid input fails. Never silently required
  by the public portable gate.

The consolidation does not rerun or claim the historical full-discovery result of
756 pass / 1 skip as its current total. Current totals are computed in results.json.
Other native assertion totals remain uncounted unless a harness emits structured
counts; invocation count must not be presented as assertion count.

## Every top-level Python test/standalone runner

| File | Automated gate | Boundary / exclusion reason |
| --- | --- | --- |
| [`audio_rta_nvs_stubs.py`](../tests/audio_rta_nvs_stubs.py) | helper | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`audio_rta_sdk_slots.py`](../tests/audio_rta_sdk_slots.py) | helper | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`qr_native.py`](../tests/qr_native.py) | helper | native-mocked |
| [`run_audio_rta_board_host.py`](../tests/run_audio_rta_board_host.py) | sdk-native | installed-library-host; prerequisites: cc, codec |
| [`run_audio_rta_gain_store_host.py`](../tests/run_audio_rta_gain_store_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_audio_rta_incremental_host.py`](../tests/run_audio_rta_incremental_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_audio_rta_input_host.py`](../tests/run_audio_rta_input_host.py) | sdk-native | installed-library-host; prerequisites: cc, codec, idf-i2s |
| [`run_audio_rta_lifecycle_host.py`](../tests/run_audio_rta_lifecycle_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_audio_rta_scheduling_host.py`](../tests/run_audio_rta_scheduling_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_audio_rta_snapshot_host.py`](../tests/run_audio_rta_snapshot_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_audio_rta_ui_host.py`](../tests/run_audio_rta_ui_host.py) | sdk-native | installed-library-host; prerequisites: cc, lvgl |
| [`run_ble_chameleon_integration_host.py`](../tests/run_ble_chameleon_integration_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_diag_host.py`](../tests/run_ble_scan_diag_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_lifecycle_host.py`](../tests/run_ble_scan_lifecycle_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_list_host.py`](../tests/run_ble_scan_list_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_reports_host.py`](../tests/run_ble_scan_reports_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_scheduling_host.py`](../tests/run_ble_scan_scheduling_host.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`run_ble_scan_session_host.py`](../tests/run_ble_scan_session_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ble_scan_status_host.py`](../tests/run_ble_scan_status_host.py) | not-automated | native-mocked |
| [`run_ble_spam_sdk_host.py`](../tests/run_ble_spam_sdk_host.py) | sdk-native | installed-sdk-host; prerequisites: cc, idf-nimble |
| [`run_ble_stage_diag_host.py`](../tests/run_ble_stage_diag_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_classic_ble_fallback_host.py`](../tests/run_classic_ble_fallback_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_console_stream_host.py`](../tests/run_console_stream_host.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`run_display_layout_host.py`](../tests/run_display_layout_host.py) | sdk-native | installed-library-host; prerequisites: cc, lvgl |
| [`run_doom_engine_host.py`](../tests/run_doom_engine_host.py) | not-automated | native-mocked |
| [`run_fsd_gesture_host.py`](../tests/run_fsd_gesture_host.py) | sdk-native | installed-library-host; prerequisites: cc, lvgl |
| [`run_fsd_host.py`](../tests/run_fsd_host.py) | sdk-native | installed-library-host; prerequisites: cc, lvgl |
| [`run_fsd_lifecycle_host.py`](../tests/run_fsd_lifecycle_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ir_task_lifetime_host.py`](../tests/run_ir_task_lifetime_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_legacy_log_lifetime_host.py`](../tests/run_legacy_log_lifetime_host.py) | not-automated | private/output legacy; native-mocked |
| [`run_mdns_allocation_host.py`](../tests/run_mdns_allocation_host.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`run_memory_boundary_host.py`](../tests/run_memory_boundary_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_netif_lifecycle_host.py`](../tests/run_netif_lifecycle_host.py) | not-automated | private/output legacy; native-mocked |
| [`run_ntp_clock_owner_host.py`](../tests/run_ntp_clock_owner_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_ntp_lifecycle_host.py`](../tests/run_ntp_lifecycle_host.py) | not-automated | private/output legacy; native-mocked |
| [`run_ot_lifetime_host.py`](../tests/run_ot_lifetime_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_radio_repair_host.py`](../tests/run_radio_repair_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_regression.py`](../tests/run_regression.py) | orchestrator | Explicit manifest orchestrator; no unrestricted discovery |
| [`run_scope_lifecycle_host.py`](../tests/run_scope_lifecycle_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_selector_host.py`](../tests/run_selector_host.py) | not-automated | private/output legacy; SDK/managed; native-mocked; external package |
| [`run_targeted_console_host.py`](../tests/run_targeted_console_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_targeted_mdns_host.py`](../tests/run_targeted_mdns_host.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`run_targeted_owner_host.py`](../tests/run_targeted_owner_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_wardrive_gps_prompt_nav_host.py`](../tests/run_wardrive_gps_prompt_nav_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_wardrive_gps_prompt_lvgl_host.py`](../tests/run_wardrive_gps_prompt_lvgl_host.py) | sdk-native | installed-library-host; prerequisites: cc, lvgl |
| [`run_wifi_sas_lifecycle_host.py`](../tests/run_wifi_sas_lifecycle_host.py) | portable | mocked-host; prerequisites: cc |
| [`run_wifi_scan_generation_host.py`](../tests/run_wifi_scan_generation_host.py) | portable | mocked-host; prerequisites: cc |
| [`test_audio_backend.py`](../tests/test_audio_backend.py) | not-automated | private/output legacy; native-mocked |
| [`test_audio_rta_contracts.py`](../tests/test_audio_rta_contracts.py) | portable | structural; prerequisites:  |
| [`test_audio_rta_dsp_host.py`](../tests/test_audio_rta_dsp_host.py) | not-automated | private/output legacy; native-mocked; external package |
| [`test_ble_reliability_candidate.py`](../tests/test_ble_reliability_candidate.py) | sdk-native | structural; prerequisites: generated-tick-configs |
| [`test_camera_lifecycle.py`](../tests/test_camera_lifecycle.py) | not-automated | native-mocked |
| [`test_chameleon96.py`](../tests/test_chameleon96.py) | not-automated | native-mocked |
| [`test_chameleon_ble_scan_contract.py`](../tests/test_chameleon_ble_scan_contract.py) | portable | structural; prerequisites:  |
| [`test_chameleon_phase5_6_contract.py`](../tests/test_chameleon_phase5_6_contract.py) | portable | structural; prerequisites:  |
| [`test_chameleon_t55xx_contract.py`](../tests/test_chameleon_t55xx_contract.py) | not-automated | native-mocked |
| [`test_classic_ble_fallback.py`](../tests/test_classic_ble_fallback.py) | not-automated | native-mocked |
| [`test_classic_candidate_version.py`](../tests/test_classic_candidate_version.py) | not-automated | native-mocked |
| [`test_classic_cyd_gps_contract.py`](../tests/test_classic_cyd_gps_contract.py) | portable | structural; prerequisites:  |
| [`test_classic_cyd_gps_test_tool.py`](../tests/test_classic_cyd_gps_test_tool.py) | portable | structural; prerequisites:  |
| [`test_classic_rgb_led_boot_contract.py`](../tests/test_classic_rgb_led_boot_contract.py) | portable | structural; prerequisites:  |
| [`test_classic_usb_debug.py`](../tests/test_classic_usb_debug.py) | not-automated | native-mocked |
| [`test_classic_usb_debug_next.py`](../tests/test_classic_usb_debug_next.py) | not-automated | native-mocked |
| [`test_classic_usb_debug_routing.py`](../tests/test_classic_usb_debug_routing.py) | not-automated | native-mocked |
| [`test_classic_usb_debug_ui.py`](../tests/test_classic_usb_debug_ui.py) | not-automated | SDK/managed; native-mocked |
| [`test_clock_data_placement_host.py`](../tests/test_clock_data_placement_host.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle79_gatt_ui.py`](../tests/test_cycle79_gatt_ui.py) | not-automated | private/output legacy; SDK/managed; native-mocked; external package |
| [`test_cycle79_loading.py`](../tests/test_cycle79_loading.py) | portable | structural; prerequisites:  |
| [`test_cycle79_transport.py`](../tests/test_cycle79_transport.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle79_validation.py`](../tests/test_cycle79_validation.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle81_controls.py`](../tests/test_cycle81_controls.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle81_touch_driver.py`](../tests/test_cycle81_touch_driver.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle84_dma_timekeeper.py`](../tests/test_cycle84_dma_timekeeper.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle85_battery_visibility.py`](../tests/test_cycle85_battery_visibility.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_cycle85_startup_transport.py`](../tests/test_cycle85_startup_transport.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_cycle85_startup_ui.py`](../tests/test_cycle85_startup_ui.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`test_cycle87_display_diagnostics.py`](../tests/test_cycle87_display_diagnostics.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle90_native.py`](../tests/test_cycle90_native.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle90_native_transport.py`](../tests/test_cycle90_native_transport.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle98_audio_policy.py`](../tests/test_cycle98_audio_policy.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle98_gps.py`](../tests/test_cycle98_gps.py) | not-automated | private/output legacy; native-mocked |
| [`test_cycle99_gps.py`](../tests/test_cycle99_gps.py) | not-automated | native-mocked; historical git prerequisite |
| [`test_cyd2432s028_display_contract.py`](../tests/test_cyd2432s028_display_contract.py) | portable | structural; prerequisites:  |
| [`test_cyd_l_variant.py`](../tests/test_cyd_l_variant.py) | not-automated | native-mocked; historical git prerequisite |
| [`test_cyd_landscape304.py`](../tests/test_cyd_landscape304.py) | not-automated | SDK/managed; native-mocked |
| [`test_debug94.py`](../tests/test_debug94.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`test_defensive_validation.py`](../tests/test_defensive_validation.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`test_detect_defend_harvester_contract.py`](../tests/test_detect_defend_harvester_contract.py) | portable | structural; prerequisites:  |
| [`test_display_layout_host.py`](../tests/test_display_layout_host.py) | not-automated | native-mocked |
| [`test_doom_contracts.py`](../tests/test_doom_contracts.py) | not-automated | private/output legacy; native-mocked |
| [`test_doom_finish_contract.py`](../tests/test_doom_finish_contract.py) | portable | structural; prerequisites:  |
| [`test_doom_real_asset.py`](../tests/test_doom_real_asset.py) | not-automated | private/output legacy; native-mocked |
| [`test_es3c35p_promotion_contract.py`](../tests/test_es3c35p_promotion_contract.py) | portable | structural; prerequisites:  |
| [`test_exclusive_audio.py`](../tests/test_exclusive_audio.py) | not-automated | private/output legacy; native-mocked |
| [`test_exclusive_owner_lifecycle.py`](../tests/test_exclusive_owner_lifecycle.py) | not-automated | private/output legacy; native-mocked |
| [`test_flasher95.py`](../tests/test_flasher95.py) | not-automated | native-mocked |
| [`test_flasher_channel_deployment.py`](../tests/test_flasher_channel_deployment.py) | not-automated | native-mocked |
| [`test_footer_launch_access.py`](../tests/test_footer_launch_access.py) | portable | structural; prerequisites:  |
| [`test_fsd_build_nav.py`](../tests/test_fsd_build_nav.py) | not-automated | native-mocked |
| [`test_fsd_gesture_contract.py`](../tests/test_fsd_gesture_contract.py) | not-automated | native-mocked |
| [`test_fsd_pc.py`](../tests/test_fsd_pc.py) | portable | mocked-host; prerequisites:  |
| [`test_game_mode.py`](../tests/test_game_mode.py) | not-automated | private/output legacy; native-mocked |
| [`test_gatt23_metadata.py`](../tests/test_gatt23_metadata.py) | private-optional | private-optional; prerequisites: cc, git-gatt-history |
| [`test_go_dark_wake.py`](../tests/test_go_dark_wake.py) | not-automated | native-mocked |
| [`test_hackerbox_cyd_contract.py`](../tests/test_hackerbox_cyd_contract.py) | portable | structural; prerequisites:  |
| [`test_memory_boundary_host.py`](../tests/test_memory_boundary_host.py) | not-automated | native-mocked |
| [`test_modern_attack_disclaimer_contract.py`](../tests/test_modern_attack_disclaimer_contract.py) | portable | structural; prerequisites:  |
| [`test_ntp_lifecycle_host.py`](../tests/test_ntp_lifecycle_host.py) | not-automated | native-mocked |
| [`test_observer315.py`](../tests/test_observer315.py) | not-automated | native-mocked |
| [`test_observer95.py`](../tests/test_observer95.py) | not-automated | native-mocked |
| [`test_pancake_c5_contract.py`](../tests/test_pancake_c5_contract.py) | portable | structural; prerequisites:  |
| [`test_patch03_battery_camera_contract.py`](../tests/test_patch03_battery_camera_contract.py) | portable | structural; prerequisites:  |
| [`test_patch0506_contract.py`](../tests/test_patch0506_contract.py) | not-automated | private/output legacy; native-mocked |
| [`test_project_image_assets.py`](../tests/test_project_image_assets.py) | not-automated | external package |
| [`test_qr310.py`](../tests/test_qr310.py) | not-automated | native-mocked; external package |
| [`test_qr311.py`](../tests/test_qr311.py) | not-automated | native-mocked |
| [`test_qr311_packet.py`](../tests/test_qr311_packet.py) | not-automated | native-mocked |
| [`test_qr312.py`](../tests/test_qr312.py) | not-automated | native-mocked |
| [`test_qr312_admission.py`](../tests/test_qr312_admission.py) | not-automated | native-mocked |
| [`test_qr315.py`](../tests/test_qr315.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_qr316.py`](../tests/test_qr316.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_qr_allocations.py`](../tests/test_qr_allocations.py) | not-automated | native-mocked |
| [`test_qr_decoder_contract.py`](../tests/test_qr_decoder_contract.py) | not-automated | native-mocked; external package |
| [`test_qr_font309.py`](../tests/test_qr_font309.py) | portable | structural; prerequisites:  |
| [`test_qr_payload.py`](../tests/test_qr_payload.py) | not-automated | native-mocked |
| [`test_qr_record_faults.py`](../tests/test_qr_record_faults.py) | not-automated | native-mocked |
| [`test_qr_sd_pack.py`](../tests/test_qr_sd_pack.py) | not-automated | native-mocked |
| [`test_qr_ui_stop.py`](../tests/test_qr_ui_stop.py) | not-automated | native-mocked |
| [`test_qr_worker309.py`](../tests/test_qr_worker309.py) | not-automated | native-mocked |
| [`test_reboot_startup.py`](../tests/test_reboot_startup.py) | portable | structural; prerequisites:  |
| [`test_reboot_transaction.py`](../tests/test_reboot_transaction.py) | not-automated | private/output legacy; native-mocked |
| [`test_regression_runner.py`](../tests/test_regression_runner.py) | portable | runner-contract; prerequisites:  |
| [`test_release300_contract.py`](../tests/test_release300_contract.py) | portable | structural; prerequisites:  |
| [`test_release_workflow_contract.py`](../tests/test_release_workflow_contract.py) | portable | structural; prerequisites:  |
| [`test_revision91.py`](../tests/test_revision91.py) | not-automated | private/output legacy; SDK/managed; native-mocked |
| [`test_revision95.py`](../tests/test_revision95.py) | not-automated | native-mocked |
| [`test_rfhat_nrf24_ownership.py`](../tests/test_rfhat_nrf24_ownership.py) | not-automated | native-mocked |
| [`test_rfhat_receive_integration.py`](../tests/test_rfhat_receive_integration.py) | not-automated | native-mocked; historical git prerequisite |
| [`test_s3_lvgl_memory_contract.py`](../tests/test_s3_lvgl_memory_contract.py) | portable | structural; prerequisites:  |
| [`test_screen_settings_contract.py`](../tests/test_screen_settings_contract.py) | portable | structural; prerequisites:  |
| [`test_sd_no_psram305.py`](../tests/test_sd_no_psram305.py) | not-automated | native-mocked |
| [`test_sd_psram_led_capabilities.py`](../tests/test_sd_psram_led_capabilities.py) | not-automated | native-mocked |
| [`test_selector_ui.py`](../tests/test_selector_ui.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_startup_diag306.py`](../tests/test_startup_diag306.py) | not-automated | native-mocked |
| [`test_startup_seek307.py`](../tests/test_startup_seek307.py) | not-automated | native-mocked |
| [`test_storage_gate.py`](../tests/test_storage_gate.py) | not-automated | private/output legacy; native-mocked |
| [`test_targeted92.py`](../tests/test_targeted92.py) | not-automated | Transitive legacy helper/import or not yet reviewed for output isolation |
| [`test_targeted93.py`](../tests/test_targeted93.py) | not-automated | private/output legacy; native-mocked |
| [`test_tile_trigger.py`](../tests/test_tile_trigger.py) | not-automated | native-mocked |
| [`test_universal_clock_contract.py`](../tests/test_universal_clock_contract.py) | portable | structural; prerequisites:  |
| [`test_wardrive_startup_lifecycle.py`](../tests/test_wardrive_startup_lifecycle.py) | not-automated | native-mocked |
| [`test_ws28_audio_settle97.py`](../tests/test_ws28_audio_settle97.py) | not-automated | private/output legacy; native-mocked |
| [`test_ws35_rotation.py`](../tests/test_ws35_rotation.py) | portable | structural; prerequisites:  |
| [`test_ws_c5_28_ntp_clock_contract.py`](../tests/test_ws_c5_28_ntp_clock_contract.py) | portable | structural; prerequisites:  |
| [`test_ws_c5_35_power_rtc.py`](../tests/test_ws_c5_35_power_rtc.py) | not-automated | native-mocked; historical git prerequisite |
| [`test_ws_c5_35_support_contract.py`](../tests/test_ws_c5_35_support_contract.py) | portable | structural; prerequisites:  |
| [`test_ws_default_orientation.py`](../tests/test_ws_default_orientation.py) | portable | structural; prerequisites:  |
| [`test_ws_s3_5b_contract.py`](../tests/test_ws_s3_5b_contract.py) | not-automated | private/output legacy; native-mocked |

## Other committed runners

- [`scripts/verify-dev-packages.py`](../scripts/verify-dev-packages.py): Read-only nine-board ELF/package/manifests verifier; requires built ELF/config/package inputs; separate manual package gate, not host test coverage. Not in the automated manifest.
- [`tools/WS28AudioDiag/tests/test_host.py`](../tools/WS28AudioDiag/tests/test_host.py): Separate diagnostic firmware host test; fixed private scratch prerequisite. Not in the automated manifest.
- [`tools/WS28AudioDiag/tests/test_console.py`](../tools/WS28AudioDiag/tests/test_console.py): Separate diagnostic ELF/link/config verifier; requires diagnostic build and cross nm. Not in the automated manifest.
- [`tools/qr_frame_replay.py`](../tools/qr_frame_replay.py): Optional private offline image replay; Pillow/zxing-cpp and authorized captures; not default gate. Not in the automated manifest.
- [`tools/fsd.py`](../tools/fsd.py): Explicit hardware serial tool; installed but unavailable on this VM due absent physical serial access. Not in the automated manifest.

C fixtures, harness headers and baselines are listed in `support_files` in the JSON
inventory; they are compiled/consumed by their Python owners, not separately counted.
`qr_native.py`, audio SDK-slot helpers and NVS stubs are helper modules, not gates.

## Release-specific evidence (preserved, not imported wholesale)

The original v3.0.42 evidence workspace remains outside the checkout and is not a
dependency of any new harness. `cym042-create-tests.py` is a release generator with
unrelated copy/ownership checks and file-write side effects: it was inspected,
**not executed**. Only its useful extraction logic/scaffold was promoted and
corrected. `ble-native/host.c`, `nimble-semantics.txt`, `layout-harness.py` and
`final-verification.json` were inspected as accepted/reference evidence. The
expanded layout logic replaces the existing maintained layout runner; it does
not import a candidate firmware source. Original scripts and logs are preserved.

`full-suite.py`, `run-tests.py`, `extra-gates.py`, selector adaptations, baseline
scripts and nine-board build/package drivers are release/evidence orchestration,
not portable repo gates. Their broad or historical counts are not inherited here.
Package A's supplied standalone script is not imported as accepted proof; see the
[corrected note](../docs/testing/package-a-corrected-coverage.md). No unaccepted
candidate firmware, entire evidence tree, private capture, or generated binary is
added to this repository. Historical FSD/RF claims are not upgraded by consolidation.

## Package G maintained additions

- `tests/run_pn532_ownership_host.py`: portable, mocked-host; prerequisites cc.
- `tests/run_pn532_manager_host.py`: portable, mocked-host; prerequisites cc.
- `tests/run_pn532_claims_host.py`: portable, mocked-host; prerequisites cc.
- `tests/run_pn532_idf_contract_host.py`: sdk-native, installed-sdk-host; prerequisites cc, idf-i2c.

Package C: `run_hat_tx_host.py`, `run_hat_emitters_host.py`, and `run_hat_runtime_host.py` execute production state/emitter/control code with sanitizers, synthetic SDK faults and semantic mutants (portable gate). Actual LVGL topbar geometry/click/delete coverage is in the existing display-layout SDK-native gate. None establishes physical RF/optical silence.
