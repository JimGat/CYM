#!/usr/bin/env python3
"""Messenger SDK/owner source contracts; native behavioral worker harness is a separate gate."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class MessengerSDK(unittest.TestCase):
 def test_actual_adapter_and_bounded_callback(self):
  p=R/'ESP32C5/main/cym_messenger.c';self.assertTrue(p.exists(),'ESP-NOW worker not implemented')
  s=p.read_text();self.assertIn('esp_now_send(',s);self.assertIn('esp_now_register_recv_cb(',s);self.assertIn('psa_mac_compute(',s)
  self.assertNotIn('esp_now_deinit(',s);self.assertNotIn('ESP_LOG',s);self.assertIn('4096',s);self.assertIn('MALLOC_CAP_INTERNAL',s)
  cb=s[s.index('static void receive_cb('):s.index('static bool sdk_auth(')]
  self.assertNotIn('lv_',cb);self.assertNotIn('mbedtls',cb);self.assertNotIn('portMAX_DELAY',cb)
 def test_installed_sdk_contract(self):
  import os
  sdk=Path(os.environ['IDF_PATH'])/'components/esp_wifi/include/esp_now.h';s=sdk.read_text()
  self.assertIn('#define ESP_NOW_MAX_IE_DATA_LEN      250',s)
  info=s[s.index('typedef struct esp_now_recv_info'):s.index('} esp_now_recv_info_t')]
  self.assertNotIn('encrypt;',info);self.assertIn('primary master key is used to encrypt local master key',s)
 def test_b_and_d_lifetime_boundaries(self):
  common=(R/'ESP32C5/components/wifi_cli/wifi_common.c').read_text()
  self.assertIn('cym_wifi_messenger_claim',common);self.assertIn('messenger_owner',common)
  main=(R/'ESP32C5/main/main.c').read_text();self.assertIn('cym_messenger_radio_claim',main)
  attacks=(R/'ESP32C5/components/wifi_attacks/wifi_attacks.c').read_text();self.assertIn('owner > 5',attacks)
if __name__=='__main__':unittest.main(verbosity=2)
