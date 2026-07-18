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

import bmesh
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
    p.add_argument("--mode", choices=["generate", "dome"], default="generate",
                   help="generate=eigene Brust-Geometrie erzeugen (Standard), "
                        "dome=vorhandene Flaeche verformen (Legacy)")
    p.add_argument("--bikini", action="store_true",
                   help="Bikini-Top als Geometrie ueber den Bruesten erzeugen")
    p.add_argument("--jiggle", action="store_true",
                   help="Jiggle-Bones (breast_l/r) hinzufuegen und die "
                        "Geometrie daran binden (fuer Physik im Spiel)")
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


def analyze(body, mesh, armature, front, side, height):
    """Selektiert Brustregion, bestimmt Zentren/Radius. Laeuft zweimal:
    vor und nach der Subdivision (Vertex-Indizes aendern sich)."""
    lower = find_bone(armature, BAND_LOWER_BONES)
    upper = find_bone(armature, BAND_UPPER_BONES)
    if lower is None or upper is None:
        raise RuntimeError("Anker-Bones fehlen. Vorhanden: "
                           + ", ".join(b.name for b in armature.data.bones))
    band_lo = lower.head_local.z - 0.02 * height
    band_hi = upper.head_local.z + 0.02 * height

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
    reach = radius * 1.25
    candidates = [v for v in mesh.vertices
                  if v.co.dot(front) > -0.05 * height
                  and weight_on(v, exclude_ids) < EXCLUDE_WEIGHT
                  and min((v.co - c).length for c in centers) <= reach]
    return {"anchors": anchors, "centers": centers, "cs": cs,
            "radius": radius, "candidates": candidates,
            "weight_on": weight_on, "companion_ids": companion_ids}


