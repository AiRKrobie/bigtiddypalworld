"""Vergroessert die Brustregion eines aus FModel exportierten Skeletal Mesh.

Aufruf (Headless):
    blender --background --python scripts/bust_morph.py -- \
        --input export/mesh.gltf --output work/morphed.fbx --factor 1.6

Vorgehen:
  1. glTF importieren (Mesh + Skelett + Weights bleiben erhalten)
  2. Brustregion selektieren: Vertices, die auf Chest-/Spine-Bones gewichtet
     sind, eingegrenzt auf den vorderen oberen Torso (Heuristik ueber
     Bounding-Box-Koordinaten relativ zur Chest-Bone-Position)
  3. Verschiebung entlang der Vertex-Normalen mit weichem radialem Falloff
     um zwei Zentren (links/rechts) — Vertex-Anzahl und Weights unveraendert
  4. Export als FBX fuer den UE-Import

Der Selektions-Bereich muss ggf. je nach Mesh nachjustiert werden --
dafuer die REGION_*-Konstanten unten anpassen und mit --preview pruefen
(speichert eine .blend-Datei mit der Selektion als Vertex Group statt zu
exportieren).
"""

import argparse
import math
import sys

import bpy
from mathutils import Vector

# --- Heuristik-Parameter (relativ zur Gesamthoehe des Meshes, Z aufwaerts) ---
# Hoehenband des Torsos, in dem die Brustregion liegt
REGION_Z_MIN_FRAC = 0.60
REGION_Z_MAX_FRAC = 0.78
# Nur Vertices auf der Koerper-Vorderseite (negatives Y in Blender bei
# UE-Import ist "vorne" -- Vorzeichen ggf. drehen, siehe --front-axis)
FRONT_SIGN = -1
# Bones, auf die betroffene Vertices (auch) gewichtet sein muessen
CHEST_BONE_HINTS = ("spine_02", "spine02", "chest", "breast", "bust", "spine_03")
# Mindest-Weight auf einen der Chest-Bones
MIN_WEIGHT = 0.15


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="glTF/GLB aus FModel")
    p.add_argument("--output", required=True, help="Ziel-FBX")
    p.add_argument("--factor", type=float, default=1.5,
                   help="Staerke: 1.0 = unveraendert, 1.5 = deutlich, 2.0 = extrem")
    p.add_argument("--preview", action="store_true",
                   help="Statt Export: .blend mit Selektion speichern")
    p.add_argument("--front-axis", choices=["-y", "+y"], default="-y",
                   help="Welche Y-Richtung 'vorne' ist (Import-abhaengig)")
    return p.parse_args(argv)


def import_mesh(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lower = path.lower()
    if lower.endswith((".gltf", ".glb")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif lower.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise ValueError(f"Nicht unterstuetztes Format: {path}")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("Kein Mesh im Import gefunden")
    # Groesstes Mesh = Koerper (Datei kann auch Augen/Wimpern etc. enthalten)
    return max(meshes, key=lambda o: len(o.data.vertices))


def chest_vertex_indices(obj):
    """Indizes aller Vertices mit Weight auf einen Chest-Bone."""
    group_ids = {
        g.index for g in obj.vertex_groups
        if any(h in g.name.lower() for h in CHEST_BONE_HINTS)
    }
    if not group_ids:
        print("WARNUNG: Keine Chest-Bones gefunden, nutze nur Raum-Heuristik.")
        print("Vorhandene Gruppen:", [g.name for g in obj.vertex_groups])
        return None
    result = set()
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group in group_ids and g.weight >= MIN_WEIGHT:
                result.add(v.index)
                break
    return result


def main():
    args = parse_args()
    front = -1 if args.front_axis == "-y" else 1
    obj = import_mesh(args.input)
    mesh = obj.data

    zs = [v.co.z for v in mesh.vertices]
    z_min, z_max = min(zs), max(zs)
    height = z_max - z_min
    band_lo = z_min + REGION_Z_MIN_FRAC * height
    band_hi = z_min + REGION_Z_MAX_FRAC * height

    weighted = chest_vertex_indices(obj)

    # Kandidaten: im Hoehenband, auf der Vorderseite, (optional) Chest-Weight
    candidates = [
        v for v in mesh.vertices
        if band_lo <= v.co.z <= band_hi
        and (v.co.y * front) > 0
        and (weighted is None or v.index in weighted)
    ]
    if not candidates:
        raise RuntimeError("Selektion leer -- REGION_*-Parameter anpassen")
    print(f"{len(candidates)} von {len(mesh.vertices)} Vertices selektiert")

    # Zwei Falloff-Zentren (links/rechts) aus den vordersten Punkten schaetzen
    left = [v for v in candidates if v.co.x < 0]
    right = [v for v in candidates if v.co.x >= 0]
    centers = []
    for side in (left, right):
        if side:
            tip = max(side, key=lambda v: v.co.y * front)
            centers.append(Vector(tip.co))
    radius = 0.6 * (band_hi - band_lo)

    strength = args.factor - 1.0
    for v in candidates:
        d = min((v.co - c).length for c in centers)
        fall = max(0.0, 1.0 - (d / radius) ** 2)  # weicher quadratischer Falloff
        fall = math.sin(fall * math.pi / 2)        # noch weicher am Rand
        v.co += v.normal * (strength * radius * fall)

    mesh.update()

    if args.preview:
        vg = obj.vertex_groups.new(name="MORPH_SELECTION")
        vg.add([v.index for v in candidates], 1.0, "REPLACE")
        blend_path = args.output.rsplit(".", 1)[0] + "_preview.blend"
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print(f"Preview gespeichert: {blend_path}")
        return

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(
        filepath=args.output,
        use_selection=True,
        add_leaf_bones=False,
        mesh_smooth_type="FACE",
        use_armature_deform_only=True,
        bake_anim=False,
    )
    print(f"Exportiert: {args.output}")


if __name__ == "__main__":
    main()
