"""Vergroessert die Brustregion eines Pal-Skeletal-Mesh (ActorX .psk).

Pipeline: CUE4Parse exportiert .psk (UE-Koordinaten, cm, keine Spiegelung),
dieses Skript morpht und exportiert FBX fuer den UE-Reimport.

Aufruf (Headless):
    blender --background --python scripts/bust_morph.py -- \
        --input export/.../SK_X.psk --output work/X_morphed.fbx \
        --factor 2.5 --render work/X

Formmodell: zwei getrennte Lobes (links/rechts symmetrisch) mit
Dekolleté-Daempfung an der Mittellinie, radiale Verschiebung von
innenliegenden, leicht abgesenkten Zentren plus Vorwaerts-Projektion.
Region wird bone-verankert bestimmt (spine_02..clavicle, Weights),
Front-Achse automatisch ueber Kiefer-Bones erkannt.
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

PSK_ADDON_ZIP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "tools", "io_scene_psk_psa.zip")

# Bones, die das Hoehenband definieren
BAND_LOWER_BONES = ("spine_02", "spine02")
BAND_UPPER_BONES = ("clavicle_l", "clavicle_r", "neck",
                    "shoulder_l", "shoulder_r", "head")
# Bones, auf die Anker-Vertices gewichtet sein muessen
CHEST_WEIGHT_BONES = ("spine_02", "spine02", "spine_03", "spine03",
                      "chest", "breast", "bust", "clavicle_l", "clavicle_r",
                      "shoulder_l", "shoulder_r")
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
    p.add_argument("--input", required=True, help=".psk aus CUE4Parse")
    p.add_argument("--output", required=True, help="Ziel-FBX")
    p.add_argument("--factor", type=float, default=1.5,
                   help="Staerke: 1.0 = unveraendert, 1.5 = deutlich, 2.0+ = extrem")
    p.add_argument("--cleavage", type=float, default=0.65,
                   help="Trennung der Lobes an der Mittellinie (0=keine, 1=maximal)")
    p.add_argument("--render", default=None,
                   help="Praefix fuer Vorher/Nachher-PNGs")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--bone-axis-primary", default="Y")
    p.add_argument("--bone-axis-secondary", default="X")
    p.add_argument("--shapekey", action="store_true",
                   help="Morph als Shape Key 'BustSize' statt ins Basis-Mesh "
                        "backen (fuer Laufzeit-Slider via Morph Target)")
    return p.parse_args(argv)


def ensure_psk_addon():
    """Aktiviert die vorinstallierte psk-Extension (siehe tools/, per
    `blender --command extension install-file` eingerichtet)."""
    import addon_utils
    for name in ("bl_ext.user_default.io_scene_psk_psa",):
        try:
            addon_utils.enable(name, default_set=False)
            return
        except Exception as ex:
            print(f"Enable {name} fehlgeschlagen: {ex}")
    for mod in addon_utils.modules(refresh=True):
        if "psk" in mod.__name__.lower():
            addon_utils.enable(mod.__name__, default_set=False)
            return
    raise RuntimeError("psk-Addon konnte nicht aktiviert werden")


def import_psk(path):
    ensure_psk_addon()
    for op_path in ("psk.import_file", "import_scene.psk"):
        ns, name = op_path.split(".")
        group = getattr(bpy.ops, ns, None)
        op = getattr(group, name, None) if group else None
        if op is not None:
            try:
                op(filepath=path)
                break
            except AttributeError:
                continue
    else:
        raise RuntimeError("Kein psk-Import-Operator gefunden")
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    if not meshes or not arms:
        raise RuntimeError("psk-Import lieferte kein Mesh/Skelett")
    return max(meshes, key=lambda o: len(o.data.vertices)), arms[0]


def find_bone(armature, names):
    for n in names:
        for b in armature.data.bones:
            if b.name.lower() == n:
                return b
    return None


def detect_front(armature):
    """Front-Vektor ueber Kiefer/Kopf-Bones (Kiefer liegt vor dem Kopf).

    Gibt einen Einheitsvektor in der XY-Ebene zurueck (+/-X oder +/-Y).
    """
    head = find_bone(armature, ("head",))
    jaw = find_bone(armature, ("jaw_02", "jaw_01", "jaw"))
    if head and jaw:
        d = jaw.head_local - head.head_local
        d.z = 0.0
        if d.length > 1e-4:
            if abs(d.x) >= abs(d.y):
                return Vector((math.copysign(1.0, d.x), 0.0, 0.0))
            return Vector((0.0, math.copysign(1.0, d.y), 0.0))
    return Vector((0.0, -1.0, 0.0))


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body, armature = import_psk(args.input)
    mesh = body.data

    front = detect_front(armature)
    side = front.cross(Vector((0.0, 0.0, 1.0)))
    print(f"Front={tuple(front)}  Seite={tuple(side)}")

    zs = [v.co.z for v in mesh.vertices]
    height = max(zs) - min(zs)
    print(f"Mesh-Hoehe: {height:.1f} Einheiten, {len(mesh.vertices)} Vertices")

    lower = find_bone(armature, BAND_LOWER_BONES)
    upper = find_bone(armature, BAND_UPPER_BONES)
    if lower is None or upper is None:
        raise RuntimeError("Anker-Bones fehlen. Vorhanden: "
                           + ", ".join(b.name for b in armature.data.bones))
    band_lo = lower.head_local.z - 0.02 * height
    band_hi = upper.head_local.z + 0.02 * height
    print(f"Band z=[{band_lo:.2f}, {band_hi:.2f}]")

    group_ids = {g.index for g in body.vertex_groups
                 if g.name.lower() in CHEST_WEIGHT_BONES}
    companion_ids = {g.index for g in body.vertex_groups
                     if any(h in g.name.lower() for h in COMPANION_BONE_HINTS)}
    exclude_ids = {g.index for g in body.vertex_groups
                   if any(h in g.name.lower() for h in EXCLUDE_BONE_HINTS)}

    def weight_on(v, ids):
        return sum(g.weight for g in v.groups if g.group in ids)

    anchors = [v for v in mesh.vertices
               if band_lo <= v.co.z <= band_hi
               and v.co.dot(front) > 0
               and weight_on(v, exclude_ids) < EXCLUDE_WEIGHT
               and weight_on(v, companion_ids) < 0.5
               and any(g.group in group_ids and g.weight >= MIN_WEIGHT
                       for g in v.groups)]
    if len(anchors) < 20:
        raise RuntimeError(f"Anker-Selektion zu klein ({len(anchors)} Vertices)")
    print(f"Anker: {len(anchors)} von {len(mesh.vertices)} Vertices")

    # Zentren pro Seite: Centroid, auf den Front-Apex geschoben, symmetrisiert
    raw = []
    for sgn in (-1, 1):
        pts = [v.co for v in anchors if (v.co.dot(side) or 1e-9) * sgn > 0]
        if not pts:
            continue
        centroid = sum(pts, Vector()) / len(pts)
        apex = max(p.dot(front) for p in pts)
        raw.append(centroid + front * (apex - centroid.dot(front)))
    if not raw:
        raise RuntimeError("Keine Falloff-Zentren bestimmbar")
    if len(raw) == 2:
        cs = sum(abs(c.dot(side)) for c in raw) / 2
        base = sum(raw, Vector()) / 2
        base -= side * base.dot(side)
        centers = [base - side * cs, base + side * cs]
    else:
        centers = raw
        cs = abs(centers[0].dot(side))

    radius = max(max((v.co - c).length for c in centers) for v in anchors) * 0.75
    strength = (args.factor - 1.0) * 0.5 * radius
    # Deckel relativ zur Koerpergroesse: schmale Figuren mit breiter
    # Ankerregion bekommen sonst unproportionale Ballons
    strength = min(strength, 0.085 * height * (args.factor / 2.5))

    reach = radius * 1.25
    candidates = [v for v in mesh.vertices
                  if v.co.dot(front) > -0.05 * height
                  and weight_on(v, exclude_ids) < EXCLUDE_WEIGHT
                  and min((v.co - c).length for c in centers) <= reach]
    print(f"Zentren={[tuple(round(x, 1) for x in c) for c in centers]}  "
          f"Radius={radius:.1f}  Verschiebung max={strength:.1f}  "
          f"Verschoben werden {len(candidates)} Vertices")

    chest_focus = (sum(centers, Vector()) / len(centers), radius * 3.5)
    if args.render:
        render_views(body, front, side, args.render + "_before", chest_focus)

    inner = [c - front * (radius * 0.6) + Vector((0, 0, -radius * 0.25))
             for c in centers]
    cleave_w = max(cs * 0.9, 1e-6)
    displaced = {}
    for v in candidates:
        i = 0 if (len(centers) == 2 and v.co.dot(side) < 0) else len(centers) - 1
        d = (v.co - centers[i]).length
        fall = max(0.0, 1.0 - (d / radius) ** 2)
        fall = math.sin(fall * math.pi / 2)
        if fall <= 0.0:
            continue
        # Dekolleté: Mittellinien-Daempfung trennt die Lobes
        sep = min(1.0, abs(v.co.dot(side)) / cleave_w)
        sep = sep * sep * (3 - 2 * sep)
        fall *= args.cleavage * sep + (1.0 - args.cleavage)
        # Teardrop-Profil: unterhalb des Zentrums voller, nach oben sanft
        # auslaufend statt kugelsymmetrisch
        dz = (v.co.z - centers[i].z) / radius
        vert = 1.0 + 0.22 * max(0.0, -dz) - 0.38 * max(0.0, dz)
        fall *= max(0.15, vert)
        direction = v.co - inner[i]
        if direction.length < 1e-6:
            continue
        # Leichte Aussen-Neigung der Lobes + Vorwaerts-Projektion
        lobe_out = side * (-1.0 if i == 0 else 1.0)
        direction = (direction.normalized() * 0.62 + front * 0.28
                     + lobe_out * 0.10).normalized()
        displaced[v.index] = v.co + direction * (strength * fall)

    # Delta-Glaettung: Verschiebungsfeld ueber die Mesh-Nachbarschaft
    # mitteln -- rundet Low-Poly-Facetten und weicht die Raender aus.
    # Nicht verschobene Nachbarn zaehlen als Null-Delta, dadurch laeuft
    # der Rand sanft aus.
    adjacency = {}
    for e in mesh.edges:
        a, b = e.vertices
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    deltas = {i: displaced[i] - mesh.vertices[i].co for i in displaced}
    for _ in range(2):
        smoothed = {}
        for i, d in deltas.items():
            nbrs = adjacency.get(i, [])
            if nbrs:
                avg = sum((deltas.get(j, Vector()) for j in nbrs),
                          Vector()) / len(nbrs)
                smoothed[i] = d * 0.45 + avg * 0.55
            else:
                smoothed[i] = d
        deltas = smoothed
    displaced = {i: mesh.vertices[i].co + d for i, d in deltas.items()}

    if args.shapekey:
        # Basis bleibt Original; Morph landet im Shape Key "BustSize",
        # den UE als Morph Target importiert (Laufzeit-Steuerung)
        body.shape_key_add(name="Basis", from_mix=False)
        key = body.shape_key_add(name="BustSize", from_mix=False)
        for idx, co in displaced.items():
            key.data[idx].co = co
        key.value = 1.0  # fuer die Vorschau-Renders
        print(f"Shape Key 'BustSize' mit {len(displaced)} Vertices angelegt")
    else:
        for idx, co in displaced.items():
            mesh.vertices[idx].co = co
        mesh.update()

    if args.render:
        render_views(body, front, side, args.render + "_after", chest_focus)

    if not args.no_export:
        # "Armature" als Objektname: UE laesst den Knoten dann beim Import weg
        armature.name = "Armature"
        # Socket-Bones (Anbaupunkte) verwerfen, falls im psk enthalten --
        # sie gehoeren nicht ins Referenz-Skelett des Meshes
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="EDIT")
        for eb in [b for b in armature.data.edit_bones
                   if b.name.lower().startswith("socket_")]:
            print(f"Entferne Socket-Bone: {eb.name}")
            armature.data.edit_bones.remove(eb)
        bpy.ops.object.mode_set(mode="OBJECT")
        # psk-Daten sind cm-Zahlen: Szene als cm deklarieren, damit der
        # FBX-Export keine Einheiten-Umrechnung draufmultipliziert
        bpy.context.scene.unit_settings.scale_length = 0.01
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.fbx(
            filepath=args.output,
            use_selection=True,
            add_leaf_bones=False,
            mesh_smooth_type="FACE",
            use_armature_deform_only=True,
            bake_anim=False,
            apply_unit_scale=True,
            primary_bone_axis=args.bone_axis_primary,
            secondary_bone_axis=args.bone_axis_secondary,
        )
        print(f"Exportiert: {args.output}")


def render_views(body, front, side, prefix, focus=None):
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
    # Grosse Pals: Kamera steht weiter weg als die Standard-Clipping-Distanz
    cam_data.clip_end = max(1000.0, size * 20)
    cam = bpy.data.objects.get("preview_cam_obj")
    if cam is None:
        cam = bpy.data.objects.new("preview_cam_obj", cam_data)
        scene.collection.objects.link(cam)
    scene.camera = cam

    views = [
        ("front", center + front * size * 3, center, size),
        ("side", center + side * size * 3, center, size),
    ]
    if focus is not None:
        f_center, f_size = focus
        views.append(("zoom_front", f_center + front * size * 3, f_center, f_size))
        views.append(("zoom_side", f_center + side * size * 3, f_center, f_size))

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
