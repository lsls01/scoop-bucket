#Requires -Version 7
<#
.SYNOPSIS
    Daily manifest sweep for the personal scoop bucket.
.DESCRIPTION
    This is the automation that actually runs. GitHub `schedule` never fired for this
    account (measured 2026-10-19/20: two workflows, both visibilities, off-peak and
    top-of-hour crons, disable/enable re-registration, ~15 expected windows, 0 runs -- while
    `push` and `workflow_dispatch` runs on the same repo all completed). The workflow stays
    as a manual/push-triggered fallback, not as the timer.

    Order matters: pull first (a CI run or another machine may have bumped already), then
    bump + commit + push. Nothing is ever force-pushed; checkver.py rebases onto the branch
    tip and refuses loudly if the tip moved somewhere unexpected.
.OUTPUTS
    Append-only log at %LOCALAPPDATA%\scoop-bucket-checkver.log, exit 0 on success.
#>
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$pythonScript = Join-Path $PSScriptRoot 'checkver.py'
$interpreter = ''

function Write-Log {
    param([string] $Message)
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $log -Value $line
    Write-Host $line
}

function Invoke-SweepPython {
    param([string[]] $ScriptArgs)
    # uv first (global rule: Python goes through uv). If uv cannot resolve an interpreter --
    # offline, cold cache -- fall back to a system python. checkver.py is idempotent, so a
    # retry after a failed attempt cannot double-bump.
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & uv run --no-project --python 3.12 $pythonScript @ScriptArgs 2>&1 |
            ForEach-Object { Add-Content -Path $log -Value "    $_"; Write-Host "    $_" }
        if ($LASTEXITCODE -eq 0) { $script:interpreter = 'uv'; return }
        Write-Log "uv run failed (exit $LASTEXITCODE); retrying with system python"
    }
    $py = Get-Command python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $py) { throw 'neither uv nor a python interpreter is on PATH' }
    & $py.Source $pythonScript @ScriptArgs 2>&1 |
        ForEach-Object { Add-Content -Path $log -Value "    $_"; Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { throw "checkver exited $LASTEXITCODE" }
    $script:interpreter = $py.Source
}

$log = Join-Path $env:LOCALAPPDATA 'scoop-bucket-checkver.log'
# Scheduled tasks get a bare PATH (no scoop shims); uv/git live there.
$env:PATH = (Join-Path $env:USERPROFILE 'scoop\shims') + ';' + $env:PATH

Write-Log "sweep start ($root)"
Push-Location $root
try {
    # --autostash: editing a manifest or this script locally must not break the daily task.
    git pull --rebase --autostash --quiet origin master
    if ($LASTEXITCODE -ne 0) { throw "git pull failed ($LASTEXITCODE); bucket left untouched" }
    Invoke-SweepPython -ScriptArgs @('--commit')
    Write-Log "done (interpreter: $interpreter)"
} catch {
    Write-Log "FAILED: $($_.Exception.Message)"
    exit 1
} finally {
    Pop-Location
}
