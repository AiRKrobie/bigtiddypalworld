# Installationsanleitung

Von einer unveränderten Palworld-Installation (Steam) zum fertigen Mod.
Dauer: ca. 2 Minuten. **Seit v2.0.0 wird kein UE4SS und kein Slider mehr
benötigt** — die Form ist fest ins Mesh gebacken.

## Installation

1. Lade `zzz_BustMod_P.pak` aus den [Releases](../../releases) herunter.
2. Öffne deinen Palworld-Ordner. Bei Steam:
   Rechtsklick auf Palworld → *Verwalten* → *Lokale Dateien durchsuchen*.
3. Navigiere zu `Pal\Content\Paks\`.
4. Lege dort einen Ordner **`~mods`** an, falls er nicht existiert
   (die Tilde `~` gehört zum Namen).
5. Kopiere die `zzz_BustMod_P.pak` in den `~mods`-Ordner.
6. Palworld starten. Fertig.

> **Wichtig:** Das Spiel lädt Paks nur beim Start. Nach dem Kopieren also
> neu starten. Auf Servern sehen nur **du** die Änderung (clientseitig).

## Deinstallation

`zzz_BustMod_P.pak` aus `~mods` löschen. Fertig — alles ist wieder original.

## Hinweis zum früheren Slider

Bis v1.5.0 steckte die Vergrößerung als *Morph Target* im Mesh und wurde von
einem UE4SS-Lua-Mod (F6/F7) gesteuert. Das hat sich als fehleranfällig
erwiesen: Je nach Slider-Zustand waren die Brüste überzogen verzerrt oder gar
nicht sichtbar. Seit v2.0.0 ist die Form **fest gebacken** und damit immer
korrekt. Falls du noch den alten `BustSliderMod` installiert hast, kannst du
ihn entfernen (Ordner löschen und Zeile aus `ue4ss\Mods\mods.txt` streichen) —
er tut nichts mehr.

Die Größe lässt sich weiterhin **beim Selbstbauen** pro Pal einstellen, siehe
`data/pal_overrides.json` und den Abschnitt „Selbst bauen" in der
[README](README.md).

## Problembehandlung

- **Pals sehen unverändert aus:** Liegt die Pak wirklich in
  `Pal\Content\Paks\~mods\`? Spiel neu gestartet?
- **Nach einem Palworld-Update kaputt:** Größere Updates können Meshes oder
  das Skelett ändern — dann muss das Pak neu gebaut werden (siehe README,
  Abschnitt „Selbst bauen"). Das ist eine bekannte Stolperfalle bei
  Mesh-Mods.
