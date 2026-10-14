from pathlib import Path
import unittest,subprocess,re,json
ROOT=Path(__file__).resolve().parents[1]
class Flasher95(unittest.TestCase):
 def test_real_selector_normal_and_beta_grouping(self):
  s=(ROOT/'ESP32C5/docs/index.html').read_text()
  defs=s[s.index('const BOARDS ='):s.index('// Hidden opt-in:')]
  render=s[s.index('const renderBoardButtons ='):s.index('const manifestError =')]
  for beta,n in [(False,6),(True,8)]:
   code=defs+f'\nconst betaUnlock={str(beta).lower()};const state={{board:"nm-cyd-c5"}};'+r'''
const mk=()=>({children:[],dataset:{},appendChild(x){this.children.push(x)},addEventListener(){},querySelectorAll(){return []},remove(){}});
const document={createElement:mk};const ui={boardSelectorRow:mk()};const switchBoard=()=>{};
'''+render+r'''
renderBoardButtons();
const groups=ui.boardSelectorRow.children.filter(x=>x.dataset.boardClass);
const result=groups.map(g=>({chip:g.dataset.boardClass,boards:g.children.filter(x=>x.dataset.board).map(x=>({id:x.dataset.board,label:x.textContent}))}));
console.log(JSON.stringify(result));
'''
   p=subprocess.run(['node','-e',code],text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
   groups=json.loads(p.stdout);self.assertEqual([g['chip'] for g in groups],['ESP32 Wroom','ESP32-S3','ESP32-C5'])
   boards=[b for g in groups for b in g['boards']];self.assertEqual(len(boards),n)
   self.assertIn('hackerbox-cyd',[b['id'] for b in boards]);self.assertNotIn('Dev Only',next(b['label'] for b in boards if b['id']=='hackerbox-cyd'))
   for g in groups:self.assertEqual([b['label'].lower() for b in g['boards']],sorted(b['label'].lower() for b in g['boards']))
 def test_main_page_deployment_updates_ui_not_stable_firmware(self):
  s=(ROOT/'.github/workflows/deploy-flasher.yml').read_text()
  self.assertIn("Path('_site/index.html').write_text",s)
  self.assertIn('stable: "main"',s)
  page=(ROOT/'ESP32C5/docs/index.html').read_text();hb=re.search(r'"hackerbox-cyd": \{.*?\n        \}',page,re.S).group()
  self.assertIn('beta: false',hb);self.assertIn('stableAvailable: true',hb)
if __name__=='__main__':unittest.main()
