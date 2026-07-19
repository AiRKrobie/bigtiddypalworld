# Recherche: Wie man Pals wirklich gute Brüste gibt

Zusammenfassung dreier paralleler Recherche-Durchläufe (2026-07-19), warum
der prozedurale Ansatz scheitert und was stattdessen funktioniert.

## Kernbefund

Die aktive Palworld-Body-Mod-Szene löst das Problem **nicht prozedural**,
sondern durch **manuelles Sculpten in Blender** + **eingebackene Schatten in
der Textur**. Das ist der Grund, warum deren Ergebnisse gut aussehen und
generierte Kugeln nicht.

## Was funktioniert (3 Bausteine)

1. **Silhouette = echte Geometrie.** Brust aus dem Torso *herausziehen*
   (Proportional Edit, durchgehende Topologie), nicht als separate Kugel
   aufsetzen. Entfernt Naht und „Ball"-Look.
2. **Definition = AO/Schatten im Albedo.** Unter Palworlds flachem Licht ist
   eine Normalmap fast wirkungslos (kann Silhouette nicht ändern, wirft keine
   echten Schatten). Was *immer* liest: Ambient Occlusion / Cavity direkt in
   die Base-Color-Textur multipliziert — Cleavage-V und Unterbrust-Falte dunkel
   „einmalen".
3. **Falten = Geometrie-Creases.** Unterbrust-Knick (mit stützender Edge-Loop)
   + Cleavage-Tal. Die zwei Signale, die das Auge als „Brust" erkennt.

Blender-Techniken: Proportional Edit (Grobform) → Multires + Sculpt
(Crease/Tropfen) → Shade Smooth/Auto Smooth + Mark Sharp nur an Falten →
AO/Normal von High→Low backen (Cycles, Selected-to-Active, Grün-Kanal -Y für
UE, MikkTSpace).

## Assets / Lizenz

- Fremde Mods liefern **keine** Quell-Meshes (nur gepackte `.pak`), Lizenzen
  fehlen/unklar → nicht sauber wiederverwendbar.
- Saubere CC0-Grundform: **MakeHuman** (parametrische Brustgröße, FBX/OBJ,
  CC0-Export). Ergänzend: Genshin-Style Anime-Basemesh (CC BY, „bust"-Shape-Keys).

## Bekannte Beispiel-Mods (Technik-Referenz)

- Gowly's THICC Lovander — nexusmods.com/palworld/mods/913 (Mesh-Swap)
- Blehbreh Redesigned Body + Exposed Armor (Jiggle via Physics-Asset) — mods/499
- Altermatic Runtime Replacer (Laufzeit-Swap-Framework) — mods/1626
- Guides: github.com/AidenM6901/PalworldModdingGuide ·
  unofficial-modding-guide.com/posts/skeletalmeshmodding/

## Ehrliche Konsequenz

Der polierte Anime-Look ist **manuelle 3D-Handarbeit** (Sculpt + Texture-Paint
pro Pal), nicht vollautomatisierbar. Automatisierbare Bausteine, die die
Pipeline unterstützen können: Textur-Export (CUE4Parse), AO-Komposit ins
Albedo, MakeHuman-Import. Die künstlerische Formgebung selbst bleibt manuell.
