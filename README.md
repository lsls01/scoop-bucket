# lishe — personal scoop bucket

Remote (source of truth): `https://gitee.com/xuemi01/scoop-bucket.git` (private).
Clone it on another machine with:

```powershell
scoop bucket add lishe https://gitee.com/xuemi01/scoop-bucket.git
```

Locally maintained manifests for tools that upstream scoop buckets (main/extras) do not carry.

## gitee (Gitee CLI, official)

- Upstream: https://gitee.com/oschina/gitee-cli (Gitee org `oschina`, MIT, Go binary per release)
- Source of truth: Gitee release assets `gitee_<version>_windows_amd64.zip` + `checksums.txt`
- No scoop manifest exists in main/extras and Gitee publishes no official bucket, hence this file.
- Windows amd64 only. macOS/Linux: upstream install script or `npm i -g @gitee/gitee-cli`.
- Credentials live in `~/.config/gitee/` (written by the CLI itself), so they survive updates.

## How a new upstream release reaches scoop

Scoop's update path reads **only** the `version` field of the bucket manifest
(`lib/versions.ps1` → `Get-LatestVersion`); `checkver`/`autoupdate` are maintainer-side
metadata that scoop never executes. So something has to rewrite `bucket/gitee.json` first.
That is `ci/checkver.py`, and it is meant to run in CI so every machine just pulls:

```
upstream release → ci/checkver.py --commit (bump + commit + push here)
                 → scoop update          (git pull of this bucket)
                 → scoop update *        (installs the new gitee)
```

`ci/checkver.py` is stdlib-only Python: it resolves the newest tag from
`https://gitee.com/api/v5/repos/<upstream>/releases/latest`, takes the real sha256 from that
release's `checksums.txt` (never `hash: skip`), rewrites `version`/`url`/`hash`, and commits.
It mirrors the manifest's own `checkver`/`autoupdate` fields — verified to produce byte-identical
output on the 0.3.1 → 0.3.2 bump.

```bash
python3 ci/checkver.py --dry-run   # what would change
python3 ci/checkver.py --commit    # change it and push
```

### Gitee Go schedule

`checkver-sweep.yml` (repo root, kept in sync with `ci/checkver-sweep.yml`) is the pipeline:
a `custom-build@custom` step running `python3 ci/checkver.py --commit`, cron `0 3 9 * * ?`
(09:03 北京时间 daily). It is inert until **Gitee Go is opened for this account/repo** — the API
refuses pipeline commits with `Gitee Go service is already closed!`, which is a web-side switch
(仓库 → 服务 → Gitee Go 开通，个人账号需绑定手机号；开通后单仓库送 200 分钟构建时长，个人每月另有 1000 分钟).
After that, `gitee pipeline list -R xuemi01/scoop-bucket --ref master` picks the file up and the
cron starts firing.

Until then, run `python3 ci/checkver.py --commit` by hand (or from a scheduled task) — it needs
no scoop internals and takes one second.

### Do not self-update the binary

`gitee update` (the CLI's own self-update) overwrites the exe in place and leaves scoop's
recorded version stale. `gitee config set update_check false` is applied on this machine for
that reason.
