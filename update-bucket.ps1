#Requires -Version 5
<#
.SYNOPSIS
    Refresh every manifest in this bucket from its own checkver source, then commit.
.DESCRIPTION
    Scoop's update path only ever reads the "version" field of a bucket manifest
    (lib/versions.ps1 -> Get-LatestVersion), so checkver/autoupdate never run by
    themselves. For apps with no upstream bucket, that means the manifest goes stale
    until this script runs. Do it before `scoop update *` and the new version lands.
.EXAMPLE
    pwsh -NoProfile -File update-bucket.ps1            # all manifests
    pwsh -NoProfile -File update-bucket.ps1 -App gitee # one app
    pwsh -NoProfile -File update-bucket.ps1 -NoCommit  # dry look, no git write
#>
[CmdletBinding()]
param (
    [string[]] $App = @(),
    [switch] $NoCommit
)

$ErrorActionPreference = 'Stop'

$bucketRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bucketDir = Join-Path $bucketRoot 'bucket'
$scoopCurrent = Join-Path $env:USERPROFILE 'scoop/apps/scoop/current'
$checkver = Join-Path $scoopCurrent 'bin/checkver.ps1'
if (-not (Test-Path $checkver)) { throw "checkver.ps1 not found at $checkver" }

$apps = if ($App.Count -gt 0) { $App } else {
    Get-ChildItem $bucketDir -Filter '*.json' | ForEach-Object { $_.BaseName }
}

foreach ($a in $apps) {
    Write-Host "== $a ==" -ForegroundColor Cyan
    & $checkver -App $a -Dir $bucketDir -Update
}

if ($NoCommit) { return }

Push-Location $bucketRoot
try {
    git add -- bucket | Out-Null
    $dirty = @(git diff --cached --name-only -- bucket)
    if ($dirty.Count -gt 0) {
        $msg = ($dirty | ForEach-Object { (Split-Path $_ -Leaf) -replace '\.json$', '' }) -join ', '
        git commit -q -m "bump manifests via checkver: $msg"
        Write-Host "committed: $msg" -ForegroundColor Green
    } else {
        Write-Host 'no manifest changes'
    }
} finally {
    Pop-Location
}
