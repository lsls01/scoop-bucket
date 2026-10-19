# lishe — personal scoop bucket

Remote (source of truth): `https://github.com/lsls01/scoop-bucket.git` (private).
Add it on any Windows machine:

```powershell
scoop bucket add lishe https://github.com/lsls01/scoop-bucket.git
```

## gitee (Gitee CLI, official)

- Upstream: https://gitee.com/oschina/gitee-cli (Gitee org `oschina`, MIT, Go binary per release)
- Assets used: `gitee_<version>_windows_amd64.zip` + that release's `checksums.txt`
- Neither scoop's main/extras nor Gitee publishes a manifest for it, hence this bucket.
- Windows amd64 only. macOS/Linux: upstream install script or `npm i -g @gitee/gitee-cli`.
- Credentials live in `~/.config/gitee/` (written by the CLI), so they survive updates.

## Why the bucket needs CI

Scoop's update path reads **only** the `version` field of the manifest it finds in the bucket
(`lib/versions.ps1` → `Get-LatestVersion`). `checkver`/`autoupdate` in the manifest are
maintainer-side metadata that scoop never executes. So a manifest nobody rewrites stays pinned
forever and `scoop update *` reports it up to date even after upstream ships a release.

`ci/checkver.py` is the rewriter: newest tag from the Gitee releases API, real sha256 from that
release's own `checksums.txt` (never `hash: skip`), then `version`/`url`/`hash` rewritten and
pushed back here.

```bash
python3 ci/checkver.py --dry-run   # what would change
python3 ci/checkver.py --commit    # change it and push
```

`.github/workflows/checkver.yml` runs `--commit` every day at 01:03 UTC (09:03 北京时间) and on
`workflow_dispatch`. Write access uses the job's short-lived `GITHUB_TOKEN` only; no personal
credential, PAT or secret lives in this repository. GitHub Free gives 2000 private-repo minutes
per month and a sweep takes under a minute.

## Updating gitee on a machine

```powershell
scoop update      # git pull of this bucket -> picks up the CI bump
scoop update *    # installs the new version
```

Never use `gitee update` (the CLI's own self-update): it replaces the exe in place and leaves
scoop's recorded version stale. `gitee config set update_check false` is set on this machine so
it does not even nag.
