<#
.SYNOPSIS
    Install the pb-ai-code skills + commands into the directory an AI coding
    assistant actually reads.

.DESCRIPTION
    The canonical copies live in this repository, in agent-neutral locations:

        skills/<name>/SKILL.md      Agent Skills (agentskills.io) format
        commands/<name>.md          slash-command wrappers
        harness/<harness>/          harness-specific config (permissions, ...)

    No assistant reads those paths directly. This script copies them into the
    layout a given harness expects, so one source of truth serves every tool.
    It is used two ways:

      * on this repository, to make the skills usable while developing them
        (the generated directory is gitignored - regenerate, never hand-edit);
      * on a consumer project (a PowerBuilder workspace), as a vendored
        snapshot, matching the drop-in convention PB projects already use.

    A marker file records the source commit so drift is auditable: fix things
    in pb-ai-code and re-run, do not patch the installed copy.

.PARAMETER Target
    Project that receives the install. Defaults to this repository, which is
    what you want while developing the skills themselves.

.PARAMETER Harness
    Which assistant's layout to write.

        claude-code   <target>/.claude/{skills,commands,settings.json}
        generic       paths you pass explicitly via -SkillsDir / -CommandsDir

    Only harnesses whose on-disk contract is known are named here. For anything
    else use -Harness generic and point it at the right directory; see
    docs/install.md.

.PARAMETER Bundle
    Which subset to install.

        full     every skill and command (default)
        review   the code-review bundle only: pb-review, pb-context-build,
                 pb-apply-plan, appeon-query, pb-src-format

.PARAMETER SkillsDir
    -Harness generic only: destination directory for skills, relative to
    Target or absolute. Required in generic mode.

.PARAMETER CommandsDir
    -Harness generic only: destination directory for command files. Omit to
    skip commands (every flow is also reachable as a skill).

.PARAMETER DryRun
    Print the planned operations and write nothing.

.EXAMPLE
    .\install-skills.ps1
    Install everything into this repository's own .claude/ directory.

.EXAMPLE
    .\install-skills.ps1 -Target ..\my-pb-app -Bundle review
    Vendor the review bundle into a PowerBuilder workspace.

.EXAMPLE
    .\install-skills.ps1 -Target ..\my-pb-app -Harness generic -SkillsDir .agent\skills
#>
param(
    [Parameter(Position = 0)]
    [string]$Target,

    [ValidateSet('claude-code', 'generic')]
    [string]$Harness = 'claude-code',

    [ValidateSet('full', 'review')]
    [string]$Bundle = 'full',

    [string]$SkillsDir,

    [string]$CommandsDir,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# --- Resolve source + target ---
$source = (Get-Item (Join-Path $PSScriptRoot '..')).FullName

if ([string]::IsNullOrWhiteSpace($Target)) {
    $target = $source
    $selfInstall = $true
}
else {
    if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
        throw "Target is not a directory: $Target"
    }
    $target = (Resolve-Path -LiteralPath $Target).Path
    $selfInstall = ($target -eq $source)
}

# --- Harness layout ---
$settingsSrc = $null
$settingsRel = $null
switch ($Harness) {
    'claude-code' {
        $skillsRel = '.claude\skills'
        $commandsRel = '.claude\commands'
        $settingsSrc = Join-Path $source 'harness\claude-code\settings.json'
        $settingsRel = '.claude\settings.json'
        $markerRel = '.claude\_installed-from-pb-ai-code.txt'
    }
    'generic' {
        if ([string]::IsNullOrWhiteSpace($SkillsDir)) {
            throw "-Harness generic requires -SkillsDir (e.g. -SkillsDir .agent\skills)"
        }
        $skillsRel = $SkillsDir
        $commandsRel = $CommandsDir
        $markerRel = Join-Path $SkillsDir '_installed-from-pb-ai-code.txt'
    }
}

# --- Bundle contents ---
# pb-scaffold and pb-format are deliberately absent from 'review': reviewing
# existing code rarely creates new top-level objects, and pb-format needs the
# separate, optional pb-format tool installed. Skills that cross-reference a
# skill that was not installed say so rather than failing.
if ($Bundle -eq 'review') {
    $skills = @('pb-review', 'pb-context-build', 'pb-apply-plan', 'appeon-query', 'pb-src-format')
    $commandFiles = @('pb-review.md')
}
else {
    $skills = @(Get-ChildItem -LiteralPath (Join-Path $source 'skills') -Directory |
        Select-Object -ExpandProperty Name)
    $commandFiles = @(Get-ChildItem -LiteralPath (Join-Path $source 'commands') -Filter '*.md' -File |
        Select-Object -ExpandProperty Name)
}

# --- Source repo metadata ---
$sha = (& git -C $source rev-parse --short HEAD).Trim()
$branch = (& git -C $source rev-parse --abbrev-ref HEAD).Trim()
$dirtyOutput = (& git -C $source status --porcelain)
$isDirty = -not ([string]::IsNullOrWhiteSpace($dirtyOutput))
$now = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'

