"""Installer invariants; all paths are isolated, no network or real installations."""
import importlib.util,io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("essay_install",ROOT/"install.py")
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
class InstallerTests(unittest.TestCase):
 def test_https_or_loopback(self):
  self.assertEqual(install.safe_url("https://example.org/"),"https://example.org/")
  self.assertEqual(install.safe_url("http://127.0.0.1:8767/"),"http://127.0.0.1:8767/")
  for url in ("http://example.org/","file:///tmp/a","https://user:password@example.org/"):
   with self.assertRaises(ValueError):install.safe_url(url)
 def test_safe_zip(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   for n,entry in enumerate(("../escape","/absolute","review-elementary-essays-local/../../escape",
                              "review-elementary-essays-local/C:/escape","bad-root/SKILL.md")):
    archive=root/(str(n)+".zip")
    with zipfile.ZipFile(archive,"w") as z:z.writestr(entry,"x")
    stage=root/("out"+str(n));stage.mkdir()
    with self.assertRaises(ValueError):install.extract_bundle(archive,stage)
 def test_existing_target_stops_before_download(self):
  import argparse
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);target=root/"existing";target.mkdir()
   (target/"preserve.txt").write_text("keep")
   args=argparse.Namespace(mode="core",agent="opencode",dest=str(target),runtime=str(root/"runtime"),font=None,site="https://example.org/")
   with patch.object(install,"download",side_effect=AssertionError("network must not be used")):
    with self.assertRaisesRegex(ValueError,"Target exists"):install.install(args)
   self.assertEqual((target/"preserve.txt").read_text(),"keep")
   self.assertFalse((root/"runtime").exists())
 def test_unowned_runtime_preserved(self):
  import argparse
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);runtime=root/"runtime";runtime.mkdir();(runtime/"keep").write_text("keep")
   args=argparse.Namespace(mode="core",agent="opencode",dest=str(root/"new-skill"),runtime=str(runtime),font=None,site="https://example.org/")
   with self.assertRaisesRegex(ValueError,"not owned"):install.install(args)
   self.assertEqual((runtime/"keep").read_text(),"keep")
 def test_defaults_and_legacy_protection(self):
  with tempfile.TemporaryDirectory() as temp:
   home=Path(temp)
   with patch.object(Path,"home",return_value=home),patch.dict(install.os.environ,{"CODEX_HOME":str(home/".codex")}):
    self.assertEqual(install.skill_target("opencode"),(home/".config/opencode/skills"/install.NAME).resolve())
    self.assertEqual(install.skill_target("codex"),(home/".agents/skills"/install.NAME).resolve())
    (home/".codex/skills"/install.NAME).mkdir(parents=True)
    with self.assertRaisesRegex(ValueError,"legacy"):install.skill_target("codex")
 def test_release_archive_matches_every_file(self):
  import hashlib
  m=json.loads((ROOT/"docs/downloads/release.json").read_text(encoding="utf-8"))
  raw=(ROOT/"docs"/m["archive"]).read_bytes()
  self.assertEqual(len(raw),m["bytes"]);self.assertEqual(hashlib.sha256(raw).hexdigest(),m["sha256"])
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   self.assertIsNone(z.testzip())
   self.assertEqual(len(z.namelist()),len(m["files"]))
   for path,digest in m["files"].items():
    self.assertEqual(hashlib.sha256(z.read(install.NAME+"/"+path)).hexdigest(),digest)
 def test_site_has_complete_install_resources(self):
  for name in ("INSTALL.md","USAGE.md","README.md","install.py","models.json","agent.json","index.html"):
   self.assertTrue((ROOT/"docs"/name).is_file(),name)
  import re
  for link in re.findall(r'href="([^"]+)"',(ROOT/"docs/index.html").read_text(encoding="utf-8")):
   if not link.startswith("https://"):self.assertTrue((ROOT/"docs"/link).is_file(),link)
if __name__=="__main__":unittest.main(verbosity=2)
