#!/usr/bin/env python3
"""Bump scoop bucket manifests from upstream Gitee releases.

Portable (stdlib only) twin of scoop's checkver+autoupdate for the manifests in this
bucket, so it can run either in a Gitee Go runner or on the Windows box.

  checkver.py                     # report + rewrite manifests in place
  checkver.py --dry-run           # report only
  checkver.py --commit-api        # also commit the changed files back via the Gitee V5
                                  # contents API; needs GITEE_TOKEN and CHECKVER_REPO
Exit code: 0 = no change or change applied, 10 = changes pending with --commit-api but
no token (so a scheduled job surfaces it), 1 = failure.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
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


def commit_api(spec_files: dict[str, str]) -> None:
    """PUT each changed file through the Gitee contents API (no git in the runner)."""
    token = os.environ.get("GITEE_TOKEN")
    repo = os.environ.get("CHECKVER_REPO") or spec_files.get("_repo")
    if not token or not repo:
        print("GITEE_TOKEN / CHECKVER_REPO missing; leaving the working tree updated", file=sys.stderr)
        raise SystemExit(10)
    for rel in spec_files["paths"]:
        blob = json.loads(http_get(f"https://gitee.com/api/v5/repos/{repo}/contents/{rel}"))
        payload = json.dumps(
            {
                "access_token": token,
                "content": base64.b64encode((ROOT / rel).read_bytes()).decode(),
                "sha": blob["sha"],
                "message": f"checkver: bump {Path(rel).name}",
                "branch": os.environ.get("CHECKVER_BRANCH", "master"),
            }
        ).encode()
        req = urllib.request.Request(
            f"https://gitee.com/api/v5/repos/{repo}/contents/{rel}",
            data=payload,
            method="PUT",
            headers={"User-Agent": UA, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            json.loads(resp.read().decode())
        print(f"committed {rel} to {repo}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit-api", action="store_true", help="push changes with the Gitee contents API")
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
    if args.commit_api:
        commit_api({"paths": [p for p, _, _ in stale], "_repo": cfg["manifest_repo"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
