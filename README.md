# Palworld Body-Mod Pipeline

Pipeline zum Erstellen eines Körper-Mods (vergrößerte Oberweite) für den
weiblichen Spielercharakter in Palworld.

## Rahmenbedingungen

- **Spiel:** Palworld (Steam), `M:\SteamLibrary\steamapps\common\Palworld`
- **Engine:** Unreal Engine **5.1** (im Spiel-Binary verifiziert: `+UE5+Release-5.1`)
- **Pak-Format:** klassisches `.pak` (`Pal-Windows.pak`, ~38 GB), kein IoStore
- **Mod-Typ:** clientseitiger Pak-Mod in `Pal/Content/Paks/~mods` — überschreibt
  Original-Assets, ohne Spieldateien anzufassen. Andere Spieler sehen die
  Änderung nicht.

## Pipeline-Übersicht

```
FModel                Blender                    UE 5.1              UnrealPak
  │                      │                          │                    │
  │ Mesh als glTF        │ scripts/                 │ Import als         │ Cooked Assets
  │ exportieren     ───► │ bust_morph.py       ───► │ Skeletal Mesh, ───►│ als .pak
  │ (+ Skelett,          │ (Vertices morphen,       │ Original-Pfade,    │ packen,
  │  Weights)            │  FBX exportieren)        │ cooken             │ nach ~mods
```

## Schritte im Detail

### 1. Assets extrahieren (FModel)

1. `tools/FModel/FModel.exe` starten
2. Game Directory: `M:\SteamLibrary\steamapps\common\Palworld\Pal\Content\Paks`
3. UE-Version: `GAME_UE5_1`
4. **Mappings:** Palworld nutzt unversionierte Properties — FModel braucht eine
   `.usmap`-Datei (liegt nach Setup unter `tools/mappings/`).
5. Zum weiblichen Player-Mesh navigieren (unter
   `Pal/Content/Pal/Model/Character/Player/`), als **glTF** exportieren
   (Settings → Models → Gltf2, "Export Materials" an).
6. Export nach `export/` legen.

### 2. Mesh morphen (Blender)

```
blender --background --python scripts/bust_morph.py -- ^
    --input export/<mesh>.gltf --output work/morphed.fbx --factor 1.6
```

Das Skript selektiert die Brustregion (über Bone-Weights + räumliche
Eingrenzung), verschiebt die Vertices entlang ihrer Normalen mit weichem
Falloff und exportiert als FBX. Skelett, Vertex-Anzahl und Weights bleiben
unverändert. `--factor` steuert die Stärke (1.0 = unverändert).

### 3. In UE 5.1 cooken

1. Leeres UE-5.1-Projekt `ue_project/` (Blank, ohne Starter Content)
2. FBX als Skeletal Mesh importieren — **exakt derselbe Content-Pfad** wie im
   Original (z. B. `/Game/Pal/Model/Character/Player/...`)
3. Material-Slots benennen wie im Original (Slot-Namen aus FModel ablesen)
4. Cooken: siehe `scripts/cook_and_pack.ps1`

### 4. Packen & installieren

`scripts/cook_and_pack.ps1` ruft UnrealPak aus der UE-Installation auf,
verpackt die gecookten Assets als `zzz_BustMod_P.pak` und kopiert sie nach
`Pal/Content/Paks/~mods/`. Suffix `_P` ist Pflicht (Patch-Pak, überschreibt
Originale). **Palworld muss dafür geschlossen sein** — Paks werden nur beim
Spielstart geladen.

## Deinstallation

`zzz_BustMod_P.pak` aus `~mods` löschen. Fertig.
