# Batch-Pipeline: alle Meshes aus export/manifest.json morphen, in UE
# importieren, cooken, packen, verifizieren.
#
# Aufruf:  .\scripts\run_batch.ps1 [-Factor 2.5] [-Install]

param(
    [double]$Factor = 2.5,
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$Root     = Split-Path $PSScriptRoot -Parent
$Blender  = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
$UeCmd    = "O:\UE_5.1\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$Project  = "$Root\ue_project\PalMod\PalMod.uproject"
$Paks     = "M:\SteamLibrary\steamapps\common\Palworld\Pal\Content\Paks"
$Usmap    = "$Root\tools\mappings\Palworld.usmap"

function ConvertTo-GamePath($p) {
    if (-not $p) { return $null }
    ($p -replace '^Pal/Content', '/Game').Split('.')[0]
}

$manifest = Get-Content "$Root\export\manifest.json" -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force "$Root\work\renders" | Out-Null

$jobs = @()
$failed = @()

foreach ($entry in $manifest) {
    foreach ($mesh in $entry.meshes) {
        $psk = $mesh.file -replace '\.glb$', '.psk'
        if (-not (Test-Path $psk)) { $psk = $mesh.file }
        if (-not (Test-Path $psk) -or $psk -notlike "*.psk") {
            $failed += "$($entry.display): psk fehlt ($($mesh.file))"
            continue
        }
        $name = [IO.Path]::GetFileNameWithoutExtension($psk)
        $fbx = "$Root\work\$($name)_morphed.fbx"
        Write-Host "== Morphe $name ($($entry.display)) =="
        & $Blender --background --python "$Root\scripts\bust_morph.py" -- `
            --input $psk --output $fbx --factor $Factor --shapekey `
            --render "$Root\work\renders\$name" > "$Root\work\renders\$name.log"
        if (-not (Select-String -Path "$Root\work\renders\$name.log" -Pattern "Exportiert" -Quiet)) {
            $reason = (Select-String -Path "$Root\work\renders\$name.log" `
                -Pattern "RuntimeError: (.+)" | Select-Object -First 1)
            $failed += "$($entry.display) / $name : $(if ($reason) { $reason.Matches[0].Groups[1].Value } else { 'unbekannt (siehe Log)' })"
            continue
        }
        $jobs += @{
            fbx          = $fbx -replace '\\', '/'
            assetPath    = $mesh.assetPath
            skeletonPath = ConvertTo-GamePath $mesh.skeleton
            materials    = @($mesh.materials | ForEach-Object {
                                @{ slot = $_.slot; path = ConvertTo-GamePath $_.material } })
        }
    }
}

Write-Host ""
Write-Host "Morph fertig: $($jobs.Count) ok, $($failed.Count) uebersprungen"
$failed | ForEach-Object { Write-Host "  SKIP: $_" }
if ($jobs.Count -eq 0) { throw "Keine Jobs" }

ConvertTo-Json $jobs -Depth 5 | Set-Content "$Root\work\ue_jobs.json" -Encoding utf8

Write-Host "== UE-Import ($($jobs.Count) Meshes) =="
$env:PALMOD_JOBS = "$Root\work\ue_jobs.json"
$scratch = "$env:TEMP\palmod_ue_import.py"
Copy-Item "$Root\scripts\ue_import.py" $scratch -Force
& $UeCmd $Project -stdout -unattended -nopause -nosplash -ExecutePythonScript="$scratch" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "UE-Import fehlgeschlagen (Exit $LASTEXITCODE)" }

Write-Host "== Cook & Pack =="
if ($Install) { & "$Root\scripts\cook_and_pack.ps1" -Cook -Install }
else          { & "$Root\scripts\cook_and_pack.ps1" -Cook }

Write-Host "== Verifiziere Skelette =="
$bad = 0
foreach ($job in $jobs) {
    $meshPath = "Pal/Content" + $job.assetPath.Substring(5)
    $out = dotnet run --project "$Root\src\PalExporter" -c Release --no-build -- `
        --paks $Paks --usmap $Usmap --verify-pak "$Root\build" --mesh $meshPath 2>&1
    $bones = ($out | Select-String "Bones Original=(\d+)\s+Mod=(\d+)").Matches
    $diffs = ($out | Select-String "dT=\d|FEHLT").Count
    $label = [IO.Path]::GetFileName($job.assetPath)
    if ($bones.Count -gt 0 -and $bones[0].Groups[1].Value -eq $bones[0].Groups[2].Value -and $diffs -eq 0) {
        Write-Host ("  OK   {0} ({1} Bones)" -f $label, $bones[0].Groups[1].Value)
    } else {
        Write-Host ("  DIFF {0}: Bones={1} Abweichungen={2}" -f $label, ($bones | ForEach-Object { $_.Groups[2].Value }), $diffs)
        $bad++
    }
}
Write-Host ""
if ($bad -eq 0) { Write-Host "ALLE SKELETTE VERIFIZIERT" } else { Write-Host "$bad Mesh(es) mit Abweichungen!" }
