from pathlib import Path
import re, unittest
ROOT=Path(__file__).resolve().parents[1]
class StartupIsolation(unittest.TestCase):
 def test_early_branch_precedes_every_normal_initializer(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();app=s[s.index('void app_main(void)\n{'):s.index('// Wake from Go Dark:',s.index('void app_main(void)\n{'))]
  app=re.sub(r'/\*.*?\*/|//[^\n]*','',app,flags=re.S)
  branch=app.index('if(game_early_consume(nvs_ret)==GAME_DOOM)')
  self.assertLess(app.index('nvs_flash_init()'),branch)
  for call in ('obs_store_init(','ot_radio_init(','esp_timer_start_periodic(s_survey_flush_tmr','init_gps_uart(','wifi_cli_init() : nvs_ret','nvs_settings_load(','gw_init(','cham_init(','honeypair_init(','blueduck_init(','wp_init(','show_splash_screen(','sd_cache_init('):
   self.assertLess(branch,app.index(call),call)
  self.assertNotIn('wifi_attacks_init_portal_html_buffer(',app) # now admitted by HTML load
  self.assertNotIn('shot_save',app) # now admitted by screenshot click
  self.assertIn('{(void)cym_debug_console_start();game_isolated_main();return;}',app)
 def test_allowlist_suppresses_normal_timers_workers_and_radios(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();f=s[s.index('static void game_isolated_main(void)\n{'):s.index('void app_main(void)\n{')]
  for forbidden in ('wifi_cli_init(','nvs_settings_load(','cym_timekeeper_init(','obs_store_init(','ot_radio_init(','gps_task','shot_save','gw_init(','cham_init(','honeypair_init(','blueduck_init(','wp_init(','show_splash_screen(','screen_idle_timer','sd_cache_init(','load_whitelist','sd_lazy_mount_task','survey_flush','xTaskCreate','nimble','esp_wifi_'):
   self.assertNotIn(forbidden,f,forbidden)
  self.assertIn('wifi_wardrive_init_sd_ex(BOARD_SD_SPI_FREQ_HZ/1000,false)',f)
  self.assertIn('doom_ui_boot_start',f);self.assertIn('apply_screen_orientation(3)',f)
 def test_intent_has_no_ota_partition_or_erase_repair(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();f=s[s.index('static game_read game_nvs_read'):s.index('void app_main(void)\n{')]
  for forbidden in ('nvs_flash_erase','esp_ota_','esp_partition_'):
   self.assertNotIn(forbidden,f)
  self.assertIn('esp_reset_reason()==ESP_RST_SW',f);self.assertIn('game_boot_button_pressed()',f)
 def test_no_live_takeover_and_named_storage_admission(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();f=s[s.index('static const char *game_storage_blocker(void)\n{'):]
  for token in ('s_fileserv_httpd','sd_provision_active','wpasec_upload_task_handle','wdup_task_handle','screenshot_in_progress','g_active_survey','SD transport operation','NVS intent set/commit'):
   self.assertIn(token,f)
  for bad in ('radio_reset_to_idle(','vTaskDelete(','bt_nimble_deinit(','esp_wifi_stop(','cym_exclusive_begin('):self.assertNotIn(bad,f)
  self.assertLess(f.index('game_storage_blocker();'),f.index('game_mode_record('))
  self.assertLess(f.index('game_mode_record('),f.index('esp_restart()'))
  app=s[s.index('void app_main(void)\n{'):s.index('static void lvgl_flush_cb',s.index('void app_main(void)\n{'))] if 'static void lvgl_flush_cb' in s[s.index('void app_main(void)\n{'):] else s[s.index('void app_main(void)\n{'):s.index('// Screenshot utilities')]
  self.assertNotIn('wifi_cli_start_console(',app)

 def test_ws_nvs_unavailable_never_erases_saved_config(self):
  s=(ROOT/'ESP32C5/main/main.c').read_text();app=s[s.index('void app_main(void)\n{'):s.index('    // Passive observation store:',s.index('void app_main(void)\n{'))]
  ws=app[app.index('#if defined(CONFIG_BOARD_WS_C5_28)'):app.index('#else')]
  self.assertNotIn('nvs_flash_erase',ws)
  failure=ws[ws.index('if(nvs_ret!=ESP_OK)'):]
  self.assertNotIn('return;',failure);self.assertIn('degraded normal CYM',failure)
  s=(ROOT/'ESP32C5/components/wifi_cli/wifi_cli.c').read_text();start=s.index('esp_err_t wifi_cli_init(void)');s=s[start:s.index('    // Initialize LED',start)]
  ws=s[s.index('#if defined(CONFIG_BOARD_WS_C5_28)'):s.index('#else')]
  self.assertIn('return ret;',ws);self.assertNotIn('nvs_flash_erase',ws)
