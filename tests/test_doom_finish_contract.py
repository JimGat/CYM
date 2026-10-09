from pathlib import Path
import hashlib,json,re,unittest
ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/'ESP32C5/components/cym_doom'
class FinishContracts(unittest.TestCase):
 def test_full_asset_help_both_errors(self):
  s=(COMP/'doom_ui.c').read_text()
  self.assertIn('https://github.com/JimGat/CYM-SD-Assets/tree/feature/doom-sd-assets/sdcard',s)
  self.assertIn('Copy the contents of sdcard/ to the FAT32 SD root.',s)
  self.assertIn('Required: doom/doom1.wad',s)
  self.assertRegex(s,r'"Missing WAD:[^"]+" ASSET_HELP')
  self.assertRegex(s,r'"Invalid/unsupported WAD[^"]+" ASSET_HELP')
  self.assertIn('worker_status[768]',s)
  self.assertIn('_Static_assert(sizeof(worker_status) > sizeof(ASSET_HELP) + 128',s)
 def test_error_wrap_scroll_leaves_exit(self):
  s=(COMP/'doom_ui.c').read_text()
  self.assertIn('lv_label_set_long_mode(status,LV_LABEL_LONG_WRAP)',s)
  self.assertIn('lv_obj_set_scroll_dir(status_scroll,LV_DIR_VER)',s)
  self.assertIn('lv_obj_set_height(status_scroll,lv_disp_get_ver_res(NULL)-90)',s)
  self.assertIn('lv_obj_move_foreground(status_scroll)',s)
  self.assertIn('lv_obj_add_flag(canvas,LV_OBJ_FLAG_HIDDEN)',s)
  self.assertIn('"Menu","OK","Exit"',s)
 def test_join_precedes_ui_free(self):
  s=(COMP/'doom_ui.c').read_text();release=s[s.index('static void release_ui'):s.index('static void update')]
  self.assertLess(release.index('vTaskDelete(worker)'),release.index('lv_obj_del(overlay)'))
  self.assertLess(release.index('vTaskDelete(worker)'),release.index('free(surface)'))
  self.assertIn('if(!__atomic_load_n(&done,__ATOMIC_ACQUIRE))return;',release)
  self.assertNotIn('vTaskDelete(NULL)',s)
 def test_persistent_engine_arguments(self):
  self.assertIn('static void create(void){static char *argv[]',(COMP/'doom_session.c').read_text())
 def test_idf_early_dependencies(self):
  s=(COMP/'CMakeLists.txt').read_text()
  self.assertLess(s.index('REQUIRES heap esp_timer freertos lvgl mbedtls'),s.index('return()'))
  self.assertIn('SRCS ${doom_sources}',s)
  self.assertIn('CONFIG_BOARD_WS_C5_28 OR CONFIG_BOARD_WS_C5_35',s)
 def test_distributable_source_and_exact_patch(self):
  p=json.loads((COMP/'PROVENANCE.json').read_text())
  self.assertEqual(p['commit'],'92bd5c3968197683041e7917e5f9e709164ba1fd')
  self.assertTrue((COMP/p['patch']).is_file())
  for e in p['imported_files']:
   self.assertEqual(hashlib.sha256((COMP/e['path']).read_bytes()).hexdigest(),e['source_sha256'])
  ui=(COMP/'doom_ui.c').read_text()
  for obsolete in ('Corresponding private source','Publication is held','No WAD is bundled'):
   self.assertNotIn(obsolete,ui)
  self.assertIn('Firmware embeds no WAD.',ui)
  self.assertIn('license and credits in the SD assets',ui)
 def test_beta_pin_never_changes_stable_source(self):
  w=(ROOT/'.github/workflows/deploy-flasher.yml').read_text()
  self.assertIn('ref: main',w)
  self.assertIn('cp -a stable-site/_site _site',w)
  self.assertIn('test "$GITHUB_REF" = "refs/heads/Jimgat_Dev"',w)
  self.assertIn('test "$GITHUB_SHA" = "$EXPECTED_SHA"',w)
  self.assertIn("sha = os.environ['GITHUB_SHA']",w)
  self.assertIn("page = Path('_site/beta/index.html')",w)
if __name__=='__main__':unittest.main(verbosity=2)
