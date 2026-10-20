# lishe — personal scoop bucket

Remote (source of truth): `https://github.com/lsls01/scoop-bucket.git` — public, so another machine
can add the bucket with no GitHub credential.
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
pwsh -File ci/dispatch.ps1         # do the same thing inside a GitHub runner
```

`.github/workflows/checkver.yml` runs `--commit` on `push` and `workflow_dispatch`. Write access uses
the job's short-lived `GITHUB_TOKEN` only: no personal credential, PAT or secret lives in this
repository (`gh api repos/lsls01/scoop-bucket/actions/secrets` → `total_count: 0`). Standard
GitHub-hosted runners are free on public repos; one sweep takes seconds.

## How the bump actually happens (measured)

`schedule` does **not** fire for this account. Verified 2026-10-19/20 with two workflows on this
repo, both visibilities, off-peak and top-of-hour crons, plus a disable/enable re-registration:
about 15 expected windows produced `event == schedule` runs = 0, while `push` and
`workflow_dispatch` runs on the same repo completed every time (11 + 6 of them). Making the repo
public did not change it. So the workflow is a manual/push fallback only, and the automation lives
on this machine:

```powershell
# scheduled task scoop-bucket-checkver runs ci/sweep.ps1 daily at 09:03  (see pi-setup MANIFEST §6)
pwsh -NoProfile -File ~\scoop\buckets\lishe\ci\sweep.ps1     # pull → bump → commit → push
# log: $env:LOCALAPPDATA\scoop-bucket-checkver.log
gh workflow run checkver.yml -R lsls01/scoop-bucket            # or: pwsh -File ci/dispatch.ps1
```

## Updating gitee on a machine

```powershell
scoop update      # git pull of this bucket -> picks up the bump (from the task or from CI)
scoop update *    # installs the new version
```

Never use `gitee update` (the CLI's own self-update): it replaces the exe in place and leaves
scoop's recorded version stale. `gitee config set update_check false` is set on this machine so
it does not even nag.
