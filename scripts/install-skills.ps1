<#
.SYNOPSIS
    Install the pb-ai-code skills, commands, knowledge base and MCP server
    configuration into the places an AI coding assistant actually reads.

.DESCRIPTION
    The canonical copies live in this repository, in agent-neutral locations:

        skills/<name>/SKILL.md      Agent Skills (agentskills.io) format
        commands/<name>.md          slash-command wrappers
        docs/pb-antipatterns/       the knowledge the skills consult
        docs/pb-source-format/
        harness/mcp-servers.json    the pb-orca MCP server, pinned
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

    The MCP server configuration travels with them. It carries the version pin
    that decides which pb-orca-mcp the project talks to, so leaving it for each
    developer to copy by hand is how a team stops being on the same toolchain:
    the canonical file moves to a new tag and every hand-made copy stays behind.
    Installed together with the skills, the two cannot drift. A project using
    this kit therefore commits nothing agentic at all, and re-running this
    script is the whole synchronization story.

    Existing MCP servers in the target are preserved - only the keys this kit
    owns are written. A target config that cannot be parsed is never touched;
    the block is printed for you to merge by hand instead. A preserved server
    that turns out to be a second copy of one of ours under a different key
    earns a warning and stays put: two processes driving a single-session ORCA
    library is a problem, but so is deleting a server somebody meant to keep.

    A marker file records the source commit so drift is auditable: fix things
    in pb-ai-code and re-run, do not patch the installed copy.

.PARAMETER Target
    Project that receives the install. Defaults to this repository, which is
    what you want while developing the skills themselves.

.PARAMETER Harness
    Which assistant's layout to write.

        claude-code   <target>/.claude/{skills,commands,settings.json}
                      <target>/.mcp.json
        generic       paths you pass explicitly via -SkillsDir / -CommandsDir;
                      the MCP block is printed rather than written, because
                      where it goes depends on the client

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

.PARAMETER SkipMcpConfig
    Leave the target's MCP configuration alone. For a project whose servers are
    managed elsewhere - a user-wide entry added with `claude mcp add`, or a
    config the team maintains by another route. The skills still install; they
    just assume the `pb_*` tools are reachable some other way.

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

    [switch]$SkipMcpConfig,

    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# Documentation trees the skills link to. Vendored into a consumer so the
# bundle is self-contained; not copied on a self-install, where the repository's
# own docs/ already sits where the links point.
$docTrees = @('pb-antipatterns', 'pb-source-format')
$docsFolderName = 'pb-ai-code-docs'

# The MCP servers this kit owns live in one harness-neutral file: the JSON block
# is identical for every MCP client, only its destination differs. Set below,
# once $source is resolved.
$mcpSourceFile = $null

function Get-McpServerBlock {
    <#
        The canonical mcpServers object, as an ordered hashtable so the key
        order survives a round trip through ConvertTo-Json.
    #>
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "MCP server config missing: $Path"
    }
    $parsed = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
    # .Contains(), not .ContainsKey(): -AsHashtable returns an OrderedHashtable
    # on pwsh 7.3+ and a plain Hashtable before that, and Contains is the member
    # both of them - and [ordered]@{} - actually have.
    if (-not $parsed.Contains('mcpServers')) {
        throw "$Path has no 'mcpServers' key."
    }
    return $parsed['mcpServers']
}

