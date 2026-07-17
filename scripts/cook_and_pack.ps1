# Cooked Assets aus dem UE-Projekt als Patch-Pak packen und installieren.
#
# Voraussetzung: Das UE-5.1-Projekt wurde im Editor gecookt
# (oder per RunUAT, siehe -Cook-Schalter unten).
#
# Aufruf:  .\scripts\cook_and_pack.ps1 [-Cook] [-Install]

param(
    [switch]$Cook,     # Vorher per RunUAT cooken (headless, ohne Editor)
    [switch]$Install   # Fertiges Pak nach ~mods kopieren
)

$ErrorActionPreference = "Stop"

# --- Pfade (bei Bedarf anpassen) ---
$UeRoot      = "C:\Program Files\Epic Games\UE_5.1"
$Project     = "$PSScriptRoot\..\ue_project\PalMod\PalMod.uproject"
$CookedDir   = "$PSScriptRoot\..\ue_project\PalMod\Saved\Cooked\Windows\PalMod\Content"
$BuildDir    = "$PSScriptRoot\..\build"
$PakName     = "zzz_BustMod_P.pak"
$ModsDir     = "M:\SteamLibrary\steamapps\common\Palworld\Pal\Content\Paks\~mods"

$UnrealPak   = "$UeRoot\Engine\Binaries\Win64\UnrealPak.exe"
$RunUAT      = "$UeRoot\Engine\Build\BatchFiles\RunUAT.bat"

if ($Cook) {
    Write-Host "== Cooke Projekt (headless) =="
    & $RunUAT BuildCookRun -project="$Project" -platform=Win64 `
        -cook -skipstage -nocompileeditor -nop4 -utf8output
    if ($LASTEXITCODE -ne 0) { throw "Cook fehlgeschlagen (Exit $LASTEXITCODE)" }
}

if (-not (Test-Path $CookedDir)) {
    throw "Kein Cooked-Output unter $CookedDir -- erst cooken (Editor oder -Cook)"
}

Write-Host "== Baue Pak-Dateiliste =="
New-Item -ItemType Directory -Force $BuildDir | Out-Null
$ResponseFile = "$BuildDir\filelist.txt"

# Cooked-Assets auf die Original-Mount-Pfade des Spiels mappen:
#   <Cooked>/Pal/Content/...  ->  ../../../Pal/Content/...
$lines = Get-ChildItem $CookedDir -Recurse -File |
    Where-Object { $_.Extension -in ".uasset", ".uexp", ".ubulk" } |
    ForEach-Object {
        $rel = $_.FullName.Substring((Resolve-Path $CookedDir).Path.Length).TrimStart("\")
        "`"$($_.FullName)`" `"../../../Pal/Content/$($rel -replace '\\','/')`""
    }
if (-not $lines) { throw "Keine Assets im Cooked-Output gefunden" }
$lines | Set-Content $ResponseFile -Encoding utf8
Write-Host ("{0} Dateien in der Liste" -f $lines.Count)

Write-Host "== Packe $PakName =="
& $UnrealPak "$BuildDir\$PakName" -create="$ResponseFile" -compress
if ($LASTEXITCODE -ne 0) { throw "UnrealPak fehlgeschlagen (Exit $LASTEXITCODE)" }

if ($Install) {
    if (Get-Process -Name "Palworld-Win64-Shipping" -ErrorAction SilentlyContinue) {
        throw "Palworld laeuft noch -- bitte erst beenden, Paks laden nur beim Start."
    }
    New-Item -ItemType Directory -Force $ModsDir | Out-Null
    Copy-Item "$BuildDir\$PakName" $ModsDir -Force
    Write-Host "Installiert: $ModsDir\$PakName"
} else {
    Write-Host "Fertig: $BuildDir\$PakName (Installation mit -Install)"
}
