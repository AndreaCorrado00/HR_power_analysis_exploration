$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$archive = Join-Path $root 'archive'
$names = @('data','dataset','experiments','power_response_estimation','references','reports','scripts','src','tests','webapp','history.md','README.md','requirements.txt','requirements-gru.txt','pytest.ini','start-athlete.ps1')
$manifestPath = Join-Path $PSScriptRoot 'archive_manifest.local.json'
if (Test-Path -LiteralPath $archive) { throw 'Archive already exists; inspect manifest before resuming.' }
$frozen = Get-Content (Join-Path $root 'experiments/prescribed_joint/results/frozen.json') -Raw | ConvertFrom-Json
foreach ($pair in @(@('power/model.json',$frozen.hashes.power), @('hr_model.json',$frozen.hashes.hr))) {
    $actual = (Get-FileHash -LiteralPath (Join-Path $root ('experiments/prescribed_joint/results/' + $pair[0])) -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $pair[1]) { throw "Frozen artifact mismatch: $($pair[0])" }
}
$tracked = @{}
git -C $root ls-files | ForEach-Object { $tracked[$_] = $true }
$rows = [Collections.Generic.List[object]]::new()
foreach ($name in $names) {
    $source = [IO.Path]::GetFullPath((Join-Path $root $name))
    if (-not $source.StartsWith($root + [IO.Path]::DirectorySeparatorChar)) { throw 'Source escapes workspace' }
    $entries = @(Get-Item -LiteralPath $source -Force)
    if ($entries[0].PSIsContainer) { $entries += @(Get-ChildItem -LiteralPath $source -Recurse -Force) }
    foreach ($entry in $entries) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { $relative = $entry.FullName.Substring($root.Length + 1).Replace('\','/'); $rows.Add([pscustomobject]@{ source=$relative; destination=('archive/'+$relative); bytes=0; sha256=$null; link_target=@($entry.Target); tracked=$tracked.ContainsKey($relative) }); continue }
        if ($entry.PSIsContainer) { continue }
        $relative = $entry.FullName.Substring($root.Length + 1).Replace('\','/')
        $rows.Add([pscustomobject]@{ source=$relative; destination=('archive/'+$relative); bytes=$entry.Length; sha256=(Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLower(); tracked=$tracked.ContainsKey($relative) })
    }
    Write-Output "Inventoried $name ($($rows.Count) files total)"
}
@{ commit=(git -C $root rev-parse HEAD); created_at=[DateTime]::UtcNow.ToString('o'); files=@($rows.ToArray()); move_roots=$names } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
New-Item -ItemType Directory -Path $archive | Out-Null
foreach ($name in $names) {
    $source = [IO.Path]::GetFullPath((Join-Path $root $name))
    $destination = [IO.Path]::GetFullPath((Join-Path $archive $name))
    if (-not $source.StartsWith($root + '\') -or -not $destination.StartsWith($archive + '\')) { throw 'Move target escapes intended directory' }
    if (Test-Path -LiteralPath $destination) { throw "Collision: $destination" }
    Move-Item -LiteralPath $source -Destination $destination
}
foreach ($row in $rows) {
    $target = Join-Path $root $row.destination
    if ($row.PSObject.Properties.Name -contains 'link_target') { if ((@(Get-Item -LiteralPath $target -Force).Target -join '|') -ne ($row.link_target -join '|')) { throw "Link changed: $target" }; continue }
    if ((Get-Item -LiteralPath $target).Length -ne $row.bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower() -ne $row.sha256) { throw "Verification failed: $target" }
}
Write-Output "VERIFIED $($rows.Count) files, $(($rows | Measure-Object bytes -Sum).Sum) bytes; no refit."
