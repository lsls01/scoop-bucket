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
python3 ci/checkver.py --commit    # change it, push from here
pwsh -File ci/dispatch.ps1         # change it in GitHub Actions instead of locally
```

`.github/workflows/checkver.yml` runs `--commit` on `push` and `workflow_dispatch`. Write access uses
the job's short-lived `GITHUB_TOKEN` only: no personal credential, PAT or secret lives in this
repository (`gh api repos/lsls01/scoop-bucket/actions/secrets` → `total_count: 0`). GitHub Free includes
2000 private-repo minutes per month and standard runners are free on public repos; one sweep costs seconds.

**The daily `schedule` trigger does not fire while this repo is private.** Measured 2026-10-19 with two
probe crons -- `*/10 * * * *` (lands on the busy top of the hour) and `7,17,27,37,47,57 * * * *` (the
documented off-peak minutes), plus a disable/enable re-registration: across 5 expected windows the count
of `event == schedule` runs stayed 0, while `push` and `workflow_dispatch` runs in the same repo and file
all completed successfully. Official docs only document the 60-day schedule auto-disable *for public
repos*, so this is undocumented behaviour of private + Free. Two ways forward:

```powershell
python3 ci/checkver.py --commit                                   # manual, identical to the workflow
gh workflow run checkver.yml -R lsls01/scoop-bucket               # manual, in the runner
gh repo edit lsls01/scoop-bucket --visibility public                # makes cron actually fire
```

## Visibility: private, and what that costs

The repo is private, which has two consequences worth knowing:

1. **Another machine needs GitHub credentials** for `scoop bucket add` (GCM/gh handles it here;
   the pull happens non-interactively once the credential exists).
2. **`schedule` on GitHub Free private repos is unreliable** -- community reports (github.community
   discussion 201354) describe cron events not firing on free personal accounts' private repos, while
   `workflow_dispatch` works. That is not officially documented, so it is unverified here.

If the daily bump stops appearing, flip it public -- the payload is public information anyway
(upstream release URLs and hashes) and public repos get unlimited standard GitHub-hosted minutes:

```powershell
gh repo edit lsls01/scoop-bucket --visibility public
```

Manual backfill that always works regardless: `gh workflow run checkver.yml -R lsls01/scoop-bucket`.

## Updating gitee on a machine

```powershell
scoop update      # git pull of this bucket -> picks up the CI bump
scoop update *    # installs the new version
```

Never use `gitee update` (the CLI's own self-update): it replaces the exe in place and leaves
scoop's recorded version stale. `gitee config set update_check false` is set on this machine so
it does not even nag.
