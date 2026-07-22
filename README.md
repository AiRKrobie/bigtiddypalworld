# Big Tiddy Palworld

Body-Mod für 20+ weibliche Pals in **Palworld** — mit stufenlosem
**Größen-Slider im Spiel** (F6/F7). Clientseitig, jederzeit rückstandslos
deinstallierbar.

*Body mod for 20+ female Pals in Palworld with an in-game size slider —
[English quick install below](#english-quick-install).*

![Lovander Vorher/Nachher](docs/img/gallery/SK_PinkLizard.png)

> Vorher/Nachher aller Modelle in der **[Galerie](#galerie--vorhernachher)** weiter unten.

## Features

- **28 Meshes / 22 Pal-Arten** inkl. Varianten: Bellanoir (+Libero), Bristla,
  Carnibora, Dazzi (+Noct), Elizabee, Flaracle, Flopie, Gloopie (+Primo),
  Icelyn, Katress (+Ignis), Lapure, Lovander, Lullu, Lunaris, Lyleen (+Noct),
  Nitemary (+Botan), Nyafia, Petallia (+Ignis), Prunelia, Sekhmet, Selyne,
  Splatterina
- **Eigens generierte Geometrie**: Echte, runde Brüste werden als neue
  Geometrie erzeugt und ins Mesh integriert (mit übernommenen
  Skinning-Gewichten, UVs und Material) — statt den vorhandenen Brustkorb
  nur zu verformen
- **Fest ins Mesh gebacken** (seit v2.0.0): keine Morph-Targets, kein Slider
  mehr nötig. Die Form ist immer sichtbar und kann nicht mehr durch einen
  falschen Slider-Zustand verzerrt oder unsichtbar werden — das war zuvor
  die häufigste Fehlerquelle. Größe pro Pal über
  [`data/pal_overrides.json`](data/pal_overrides.json) beim Selbstbauen
- **Original-Animationen, -Texturen und -Materialien** bleiben vollständig
  erhalten (Referenz-Skelett wird beim Bauen bit-genau gegen das Original
  verifiziert)
- Rein clientseitig — andere Spieler auf Servern sehen nichts davon

**Nicht enthalten:** Jelliette — der Quallen-Körperbau verträgt den
Morph (noch) nicht.

## Installation (Deutsch)

Siehe **[INSTALLATION.md](INSTALLATION.md)** für die ausführliche Anleitung
mit UE4SS-Einrichtung. Kurzfassung:

1. `zzz_BustMod_P.pak` (aus den [Releases](../../releases)) nach
   `Palworld\Pal\Content\Paks\~mods\` kopieren (Ordner ggf. anlegen)
2. Spiel starten — fertig. **Kein UE4SS und kein Slider nötig.**

Deinstallation: die `.pak` aus `~mods` löschen, fertig.

## Galerie – Vorher/Nachher

Alle enthaltenen Modelle bei Slider-Wert 1.0. Graustufen-Renders aus der Build-Pipeline (Blender Workbench).

<details>
<summary><b>Alle 28 Modelle anzeigen</b></summary>

**Bellanoir**

![Bellanoir](docs/img/gallery/SK_NightLady.png)

**Bristla**

![Bristla](docs/img/gallery/SK_LittleBriarRose.png)

**Carnibora**

![Carnibora](docs/img/gallery/SK_VenusFlytrap.png)

**Dazzi**

![Dazzi](docs/img/gallery/SK_RaijinDaughter.png)

**Dazzi Noct**

![Dazzi Noct](docs/img/gallery/SK_RaijinDaughter_Water.png)

**Elizabee**

![Elizabee](docs/img/gallery/SK_QueenBee.png)

**Flaracle**

![Flaracle](docs/img/gallery/SK_FoxExorcist.png)

**Flopie**

![Flopie](docs/img/gallery/SK_FlowerRabbit.png)

**Gloopie**

![Gloopie](docs/img/gallery/SK_OctopusGirl.png)

**Gloopie Primo**

![Gloopie Primo](docs/img/gallery/SK_OctopusGirl_Neutral.png)

**Icelyn**

![Icelyn](docs/img/gallery/SK_IceWitch.png)

**Katress**

![Katress](docs/img/gallery/SK_CatMage.png)

**Katress Ignis**

![Katress Ignis](docs/img/gallery/SK_CatMage_Fire.png)

**Lapure**

![Lapure](docs/img/gallery/SK_SleeveRabbit.png)

**Lovander**

![Lovander](docs/img/gallery/SK_PinkLizard.png)

**Lullu**

![Lullu](docs/img/gallery/SK_LeafPrincess.png)

**Lunaris**

![Lunaris](docs/img/gallery/SK_Mutant.png)

**Lyleen**

![Lyleen](docs/img/gallery/SK_LilyQueen.png)

**Lyleen (Ice)**

![Lyleen Ice](docs/img/gallery/SK_LilyQueen_Ice.png)

**Nitemary**

![Nitemary](docs/img/gallery/SK_GhostRabbit.png)

**Nitemary Botan**

![Nitemary Botan](docs/img/gallery/SK_GhostRabbit_Grass.png)

**Nyafia**

![Nyafia](docs/img/gallery/SK_BadCatgirl.png)

**Petallia**

![Petallia](docs/img/gallery/SK_FlowerDoll.png)

**Petallia Ignis**

![Petallia Ignis](docs/img/gallery/SK_FlowerDoll_Fire.png)

**Prunelia**

![Prunelia](docs/img/gallery/SK_BlueberryFairy.png)

**Sekhmet**

![Sekhmet](docs/img/gallery/SK_Sekhmet.png)

**Selyne**

![Selyne](docs/img/gallery/SK_MoonQueen.png)

**Splatterina**

![Splatterina](docs/img/gallery/SK_GrimGirl.png)

</details>

## Selbst bauen (Pipeline)

Das Repo enthält die komplette, automatisierte Build-Pipeline — es werden
**keine Spiel-Assets** mitgeliefert, alles wird lokal aus der eigenen
Palworld-Installation extrahiert:

```
PalExporter (CUE4Parse)      Blender 5.x headless           UE 5.1 headless
.psk + manifest.json    ->   bust_morph.py                ->  ue_import.py     -> cook_and_pack.ps1
(UE-Koordinaten, cm)         (Morph als Shape Key             (Import an           (Pak bauen,
                              "BustSize", QA-Renders)          Original-Pfade)      verifizieren,
                                                                                    installieren)
```

Voraussetzungen: Palworld (Steam), [Blender 5.x](https://www.blender.org/)
mit [io_scene_psk_psa](https://github.com/DarklightGames/io_scene_psk_psa),
[Unreal Engine 5.1](https://www.unrealengine.com/), .NET-10-SDK, eine zur
Spielversion passende `Mappings.usmap`
(z. B. aus [PalworldModding/UsefulFiles](https://github.com/PalworldModding/UsefulFiles)).

```powershell
# 1. Meshes + Metadaten aus dem Spiel exportieren
dotnet run --project src/PalExporter -c Release -- `
    --paks "<Palworld>\Pal\Content\Paks" --usmap tools\mappings\Palworld.usmap `
    --targets data\target_pals.txt --out export

# 2. Alles morphen, importieren, cooken, packen, verifizieren, installieren
.\scripts\run_batch.ps1 -Factor 2.5 -Install
```

Pfade (Engine, Spiel, Blender) stehen am Kopf von `scripts/cook_and_pack.ps1`
und `scripts/run_batch.ps1`.

## Technische Details

- Der Export läuft über **ActorX (.psk)** statt glTF — glTF spiegelt das
  Koordinatensystem und invertiert damit alle Bone-Rotationen (kaputte
  Animationen). Die Lektion steht ausführlich in der Git-Historie.
- Ins Pak kommen **nur die SkeletalMesh-Assets**; Skeleton, Materialien und
  PhysicsAsset bleiben Platzhalter und lösen zur Laufzeit auf die Originale
  des Spiels auf.
- `PalExporter --verify-pak` vergleicht nach jedem Build das Referenz-Skelett
  jedes Meshes Knochen für Knochen (Namen, Hierarchie, Transforms) mit dem
  Original — erst bei null Abweichungen wird installiert.

## English Quick Install

1. Download `zzz_BustMod_P.pak` from [Releases](../../releases) and drop it
   into `Palworld\Pal\Content\Paks\~mods\` (create the folder if needed).
2. Start the game — done. **No UE4SS, no slider needed** (the shape is baked
   into the mesh since v2.0.0). Uninstall = delete the pak. Client-side only.

## Disclaimer

Dieses Repo enthält keine Assets von Pocketpair. Nutzung auf eigene Gefahr;
nicht für den Einsatz auf Servern gedacht, deren Regeln Mods untersagen.
