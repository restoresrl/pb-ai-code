<#
.SYNOPSIS
    Install the pb-ai-code skills, commands and knowledge base into the
    directory an AI coding assistant actually reads.

.DESCRIPTION
    The canonical copies live in this repository, in agent-neutral locations:

        skills/<name>/SKILL.md      Agent Skills (agentskills.io) format
        commands/<name>.md          slash-command wrappers
        docs/pb-antipatterns/       the knowledge the skills consult
        docs/pb-source-format/
        harness/<harness>/          harness-specific config (permissions, ...)

    No assistant reads those paths. This script copies them into the layout a
    given harness expects, so one source of truth serves every tool. It is
    used two ways:

      * on this repository, to make the skills usable while developing them
        (the generated directory is gitignored - regenerate, never hand-edit);
      * on a consumer project - a PowerBuilder workspace - as a vendored
        snapshot, matching the drop-in convention PB projects already use.

    Installing into a consumer also copies the two documentation trees the
    skills link to, because a review skill whose antipattern catalog is
    missing cannot do its job. They land beside the skills, as
    `pb-ai-code-docs/`, and the links inside the installed skills are
    rewritten to point at them. They deliberately do NOT land in the
    consumer's own `docs/`, which belongs to the host project.

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

.PARAMETER SkillsDir
    -Harness generic only: destination directory for skills, relative to
    Target or absolute. Required in generic mode. The knowledge base lands in
    its parent directory, which is what the rewritten links expect.

.PARAMETER CommandsDir
    -Harness generic only: destination directory for command files. Omit to
    skip commands (every flow is also reachable as a skill).

.PARAMETER DryRun
    Print the planned operations and write nothing.

.EXAMPLE
    .\install-skills.ps1
    Install into this repository's own .claude/ directory.

.EXAMPLE
    .\install-skills.ps1 -Target ..\my-pb-app
    Vendor the whole bundle into a PowerBuilder workspace.

.EXAMPLE
    .\install-skills.ps1 -Target ..\my-pb-app -Harness generic -SkillsDir .agent\skills
#>
param(
    [Parameter(Position = 0)]
    [string]$Target,

    [ValidateSet('claude-code', 'generic')]
    [string]$Harness = 'claude-code',

    [string]$SkillsDir,

    [string]$CommandsDir,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# Documentation trees the skills link to. Vendored into a consumer so the
# bundle is self-contained; not copied on a self-install, where the repository's
# own docs/ already sits where the links point.
$docTrees = @('pb-antipatterns', 'pb-source-format')
$docsFolderName = 'pb-ai-code-docs'

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

# The knowledge base goes in the skills directory's parent, because a skill at
# <skills>/<name>/SKILL.md reaches it as ../../<docsFolderName>/.
$docsParentRel = Split-Path -Parent $skillsRel
$docsRel = if ([string]::IsNullOrWhiteSpace($docsParentRel)) {
    $docsFolderName
}
else {
    Join-Path $docsParentRel $docsFolderName
}

# --- Contents: everything. A skill left out is a dangling cross-reference in
# the ones that ship, and the saving is a handful of Markdown files. ---
$skills = @(Get-ChildItem -LiteralPath (Join-Path $source 'skills') -Directory |
    Select-Object -ExpandProperty Name)
$commandFiles = @(Get-ChildItem -LiteralPath (Join-Path $source 'commands') -Filter '*.md' -File |
    Select-Object -ExpandProperty Name)

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
Write-Host "Harness: $Harness"
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
foreach ($d in $docTrees) {
    $src = Join-Path $source "docs\$d"
    if (-not (Test-Path -LiteralPath $src)) {
        throw "Source docs tree missing: $src"
    }
    $plan += [pscustomobject]@{ Op = 'docs'; Src = $src; Dst = (Join-Path (Join-Path $target $docsRel) $d) }
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
Write-Host ("{0,-9} ../../docs/ -> ../../{1}/  in the installed skills" -f 'rewrite', $docsFolderName)
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
    if ($p.Op -eq 'skill' -or $p.Op -eq 'docs') {
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

# --- Rewrite the knowledge-base links in the installed skills ---
# In the repository, skills/<name>/SKILL.md reaches the docs as ../../docs/,
# because two levels up from skills/<name>/ is the repository root. Installed,
# two levels up from <harness>/skills/<name>/ is the harness directory instead —
# so the same link would point at a docs/ that is not there. This applies to a
# self-install exactly as much as to a consumer: the installed tree is one level
# deeper than the canonical one either way.
$rewritten = 0
foreach ($s in $skills) {
    $file = Join-Path (Join-Path $skillsTarget $s) 'SKILL.md'
    if (-not (Test-Path -LiteralPath $file)) { continue }
    $text = [System.IO.File]::ReadAllText($file)
    $new = $text.Replace('../../docs/', "../../$docsFolderName/")
    if ($new -ne $text) {
        [System.IO.File]::WriteAllText($file, $new)
        $rewritten++
    }
}
Write-Host ("Rewrote knowledge-base links in {0} skill file(s)." -f $rewritten) -ForegroundColor Green

# --- Marker file (UTF-8, CRLF, so other tools and git diff it cleanly) ---
$markerLines = @(
    "# Skills, commands and knowledge base installed from pb-ai-code.",
    "# Generated - do not edit. Change things in pb-ai-code and re-run.",
    "#",
    "# Installed: $now",
    "# Source:    pb-ai-code @ $sha ($branch)",
    "# Harness:   $Harness"
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
    "# The knowledge base above is a SNAPSHOT. The skills grow it as they meet",
    "# undocumented cases - do that in pb-ai-code, not here, or the next",
    "# install discards it."
)
$markerLines += @(
    "#",
    "# Source of truth: https://github.com/restoresrl/pb-ai-code",
    "# To update: from a pb-ai-code checkout, run",
    "#   scripts\install-skills.ps1 -Target <this-project> -Harness $Harness",
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
