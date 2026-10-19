#!/usr/bin/env python3
"""Bump scoop bucket manifests from upstream Gitee releases.

Portable (stdlib only) twin of scoop's checkver+autoupdate for the manifests in this
bucket, so it can run either in a Gitee Go runner or on the Windows box.

  checkver.py                     # report + rewrite manifests in place
  checkver.py --dry-run           # report only
  checkver.py --commit            # git commit + push the bumped manifests to origin
                                  # (this is what the Gitee Go pipeline runs)
Exit code: 0 = nothing to do or change applied, 1 = failure.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "scoop-bucket-checkver/1.0"


def http_get(url: str, binary: bool = False) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    return data if binary else data.decode("utf-8", "replace")


def latest_tag(source_repo: str) -> str:
    body = json.loads(http_get(f"https://gitee.com/api/v5/repos/{source_repo}/releases/latest"))
    tag = str(body["tag_name"])
    return re.sub(r"^v", "", tag)


def hash_for(spec: dict, version: str) -> str:
    text = http_get(spec["checksums_template"].format(version=version))
    needle = spec["asset_pattern"].format(version=version)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1].endswith(needle):
            return fields[0].lower()
    raise SystemExit(f"checksums.txt has no line for {needle}")


def bump(spec: dict, dry: bool) -> tuple[str, str] | None:
    """Return (old, new) when the manifest is stale, else None."""
    path = ROOT / spec["manifest"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    current = manifest["version"]
    newest = latest_tag(spec["source_repo"])
    if newest == current:
        return None
    url = spec["url_template"].format(version=newest)
    digest = hash_for(spec, newest)
    print(f"{path.name}: {current} -> {newest}")
    if not dry:
        manifest["version"] = newest
        manifest["url"] = url
        manifest["hash"] = digest
        path.write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    return current, newest


def commit_git(paths: list[str], version_summary: str) -> None:
    """Commit the rewritten manifests and push them to origin.

    Used by the Gitee Go pipeline: the runner's checked-out workspace already carries the
    pipeline access token in its remote URL, so `git push` is the write path that needs no
    secret of mine in the YAML. Nothing is ever printed; if the remote rejects the push the
    command surfaces the error and the build fails loudly.
    """
    def git(*a):
        r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"git {' '.join(a)} failed: {r.stderr.strip()[:200]}")
        return r.stdout.strip()

    git("add", "--", *paths)
    if not git("diff", "--cached", "--name-only"):
        print("nothing staged; skipping commit")
        return
    git("commit", "-q", "-m", f"checkver: bump {version_summary}")
    git("push", "-q", "origin", "HEAD")
    print(f"pushed bump commit for {version_summary}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit", action="store_true", help="git commit + push the bumped manifests")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "ci" / "checkver.json").read_text(encoding="utf-8"))
    stale: list[tuple[str, str, str]] = []
    for spec in cfg["apps"]:
        moved = bump(spec, args.dry_run)
        if moved:
            stale.append((spec["manifest"], moved[0], moved[1]))
    if not stale:
        print("all manifests already at the newest release")
        return 0
    summary = ", ".join(f"{Path(p).name} {old}->{new}" for p, old, new in stale)
    if args.dry_run:
        print(f"would commit {len(stale)} manifest change(s): {summary}")
        return 0
    print(f"updated {len(stale)} manifest(s) in place: {summary}")
    if args.commit:
        commit_git([p for p, _, _ in stale], summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
