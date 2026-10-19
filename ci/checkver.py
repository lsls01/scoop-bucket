#!/usr/bin/env python3
"""Bump scoop bucket manifests from upstream Gitee releases.

Stdlib-only twin of scoop's checkver+autoupdate for the manifests in this bucket, so the
same logic runs in a GitHub Actions runner and on the Windows box. Scoop itself never
executes checkver/autoupdate (its update path reads only the manifest "version" field), so
this script is what keeps a bucket that has no upstream bucket fresh.

  checkver.py                 # report + rewrite manifests in place
  checkver.py --dry-run       # report only
  checkver.py --commit        # also git commit + push (what the workflow runs)

Exit codes: 0 = no change, or change applied; 2 = change detected but the commit/push step
was refused (so a scheduled run surfaces it instead of looking green).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "scoop-bucket-checkver/1.0"
API = "https://gitee.com/api/v5"


def http_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def latest_tag(source_repo: str) -> str:
    body = json.loads(http_text(f"{API}/repos/{source_repo}/releases/latest"))
    return re.sub(r"^v", "", str(body["tag_name"]))


def hash_for(spec: dict, version: str) -> str:
    """The upstream release's own checksums.txt, never a guess and never hash: skip."""
    text = http_text(spec["checksums_template"].format(version=version))
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
    print(f"{path.name}: {current} -> {newest}")
    if not dry:
        manifest["version"] = newest
        manifest["url"] = spec["url_template"].format(version=newest)
        manifest["hash"] = hash_for(spec, newest)
        path.write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    return current, newest


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout.strip()


def current_branch() -> str:
    """Branch to push back to.

    In Actions the runner checks out a detached HEAD, so GITHUB_REF_NAME is the reliable
    source there; locally the checked-out branch is.
    """
    name = os.environ.get("GITHUB_REF_NAME", "").strip()
    if name:
        return name
    ref = git("rev-parse", "--abbrev-ref", "HEAD")
    if ref != "HEAD":
        return ref
    raise SystemExit("cannot resolve a branch to push to (detached HEAD, no GITHUB_REF_NAME)")


def commit_and_push(paths: list[str], summary: str) -> None:
    """Commit the bumped manifests and push them to the branch we started from.

    The runner's remote already carries the job's short-lived GITHUB_TOKEN, so no personal
    credential is involved and nothing secret is stored in this repository.
    """
    branch = current_branch()
    git("add", "--", *paths)
    if not git("diff", "--cached", "--name-only"):
        print("nothing staged; the bump matched what is already committed")
        return
    git("commit", "-q", "-m", f"checkver: bump {summary}")
    try:
        git("push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    except SystemExit as exc:
        print(f"push refused: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"pushed bump commit to {branch}: {summary}")


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
    if args.commit:
        commit_and_push([p for p, _, _ in stale], summary)
    else:
        print(f"updated {len(stale)} manifest(s) in place only: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