function Write-McpConfig {
    <#
        Merge the kit's servers into the target's MCP config, preserving every
        server the project already had. Returns a list of human-readable
        outcomes, one per server key, or $null when nothing was written.

        Never clobbers a file it could not parse: a project's MCP config may
        hold servers unrelated to PowerBuilder, and overwriting them because
        the file has a stray comma would be a poor trade for saving the user
        one merge.
    #>
    param(
        [hashtable]$Servers,
        [string]$DestPath,
        [switch]$WhatIfOnly
    )

    $existing = [ordered]@{}
    if (Test-Path -LiteralPath $DestPath) {
        $raw = Get-Content -LiteralPath $DestPath -Raw
        try {
            $parsed = if ([string]::IsNullOrWhiteSpace($raw)) {
                @{}
            }
            else {
                $raw | ConvertFrom-Json -AsHashtable
            }
        }
        catch {
            Write-Host ""
            Write-Host "WARN: $DestPath is not valid JSON - leaving it untouched." -ForegroundColor Yellow
            Write-Host "      Merge this into its 'mcpServers' object by hand:" -ForegroundColor Yellow
            Write-Host (@{ mcpServers = $Servers } | ConvertTo-Json -Depth 10)
            Write-Host ""
            return $null
        }
        foreach ($k in $parsed.Keys) { $existing[$k] = $parsed[$k] }
    }

    if (-not $existing.Contains('mcpServers') -or $null -eq $existing['mcpServers']) {
        $existing['mcpServers'] = [ordered]@{}
    }
    $merged = [ordered]@{}
    foreach ($k in $existing['mcpServers'].Keys) { $merged[$k] = $existing['mcpServers'][$k] }

    $outcomes = @()
    foreach ($name in $Servers.Keys) {
        $incoming = $Servers[$name]
        if ($merged.Contains($name)) {
            $before = $merged[$name] | ConvertTo-Json -Depth 10 -Compress
            $after = $incoming | ConvertTo-Json -Depth 10 -Compress
            $outcomes += if ($before -eq $after) { "$name (already current)" } else { "$name (updated)" }
        }
        else {
            $outcomes += "$name (added)"
        }
        $merged[$name] = $incoming
    }
    $kept = @($merged.Keys | Where-Object { $Servers.Keys -notcontains $_ })
    if ($kept.Count -gt 0) {
        $outcomes += "kept: " + ($kept -join ', ')
    }

    # Preserving a project's own servers is right; preserving a second copy of
    # one of ours under a different key is not. It happens on any project that
    # was configured before the key settled, and the result is two servers
    # driving the same single-session ORCA library and two sets of identical
    # tools under different prefixes - of which only one matches the permission
    # allowlist. Warn rather than remove: it is the user's file, and a wrong
    # guess here silently deletes a server somebody meant to keep.
    $ourPackages = @($Servers.Keys | ForEach-Object {
            ($Servers[$_] | ConvertTo-Json -Depth 10 -Compress)
        }) -join ' '
    foreach ($name in $kept) {
        $blob = $merged[$name] | ConvertTo-Json -Depth 10 -Compress
        foreach ($pkg in @('pb-orca-mcp')) {
            if ($blob -match [regex]::Escape($pkg) -and $ourPackages -match [regex]::Escape($pkg)) {
                Write-Host ""
                Write-Host "WARN: the target already has a server '$name' that runs $pkg, which is what" -ForegroundColor Yellow
                Write-Host "      this kit installs as '$($Servers.Keys -join "', '")'. Two of them means two processes" -ForegroundColor Yellow
                Write-Host "      competing for a single-session ORCA library, duplicate tools under different" -ForegroundColor Yellow
                Write-Host "      prefixes, and only one of them matching the permission allowlist." -ForegroundColor Yellow
                Write-Host "      Left in place - it is your file. Remove '$name' unless you meant to keep it." -ForegroundColor Yellow
                Write-Host ""
            }
        }
    }

    $existing['mcpServers'] = $merged

    if (-not $WhatIfOnly) {
        $parent = Split-Path -Parent $DestPath
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Set-Content -LiteralPath $DestPath `
            -Value ($existing | ConvertTo-Json -Depth 10) -Encoding utf8
    }
    return $outcomes
}

# --- Resolve source + target ---
$source = (Get-Item (Join-Path $PSScriptRoot '..')).FullName
$mcpSourceFile = Join-Path $source 'harness\mcp-servers.json'

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
$mcpRel = $null
switch ($Harness) {
    'claude-code' {
        $skillsRel = '.claude\skills'
        $commandsRel = '.claude\commands'
        $settingsSrc = Join-Path $source 'harness\claude-code\settings.json'
        $settingsRel = '.claude\settings.json'
        $mcpRel = '.mcp.json'
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
# Checked here rather than where it is read, so a missing source file stops the
# run before anything has been copied - and so -DryRun catches it too.
if (-not $SkipMcpConfig -and -not (Test-Path -LiteralPath $mcpSourceFile)) {
    throw "MCP server config missing: $mcpSourceFile"
}

foreach ($p in $plan) {
    $srcShort = $p.Src.Replace($source, '<src>')
    $dstShort = $p.Dst.Replace($target, '<dst>')
    Write-Host ("{0,-9} {1} -> {2}" -f $p.Op, $srcShort, $dstShort)
}
$mcpSrcShort = $mcpSourceFile.Replace($source, '<src>')
if ($SkipMcpConfig) {
    Write-Host ("{0,-9} skipped (-SkipMcpConfig)" -f 'mcp')
}
elseif ($mcpRel) {
    Write-Host ("{0,-9} {1} -> {2}  (merged; other servers preserved)" -f 'mcp', $mcpSrcShort, (Join-Path '<dst>' $mcpRel))
}
else {
    Write-Host ("{0,-9} {1} -> printed below (location is client-specific)" -f 'mcp', $mcpSrcShort)
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

# --- MCP server configuration ---
# Installed with the skills rather than left to the reader, because it carries
# the version pin: a copy made by hand stays on whatever tag was current the day
# it was made, and the pin quietly becomes documentation instead of config.
$mcpServers = Get-McpServerBlock -Path $mcpSourceFile
$mcpOutcome = $null
if ($SkipMcpConfig) {
    Write-Host "Skipped MCP config (-SkipMcpConfig). The skills expect the pb_* tools to be reachable." -ForegroundColor Yellow
    $mcpOutcome = 'skipped (-SkipMcpConfig)'
}
elseif ($mcpRel) {
    $mcpDest = Join-Path $target $mcpRel
    $result = Write-McpConfig -Servers $mcpServers -DestPath $mcpDest
    if ($null -eq $result) {
        $mcpOutcome = "NOT written - $mcpRel could not be parsed; merge by hand"
    }
    else {
        Write-Host ("Installed {0,-9} {1}  [{2}]" -f 'mcp', $mcpRel, ($result -join '; ')) -ForegroundColor Green
        $mcpOutcome = "$mcpRel  [$($result -join '; ')]"
    }
}
else {
    # No known on-disk location for this harness. Printing the block and saying
    # so beats writing it somewhere invented, which would look like it worked.
    Write-Host ""
    Write-Host "MCP config: add these servers to your client's MCP configuration." -ForegroundColor Cyan
    Write-Host "Same JSON for every MCP client; only the file it goes in differs." -ForegroundColor Cyan
    Write-Host (@{ mcpServers = $mcpServers } | ConvertTo-Json -Depth 10)
    Write-Host ""
    $mcpOutcome = 'printed (location is client-specific)'
}

# --- Marker file (UTF-8, CRLF, so other tools and git diff it cleanly) ---
$markerLines = @(
    "# Skills, commands, knowledge base and MCP config installed from pb-ai-code.",
    "# Generated - do not edit. Change things in pb-ai-code and re-run.",
    "#",
    "# Installed: $now",
    "# Source:    pb-ai-code @ $sha ($branch)",
    "# Harness:   $Harness",
    "# MCP:       $mcpOutcome"
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
if ($Harness -eq 'claude-code' -and -not $SkipMcpConfig) {
    Write-Host "Restart your assistant to pick up the MCP config, then confirm the pb_* tools are listed (/mcp)."
}
