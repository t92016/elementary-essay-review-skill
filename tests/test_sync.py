"""Mirror invariants and checkout-local installer behavior; no OCR or real install."""
import functools, hashlib, http.server, importlib.util, io, json, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
sync=load("mirror_sync",ROOT/"tools/sync_private.py")
local=load("checkout_install",ROOT/"tools/install_from_checkout.py")

class SyncTests(unittest.TestCase):
    def fixture(self, temp):
        source=Path(temp)/"source"; target=Path(temp)/"target"
        for p in (source,target):
            p.mkdir();sync.git(p,"init","-q");sync.git(p,"config","user.name","Test");sync.git(p,"config","user.email","test@example.invalid")
        sync.git(target,"remote","add","origin","https://github.com/t92016/Codex-Skills.git")
        payload=b"---\nname: review-elementary-essays-local\ndescription: test\n---\n"
        (source/sync.SKILL).mkdir(parents=True);(source/sync.SKILL/"SKILL.md").write_bytes(payload)
        (source/"docs/downloads").mkdir(parents=True)
        for name in ("INSTALL.md","USAGE.md","install.py"):
            (source/name).write_text("test",encoding="utf-8");(source/"docs"/name).write_text("test",encoding="utf-8")
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,"w") as z:z.writestr(sync.NAME+"/SKILL.md",payload)
        raw=archive.getvalue();(source/"docs/downloads/skill.zip").write_bytes(raw)
        release=dict(name=sync.NAME,version="1.0.0",archive="downloads/skill.zip",bytes=len(raw),sha256=sync.digest(raw),files={"SKILL.md":sync.digest(payload)})
        (source/"docs/downloads/release.json").write_text(json.dumps(release),encoding="utf-8")
        sync.git(source,"add",".");sync.git(source,"commit","-qm","fixture")
        (target/"manifest").mkdir();(target/"manifest/skills.json").write_text(json.dumps({"skills":[{"name":"other","fileCount":1}]}),encoding="utf-8")
        (target/"unrelated.txt").write_text("keep")
        return source,target

    def test_check_write_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=self.fixture(temp)
            self.assertFalse(sync.synchronize(a,b)["synchronized"])
            self.assertFalse((b/sync.SKILL).exists())
            self.assertTrue(sync.synchronize(a,b,True)["synchronized"])
            self.assertTrue(sync.synchronize(a,b)["synchronized"])
            self.assertEqual((b/"unrelated.txt").read_text(),"keep")
            self.assertEqual(json.loads((b/"manifest/skills.json").read_text())["skills"][0],{"name":"other","fileCount":1})
            (b/sync.SKILL/"SKILL.md").write_text("tamper")
            self.assertFalse(sync.synchronize(a,b)["synchronized"])

    def test_source_manifest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=self.fixture(temp)
            (a/sync.SKILL/"SKILL.md").write_text("tamper")
            sync.git(a,"add",".");sync.git(a,"commit","-qm","broken source")
            with self.assertRaisesRegex(ValueError,"manifest"):sync.synchronize(a,b,True)
            self.assertFalse((b/sync.SKILL).exists())

    def test_dirty_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=self.fixture(temp);(a/"untracked").write_text("x")
            with self.assertRaisesRegex(ValueError,"source changes"):sync.synchronize(a,b,True)

    def test_unmanaged_extra_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=self.fixture(temp);sync.synchronize(a,b,True)
            extra=b/sync.SKILL/"keep.txt";extra.write_text("keep")
            with self.assertRaisesRegex(ValueError,"Unmanaged"):sync.synchronize(a,b,True)
            self.assertEqual(extra.read_text(),"keep")

    def test_unsafe_target_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in ("../escape","/absolute","x/.git/config","C:/escape","x\\escape"):
                with self.assertRaises(ValueError):sync.checked_path(Path(temp).resolve(),value)

    def test_checkout_installer_serves_own_bundle(self):
        import urllib.request
        def fake_run(command,check):
            self.assertEqual(command[-2:],["--help","sample"])
            site=command[command.index("--site")+1]
            self.assertEqual(urllib.request.urlopen(site+"downloads/release.json",timeout=3).read(),(ROOT/"docs/downloads/release.json").read_bytes())
            self.assertEqual(urllib.request.urlopen(site+"install.py",timeout=3).read(),(ROOT/"install.py").read_bytes())
            return subprocess.CompletedProcess(command,0)
        with patch.object(local.subprocess,"run",side_effect=fake_run):
            self.assertEqual(local.main(["--help","sample"]),0)
        with self.assertRaises(ValueError):local.main(["--site=https://example.org"])
if __name__=="__main__":unittest.main(verbosity=2)
