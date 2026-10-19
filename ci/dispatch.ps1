#!/usr/bin/env pwsh
# Trigger the scoop-bucket checkver sweep in GitHub Actions (private repos on GitHub Free
# never fire the `schedule` trigger -- measured 2026-10-19, see README).
# GitHub's own token is enough; nothing is stored in this repo.
$ErrorActionPreference = 'Stop'
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Error 'gh not on PATH' }
& gh workflow run checkver.yml -R lsls01/scoop-bucket
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'dispatched; watching the run...'
$deadline = (Get-Date).AddMinutes(15)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 20
    $run = & gh run list -R lsls01/scoop-bucket -L 1 --json databaseId,status,conclusion --output json | ConvertFrom-Json
    if ($run.status -eq 'completed') {
        Write-Host "run $($run.databaseId) $($run.conclusion)"
        & gh run view $run.databaseId -R lsls01/scoop-bucket --log | Select-String 'manifests already|bump|pushed|nothing'
        exit $(if ($run.conclusion -eq 'success') { 0 } else { 1 })
    }
}
Write-Error 'run still queued after 15 minutes (free-tier queue); it will finish on its own'
exit 1
