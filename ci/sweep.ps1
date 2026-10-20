#Requires -Version 7
<#
.SYNOPSIS
    Daily manifest sweep for the personal scoop bucket.
.DESCRIPTION
    This is the automation that actually runs. GitHub `schedule` never fired for this
    account (measured 2026-10-20: two workflows, off-peak minutes, disable/enable
    re-registration, public and private, ~15 expected windows, 0 runs; while `push` and
    `workflow_dispatch` on the same repo all completed). So the bump is done here and
    pushed to origin; the workflow stays as a manual/push-triggered fallback.

    Order matters: pull first (another machine or a CI run may have bumped already), then
    bump + commit + push. Nothing is force-pushed, and a conflict is surfaced in the log
    rather than resolved by guesswork.
.EXAMPLE
    pwsh -NoProfile -File ci/sweep.ps1
#>
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $env:LOCALAPPDATA 'scoop-bucket-checkver.log'
$env:PATH = (Join-Path $env:USERPROFILE 'scoop\shims') + ';' + $env:PATH

function Invoke-SweepPython {
    param([string[]] $Args)
    # uv first (global rule: Python goes through uv), then a system interpreter.
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & uv run --no-project --python 3.12 (Join-Path $root 'ci\checkver.py') @Args
        return
    }
    $py = Get-Command python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $py) { throw 'no python interpreter and no uv on PATH' }
    & $py.Source (Join-Path $root 'ci\checkver.py') @Args
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sweep start ($root)" | Tee-Object -FilePath $log -Append
Push-Location $root
try {
    git pull --rebase --quiet origin master
    if ($LASTEXITCODE -ne 0) { throw "git pull failed ($LASTEXITCODE); bucket left untouched" }
    Invoke-SweepPython --commit 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "checkver exited $LASTEXITCODE" }
} catch {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FAILED: $($_.Exception.Message)" | Tee-Object -FilePath $log -Append
    exit 1
} finally {
    Pop-Location
}