Write-Host ""
Write-Host "Source:  $source @ $sha ($branch)" -ForegroundColor Cyan
if ($isDirty) {
    Write-Host "WARN: source repo has uncommitted changes; the install may include unversioned work." -ForegroundColor Yellow
}
if ($selfInstall) {
    Write-Host "Target:  $target  (self-install: generated copy, gitignored)"
}
else {
    Write-Host "Target:  $target"
}
Write-Host "Harness: $Harness      Bundle: $Bundle"
Write-Host ""

$skillsTarget = Join-Path $target $skillsRel
$commandsTarget = $null
if (-not [string]::IsNullOrWhiteSpace($commandsRel)) {
    $commandsTarget = Join-Path $target $commandsRel
}
$markerPath = Join-Path $target $markerRel

# --- Plan ---
$plan = @()
foreach ($s in $skills) {
    $src = Join-Path $source "skills\$s"
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Source skill missing: $src"
    }
    $plan += [pscustomobject]@{ Op = 'skill'; Src = $src; Dst = (Join-Path $skillsTarget $s) }
}
if ($commandsTarget) {
    foreach ($c in $commandFiles) {
        $src = Join-Path $source "commands\$c"
        if (-not (Test-Path -LiteralPath $src)) {
            throw "Source command missing: $src"
        }
        $plan += [pscustomobject]@{ Op = 'command'; Src = $src; Dst = (Join-Path $commandsTarget $c) }
    }
}
elseif ($commandFiles.Count -gt 0) {
    Write-Host "Note: no commands directory for this harness; skipping $($commandFiles.Count) command file(s)." -ForegroundColor Yellow
    Write-Host "      Every flow is also reachable as a skill of the same name." -ForegroundColor Yellow
    Write-Host ""
}
if ($settingsSrc) {
    if (-not (Test-Path -LiteralPath $settingsSrc)) {
        throw "Harness settings file missing: $settingsSrc"
    }
    $plan += [pscustomobject]@{ Op = 'settings'; Src = $settingsSrc; Dst = (Join-Path $target $settingsRel) }
}

foreach ($p in $plan) {
    $srcShort = $p.Src.Replace($source, '<src>')
    $dstShort = $p.Dst.Replace($target, '<dst>')
    Write-Host ("{0,-9} {1} -> {2}" -f $p.Op, $srcShort, $dstShort)
}
Write-Host ("{0,-9} {1}" -f 'marker', $markerPath.Replace($target, '<dst>'))
Write-Host ""

if ($DryRun) {
    Write-Host "DryRun mode. No changes written." -ForegroundColor Yellow
    return
}

# --- Apply ---
foreach ($p in $plan) {
    $parent = Split-Path -Parent $p.Dst
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if ($p.Op -eq 'skill') {
        if (Test-Path -LiteralPath $p.Dst) {
            Remove-Item -LiteralPath $p.Dst -Recurse -Force
        }
        Copy-Item -LiteralPath $p.Src -Destination $p.Dst -Recurse -Force
    }
    else {
        Copy-Item -LiteralPath $p.Src -Destination $p.Dst -Force
    }
    Write-Host ("Installed {0,-9} {1}" -f $p.Op, (Split-Path -Leaf $p.Dst)) -ForegroundColor Green
}

# --- Marker file (UTF-8, CRLF, so other tools and git diff it cleanly) ---
$markerLines = @(
    "# Skills and commands installed from pb-ai-code. Generated file - do not edit.",
    "#",
    "# Installed: $now",
    "# Source:    pb-ai-code @ $sha ($branch)",
    "# Harness:   $Harness",
    "# Bundle:    $Bundle"
)
if ($isDirty) {
    $markerLines += "# WARN: source repo had uncommitted changes at install time."
}
$markerLines += @("#", "# Contents:")
foreach ($p in $plan) {
    $markerLines += "#   " + $p.Dst.Replace($target, '').TrimStart('\')
}
$markerLines += @(
    "#",
    "# Source of truth: https://github.com/restoresrl/pb-ai-code",
    "# To update: from a pb-ai-code checkout, run",
    "#   scripts\install-skills.ps1 -Target <this-project> -Harness $Harness -Bundle $Bundle",
    "# Make changes in pb-ai-code, not here."
)
$markerParent = Split-Path -Parent $markerPath
if (-not (Test-Path -LiteralPath $markerParent)) {
    New-Item -ItemType Directory -Path $markerParent -Force | Out-Null
}
Set-Content -LiteralPath $markerPath -Value ($markerLines -join "`r`n") -Encoding utf8

Write-Host ""
Write-Host "Done." -ForegroundColor Green
if ($Harness -eq 'claude-code') {
    Write-Host "MCP servers are configured separately, in the project's .mcp.json - see docs/install.md."
}