def subdivide_region(mesh, cand_idx, cuts):
    """Unterteilt die Flaechen der Brustregion: erschafft die Geometrie,
    aus der sich echte Rundungen formen lassen (flache Low-Poly-Brustkoerbe
    haben sonst zu wenige Vertices fuer eine Brustform)."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    faces = [f for f in bm.faces if any(v.index in cand_idx for v in f.verts)]
    edges = list({e for f in faces for e in f.edges})
    if edges:
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts,
                                  use_grid_fill=True)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def generate_breasts(body, mesh, centers, front, side, R_lobe, H,
                     candidates, weight_on, companion_ids, height,
                     make_bikini=False):
    """Erzeugt eigenstaendige Brust-Geometrie (glatte Teardrop-Halbkugeln,
    18x12-Kugelaufloesung) und integriert sie ins Mesh:
    - Position/Groesse aus der Bone-verankerten Analyse
    - Skinning-Gewichte und UVs von der naechstgelegenen Koerperflaeche
    - Material der Brustregion
    Rueckgabe: {neuer_vertex_index: volle_Position}; die Basis-Positionen im
    Mesh werden auf 'eingesunken' gesetzt (fuer den Morph-Target-Slider).
    """
    from collections import Counter
    from mathutils.kdtree import KDTree

    surface = [v for v in candidates if weight_on(v, companion_ids) < 0.5]
    if len(surface) < 10:
        raise RuntimeError("Zu wenig Koerperflaeche fuer Referenz")
    # Snapshot als reine Daten: nach bm.to_mesh() sind die alten
    # MeshVertex-Referenzen ungueltig (Crash bei Zugriff)
    surf_data = [(v.co.copy(), [(g.group, g.weight) for g in v.groups],
                  v.index) for v in surface]
    tree = KDTree(len(surf_data))
    for k, (co, _, _) in enumerate(surf_data):
        tree.insert(co, k)
    tree.balance()

    # Per-Vertex-UV der Koerperflaeche (erste Loop-UV je Vertex)
    uvl = mesh.uv_layers.active
    vert_uv = {}
    if uvl:
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                if vi not in vert_uv:
                    vert_uv[vi] = tuple(uvl.data[li].uv)

    # Haeufigstes Material der Brustregion
    cand_set = {v.index for v in surface}
    mats = Counter(p.material_index for p in mesh.polygons
                   if any(mesh.loops[li].vertex_index in cand_set
                          for li in p.loop_indices))
    mat_index = mats.most_common(1)[0][0] if mats else 0

    n_old = len(mesh.vertices)
    up = Vector((0.0, 0.0, 1.0))
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # --- Silhouette-Konstruktion: gross, nach vorn, tiefe Cleavage ---
    # Groesser und staerker projiziert, damit die FORM eindeutig als Brust
    # liest (unabhaengig von Farbe/Licht). Kugeln ueberlappen an der Mitte
    # -> tiefe Trennung.
    Rb = max(H * 1.45, R_lobe * 1.05)
    depth = Rb * 1.05                        # deutlich nach vorn (Silhouette)
    sink = Rb * 0.55
    cx = Rb * 0.68                           # nah -> Ueberlappung = tiefe Cleavage
    mid = sum(centers, Vector()) / len(centers)
    mid = mid - side * mid.dot(side)         # x auf Mittellinie
    rise = Rb * 0.35                         # anheben
    # Front-Achse: nach vorn, leicht nach unten (natuerlicher Fall), KEIN Auswaerts
    zax = (front - up * 0.08).normalized()
    yax = (up - zax * (up.dot(zax))).normalized()
    xax = yax.cross(zax)

    breast_info = []
    for sgn in ((-1, 1) if len(centers) == 2 else (0,)):
        cline = mid + side * (sgn * cx) + up * rise
        # Koerperoberflaeche vor diesem Punkt finden
        proj_max = -1e9
        for v in candidates:
            rel = v.co - cline
            p = rel.dot(zax)
            lat = (rel - zax * p).length
            if lat < Rb * 0.7:
                proj_max = max(proj_max, p)
        if proj_max < -1e8:
            proj_max = 0.0
        base = cline + zax * (proj_max - sink)
        v_start = len(bm.verts)

        ret = bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16,
                                        radius=1.0)
        verts = [v for v in ret["verts"]]
        to_del = [v for v in verts if v.co.z < -0.35]
        bmesh.ops.delete(bm, geom=to_del, context="VERTS")
        verts = [v for v in verts if v.is_valid]

        for v in verts:
            x, y, z = v.co.x, v.co.y, v.co.z
            # Volle Tropfenform: unten voller, oben leicht verjuengt
            fullness = 1.0 + 0.24 * max(0.0, -y) - 0.06 * max(0.0, y)
            droop = -0.06 * (1.0 - z)
            # Unterbrust-Knick: unteres Drittel kruemmt zum Koerper zurueck
            tuck = max(0.0, -y - 0.35) * 0.7
            sphere_co = (base + xax * (x * Rb * fullness)
                         + yax * (y * Rb * fullness + droop * Rb)
                         + zax * ((z - tuck) * depth))
            blend = max(0.0, min(1.0, (z + 0.35) / 0.85))
            blend = blend * blend * (3 - 2 * blend)
            _, k, _ = tree.find(sphere_co)
            surf_pt = surf_data[k][0]
            v.co = surf_pt.lerp(sphere_co, 0.12 + 0.88 * blend)

        for f in {f for v in verts for f in v.link_faces}:
            f.smooth = True
            f.material_index = mat_index

        breast_info.append({
            "apex": base + zax * depth,
            "root": base,
            "side": (sgn if sgn != 0 else 1),
            "v_start": v_start,
            "base": base.copy(), "xax": xax.copy(), "yax": yax.copy(),
            "zax": zax.copy(), "Rb": Rb, "depth": depth,
        })

    bikini_idx = None
    if make_bikini:
        bikini_mat = bpy.data.materials.new("Bikini")
        bikini_mat.diffuse_color = (0.02, 0.02, 0.03, 1.0)  # schwarz (Kontrast)
        mesh.materials.append(bikini_mat)
        bikini_idx = len(mesh.materials) - 1
        generate_bikini(bm, breast_info, bikini_idx, up, side, front)

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    new_idx = range(n_old, len(mesh.vertices))
    full_pos = {}
    nearest = {}
    inward = front * (-0.015 * height)
    for idx in new_idx:
        v = mesh.vertices[idx]
        full_pos[idx] = v.co.copy()
        _, k, _ = tree.find(v.co)
        nearest[idx] = k
        src_co, src_groups, _ = surf_data[k]
        # Gewichte der naechstgelegenen Koerperflaeche uebernehmen
        for grp, w in src_groups:
            body.vertex_groups[grp].add([idx], w, "REPLACE")
        # Basis-Position: knapp unter die Koerperflaeche eingesunken
        # (Slider 0 = unsichtbar, waechst von dort heraus)
        v.co = src_co + inward

    # UVs: neue Loops erben die UV der Referenzflaeche
    uvl = mesh.uv_layers.active
    if uvl:
        ref_uv = {idx: vert_uv.get(surf_data[k][2], (0.5, 0.5))
                  for idx, k in nearest.items()}
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                vi = mesh.loops[li].vertex_index
                if vi >= n_old:
                    uvl.data[li].uv = ref_uv[vi]

    # Neue Vertices nach Seite (Vorzeichen entlang 'side') einer Brust zuordnen
    for bi in breast_info:
        bi["vidx"] = []
    for idx in new_idx:
        s = 1 if full_pos[idx].dot(side) >= 0 else -1
        target = next((b for b in breast_info if b["side"] == s), breast_info[0])
        target["vidx"].append(idx)

    print(f"Generiert: 2x Teardrop-Halbkugel, {len(full_pos)} neue Vertices, "
          f"Material-Slot {mat_index}")
    return full_pos, breast_info


def _make_strap(bm, p0, p1, r, mat_idx, seg=8):
    """Duennes Band (Roehre) zwischen zwei Punkten -- Bikini-Schnuere."""
    d = p1 - p0
    L = d.length
    if L < 1e-5:
        return
    ax = d / L
    tmp = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(tmp).normalized()
    w = ax.cross(u).normalized()
    ring0, ring1 = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        off = u * (math.cos(a) * r) + w * (math.sin(a) * r)
        ring0.append(bm.verts.new(p0 + off))
        ring1.append(bm.verts.new(p1 + off))
    for i in range(seg):
        j = (i + 1) % seg
        f = bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        f.material_index = mat_idx
        f.smooth = True


def generate_bikini(bm, breast_info, mat_idx, up, side, front):
    """Erzeugt einen String-Bikini-Top ueber den Bruesten: Dreieck-Cups plus
    Halter- (Nacken) und Seitenbaender. Eigenes Material (mat_idx)."""
    Rb_max = max(bi["Rb"] for bi in breast_info)
    center = sum((bi["base"] for bi in breast_info), Vector()) / len(breast_info)
    neck = center + up * (Rb_max * 2.3) + front * (Rb_max * 0.1)
    for bi in breast_info:
        base, xax, yax, zax = bi["base"], bi["xax"], bi["yax"], bi["zax"]
        Rb, depth, sgn = bi["Rb"], bi["depth"], bi["side"]

        ret = bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=14,
                                        radius=1.0)
        cverts = list(ret["verts"])
        keep = []
        for v in cverts:
            x, y, z = v.co.x, v.co.y, v.co.z
            xo = x * sgn                       # >0 = aussen, <0 = innen
            # Cup deckt fast die ganze Front; nur obere Aussenecke diagonal weg
            cut = (y - 0.55) + max(0.0, xo) * 0.75
            keep.append(z > -0.12 and y > -0.92 and cut <= 0.0)
        bmesh.ops.delete(bm, geom=[v for v, k in zip(cverts, keep) if not k],
                         context="VERTS")
        cverts = [v for v in cverts if v.is_valid]
        # Cup als klare Schale ueber der Brust: groesser skaliert und deutlich
        # abgehoben -> kein z-fighting mit der Brust darunter
        fabric = Rb * 0.14
        for v in cverts:
            x, y, z = v.co.x, v.co.y, v.co.z
            fn = 1.0 + 0.20 * max(0.0, -y) - 0.06 * max(0.0, y)
            p = (base + xax * (x * Rb * fn * 1.08)
                 + yax * (y * Rb * fn * 1.08) + zax * (z * depth * 1.08))
            n = (p - base).normalized()
            v.co = p + n * fabric
        for f in {f for v in cverts for f in v.link_faces}:
            f.material_index = mat_idx
            f.smooth = True

        # Nur Halterband: Cup-Oberkante (innen) hoch zum Nacken.
        # Keine losen Seitenbaender (hingen im Spiel runter).
        top_in = base + xax * (-sgn * 0.30 * Rb) + yax * (0.55 * Rb) + zax * (0.55 * depth)
        _make_strap(bm, top_in, neck, Rb * 0.05, mat_idx)


def add_breast_bones(body, mesh, armature, breast_info, height):
    """Fuegt breast_l/breast_r als Kind-Bones des Brust-Ankers hinzu und
    bindet die generierte Geometrie daran (Gewicht steigt von Ansatz zu
    Spitze). Diese Bones werden spaeter physikalisch simuliert (Jiggle).
    Additive Bones am Ende -- Original-Animationen ignorieren sie."""
    parent = find_bone(armature, CHEST_WEIGHT_BONES) or armature.data.bones[0]
    parent_name = parent.name
    names = {-1: "breast_l", 1: "breast_r"}

    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = armature.data.edit_bones
    par = ebs.get(parent_name)
    for bi in breast_info:
        nm = names[bi["side"]]
        eb = ebs.new(nm)
        eb.head = bi["root"]
        eb.tail = bi["apex"]
        eb.parent = par
        eb.use_connect = False
        bi["bone"] = nm
    bpy.ops.object.mode_set(mode="OBJECT")

    for bi in breast_info:
        nm = bi["bone"]
        vg = body.vertex_groups.get(nm) or body.vertex_groups.new(name=nm)
        root = bi["root"]
        apex = bi["apex"]
        axis = (apex - root)
        L = max(axis.length, 1e-6)
        axis = axis / L
        for idx in bi["vidx"]:
            # Gewicht ~ Fortschritt entlang der Ansatz->Spitze-Achse
            t = max(0.0, min(1.0, (mesh.vertices[idx].co - root).dot(axis) / L))
            w = 0.25 + 0.75 * (t * t)   # Ansatz haelt, Spitze wackelt voll
            vg.add([idx], w, "REPLACE")
            # Rest-Gewicht bleibt beim Koerper (Summe wird normalisiert)
    print(f"Jiggle-Bones: {', '.join(b['bone'] for b in breast_info)} "
          f"an {parent_name}")
    return [b["bone"] for b in breast_info]


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

    # Pass 1: Region auf Original-Topologie bestimmen
    info = analyze(body, mesh, armature, front, side, height)
    centers = info["centers"]
    radius = info["radius"]

    H = (args.factor - 1.0) * 0.5 * radius
    H = min(H, 0.085 * height * (args.factor / 2.5))
    print(f"Zentren={[tuple(round(x, 1) for x in c) for c in centers]}  "
          f"Radius={radius:.1f}  Hoehe={H:.1f}  Modus={args.mode}")

    chest_focus = (sum(centers, Vector()) / len(centers), radius * 3.5)
    if args.render:
        render_views(body, front, side, args.render + "_before", chest_focus)

    if args.mode == "generate":
        # Eigene Brust-Geometrie erzeugen statt vorhandene zu verformen
        R_lobe = radius * (0.62 if len(centers) == 2 else 0.85)
        displaced, breast_info = generate_breasts(
            body, mesh, centers, front, side, R_lobe, H,
            info["candidates"], info["weight_on"], info["companion_ids"],
            height, make_bikini=args.bikini)
        bones = []
        if args.jiggle:
            bones = add_breast_bones(body, mesh, armature, breast_info, height)
            # Bone-Namen fuers Physics-Setup neben die FBX schreiben
            side_path = args.output.rsplit(".", 1)[0] + "_jigglebones.txt"
            with open(side_path, "w", encoding="utf-8") as f:
                f.write("\n".join(bones))
        finish(args, body, mesh, armature, front, side, displaced, chest_focus)
        return

    # --- Legacy: Dome-Verformung der vorhandenen Flaeche ---
    cand_idx = {v.index for v in info["candidates"]}
    cuts = 2 if len(info["anchors"]) < 70 else 1
    n_before = len(mesh.vertices)
    subdivide_region(mesh, cand_idx, cuts)
    print(f"Subdivision (cuts={cuts}): {n_before} -> {len(mesh.vertices)} Vertices")

    # Pass 2: Selektion auf der neuen Topologie
    info = analyze(body, mesh, armature, front, side, height)
    anchors = info["anchors"]
    centers = info["centers"]
    cs = info["cs"]
    radius = info["radius"]
    candidates = info["candidates"]
    weight_on = info["weight_on"]
    companion_ids = info["companion_ids"]
    print(f"Anker: {len(anchors)} von {len(mesh.vertices)} Vertices")

    # Dome-Projektion: pro Seite eine Ziel-Halbkugel (leicht nach aussen und
    # unten geneigt). Koerper-Vertices werden AUF die Dome-Flaeche gehoben --
    # das ERSCHAFFT eine Brustform auch auf voellig flachen Brustkoerben,
    # statt vorhandene Flaechen nur aufzublasen. Fell/Haar-Schalen werden
    # additiv mitgeschoben, damit sie ueber der Form liegen bleiben.
    n_axes = []
    for i in range(len(centers)):
        if len(centers) == 2:
            lobe_out = side * (-1.0 if i == 0 else 1.0)
        else:
            lobe_out = Vector()
        n_axes.append((front * 0.9 + lobe_out * 0.14
                       + Vector((0.0, 0.0, -0.10))).normalized())
    R_lobe = radius * (0.62 if len(centers) == 2 else 0.85)
    cleave_w = max(cs * 0.9, 1e-6)
    displaced = {}
    for v in candidates:
        i = 0 if (len(centers) == 2 and v.co.dot(side) < 0) else len(centers) - 1
        rel = v.co - centers[i]
        n = n_axes[i]
        proj = rel.dot(n)
        lat = (rel - n * proj).length
        if lat >= R_lobe or proj < -0.4 * R_lobe:
            continue
        dome = H * (1.0 - (lat / R_lobe) ** 2) ** 0.75
        # Teardrop: unterhalb des Zentrums voller, oben sanft auslaufend
        dz = (v.co.z - centers[i].z) / R_lobe
        vert = 1.0 + 0.18 * max(0.0, -dz) - 0.30 * max(0.0, dz)
        dome *= max(0.15, vert)
        # Dekolleté: Mittellinien-Daempfung trennt die Lobes
        sep = min(1.0, abs(v.co.dot(side)) / cleave_w)
        sep = sep * sep * (3 - 2 * sep)
        dome *= args.cleavage * sep + (1.0 - args.cleavage)
        if weight_on(v, companion_ids) >= 0.5:
            disp = dome * 0.9  # Fell-Schale: additiv verschieben
        else:
            disp = dome - max(0.0, proj)  # Flaeche auf die Dome-Form heben
            if disp <= 0.0:
                continue
        displaced[v.index] = v.co + n * disp

    # Delta-Glaettung: Verschiebungsfeld ueber die Mesh-Nachbarschaft
    # mitteln -- rundet Facetten und weicht die Raender aus.
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
    finish(args, body, mesh, armature, front, side, displaced, chest_focus)


def finish(args, body, mesh, armature, front, side, displaced, chest_focus):
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
    # Material-Farben zeigen (damit der Bikini sichtbar wird)
    try:
        scene.display.shading.color_type = "MATERIAL"
    except Exception:
        pass

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
