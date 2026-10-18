import importlib.util,json,pathlib,subprocess,sys,tempfile,unittest
root=pathlib.Path(__file__).resolve().parents[2]/'examples/uu-handoff/finished'
spec=importlib.util.spec_from_file_location('handoff',root/'handoff_brief.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Acceptance(unittest.TestCase):
 def record(self,result='passed',evidence=None):
  return dict(platform='NAS',component='terminal',check='scope',result=result,evidence=[] if evidence is None else evidence)
 def test_labels_and_scope(self):
  records=[self.record(evidence=['unit test log']),self.record(evidence=['  ']),self.record('failed',evidence=['log'])]
  text=m.build_brief(records)
  self.assertEqual(text.splitlines()[0],'# uu-remote-linux 验收交接')
  self.assertIn('- [有证据] NAS / terminal / scope: passed',text)
  self.assertIn('- [待补证] NAS / terminal / scope: passed',text)
  self.assertIn('- [未通过] NAS / terminal / scope: failed',text)
  self.assertEqual(text.splitlines()[-1],'上线状态：未确认；测试结果不代表已部署。')
  self.assertNotIn('纸灯接力',text)
 def test_order(self):
  a=self.record();b=dict(self.record(),platform='GNOME-X11',component='desktop')
  text=m.build_brief([a,b]);self.assertLess(text.index('NAS / terminal'),text.index('GNOME-X11 / desktop'))
 def test_cli_invalid(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'x.json';p.write_text('{}')
   v=subprocess.run([sys.executable,str(root/'handoff_brief.py'),str(p)],capture_output=True,text=True)
   self.assertEqual(v.returncode,2);self.assertEqual(v.stdout,'');self.assertTrue(v.stderr.strip())
 def test_cli_valid_failed_is_zero(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'x.json';p.write_text(json.dumps([self.record('failed')]))
   v=subprocess.run([sys.executable,str(root/'handoff_brief.py'),str(p)],capture_output=True,text=True)
   self.assertEqual(v.returncode,0);self.assertIn('[未通过]',v.stdout)
 def test_empty_input_keeps_unconfirmed_footer(self):
  self.assertEqual(m.build_brief([]).splitlines()[-1],'上线状态：未确认；测试结果不代表已部署。')
if __name__=='__main__':unittest.main(verbosity=2)
