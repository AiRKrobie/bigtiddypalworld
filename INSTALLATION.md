# Installationsanleitung

Diese Anleitung führt von einer unveränderten Palworld-Installation (Steam)
zum fertigen Mod mit Größen-Slider. Dauer: ca. 10 Minuten.

## Teil 1: Das Mesh-Pak (Pflicht)

Das Pak enthält die veränderten Körper-Meshes. Ohne den Slider-Teil (unten)
sind die Pals dauerhaft auf Referenzgröße — **mit** Slider steuerst du die
Größe im Spiel.

1. Lade `zzz_BustMod_P.pak` aus den [Releases](../../releases) herunter.
2. Öffne deinen Palworld-Ordner. Bei Steam:
   Rechtsklick auf Palworld → *Verwalten* → *Lokale Dateien durchsuchen*.
3. Navigiere zu `Pal\Content\Paks\`.
4. Lege dort einen Ordner **`~mods`** an, falls er nicht existiert
   (die Tilde `~` gehört zum Namen).
5. Kopiere die `zzz_BustMod_P.pak` in den `~mods`-Ordner.
6. Palworld starten. Fertig — die Pals aus der Liste haben jetzt die neue Form.

> **Wichtig:** Das Spiel lädt Paks nur beim Start. Nach dem Kopieren also
> neu starten. Auf Servern sehen nur **du** die Änderung (clientseitig).

## Teil 2: UE4SS + Slider (empfohlen)

### UE4SS installieren (falls noch nicht vorhanden)

1. Lade die neueste UE4SS-Version von
   [docs.ue4ss.com](https://docs.ue4ss.com/) herunter
   (Datei `UE4SS_v…zip` bzw. `zDEV-UE4SS…zip`).
2. Entpacke den Inhalt nach `Palworld\Pal\Binaries\Win64\`
   (dort liegt die `Palworld-Win64-Shipping.exe`).
   Danach sollte es u. a. `Win64\ue4ss\` und eine `dwmapi.dll` geben.

### BustSliderMod installieren

1. Lade `BustSliderMod.zip` aus den [Releases](../../releases) und entpacke
   den Ordner `BustSliderMod` nach
   `Palworld\Pal\Binaries\Win64\ue4ss\Mods\`.
   Struktur danach: `…\ue4ss\Mods\BustSliderMod\Scripts\main.lua`
2. Öffne `…\ue4ss\Mods\mods.txt` mit einem Texteditor und ergänze
   **oberhalb** des Keybinds-Blocks die Zeile:

   ```
   BustSliderMod : 1
   ```

3. Spiel starten.

### Bedienung

| Taste | Wirkung |
|---|---|
| **F7** | größer (+0.1) |
| **F6** | kleiner (−0.1) |
| **F8** | aktuellen Wert ins UE4SS-Log schreiben |

- Bereich: **0.0** (Original-Optik) bis **1.5** (über Referenzgröße hinaus)
- Der Wert wird in `ue4ss\Mods\BustSliderMod\bust_value.txt` gespeichert und
  überlebt Neustarts. Er wirkt automatisch auch auf frisch gespawnte Pals
  (mit wenigen Sekunden Verzögerung).
- Standardwert beim ersten Start: **1.0**

## Deinstallation

| Was | Wie |
|---|---|
| Nur Mod-Optik aus | Im Spiel F6 bis 0.0 drücken |
| Mesh-Pak entfernen | `~mods\zzz_BustMod_P.pak` löschen |
| Slider entfernen | `BustSliderMod`-Ordner löschen, Zeile aus `mods.txt` entfernen |
| UE4SS komplett entfernen | `ue4ss`-Ordner und `dwmapi.dll` aus `Win64\` löschen |

## Problembehandlung

- **Pals sehen unverändert aus:** Liegt die Pak wirklich in
  `Pal\Content\Paks\~mods\`? Spiel neu gestartet? Slider-Wert evtl. auf 0?
- **Slider reagiert nicht:** Steht `BustSliderMod : 1` in der `mods.txt`?
  Liegt `main.lua` unter `BustSliderMod\Scripts\`? UE4SS überhaupt aktiv
  (beim Start erscheint kurz ein Konsolenfenster bzw. `UE4SS.log` wird
  aktualisiert)?
- **Nach einem Palworld-Update kaputt:** Größere Updates können die
  Mesh-Formate ändern — dann muss das Pak neu gebaut werden
  (siehe README, Abschnitt „Selbst bauen").
