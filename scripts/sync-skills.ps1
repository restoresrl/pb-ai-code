<#
.SYNOPSIS
    Sync pb-ai-code review skills + slash command to a consumer project
    (snapshot vendoring).

.DESCRIPTION
    Copies a whitelisted subset of pb-ai-code/.claude into <consumer>/.claude.
    Coherent with the "drop-in / snapshot" convention used elsewhere in the
    Restore PB stack (pbunit.pbd, pbgettext.pbd, etc.).

    Drift between this snapshot and the pb-ai-code source-of-truth is
    explicit: modifications to skills/commands happen in pb-ai-code, then
    re-sync via this script. A marker file `.claude/_vendored-from-pb-ai-code.txt`
    in the consumer records the source commit SHA at sync time so drift is
    auditable.

.PARAMETER ConsumerPath
    Path (relative or absolute) to the consumer project that should receive
    the snapshot. The script writes into <ConsumerPath>/.claude/.

.PARAMETER DryRun
    Print the planned operations without copying anything.

.EXAMPLE
    .\sync-skills.ps1 ..\rstpb22

.EXAMPLE
    .\sync-skills.ps1 ..\rstpb22 -DryRun
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ConsumerPath,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# --- Resolve source + target ---
$source = (Get-Item (Join-Path $PSScriptRoot '..')).FullName
$target = (Resolve-Path -LiteralPath $ConsumerPath).Path

if (-not (Test-Path -LiteralPath $target -PathType Container)) {
    throw "Consumer path is not a directory: $target"
}

# --- Whitelist of what gets vendored ---
# Keep deliberately small. /pb-review needs:
# - pb-context-build (its primitive for scoped context pack)
# - pb-apply-plan (Phase B: orchestrates per-fix apply loop, invoked from
#   /pb-review Step 4 handoff)
# - appeon-query (language lookup during review)
# - pb-src-format (on-disk format reference, consulted by pb-apply-plan
#   when patches touch a variant entry type)
# pb-scaffold is intentionally NOT vendored: a consumer of code review rarely
# needs to scaffold new top-level objects.
$skills = @('pb-context-build', 'pb-apply-plan', 'appeon-query', 'pb-src-format')
$commandFiles = @('pb-review.md')

# Settings file with the pre-approved MCP permissions policy. Snapshotted as
# the consumer's project-level .claude/settings.json. The consumer's own
# settings.local.json (gitignored, user-specific) is never touched.
$settingsFile = 'settings.json'

# --- Source repo metadata ---
$sha = (& git -C $source rev-parse --short HEAD).Trim()
$branch = (& git -C $source rev-parse --abbrev-ref HEAD).Trim()
$dirtyOutput = (& git -C $source status --porcelain)
$isDirty = -not ([string]::IsNullOrWhiteSpace($dirtyOutput))
$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'

Write-Host ""
Write-Host "Source: $source @ $sha ($branch)" -ForegroundColor Cyan
if ($isDirty) {
    Write-Host "WARN: source repo has uncommitted changes; snapshot may include unversioned work." -ForegroundColor Yellow
}
Write-Host "Target: $target"
Write-Host ""

$skillsTarget = Join-Path $target '.claude\skills'
$commandsTarget = Join-Path $target '.claude\commands'
$settingsSrc = Join-Path $source ".claude\$settingsFile"
$settingsDst = Join-Path $target ".claude\$settingsFile"
$markerPath = Join-Path $target '.claude\_vendored-from-pb-ai-code.txt'

# --- Plan ---
$plan = @()
foreach ($s in $skills) {
    $src = Join-Path $source ".claude\skills\$s"
    $dst = Join-Path $skillsTarget $s
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Source skill missing: $src"
    }
    $plan += [pscustomobject]@{ Op = 'sync skill'; Src = $src; Dst = $dst }
}
foreach ($c in $commandFiles) {
    $src = Join-Path $source ".claude\commands\$c"
    $dst = Join-Path $commandsTarget $c
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Source command missing: $src"
    }
    $plan += [pscustomobject]@{ Op = 'sync command'; Src = $src; Dst = $dst }
}
if (-not (Test-Path -LiteralPath $settingsSrc)) {
    throw "Source settings file missing: $settingsSrc"
}
$plan += [pscustomobject]@{ Op = 'sync settings'; Src = $settingsSrc; Dst = $settingsDst }

foreach ($p in $plan) {
    $srcShort = $p.Src.Replace($source, '<src>')
    $dstShort = $p.Dst.Replace($target, '<dst>')
    Write-Host ("{0,-14} {1} -> {2}" -f $p.Op, $srcShort, $dstShort)
}
Write-Host ("{0,-14} <dst>\.claude\_vendored-from-pb-ai-code.txt" -f 'marker')
Write-Host ""

if ($DryRun) {
    Write-Host "DryRun mode. No changes written." -ForegroundColor Yellow
    return
}

# --- Apply ---
if (-not (Test-Path -LiteralPath $skillsTarget)) {
    New-Item -ItemType Directory -Path $skillsTarget -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $commandsTarget)) {
    New-Item -ItemType Directory -Path $commandsTarget -Force | Out-Null
}

foreach ($s in $skills) {
    $src = Join-Path $source ".claude\skills\$s"
    $dst = Join-Path $skillsTarget $s
    if (Test-Path -LiteralPath $dst) {
        Remove-Item -LiteralPath $dst -Recurse -Force
    }
    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    Write-Host "Synced skill:   $s" -ForegroundColor Green
}

foreach ($c in $commandFiles) {
    $src = Join-Path $source ".claude\commands\$c"
    $dst = Join-Path $commandsTarget $c
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "Synced command: $c" -ForegroundColor Green
}

# Project-level settings.json. Overwrites the consumer's settings.json if
# present (the snapshot pattern: the consumer's policy is what pb-ai-code
# declares). The consumer's settings.local.json is never touched — that file
# is gitignored and user-specific.
Copy-Item -LiteralPath $settingsSrc -Destination $settingsDst -Force
Write-Host "Synced settings: $settingsFile" -ForegroundColor Green

# --- Marker file (UTF-8 so other tools / git diff it cleanly) ---
$markerLines = @(
    "# Skills + slash commands vendored from pb-ai-code (snapshot)",
    "#",
    "# Last sync:  $now",
    "# Source:     pb-ai-code @ $sha ($branch)"
)
if ($isDirty) {
    $markerLines += "# WARN: source repo had uncommitted changes at sync time."
}
$markerLines += @(
    "#",
    "# Synced contents:"
)
foreach ($s in $skills) {
    $markerLines += "#   .claude/skills/$s/"
}
foreach ($c in $commandFiles) {
    $markerLines += "#   .claude/commands/$c"
}
$markerLines += "#   .claude/$settingsFile"
$markerLines += @(
    "#",
    "# Source of truth: https://github.com/restoresrl/pb-ai-code",
    "# To re-sync: from pb-ai-code, run scripts/sync-skills.ps1 <this-consumer-path>",
    "# Modifications should be made in pb-ai-code, not here.",
    "# .claude/settings.local.json (gitignored) is for user-specific overrides",
    "# and is never touched by the sync script."
)
Set-Content -LiteralPath $markerPath -Value ($markerLines -join "`r`n") -Encoding utf8
Write-Host "Wrote marker:   $markerPath" -ForegroundColor Green

Write-Host ""
Write-Host "Done." -ForegroundColor Green
