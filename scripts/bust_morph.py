"""Vergroessert die Brustregion eines aus FModel/CUE4Parse exportierten
Skeletal Mesh (glTF). Bone-verankerte Heuristik, funktioniert ohne
dedizierte Brust-Bones.

Aufruf (Headless):
    blender --background --python scripts/bust_morph.py -- \
        --input export/.../SK_X.glb --output work/X_morphed.fbx \
        --factor 1.6 --render work/X

Vorgehen:
  1. glTF importieren (Mesh + Skelett + Weights bleiben erhalten)
  2. Brustregion ueber Bones eingrenzen:
     - Hoehenband: spine_02.z .. clavicle.z (+ etwas Luft)
     - nur Vertices mit Gewicht auf spine_02/spine_03/clavicle
     - nur Koerper-Vorderseite (Front-Achse automatisch ueber Kiefer-Bones,
       sonst --front-axis)
  3. Pro Seite (links/rechts) ein Falloff-Zentrum aus der Selektion schaetzen,
     Vertices entlang ihrer Normalen mit weichem Falloff verschieben.
     Vertex-Anzahl, Reihenfolge und Weights bleiben unveraendert.
  4. Optional: Vorher/Nachher-Renderings (Front + Seite) als PNG
  5. Export als FBX fuer den UE-Import
"""

import argparse
import math
import sys

import bpy
from mathutils import Vector

# Bones, die das Hoehenband definieren
BAND_LOWER_BONES = ("spine_02", "spine02")
BAND_UPPER_BONES = ("clavicle_l", "clavicle_r", "neck")
# Bones, auf die betroffene Vertices gewichtet sein muessen
CHEST_WEIGHT_BONES = ("spine_02", "spine02", "spine_03", "spine03",
                      "chest", "breast", "bust", "clavicle_l", "clavicle_r")
MIN_WEIGHT = 0.10
# Brustfell u. ae. wird MIT verschoben (liegt als Schale ueber der Brust)
COMPANION_BONE_HINTS = ("fur", "hair")
# Vertices mit nennenswertem Gewicht auf diese Bones bleiben unangetastet
EXCLUDE_BONE_HINTS = ("veil", "wing", "ear", "jaw", "ribbon",
                      "upperarm", "lowerarm", "hand", "finger", "weapon")
EXCLUDE_WEIGHT = 0.30


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="glTF/GLB")
    p.add_argument("--output", required=True, help="Ziel-FBX")
    p.add_argument("--factor", type=float, default=1.5,
                   help="Staerke: 1.0 = unveraendert, 1.5 = deutlich, 2.0 = extrem")
    p.add_argument("--render", default=None,
                   help="Praefix fuer Vorher/Nachher-PNGs (z. B. work/PinkLizard)")
    p.add_argument("--front-axis", choices=["auto", "-y", "+y"], default="auto")
    p.add_argument("--no-export", action="store_true",
                   help="Nur rendern/analysieren, kein FBX schreiben")
    return p.parse_args(argv)


