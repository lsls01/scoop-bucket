# lishe — personal scoop bucket

Locally maintained manifests for tools that upstream scoop buckets (main/extras) do not carry.
Keep this repo in git so `scoop update` / reinstalls can reproduce it.

## gitee (Gitee CLI, official)

- Upstream: https://gitee.com/oschina/gitee-cli (Gitee org `oschina`, MIT, Go binary published per release)
- Source of truth: Gitee release assets `gitee_<version>_windows_amd64.zip` + `checksums.txt`
- No scoop manifest exists in main/extras and Gitee publishes no official bucket, hence this file.
- Windows-only manifest (amd64). macOS/Linux: use the upstream install script or `npm i -g @gitee/gitee-cli`.
- Credentials live in `~/.config/gitee/` (written by the CLI itself), so they survive updates.

### Update

Scoop's `scoop update <app>` only reads the bucket manifest version, so bump the manifest first:

```powershell
pwsh -NoProfile -File "$HOME/scoop/apps/scoop/current/bin/checkver.ps1" `
  -App gitee -Dir "$HOME/scoop/buckets/lishe/bucket" -Update
scoop update gitee
```

`checkver` queries `https://gitee.com/api/v5/repos/oschina/gitee-cli/releases/latest` and the
`autoupdate` block re-reads the real sha256 from the release's `checksums.txt`.
Do not use `gitee update` (the CLI's own self-update): it overwrites the binary in place and leaves
scoop's recorded version stale. `gitee config set update_check false` is applied for that reason.
