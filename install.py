#!/usr/bin/env python3
"""Install the versioned local essay skill without touching existing skills."""
import argparse, hashlib, json, os, platform, shutil, struct, subprocess, sys, tempfile, urllib.parse, urllib.request, uuid, venv, zipfile
from pathlib import Path, PurePosixPath

VERSION="1.0.0"
NAME="review-elementary-essays-local"
SITE="https://t92016.github.io/elementary-essay-review-skill/"

def write_json(path, data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def safe_url(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https" and not (parsed.scheme=="http" and parsed.hostname in ("127.0.0.1","localhost")):
        raise ValueError("HTTPS required (loopback HTTP is allowed for local tests)")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in download URLs are not supported")
    return url

def download(url, limit):
    with urllib.request.urlopen(safe_url(url),timeout=60) as response:
        safe_url(response.url)
        blocks=[];size=0
        while True:
            block=response.read(1024*1024)
            if not block:break
            size+=len(block)
            if size>limit:raise ValueError("Download exceeds size limit")
            blocks.append(block)
        return b"".join(blocks)

def extract_bundle(archive, stage, expected_root=NAME):
    total=0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name=PurePosixPath(item.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in item.filename or not name.parts or name.parts[0]!=expected_root or any(":" in part for part in name.parts):
                raise ValueError("Unsafe archive path")
            if (item.external_attr>>16)&0o170000==0o120000:
                raise ValueError("Symlinks are not allowed")
            total+=item.file_size
            if total>20*1048576:raise ValueError("Unpacked skill exceeds limit")
            dest=stage.joinpath(*name.parts)
            if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open("xb") as f:f.write(z.read(item))
    root=stage/expected_root
    if not (root/"SKILL.md").is_file():raise ValueError("Missing SKILL.md")
    return root

def skill_target(agent, override=None):
    if override:return Path(override).expanduser().resolve()
    base=Path.home()/(".config/opencode/skills" if agent=="opencode" else ".agents/skills")
    if agent in ("codex","shared"):
        legacy=Path(os.environ.get("CODEX_HOME",str(Path.home()/".codex")))/"skills"/NAME
        if legacy.exists():
            raise ValueError("Existing Codex legacy skill found; leave it unchanged: "+str(legacy))
    return (base/NAME).resolve()

def execute(command, log):
    print("Running: "+str(command[0])+" "+str(command[1]),flush=True)
    with log.open("a",encoding="utf-8") as stream:
        stream.write("\nCOMMAND "+json.dumps([str(x) for x in command])+"\n");stream.flush()
        subprocess.run([str(x) for x in command],stdout=stream,stderr=subprocess.STDOUT,check=True,
                       env=dict(os.environ,PYTHONUTF8="1",PYTHONDONTWRITEBYTECODE="1",
                                OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1"))

def install(args):
    if sys.version_info<(3,10):raise ValueError("Python 3.10+ required")
    if args.mode=="full" and (os.name!="nt" or struct.calcsize("P")!=8 or sys.version_info[:2]!=(3,12)):
        raise ValueError("Full OCR requires native Windows x64 and Python 3.12; use --mode core elsewhere")
    target=skill_target(args.agent,args.dest)
    if target.exists() or target.is_symlink():raise ValueError("Target exists; no overwrite: "+str(target))
    runtime=Path(args.runtime).expanduser().resolve()
    if os.name=="nt" and not str(runtime).isascii():
        raise ValueError("Use a stable local ASCII runtime path, e.g. C:/EssayReview")
    if target==runtime or runtime in target.parents or target in runtime.parents:
        raise ValueError("Runtime and global skill directories must be separate")
    marker=runtime/".essay-installer.json"
    identity={"version":VERSION,"target":str(target),"mode":args.mode}
    if runtime.exists():
        if not marker.is_file() or json.loads(marker.read_text(encoding="utf-8"))!=identity:
            raise ValueError("Runtime is not owned by this installation; choose a new directory")
    else:runtime.mkdir(parents=True)
    write_json(marker,identity)
    log=runtime/"installation.log"
    report={"version":VERSION,"agent":args.agent,"mode":args.mode,"target":str(target),
            "runtime":str(runtime),"status":"starting","ocr_inference_tested":False,
            "visual_review_completed":False}
    state=runtime/"installation-state.json"
    write_json(state,report)
    site=safe_url(args.site.rstrip("/")+"/")
    try:
        metadata=json.loads(download(urllib.parse.urljoin(site,"downloads/release.json"),1024*1024))
        if metadata["version"]!=VERSION or metadata["name"]!=NAME:
            raise ValueError("Installer and release versions differ")
        bundle_url=urllib.parse.urljoin(site,metadata["archive"])
        if urllib.parse.urlparse(bundle_url).netloc!=urllib.parse.urlparse(site).netloc:
            raise ValueError("Bundle must be served from the same site")
        raw=download(bundle_url,10*1048576)
        if len(raw)!=metadata["bytes"] or hashlib.sha256(raw).hexdigest()!=metadata["sha256"]:
            raise ValueError("Bundle checksum or size mismatch")
        archive=runtime/("skill-"+VERSION+".zip");archive.write_bytes(raw)
        with tempfile.TemporaryDirectory(prefix="essay-unpack-",dir=runtime) as temp:
            stage=Path(temp).resolve()
            assert runtime in stage.parents
            skill=extract_bundle(archive,stage)
            for relative,expected in metadata["files"].items():
                p=PurePosixPath(relative)
                if p.is_absolute() or ".." in p.parts or "\\" in relative:raise ValueError("Unsafe file manifest")
                f=skill.joinpath(*p.parts)
                if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
                    raise ValueError("Skill file mismatch: "+relative)
            actual={p.relative_to(skill).as_posix() for p in skill.rglob("*") if p.is_file()}
            if actual!=set(metadata["files"]):raise ValueError("Unexpected skill files")
            environment=runtime/"venv"
            if not environment.exists():
                print("Creating isolated Python environment",flush=True)
                venv.EnvBuilder(with_pip=True).create(environment)
            python=environment/("Scripts/python.exe" if os.name=="nt" else "bin/python")
            if not python.is_file():raise ValueError("Incomplete venv; preserve logs and choose a new runtime")
            requirements=skill/("requirements-ocr-windows-lock.txt" if args.mode=="full" else "requirements-core.txt")
            execute([python,"-m","pip","install","--disable-pip-version-check","--no-input",
                     "--retries","1","--timeout","45","--prefer-binary","-r",requirements],log)
            models=runtime/"models"
            if args.mode=="full":
                execute([python,"-X","utf8",skill/"scripts/fetch_mobile_models.py","--out",models],log)
            check=[python,"-X","utf8",skill/"scripts/check_environment.py","--out",runtime/"environment.json"]
            if args.mode=="full":check+=["--require-ocr","--models",models]
            if args.font:check+=["--font",args.font]
            execute(check,log)
            env_report=json.loads((runtime/"environment.json").read_text(encoding="utf-8"))
            font=args.font or env_report["font"]
            self_out=runtime/("self-test-"+uuid.uuid4().hex[:8])
            execute([python,"-X","utf8",skill/"scripts/self_test.py","--out",self_out,"--font",font],log)
            self_report=json.loads((self_out/"self-test.json").read_text(encoding="utf-8"))
            if not self_report["pass"]:raise ValueError("Synthetic self-test failed")
            if args.mode=="full" and self_report["pdf_status"]!="generated":
                raise ValueError("Full mode requires a successful PDF self-test; choose an embeddable TrueType CJK font")
            report.update(status="installed",python=str(python),models=str(models) if args.mode=="full" else None,
                          cache=str(runtime/"cache"),font=font,site=site,archive_sha256=metadata["sha256"],
                          environment=env_report,self_test=self_report,self_test_directory=str(self_out),
                          note="Configuration and synthetic output only; OCR inference, visual review and teacher judgment are separate.")
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="essay-install-",dir=target.parent) as deploy:
                deploy=Path(deploy).resolve()
                assert target.parent==deploy.parent
                payload=deploy/NAME
                shutil.copytree(skill,payload)
                write_json(payload/"installation.json",report)
                if target.exists():raise ValueError("Target appeared during installation; no overwrite")
                payload.rename(target)
            write_json(state,report)
        return report
    except Exception as exc:
        details=getattr(exc,"output",b"") or b""
        if isinstance(details,bytes):details=details.decode("utf-8",errors="replace")
        if details:
            with log.open("a",encoding="utf-8") as stream:stream.write("\nSUBPROCESS OUTPUT\n"+details)
        report.update(status="failed",error=str(exc),log=str(log))
        write_json(state,report)
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agent",choices=("codex","opencode","shared"),default="codex")
    p.add_argument("--mode",choices=("full","core"),default="full")
    p.add_argument("--runtime",required=True)
    p.add_argument("--dest",help="Explicit new target; used for isolated validation or custom user layouts")
    p.add_argument("--font")
    p.add_argument("--site",default=SITE)
    args=p.parse_args()
    try:
        result=install(args);print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:
        print("Installation stopped: "+str(exc),file=sys.stderr);return 1
    return 0
if __name__=="__main__":sys.exit(main())
