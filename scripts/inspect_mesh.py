"""Gibt Struktur-Infos eines glTF-Meshes aus: Objekte, Bones, Vertex-Gruppen,
Abmessungen. Grundlage fuer die Kalibrierung von bust_morph.py.

Aufruf: blender --background --python scripts/inspect_mesh.py -- --input <datei.glb>
"""

import argparse
import sys

import bpy


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    return p.parse_args(argv)


def main():
    args = parse_args()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)

    print("=" * 60)
    for obj in bpy.context.scene.objects:
        print(f"OBJEKT: {obj.name}  Typ={obj.type}")
        if obj.type == "MESH":
            m = obj.data
            xs = [v.co.x for v in m.vertices]
            ys = [v.co.y for v in m.vertices]
            zs = [v.co.z for v in m.vertices]
            print(f"  Vertices={len(m.vertices)}  Polygone={len(m.polygons)}")
            if xs:
                print(f"  X: {min(xs):.3f} .. {max(xs):.3f}")
                print(f"  Y: {min(ys):.3f} .. {max(ys):.3f}")
                print(f"  Z: {min(zs):.3f} .. {max(zs):.3f}")
            print(f"  Materialslots: {[s.name for s in obj.material_slots]}")
            print(f"  Shape Keys: {obj.data.shape_keys.key_blocks.keys() if obj.data.shape_keys else 'keine'}")
            print(f"  Vertex-Gruppen ({len(obj.vertex_groups)}):")
            for g in obj.vertex_groups:
                print(f"    {g.name}")
        elif obj.type == "ARMATURE":
            bones = obj.data.bones
            print(f"  Bones ({len(bones)}):")
            for b in bones:
                head = b.head_local
                print(f"    {b.name}  head=({head.x:.3f},{head.y:.3f},{head.z:.3f})")
    print("=" * 60)


if __name__ == "__main__":
    main()
