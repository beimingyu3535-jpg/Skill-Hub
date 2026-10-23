<#
  skillhub.ps1  -  Skill Hub manager
  ---------------------------------------------------------------
  ASCII-ONLY SOURCE on purpose:
    * host runs Windows PowerShell 5.1 with ANSI codepage gb2312
    * a no-BOM UTF-8 .ps1 containing CJK would be mis-decoded
  All Chinese/Unicode display text lives in _tools/labels.json (UTF-8)
  and is read explicitly as UTF-8.

  Commands:
    status        show hub summary
    list          list skills in hub
    index         regenerate INDEX.md
    snapshot      archive a skill version (asks nothing; caller decides)
    install       archive an installed skill package (zip or dir)
    import-zip    expand a zip into a skill folder + store raw package
    audit         compare live skill dirs against hub snapshots
    diff          diff two versions of a skill
    promote       merge a confirmed version branch into main + tag
    rollback      restore a snapshot into the live skill dir (backup first)
    push          secret scan + push branches
    net-probe     probe GitHub edge IPs and pin http.curloptResolve
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet('status','list','index','refresh','snapshot','install','import-zip','audit','diff','promote','rollback','push','net-probe')]
  [string]$Command,

  [string]$Name,
  [string]$Version,
  [string]$Note = '',
  [string]$Source,
  [string]$Zip,
  [string]$From,
  [string]$To,
  [string]$Link,
  [string]$SourceType = 'localEdit',
  [string]$Status = 'pending',

  [switch]$NoCommit,
  [switch]$Yes,
  [switch]$Force,
  [switch]$Block,
  [switch]$All
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- globals
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:ToolsDir  = $PSScriptRoot
$script:HubRoot   = [System.IO.Path]::GetDirectoryName($script:ToolsDir)
$script:CfgPath   = Join-Path $script:ToolsDir 'skillhub.config.json'
$script:Cfg       = Get-Content -LiteralPath $script:CfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$script:Lbl       = Get-Content -LiteralPath (Join-Path $script:ToolsDir 'labels.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$script:Punct     = $script:Lbl.punct
$script:RepoRoot  = $script:Cfg.repoRoot
if (-not $script:Cfg.hubRoot) { $script:Cfg.hubRoot = $script:HubRoot }

# ---------------------------------------------------------------- io helpers
function Read-Text([string]$Path) {
  return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}
function Write-Text([string]$Path, [string]$Text) {
  $dir = [System.IO.Path]::GetDirectoryName($Path)
  if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  [System.IO.File]::WriteAllText($Path, $Text, $script:Utf8NoBom)
}
function Read-Json([string]$Path) {
  return (Read-Text $Path | ConvertFrom-Json)
}
function Write-Json([string]$Path, $Object) {
  if ($Object -is [System.Array]) { $Object = $Object[$Object.Count - 1] }
  $json = $Object | ConvertTo-Json -Depth 12
  # PS5.1 escapes non-ascii as \uXXXX ; turn them back into real characters
  $json = [regex]::Replace($json, '\\u([0-9a-fA-F]{4})', {
      param($m) [char][Convert]::ToInt32($m.Groups[1].Value, 16)
    })
  Write-Text $Path $json
}
function Fmt([string]$Template, [hashtable]$Vars) {
  $s = $Template
  foreach ($k in $Vars.Keys) { $s = $s.Replace('{' + $k + '}', [string]$Vars[$k]) }
  return $s
}
function Say([string]$Text) { Write-Host $Text }

# ---------------------------------------------------------------- tree helpers
function Test-Excluded([string]$Full, [string]$Root) {
  $rel = $Full.Substring($Root.Length).TrimStart('\')
  $leaf = [System.IO.Path]::GetFileName($rel)
  $segs = $rel -split '[\\/]'
  foreach ($e in $script:Cfg.exclude) {
    if ($leaf -like $e) { return $true }
    foreach ($s in $segs) { if ($s -like $e) { return $true } }
  }
  return $false
}
function Get-TreeFiles([string]$Root) {
  if (-not (Test-Path -LiteralPath $Root)) { return @() }
  return @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object { -not (Test-Excluded $_.FullName $Root) })
}
function Get-TreeHash([string]$Root) {
  $files = Get-TreeFiles $Root
  $lines = New-Object System.Collections.Generic.List[string]
  foreach ($f in $files) {
    $rel = $f.FullName.Substring($Root.Length).TrimStart('\').Replace('\', '/')
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
    $lines.Add("$rel|$h")
  }
  $sorted = $lines | Sort-Object
  $joined = ($sorted -join "`n")
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($joined)
  return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join '')
}
function Get-TreeStat([string]$Root) {
  $files = Get-TreeFiles $Root
  $sum = 0
  foreach ($f in $files) { $sum += $f.Length }
  return [pscustomobject]@{ Count = $files.Count; Bytes = $sum }
}
function Copy-Tree([string]$Src, [string]$Dst) {
  if (-not (Test-Path -LiteralPath $Dst)) { New-Item -ItemType Directory -Force -Path $Dst | Out-Null }
  $opts = @($Src, $Dst, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/R:1', '/W:1', '/XD')
  foreach ($e in $script:Cfg.exclude) { $opts += $e }
  $opts += '/XF'
  foreach ($e in $script:Cfg.exclude) { $opts += $e }
  $null = & robocopy @opts
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }
}
function Get-Size([int64]$Bytes) {
  if ($Bytes -ge 1MB) { return ('{0:N1} MB' -f ($Bytes / 1MB)) }
  if ($Bytes -ge 1KB) { return ('{0:N1} KB' -f ($Bytes / 1KB)) }
  return "$Bytes B"
}

# ---------------------------------------------------------------- frontmatter
function Get-Frontmatter([string]$SkillDir) {
  $p = Join-Path $SkillDir 'SKILL.md'
  if (-not (Test-Path -LiteralPath $p)) { return $null }
  $txt = Read-Text $p
  if ($txt -notmatch '(?s)^\uFEFF?---\s*\r?\n(.*?)\r?\n---') { return $null }
  return $matches[1]
}
function Get-FrontValue([string]$SkillDir, [string]$Key) {
  $fm = Get-Frontmatter $SkillDir
  if (-not $fm) { return $null }
  if ($fm -match ('(?m)^\s*' + [regex]::Escape($Key) + '\s*:\s*(.+?)\s*$')) {
    return $matches[1].Trim().Trim('"').Trim("'")
  }
  return $null
}

# ---------------------------------------------------------------- skill lookup
function Get-HubSkillNames {
  $out = @()
  foreach ($d in (Get-ChildItem -LiteralPath $script:HubRoot -Directory -Force)) {
    if ($d.Name -like '_*') { continue }
    $out += $d.Name
  }
  return $out
}
function Get-Snapshots([string]$SkillName) {
  $dir = Join-Path $script:HubRoot $SkillName
  $list = @()
  if (-not (Test-Path -LiteralPath $dir)) { return $list }
  foreach ($d in (Get-ChildItem -LiteralPath $dir -Directory -Force)) {
    $mp = Join-Path $d.FullName 'MANIFEST.json'
    if (Test-Path -LiteralPath $mp) {
      $m = Read-Json $mp
      $m | Add-Member -NotePropertyName '_dir' -NotePropertyValue $d.FullName -Force
      $list += $m
    }
  }
  return ,@($list | Sort-Object -Property snapshot_at -Descending)
}
function Resolve-LiveDir([string]$SkillName, [string]$Explicit) {
  if ($Explicit) {
    if (-not (Test-Path -LiteralPath $Explicit)) { throw "source not found: $Explicit" }
    return (Resolve-Path -LiteralPath $Explicit).Path.TrimEnd('\')
  }
  foreach ($root in $script:Cfg.liveRoots) {
    $p = Join-Path $root $SkillName
    if (Test-Path -LiteralPath $p) { return (Resolve-Path -LiteralPath $p).Path.TrimEnd('\') }
  }
  throw "live dir not found for skill '$SkillName' under: $($script:Cfg.liveRoots -join ', ')"
}

# ---------------------------------------------------------------- git helpers
function Invoke-Git([string[]]$GitArgs) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $out = & git -C $script:RepoRoot @GitArgs 2>&1
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  return [pscustomobject]@{ Code = $code; Out = (($out | ForEach-Object { "$_" }) -join "`n").Trim() }
}
function Get-CurrentBranch {
  $r = Invoke-Git @('rev-parse', '--abbrev-ref', 'HEAD')
  if ($r.Code -ne 0) { return '' }
  return $r.Out
}
function Commit-IfDirty([string]$Message) {
  $st = Invoke-Git @('status', '--porcelain')
  if (-not $st.Out) { return $null }
  $a = Invoke-Git @('add', '-A')
  if ($a.Code -ne 0) { throw "git add failed: $($a.Out)" }
  $c = Invoke-Git @('commit', '-m', $Message)
  if ($c.Code -ne 0) { throw "git commit failed: $($c.Out)" }
  $h = Invoke-Git @('rev-parse', '--short', 'HEAD')
  return $h.Out
}

# ---------------------------------------------------------------- renderers
function Update-SkillReadme([string]$SkillName) {
  $L = $script:Lbl
  $snaps = Get-Snapshots $SkillName
  $dir = Join-Path $script:HubRoot $SkillName
  $readmePath = Join-Path $dir 'README.md'
  $n = $snaps.Count

  if ($n -eq 0) {
    if (-not (Test-Path -LiteralPath $readmePath)) {
      Write-Text $readmePath (Fmt $L.readme.title @{ name = $SkillName }) + "`n`n" + $L.readme.noSnapshot + "`n"
    }
    return
  }

  $latest = $snaps[0]
  $confirmed = $snaps | Where-Object { $_.status -eq 'confirmed' } | Select-Object -First 1
  $curVer = $script:Punct.dash
  if ($confirmed) { $curVer = 'v' + $confirmed.version }
  $liveP = ''
  foreach ($root in $script:Cfg.liveRoots) {
    $p = Join-Path $root $SkillName
    if (Test-Path -LiteralPath $p) { $liveP = $p; break }
  }
  if (-not $liveP) { $liveP = $script:Punct.dash }

  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine((Fmt $L.readme.title @{ name = $SkillName }))
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine('| | |')
  [void]$sb.AppendLine('|---|---|')
  $vars = @{
    name           = $SkillName
    currentVersion = $curVer
    latestSnapshot = $latest.snapshot_id
    status         = $latest.status
    source         = $latest.source.type
    livePath       = $liveP
    fileCount      = $latest.file_count
    humanSize      = (Get-Size $latest.total_bytes)
    updatedAt      = $latest.snapshot_at
  }
  foreach ($row in $L.readme.meta) {
    [void]$sb.AppendLine('| ' + $row[0] + ' | ' + (Fmt $row[1] $vars) + ' |')
  }
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine($L.readme.versionsHeader)
  [void]$sb.AppendLine('')
  $cols = $L.readme.cols
  [void]$sb.AppendLine('| ' + ($cols -join ' | ') + ' |')
  [void]$sb.AppendLine('|' + (($cols | ForEach-Object { '---' }) -join '|') + '|')
  foreach ($s in $snaps) {
    $noteTxt = $s.note
    if (-not $noteTxt) { $noteTxt = '' }
    $row = @(('v' + $s.version), ('`' + $s.snapshot_id + '`'), $s.snapshot_at, $s.status, $noteTxt)
    [void]$sb.AppendLine('| ' + ($row -join ' | ') + ' |')
  }
  [void]$sb.AppendLine('')
  if (Test-Path -LiteralPath (Join-Path $dir '_raw')) {
    [void]$sb.AppendLine($L.readme.quickUse)
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine('- `_raw/` : original package(s)')
    [void]$sb.AppendLine('')
  }
  Write-Text $readmePath $sb.ToString()
}

function Get-DiffStat([string]$OldDir, [string]$NewDir) {
  if (-not $OldDir -or -not (Test-Path -LiteralPath $OldDir)) {
    $st = Get-TreeStat $NewDir
    return "+$($st.Count) new files"
  }
  $old = @{}
  foreach ($f in (Get-TreeFiles $OldDir)) {
    $rel = $f.FullName.Substring($OldDir.Length).TrimStart('\').Replace('\', '/')
    $old[$rel] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
  }
  $added = 0; $changed = 0; $same = 0
  $seen = @{}
  foreach ($f in (Get-TreeFiles $NewDir)) {
    $rel = $f.FullName.Substring($NewDir.Length).TrimStart('\').Replace('\', '/')
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    $seen[$rel] = $true
    if (-not $old.ContainsKey($rel)) { $added++ }
    elseif ($old[$rel] -ne $h) { $changed++ }
    else { $same++ }
  }
  $deleted = 0
  foreach ($k in $old.Keys) { if (-not $seen.ContainsKey($k)) { $deleted++ } }
  return "A$added M$changed D$deleted (= $same)"
}

function Add-Changelog([string]$SkillName, $Manifest, [string]$DiffStat) {
  $L = $script:Lbl.changelog
  $path = Join-Path (Join-Path $script:HubRoot $SkillName) 'CHANGELOG.md'
  $existing = ''
  if (Test-Path -LiteralPath $path) { $existing = Read-Text $path }

  if ($existing -match [regex]::Escape($Manifest.snapshot_id)) {
    return  # idempotent
  }

  $entry = New-Object System.Text.StringBuilder
  [void]$entry.AppendLine('')
  [void]$entry.AppendLine(('## v' + $Manifest.version + ' ' + $script:Punct.dash + ' ' + $Manifest.snapshot_at))
  [void]$entry.AppendLine('- ' + $L.summary + $script:Punct.colon + $(if ($Manifest.note) { $Manifest.note } else { $script:Punct.dash }))
  [void]$entry.AppendLine('- ' + $L.diffstat + $script:Punct.colon + '`' + $DiffStat + '`')
  [void]$entry.AppendLine('- ' + $L.snapshot + $script:Punct.colon + '`' + $Manifest.snapshot_id + '`')
  $gitLine = ('branch `{0}`' + $script:Punct.dot + 'commit `{1}`') -f $Manifest.git.branch, $Manifest.git.commit
  if ($Manifest.git.tag) { $gitLine += ($script:Punct.dot + 'tag `' + $Manifest.git.tag + '`') }
  [void]$entry.AppendLine('- ' + $L.git + $script:Punct.colon + $gitLine)
  $conf = $L.pending
  if ($Manifest.status -eq 'confirmed') { $conf = $L.confirmed }
  elseif ($Manifest.status -eq 'archived') { $conf = $L.archived }
  elseif ($Manifest.status -eq 'unversioned') { $conf = $L.unversioned }
  [void]$entry.AppendLine('- ' + $L.confirm + $script:Punct.colon + $conf)
  [void]$entry.AppendLine('- ' + $L.source + $script:Punct.colon + $Manifest.source.type + ' ' + $Manifest.source.from)

  if (-not $existing) {
    $head = New-Object System.Text.StringBuilder
    [void]$head.AppendLine((Fmt $L.title @{ name = $SkillName }))
    $existing = $head.ToString()
  }
  Write-Text $path ($existing.TrimEnd() + "`n" + $entry.ToString())
}

function Update-Index {
  $L = $script:Lbl.index
  $rows = @()
  foreach ($name in (Get-HubSkillNames)) {
    $snaps = Get-Snapshots $name
    if ($snaps.Count -eq 0) {
      $rows += [pscustomobject]@{ Name = $name; Ver = $script:Punct.dash; When = $script:Punct.dash; Status = 'empty'; Count = 0; Bytes = 0 }
      continue
    }
    $latest = $snaps[0]
    $conf = $snaps | Where-Object { $_.status -eq 'confirmed' } | Select-Object -First 1
    $ver = $script:Punct.dash
    if ($conf) { $ver = 'v' + $conf.version }
    $bytes = 0
    foreach ($s in $snaps) { $bytes += $s.total_bytes }
    $rows += [pscustomobject]@{
      Name = $name; Ver = $ver; When = $latest.snapshot_at
      Status = $latest.status; Count = $snaps.Count; Bytes = $bytes
    }
  }

  $inbox = @()
  $inboxDir = Join-Path $script:HubRoot '_inbox'
  if (Test-Path -LiteralPath $inboxDir) {
    $inbox = @(Get-ChildItem -LiteralPath $inboxDir -Directory -Force | ForEach-Object { $_.Name })
  }

  $pendingBranches = @()
  $b = Invoke-Git @('branch', '--no-merged', $script:Cfg.defaultBranch)
  if ($b.Code -eq 0 -and $b.Out) {
    $pendingBranches = @($b.Out -split "`n" | ForEach-Object { $_.Trim().TrimStart('*').Trim() } | Where-Object { $_ -and $_ -ne $script:Cfg.defaultBranch })
  }

  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine($L.title)
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine($L.note)
  [void]$sb.AppendLine('')
  $cols = $L.cols
  [void]$sb.AppendLine('| ' + ($cols -join ' | ') + ' |')
  [void]$sb.AppendLine('|' + (($cols | ForEach-Object { '---' }) -join '|') + '|')
  foreach ($r in ($rows | Sort-Object Name)) {
    $line = @("[$($r.Name)]($($r.Name)/README.md)", $r.Ver, $r.When, $r.Status, $r.Count, (Get-Size $r.Bytes))
    [void]$sb.AppendLine('| ' + ($line -join ' | ') + ' |')
  }
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine('## ' + $L.pendingBranches)
  [void]$sb.AppendLine('')
  if ($pendingBranches.Count -eq 0) { [void]$sb.AppendLine($L.none) }
  else { foreach ($p in $pendingBranches) { [void]$sb.AppendLine('- `' + $p + '`') } }
  [void]$sb.AppendLine('')
  [void]$sb.AppendLine('## ' + $L.inbox)
  [void]$sb.AppendLine('')
  if ($inbox.Count -eq 0) { [void]$sb.AppendLine($L.none) }
  else { foreach ($p in $inbox) { [void]$sb.AppendLine('- `_inbox/' + $p + '/`') } }
  [void]$sb.AppendLine('')

  Write-Text (Join-Path $script:HubRoot 'INDEX.md') $sb.ToString()
}

# ---------------------------------------------------------------- secret scan
function Invoke-SecretScan([string]$Root) {
  $hits = @()
  $exts = $script:Cfg.secretScan.extensions
  foreach ($f in (Get-TreeFiles $Root)) {
    $ext = [System.IO.Path]::GetExtension($f.Name).ToLower()
    if ($exts -notcontains $ext) { continue }
    if ($f.Length -gt 2MB) { continue }
    $text = ''
    try { $text = Read-Text $f.FullName } catch { continue }
    $lines = $text -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
      foreach ($p in $script:Cfg.secretScan.patterns) {
        if ($lines[$i] -match $p) {
          $rel = $f.FullName.Substring($Root.Length).TrimStart('\')
          $hits += [pscustomobject]@{ File = $rel; Line = $i + 1; Pattern = $p }
          break
        }
      }
      if ($hits.Count -gt 200) { break }
    }
  }
  return $hits
}

# ---------------------------------------------------------------- core: snapshot
function Invoke-Snapshot {
  param(
    [Parameter(Mandatory = $true)][string]$SkillName,
    [string]$SrcPath,
    [string]$Ver,
    [string]$Msg = '',
    [string]$Origin = 'localEdit',
    [string]$SnapStatus = 'pending',
    [string]$VerSource = '',
    [switch]$SkipCommit,
    [switch]$ForceIt
  )
  $Name = $SkillName
  $Source = $SrcPath
  $Version = $Ver
  $Note = $Msg
  $SourceType = $Origin
  $Status = $SnapStatus
  $src = Resolve-LiveDir $Name $Source

  $ver = $Version
  if (-not $ver) { $ver = Get-FrontValue $src 'version' }
  if (-not $ver) { throw "cannot determine version: pass -Version or add 'version:' to SKILL.md frontmatter" }

  $fmName = Get-FrontValue $src 'name'
  if ($fmName -and $fmName -ne $Name) {
    throw "name mismatch: folder/-Name='$Name' but SKILL.md name='$fmName'"
  }

  $now = Get-Date
  $stamp = $now.ToString($script:Cfg.timeFormat)
  $snapId = '{0}_v{1}_{2}' -f $Name, $ver, $stamp
  $skillDir = Join-Path $script:HubRoot $Name
  $snapDir = Join-Path $skillDir $snapId
  $readme = Join-Path $skillDir 'README.md'

  $snaps = Get-Snapshots $Name

  # idempotency: identical content + same version -> no-op
  $srcHash = Get-TreeHash $src
  if (-not $ForceIt) {
    if ($snaps.Count -gt 0) {
      $top = $snaps[0]
      if ($top.version -eq $ver -and $top.tree_sha256 -eq $srcHash) {
        Say "NOOP: identical to $($top.snapshot_id)"
        Update-SkillReadme $Name
        return $top
      }
      if ($top.version -eq $ver -and $top.tree_sha256 -ne $srcHash) {
        throw "version $ver already archived with different content. bump the version first (or pass -Force)."
      }
    }
  }

  # parent = latest snapshot of this skill
  $parentVersion = ''
  if ($snaps.Count -gt 0) { $parentVersion = $snaps[0].version }
  $prevDir = ''
  if ($snaps.Count -gt 0) { $prevDir = $snaps[0]._dir }

  if (Test-Path -LiteralPath $snapDir) { Remove-Item -LiteralPath $snapDir -Recurse -Force }
  Copy-Tree $src $snapDir

  $hash = Get-TreeHash $snapDir
  $stat = Get-TreeStat $snapDir
  $diffStat = Get-DiffStat $prevDir $snapDir

  $manifest = [ordered]@{
    name          = $Name
    version       = $ver
    version_source = $(if ($VerSource) { $VerSource } else { 'frontmatter' })
    snapshot_id   = $snapId
    snapshot_at   = $now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    source        = [ordered]@{ type = $SourceType; from = $src; raw = '' }
    git           = [ordered]@{ branch = ''; commit = ''; tag = '' }
    status        = $Status
    publish       = $true
    confirmed_by  = ''
    confirmed_at  = ''
    tree_sha256   = $hash
    file_count    = $stat.Count
    total_bytes   = $stat.Bytes
    diffstat      = $diffStat
    excluded      = @($script:Cfg.exclude)
    parent_version = $parentVersion
    note          = $Note
  }
  Write-Json (Join-Path $snapDir 'MANIFEST.json') $manifest

  Add-Changelog $Name $manifest $diffStat
  Update-SkillReadme $Name
  Update-Index

  Say ("SNAPSHOT: {0}  files={1} bytes={2} {3}" -f $snapId, $stat.Count, $stat.Bytes, $diffStat)

  if (-not $SkipCommit) {
    $branch = '{0}/{1}/v{2}' -f $script:Cfg.branchPrefix, $Name, $ver
    $exists = Invoke-Git @('rev-parse', '--verify', '--quiet', $branch)
    if ($exists.Code -eq 0) {
      $co = Invoke-Git @('checkout', $branch)
      if ($co.Code -ne 0) { throw "checkout failed: $($co.Out)" }
    }
    else {
      $co = Invoke-Git @('checkout', '-b', $branch)
      if ($co.Code -ne 0) { throw "branch create failed: $($co.Out)" }
    }
    $msg = 'feat({0}): v{1} - {2}' -f $Name, $ver, $(if ($Note) { $Note } else { 'snapshot' })
    $commit = Commit-IfDirty $msg
    if ($commit) {
      $m2 = Read-Json (Join-Path $snapDir 'MANIFEST.json')
      $m2.git.branch = $branch
      $m2.git.commit = $commit
      Write-Json (Join-Path $snapDir 'MANIFEST.json') $m2
      Say ("BRANCH: {0}  COMMIT: {1}" -f $branch, $commit)
    }
    else {
      Say 'BRANCH: (nothing to commit)'
    }
  }

  $ret = Read-Json (Join-Path $snapDir 'MANIFEST.json')
  $ret | Add-Member -NotePropertyName '_dir' -NotePropertyValue $snapDir -Force
  return $ret
}

# ---------------------------------------------------------------- import-zip
function Invoke-ImportZip {
  if (-not $Zip) { throw '-Zip is required' }
  if (-not (Test-Path -LiteralPath $Zip)) { throw "zip not found: $Zip" }

  $skillName = $Name
  if (-not $skillName) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($Zip)
    if ($base -match '^([A-Za-z0-9][A-Za-z0-9._-]*?)(_skill)?_v?[0-9]') { $skillName = $matches[1] }
    else { $skillName = ($base -replace '[^A-Za-z0-9._-]+', '-').Trim('-') }
  }
  $skillDir = Join-Path $script:HubRoot $skillName
  $rawDir = Join-Path $skillDir '_raw'
  New-Item -ItemType Directory -Force -Path $rawDir | Out-Null

  # store raw package + sha256
  $rawName = [System.IO.Path]::GetFileName($Zip)
  $rawDest = Join-Path $rawDir $rawName
  if ([System.IO.Path]::GetFullPath($Zip) -ne [System.IO.Path]::GetFullPath($rawDest)) {
    Copy-Item -LiteralPath $Zip -Destination $rawDest -Force
  }
  else {
    Say 'RAW: source already inside _raw, keeping as is'
  }
  $sha = (Get-FileHash -LiteralPath $rawDest -Algorithm SHA256).Hash.ToLower()
  Write-Text (Join-Path $rawDir ($rawName + '.sha256')) ($sha + '  ' + $rawName + "`n")
  Say "RAW: $rawDest  sha256=$sha"

  # expand to a temp dir, find the real skill root (dir containing SKILL.md)
  $tmp = Join-Path $env:TEMP ('skillhub-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  Expand-Archive -LiteralPath $Zip -DestinationPath $tmp -Force
  $skillMd = Get-ChildItem -LiteralPath $tmp -Recurse -File -Filter 'SKILL.md' | Select-Object -First 1
  if (-not $skillMd) {
    Move-Item -LiteralPath $tmp -Destination (Join-Path $script:HubRoot ('_inbox\' + $skillName)) -Force
    Say "NO SKILL.md INSIDE -> moved to _inbox/$skillName"
    return
  }
  $rootDir = $skillMd.Directory.FullName

  # version: explicit > frontmatter > filename
  $ver = $Version
  $verSrc = 'explicit'
  if (-not $ver) {
    $ver = Get-FrontValue $rootDir 'version'
    if ($ver) { $verSrc = 'frontmatter' }
  }
  if (-not $ver) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($Zip)
    if ($baseName -match '(?:^|[_\s-])v?(\d+\.\d+(?:\.\d+)?)(?:$|[_\s-])') {
      $ver = $matches[1]
      $verSrc = 'filename'
    }
  }
  if (-not $ver) { $ver = '0.0.0'; $verSrc = 'unknown' }
  Say "VERSION: $ver (source=$verSrc)"

  # snapshot from the expanded content
  $m = @(Invoke-Snapshot -SkillName $skillName -SrcPath $rootDir -Ver $ver -VerSource $verSrc -Msg $(if ($Note) { $Note } else { 'imported from ' + $rawName }) -Origin 'installZip' -SkipCommit:$NoCommit)[-1]
  $m.source.raw = $rawName
  Write-Json (Join-Path $m._dir 'MANIFEST.json') $m

  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
  Say "IMPORTED: $skillName v$($m.version)"
}

# ---------------------------------------------------------------- audit
function Invoke-Audit {
  $issues = @()
  $liveNames = @()
  foreach ($root in $script:Cfg.liveRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($d in (Get-ChildItem -LiteralPath $root -Directory -Force)) {
      $liveNames += $d.Name
      $snaps = Get-Snapshots $d.Name
      if ($snaps.Count -eq 0) {
        $issues += [pscustomobject]@{ Skill = $d.Name; Kind = 'NOT_ARCHIVED'; Detail = $d.FullName }
        continue
      }
      $liveHash = Get-TreeHash $d.FullName
      $latest = $snaps[0]
      if ($latest.tree_sha256 -ne $liveHash) {
        $issues += [pscustomobject]@{ Skill = $d.Name; Kind = 'DRIFT'; Detail = "live != $($latest.snapshot_id)" }
      }
      $fmVer = Get-FrontValue $d.FullName 'version'
      if ($fmVer -and $fmVer -ne $latest.version) {
        $issues += [pscustomobject]@{ Skill = $d.Name; Kind = 'VERSION_MISMATCH'; Detail = "SKILL.md=$fmVer latest_snapshot=$($latest.version)" }
      }
    }
  }
  foreach ($h in (Get-HubSkillNames)) {
    if ($liveNames -notcontains $h) {
      $issues += [pscustomobject]@{ Skill = $h; Kind = 'HUB_ONLY'; Detail = 'no live dir' }
    }
  }
  if ($issues.Count -eq 0) { Say 'AUDIT: clean (0 issues)' }
  else {
    Say ("AUDIT: {0} issue(s)" -f $issues.Count)
    foreach ($i in $issues) { Say ("  [{0}] {1} - {2}" -f $i.Kind, $i.Skill, $i.Detail) }
  }
}

# ---------------------------------------------------------------- promote
function Invoke-Promote {
  if (-not $Name) { throw '-Name is required' }
  $snaps = Get-Snapshots $Name
  if ($snaps.Count -eq 0) { throw "no snapshots for $Name" }
  $target = $null
  if ($Version) { $target = $snaps | Where-Object { $_.version -eq $Version } | Select-Object -First 1 }
  else { $target = $snaps[0] }
  if (-not $target) { throw "version $Version not found for $Name" }

  $branch = '{0}/{1}/v{2}' -f $script:Cfg.branchPrefix, $Name, $target.version
  $exists = Invoke-Git @('rev-parse', '--verify', '--quiet', $branch)
  $main = $script:Cfg.defaultBranch

  # always return to the default branch first: promoting anything while sitting on
  # a feature branch would silently commit onto that branch instead of main
  $co = Invoke-Git @('checkout', $main)
  if ($co.Code -ne 0) { throw "checkout $main failed: $($co.Out)" }

  if ($exists.Code -eq 0) {
    $mg = Invoke-Git @('merge', '--no-ff', $branch, '-m', ('chore({0}): merge v{1} (confirmed)' -f $Name, $target.version))
    if ($mg.Code -ne 0) { throw "merge failed: $($mg.Out)" }
  }
  else {
    Say "NOTE: branch $branch not found, promoting working tree state on $main"
  }

  $tagName = $script:Cfg.tagFormat.Replace('{name}', $Name).Replace('{version}', $target.version)
  Invoke-Git @('tag', '-f', $tagName) | Out-Null

  $mp = Join-Path $target._dir 'MANIFEST.json'
  $m = Read-Json $mp
  $m.status = 'confirmed'
  $m.confirmed_by = 'YG'
  $m.confirmed_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
  $m.git.tag = $tagName
  Write-Json $mp $m

  Update-SkillReadme $Name
  Update-Index
  $c = Commit-IfDirty ('chore({0}): mark v{1} confirmed' -f $Name, $target.version)
  Say ("PROMOTED: {0} v{1} tag={2} commit={3}" -f $Name, $target.version, $tagName, $c)
}

# ---------------------------------------------------------------- rollback
function Invoke-Rollback {
  if (-not $Name -or -not $Version) { throw '-Name and -Version are required' }
  $snaps = Get-Snapshots $Name
  $target = $snaps | Where-Object { $_.version -eq $Version } | Select-Object -First 1
  if (-not $target) { throw "version $Version not found for $Name" }
  $live = Resolve-LiveDir $Name ''
  $stamp = (Get-Date).ToString($script:Cfg.timeFormat)
  $bkDir = Join-Path (Join-Path $script:HubRoot '_archive') ('_rollback-backup\' + $Name + '_' + $stamp)
  New-Item -ItemType Directory -Force -Path $bkDir | Out-Null
  Copy-Tree $live $bkDir
  Say "BACKUP: $bkDir"
  if (-not $Yes) {
    Say 'DRY-RUN: pass -Yes to actually overwrite the live dir'
    return
  }
  Copy-Tree $target._dir $live
  Say ("ROLLED BACK: {0} -> v{1}" -f $live, $Version)
}

# ---------------------------------------------------------------- push
function Invoke-Push {
  if (-not $Name) {
    $br = Get-CurrentBranch
    if ($script:Cfg.push.protectedBranches -contains $br) { throw "refusing to push protected branch '$br' directly; use promote" }
    $targets = @($br)
  }
  else { $targets = @($Name) }

  foreach ($t in $targets) {
    if ($script:Cfg.push.protectedBranches -contains $t) { throw "refusing to push protected branch '$t'" }
    $sr = Invoke-Git @('rev-parse', '--show-toplevel')
    $hits = Invoke-SecretScan $script:HubRoot
    if ($hits.Count -gt 0) {
      Say ("SECRET-SCAN: {0} hit(s)" -f $hits.Count)
      foreach ($h in ($hits | Select-Object -First 20)) { Say ("  {0}:{1}  {2}" -f $h.File, $h.Line, $h.Pattern) }
      if ($script:Cfg.secretScan.block -or $Block) { throw 'push blocked by secret scan (-Block or config)' }
      Say 'SECRET-SCAN: warn-only (config block=false) - continuing'
    }
    $p = Invoke-Git @('push', '-u', $script:Cfg.push.remote, $t)
    if ($p.Code -ne 0) {
      Say ("PUSH FAILED: {0}" -f $p.Out)
      $q = Join-Path $script:HubRoot $script:Cfg.push.queueFile
      $queue = @()
      if (Test-Path -LiteralPath $q) { $queue = @(Read-Json $q) }
      $queue += [pscustomobject]@{ branch = $t; at = (Get-Date).ToString('s'); error = $p.Out }
      Write-Json $q $queue
      Say "QUEUED: $q"
    }
    else { Say ("PUSHED: {0}" -f $t) }
  }
}

# ---------------------------------------------------------------- net-probe
function Test-GitHubTls([string]$Ip, [string]$SniName) {
  $tcp = $null
  $ssl = $null
  try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect($Ip, 443, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne(4000, $false)) { return $false }
    $tcp.EndConnect($iar)
    $tcp.ReceiveTimeout = 8000
    $tcp.SendTimeout = 8000
    $cb = [System.Net.Security.RemoteCertificateValidationCallback] { param($a, $b, $c, $d) return $true }
    $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, $cb)
    $ssl.AuthenticateAsClient($SniName)
    return $ssl.IsAuthenticated
  }
  catch { return $false }
  finally {
    if ($ssl) { try { $ssl.Dispose() } catch { } }
    if ($tcp) { try { $tcp.Close() } catch { } }
  }
}

function Invoke-NetProbe {
  $ghHost = $script:Cfg.githubPin.host
  $cands = @()
  if ($script:Cfg.githubPin.active) { $cands += $script:Cfg.githubPin.active }
  foreach ($c in $script:Cfg.githubPin.candidates) { $cands += $c }
  $cands = @($cands | Select-Object -Unique)
  $best = ''
  foreach ($ip in $cands) {
    $tls = Test-GitHubTls $ip $ghHost
    Say ("PROBE {0}:443 tls={1}" -f $ip, $(if ($tls) { 'OK' } else { 'FAIL' }))
    if (-not $tls) { continue }
    $pin = '{0}:443:{1}' -f $ghHost, $ip
    $r = Invoke-Git @('config', '--local', 'http.curloptResolve', $pin)
    if ($r.Code -ne 0) { Say ("  git config failed: {0}" -f $r.Out); continue }
    Say ("  ls-remote via {0} ..." -f $ip)
    $t = Invoke-Git @('ls-remote', '--heads', $script:Cfg.push.remote)
    if ($t.Code -eq 0) {
      $best = $ip
      Say ("PINNED: {0}" -f $pin)
      if ($t.Out) { Say $t.Out }
      break
    }
    Say ("  ls-remote failed (code {0})" -f $t.Code)
  }
  if (-not $best) { throw 'no github edge ip passed tls+ls-remote' }
  $script:Cfg.githubPin.active = $best
  Write-Json $script:CfgPath $script:Cfg
}

# ---------------------------------------------------------------- status/list
function Show-Status {
  Say ("HUB      : {0}" -f $script:HubRoot)
  Say ("REPO     : {0}" -f $script:RepoRoot)
  Say ("BRANCH   : {0}" -f (Get-CurrentBranch))
  Say ("SKILLS   : {0}" -f ((Get-HubSkillNames) -join ', '))
  $pin = Invoke-Git @('config', '--local', '--get', 'http.curloptResolve')
  Say ("GIT PIN  : {0}" -f $(if ($pin.Out) { $pin.Out } else { '(none)' }))
  $st = Invoke-Git @('status', '--porcelain')
  $n = 0
  if ($st.Out) { $n = ($st.Out -split "`n").Count }
  Say ("DIRTY    : {0} path(s)" -f $n)
}
function Show-List {
  foreach ($name in (Get-HubSkillNames)) {
    $snaps = Get-Snapshots $name
    $conf = $snaps | Where-Object { $_.status -eq 'confirmed' } | Select-Object -First 1
    $cur = $script:Punct.dash; if ($conf) { $cur = 'v' + $conf.version }
    Say ("{0,-28} snaps={1,-3} current={2,-10} latest={3}" -f $name, $snaps.Count, $cur, $(if ($snaps.Count) { $snaps[0].snapshot_id } else { $script:Punct.dash }))
  }
}

function Invoke-Refresh {
  foreach ($n in (Get-HubSkillNames)) { Update-SkillReadme $n }
  Update-Index
  Say ("REFRESHED: {0} skill(s)" -f (Get-HubSkillNames).Count)
}

function Invoke-Diff {
  if (-not $Name -or -not $From -or -not $To) { throw '-Name, -From and -To are required' }
  $snaps = Get-Snapshots $Name
  $a = $snaps | Where-Object { $_.version -eq $From } | Select-Object -First 1
  $b = $snaps | Where-Object { $_.version -eq $To } | Select-Object -First 1
  if (-not $a) { throw "version $From not found" }
  if (-not $b) { throw "version $To not found" }
  Say ("DIFF {0}: v{1} -> v{2}" -f $Name, $From, $To)

  $old = @{}
  foreach ($f in (Get-TreeFiles $a._dir)) {
    $rel = $f.FullName.Substring($a._dir.Length).TrimStart('\').Replace('\', '/')
    if ($rel -eq 'MANIFEST.json') { continue }
    $old[$rel] = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
  }
  $seen = @{}
  $added = 0; $changed = 0; $same = 0
  foreach ($f in (Get-TreeFiles $b._dir)) {
    $rel = $f.FullName.Substring($b._dir.Length).TrimStart('\').Replace('\', '/')
    if ($rel -eq 'MANIFEST.json') { continue }
    $seen[$rel] = $true
    $h = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    if (-not $old.ContainsKey($rel)) { Say ("  A  {0}" -f $rel); $added++ }
    elseif ($old[$rel] -ne $h) { Say ("  M  {0}" -f $rel); $changed++ }
    else { $same++ }
  }
  $deleted = 0
  foreach ($k in $old.Keys) { if (-not $seen.ContainsKey($k)) { Say ("  D  {0}" -f $k); $deleted++ } }
  Say ("SUMMARY: A{0} M{1} D{2} (= {3})" -f $added, $changed, $deleted, $same)
}

# ---------------------------------------------------------------- dispatch
switch ($Command) {
  'status'     { Show-Status }
  'list'       { Show-List }
  'index'      { Update-Index; Say 'INDEX.md regenerated' }
  'snapshot'   { $null = Invoke-Snapshot -SkillName $Name -SrcPath $Source -Ver $Version -Msg $Note -Origin $SourceType -SnapStatus $Status -SkipCommit:$NoCommit -ForceIt:$Force }
  'install'    { $null = Invoke-Snapshot -SkillName $Name -SrcPath $Source -Ver $Version -Msg $Note -Origin 'installZip' -SnapStatus $Status -SkipCommit:$NoCommit -ForceIt:$Force }
  'import-zip' { Invoke-ImportZip }
  'audit'      { Invoke-Audit }
  'diff'       { Invoke-Diff }
  'refresh'    { Invoke-Refresh }
  'promote'    { Invoke-Promote }
  'rollback'   { Invoke-Rollback }
  'push'       { Invoke-Push }
  'net-probe'  { Invoke-NetProbe }
}
