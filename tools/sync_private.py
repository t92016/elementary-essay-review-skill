"""Check or mirror the committed public release into a private Codex-Skills checkout.
No push, credential handling, global-skill installation, or model execution.
"""
import argparse, hashlib, io, json, subprocess, sys, zipfile
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[1]
NAME = "review-elementary-essays-local"
PACKAGE = "packages/elementary-essay-review-skill/"
SKILL = "skills/" + NAME + "/"
MANIFEST = "manifest/essay-release.json"

def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def checked_path(root, relative):
    p = PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(x in ("..", ".git") or ":" in x for x in p.parts) or "\\" in relative:
        raise ValueError("Unsafe managed path")
    dest = root.joinpath(*p.parts)
    if root not in dest.resolve().parents:
        raise ValueError("Managed path escapes checkout")
    if any(x.is_symlink() for x in [dest, *dest.parents] if x != root and root in x.parents):
        raise ValueError("Linked managed path")
    return dest

def release_snapshot(source):
    if git(source, "status", "--porcelain").strip():
        raise ValueError("Commit or preserve source changes before synchronization")
    commit = git(source, "rev-parse", "HEAD").decode().strip()
    paths = git(source, "ls-tree", "-r", "--name-only", "-z", "HEAD").decode().split("\0")
    files = {p: git(source, "show", "HEAD:" + p) for p in paths if p}
    release = json.loads(files["docs/downloads/release.json"])
    raw = files["docs/" + release["archive"]]
    if len(raw) != release["bytes"] or digest(raw) != release["sha256"]:
        raise ValueError("Invalid release ZIP")
    skill = {p[len(SKILL):]: b for p, b in files.items() if p.startswith(SKILL)}
    if {p: digest(b) for p, b in skill.items()} != release["files"]:
        raise ValueError("Release manifest and committed skill differ")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.testzip() or set(archive.namelist()) != {NAME + "/" + p for p in skill}:
            raise ValueError("Invalid ZIP entries")
        for p, b in skill.items():
            if archive.read(NAME + "/" + p) != b:
                raise ValueError("ZIP payload differs")
    for name in ("INSTALL.md", "USAGE.md", "install.py"):
        if files["docs/" + name] != files[name]:
            raise ValueError("Stale Pages copy: " + name)
    return commit, files, release

def expected_files(source):
    commit, files, release = release_snapshot(source)
    wanted = {PACKAGE + p: b for p, b in files.items()}
    wanted.update({p: b for p, b in files.items() if p.startswith(SKILL)})
    manifest = {
        "schemaVersion": 1, "name": NAME, "version": release["version"],
        "canonicalRepository": "https://github.com/t92016/elementary-essay-review-skill",
        "canonicalCommit": commit, "archiveSha256": release["sha256"],
        "skillFileCount": len(release["files"]),
        "files": {p: digest(b) for p, b in sorted(wanted.items())},
        "globalInstallationUpdated": False,
        "scope": "Exact committed release mirror; dependencies and models are installed separately."
    }
    wanted[MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    return wanted, manifest

def inventory_entry(wanted):
    entries = sorted(((p[len(SKILL):], b) for p, b in wanted.items() if p.startswith(SKILL)), key=lambda x: x[0].lower())
    lines = [p.replace("/", "\\") + ":" + digest(b).upper() for p, b in entries]
    return {"name": NAME, "fileCount": len(entries), "bytes": sum(len(b) for _, b in entries),
            "contentSha256": digest("\n".join(lines).encode()).upper()}

def synchronize(source, target, write=False):
    source, target = Path(source).resolve(), Path(target).resolve()
    remote = git(target, "remote", "get-url", "origin").decode().strip()
    if remote not in ("https://github.com/t92016/Codex-Skills.git", "https://github.com/t92016/Codex-Skills", "git@github.com:t92016/Codex-Skills.git"):
        raise ValueError("Target must be the private Codex-Skills checkout")
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("Source and target checkouts must be separate")
    wanted, manifest = expected_files(source)
    previous_path = checked_path(target, MANIFEST)
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    owned = set(previous.get("files", {}))
    # A new file inside these trees must be reviewed, rather than silently discarded.
    existing = set()
    for prefix in (PACKAGE, SKILL):
        folder = checked_path(target, prefix)
        if folder.exists():
            existing.update(p.relative_to(target).as_posix() for p in folder.rglob("*") if p.is_file())
    obsolete = existing - set(wanted)
    if obsolete - owned:
        raise ValueError("Unmanaged files in mirror: " + str(sorted(obsolete - owned)))
    for p in obsolete:
        if digest(checked_path(target, p).read_bytes()) != previous["files"][p]:
            raise ValueError("Locally edited obsolete mirror file: " + p)
    changes = [p for p, b in wanted.items() if not checked_path(target, p).is_file() or checked_path(target, p).read_bytes() != b]
    inventory = checked_path(target, "manifest/skills.json")
    data = json.loads(inventory.read_text(encoding="utf-8-sig"))
    desired = inventory_entry(wanted)
    current = next((x for x in data["skills"] if x["name"] == NAME), None)
    inventory_changed = current != desired
    if write:
        for p in changes:
            dest = checked_path(target, p); dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(wanted[p])
        for p in obsolete:
            checked_path(target, p).unlink()
        if inventory_changed:
            if current is None: data["skills"].append(desired)
            else: current.clear(); current.update(desired)
            inventory.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = {"version": manifest["version"], "canonicalCommit": manifest["canonicalCommit"],
              "archiveSha256": manifest["archiveSha256"], "skillFiles": manifest["skillFileCount"],
              "mirroredFiles": len(wanted), "changedFiles": len(changes),
              "obsoleteFiles": len(obsolete), "inventoryChanged": inventory_changed,
              "written": write, "synchronized": not changes and not obsolete and not inventory_changed}
    if write:
        for p, b in wanted.items():
            if checked_path(target, p).read_bytes() != b:
                raise ValueError("Post-write mismatch: " + p)
        report["synchronized"] = True
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="Private Codex-Skills local checkout")
    parser.add_argument("--write", action="store_true", help="Update only the managed mirror; does not commit or push")
    args = parser.parse_args()
    result = synchronize(ROOT, args.target, args.write)
    print(json.dumps(result, indent=2))
    return 0 if result["synchronized"] else 1

if __name__ == "__main__":
    sys.exit(main())
