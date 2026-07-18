"""UE-Editor-Python: Importiert gemorphte FBX-Meshes an die Original-Assetpfade.

Wird headless ausgefuehrt:
    UnrealEditor-Cmd.exe PalMod.uproject -ExecutePythonScript="ue_import.py <jobs.json>"

Jobs-Format (Liste):
    {
      "fbx": "D:/.../PinkLizard_morphed.fbx",
      "assetPath": "/Game/Pal/Model/Character/Monster/PinkLizard/SK_PinkLizard",
      "skeletonPath": "/Game/Pal/Model/Character/Skeleton/PinkLizard/SK_PinkLizard_Skeleton",
      "materials": [{"slot": "MI_PinkLizard_Body",
                     "path": "/Game/Pal/Model/Character/Monster/PinkLizard/MI_PinkLizard_Body"}]
    }

Prinzip: Nur das SkeletalMesh wandert spaeter ins Pak. Skeleton und Materialien
werden als Platzhalter an den ORIGINAL-Pfaden angelegt, damit die Referenzen im
gecookten Mesh auf die Originale des Spiels zeigen -- die Platzhalter selbst
werden beim Packen ausgeschlossen.
"""

import json
import os
import sys

import unreal

EAL = unreal.EditorAssetLibrary
ASSET_TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def log(msg):
    unreal.log(f"[palmod] {msg}")


def ensure_placeholder_material(asset_path):
    """Legt ein leeres Material am gewuenschten Pfad an, falls nicht vorhanden."""
    if EAL.does_asset_exist(asset_path):
        return unreal.load_asset(asset_path)
    pkg_path, name = asset_path.rsplit("/", 1)
    mat = ASSET_TOOLS.create_asset(name, pkg_path, unreal.Material,
                                   unreal.MaterialFactoryNew())
    if mat is None:
        raise RuntimeError(f"Material-Platzhalter fehlgeschlagen: {asset_path}")
    EAL.save_asset(asset_path)
    log(f"Platzhalter-Material: {asset_path}")
    return mat


def import_fbx(fbx, dest_path, dest_name):
    ui = unreal.FbxImportUI()
    ui.import_mesh = True
    ui.import_as_skeletal = True
    ui.import_animations = False
    ui.import_materials = False
    ui.import_textures = False
    ui.create_physics_asset = False
    ui.mesh_type_to_import = unreal.FBXImportType.FBXIT_SKELETAL_MESH
    sk_data = ui.skeletal_mesh_import_data
    sk_data.set_editor_property("normal_import_method",
                                unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    sk_data.set_editor_property("use_t0_as_ref_pose", False)
    sk_data.set_editor_property("preserve_smoothing_groups", True)
    sk_data.set_editor_property("import_morph_targets", True)
    sk_data.set_editor_property("convert_scene", True)
    # Einheiten werden Blender-seitig auf cm gebracht; UE liest Werte roh
    sk_data.set_editor_property("convert_scene_unit", False)

    task = unreal.AssetImportTask()
    task.filename = fbx
    task.destination_path = dest_path
    task.destination_name = dest_name
    task.automated = True
    task.save = False
    task.replace_existing = True
    task.options = ui
    ASSET_TOOLS.import_asset_tasks([task])

    asset_path = f"{dest_path}/{dest_name}"
    sk = unreal.load_asset(asset_path)
    if sk is None:
        raise RuntimeError(f"Import fehlgeschlagen: {asset_path}")
    return sk


def relocate_skeleton(sk, target_path):
    """Verschiebt das beim Import erzeugte Skeleton an den Original-Pfad."""
    current = sk.get_editor_property("skeleton")
    if current is None:
        raise RuntimeError("Mesh hat kein Skeleton nach Import")
    current_path = current.get_path_name().split(".")[0]
    if current_path == target_path:
        return current
    if EAL.does_asset_exist(target_path):
        # Original-Platzhalter existiert schon (frueherer Lauf): zuweisen
        target = unreal.load_asset(target_path)
        sk.set_editor_property("skeleton", target)
        EAL.delete_asset(current_path)
        return target
    if not EAL.rename_asset(current_path, target_path):
        raise RuntimeError(f"Skeleton-Umzug fehlgeschlagen: {current_path} -> {target_path}")
    log(f"Skeleton verschoben: {target_path}")
    return unreal.load_asset(target_path)


def assign_materials(sk, wanted):
    """Setzt Material-Slots per Slot-Name auf Platzhalter an Original-Pfaden."""
    by_slot = {m["slot"]: m["path"] for m in wanted}
    materials = list(sk.get_editor_property("materials"))
    rebuilt = []
    for m in materials:
        slot = str(m.get_editor_property("material_slot_name"))
        entry = unreal.SkeletalMaterial()
        entry.set_editor_property("material_slot_name", m.get_editor_property("material_slot_name"))
        if slot in by_slot:
            entry.set_editor_property("material_interface",
                                      ensure_placeholder_material(by_slot[slot]))
        else:
            log(f"WARNUNG: Kein Original-Material fuer Slot '{slot}'")
            entry.set_editor_property("material_interface",
                                      m.get_editor_property("material_interface"))
        rebuilt.append(entry)
    sk.set_editor_property("materials", rebuilt)


def main():
    # Pfad mit Leerzeichen uebersteht -ExecutePythonScript nicht zuverlaessig,
    # daher Uebergabe per Umgebungsvariable (argv nur als Fallback).
    jobs_file = os.environ.get("PALMOD_JOBS") or sys.argv[1]
    with open(jobs_file, encoding="utf-8-sig") as f:
        jobs = json.load(f)

    for job in jobs:
        dest_path, dest_name = job["assetPath"].rsplit("/", 1)
        log(f"=== {dest_name} ===")
        sk = import_fbx(job["fbx"], dest_path, dest_name)
        relocate_skeleton(sk, job["skeletonPath"])
        assign_materials(sk, job["materials"])
        EAL.save_asset(job["assetPath"])
        log(f"Gespeichert: {job['assetPath']}")

    log(f"Fertig: {len(jobs)} Mesh(es) importiert")


if __name__ == "__main__":
    main()