def import_scene(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError("Kein Mesh im Import")
    body = max(meshes, key=lambda o: len(o.data.vertices))
    return body, (arms[0] if arms else None)


def find_bone(armature, names):
    for n in names:
        for b in armature.data.bones:
            if b.name.lower() == n:
                return b
    return None


def detect_front(armature):
    """Front-Achse ueber Kiefer/Kopf-Bones: Kiefer liegt vor dem Kopf."""
    head = find_bone(armature, ("head",))
    jaw = find_bone(armature, ("jaw_02", "jaw_01", "jaw"))
    if head and jaw:
        d = jaw.head_local.y - head.head_local.y
        if abs(d) > 1e-4:
            return -1 if d < 0 else 1
    return -1  # UE-Standard nach glTF-Import


def main():
    args = parse_args()
    body, armature = import_scene(args.input)
    mesh = body.data
    if armature is None:
        raise RuntimeError("Kein Skelett im Import -- falsches Asset?")

    front = detect_front(armature) if args.front_axis == "auto" \
        else (-1 if args.front_axis == "-y" else 1)

    zs = [v.co.z for v in mesh.vertices]
    height = max(zs) - min(zs)

    lower = find_bone(armature, BAND_LOWER_BONES)
    upper = find_bone(armature, BAND_UPPER_BONES)
    if lower is None or upper is None:
        raise RuntimeError(
            "Anker-Bones fehlen. Vorhanden: "
            + ", ".join(b.name for b in armature.data.bones))
    band_lo = lower.head_local.z - 0.02 * height
    band_hi = upper.head_local.z + 0.02 * height
    print(f"Front={'-Y' if front < 0 else '+Y'}  Band z=[{band_lo:.3f}, {band_hi:.3f}]")

    group_ids = {g.index for g in body.vertex_groups
                 if g.name.lower() in CHEST_WEIGHT_BONES}
    companion_ids = {g.index for g in body.vertex_groups
                     if any(h in g.name.lower() for h in COMPANION_BONE_HINTS)}
    exclude_ids = {g.index for g in body.vertex_groups
                   if any(h in g.name.lower() for h in EXCLUDE_BONE_HINTS)}

    def weight_on(v, ids):
        return sum(g.weight for g in v.groups if g.group in ids)

    # Anker: reine Koerper-Brust-Vertices (ohne Fell) -> definieren Zentren
    anchors = [v for v in mesh.vertices
               if band_lo <= v.co.z <= band_hi
               and (v.co.y * front) > 0
               and weight_on(v, exclude_ids) < EXCLUDE_WEIGHT
               and weight_on(v, companion_ids) < 0.5
               and any(g.group in group_ids and g.weight >= MIN_WEIGHT
                       for g in v.groups)]
    if len(anchors) < 20:
        raise RuntimeError(f"Anker-Selektion zu klein ({len(anchors)} Vertices)")
    print(f"Anker: {len(anchors)} von {len(mesh.vertices)} Vertices")

    # Falloff-Zentren pro Seite: Centroid, nach vorn auf den Apex geschoben
    centers = []
    for side_sign in (-1, 1):
        side = [v for v in anchors if (v.co.x or 1e-9) * side_sign > 0]
        if not side:
            continue
        centroid = sum((v.co for v in side), Vector()) / len(side)
        apex_y = max(v.co.y * front for v in side) * front
        centers.append(Vector((centroid.x, apex_y, centroid.z)))
    if not centers:
        raise RuntimeError("Keine Falloff-Zentren bestimmbar")

    radius = max(max((v.co - c).length for c in centers) for v in anchors) * 0.75
    strength = (args.factor - 1.0) * 0.5 * radius

    # Verschoben wird alles im Brust-Einzugsgebiet: Anker + Begleiter (Fell)
    # + raeumlich nahe Vertices, ausser explizit ausgeschlossene.
    reach = radius * 1.25
    candidates = [v for v in mesh.vertices
                  if (v.co.y * front) > -0.05 * height
                  and weight_on(v, exclude_ids) < EXCLUDE_WEIGHT
                  and min((v.co - c).length for c in centers) <= reach]
    print(f"Zentren={[tuple(round(x, 3) for x in c) for c in centers]}  "
          f"Radius={radius:.3f}  Verschiebung max={strength:.3f}  "
          f"Verschoben werden {len(candidates)} Vertices")

    chest_focus = (sum(centers, Vector()) / len(centers), radius * 3.5)

    if args.render:
        render_views(body, front, args.render + "_before", chest_focus)

    # Verschiebung radial von innenliegenden Zentren aus: ergibt eine glatte,
    # kugelfoermige Woelbung statt Spikes entlang der Einzel-Normalen.
    inner = [c + Vector((0, -front * radius * 0.6, 0)) for c in centers]
    for v in candidates:
        i, d = min(((i, (v.co - c).length) for i, c in enumerate(centers)),
                   key=lambda t: t[1])
        fall = max(0.0, 1.0 - (d / radius) ** 2)
        fall = math.sin(fall * math.pi / 2)
        direction = (v.co - inner[i])
        if direction.length < 1e-6:
            continue
        v.co += direction.normalized() * (strength * fall)
    mesh.update()

    if args.render:
        render_views(body, front, args.render + "_after", chest_focus)

    if not args.no_export:
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


def render_views(body, front, prefix, focus=None):
    """Orthografische Front-/Seitenansicht plus Brust-Nahaufnahme als PNG."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1080
    scene.render.image_settings.file_format = "PNG"

    center = sum((body.matrix_world @ Vector(c) for c in body.bound_box),
                 Vector()) / 8
    size = max(body.dimensions) * 1.15

    cam_data = bpy.data.cameras.get("preview_cam") or bpy.data.cameras.new("preview_cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = size
    cam = bpy.data.objects.get("preview_cam_obj")
    if cam is None:
        cam = bpy.data.objects.new("preview_cam_obj", cam_data)
        scene.collection.objects.link(cam)
    scene.camera = cam

    views = [
        ("front", Vector((0, front * size * 3, center.z)), center, size),
        ("side", Vector((size * 3, 0, center.z)), center, size),
    ]
    if focus is not None:
        f_center, f_size = focus
        views.append(("zoom_side", Vector((size * 3, 0, f_center.z)), f_center, f_size))
        views.append(("zoom_front", Vector((0, front * size * 3, f_center.z)), f_center, f_size))

    for name, loc, target, scale in views:
        cam_data.ortho_scale = scale
        cam.location = loc
        direction = Vector(target) - loc
        cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{name}.png"
        bpy.ops.render.render(write_still=True)
        print(f"Render: {scene.render.filepath}")


if __name__ == "__main__":
    main()
