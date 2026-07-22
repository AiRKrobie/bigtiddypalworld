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


def import_fbx(fbx, dest_path, dest_name, existing_skeleton=None):
    ui = unreal.FbxImportUI()
    if existing_skeleton is not None:
        # Ziel-Skeleton existiert schon (z. B. Varianten-Mesh derselben Art):
        # direkt als Import-Option setzen -- die Skeleton-Property des Meshes
        # ist nachtraeglich read-only.
        ui.skeleton = existing_skeleton
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
    # Vertex-Farben (AO-Schatten) uebernehmen
    try:
        sk_data.set_editor_property(
            "vertex_color_import_option",
            unreal.VertexColorImportOption.REPLACE)
    except Exception as ex:
        log(f"Vertex-Color-Option nicht gesetzt: {ex}")

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
    if not EAL.rename_asset(current_path, target_path):
        raise RuntimeError(f"Skeleton-Umzug fehlgeschlagen: {current_path} -> {target_path}")
    log(f"Skeleton verschoben: {target_path}")
    return unreal.load_asset(target_path)


BIKINI_MAT = "/Game/Pal/Mod/M_BustBikini"


def ensure_bikini_material():
    """Pinkes Bikini-Material (wird mit ins Pak gepackt)."""
    if EAL.does_asset_exist(BIKINI_MAT):
        return unreal.load_asset(BIKINI_MAT)
    pkg, name = BIKINI_MAT.rsplit("/", 1)
    mat = ASSET_TOOLS.create_asset(name, pkg, unreal.Material,
                                   unreal.MaterialFactoryNew())
    try:
        MEL = unreal.MaterialEditingLibrary
        col = MEL.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
        col.set_editor_property("constant",
                                unreal.LinearColor(0.015, 0.015, 0.02, 1.0))
        MEL.connect_material_property(col, "",
                                      unreal.MaterialProperty.MP_BASE_COLOR)
        rough = MEL.create_material_expression(
            mat, unreal.MaterialExpressionConstant, -400, 200)
        rough.set_editor_property("r", 0.5)
        MEL.connect_material_property(rough, "",
                                      unreal.MaterialProperty.MP_ROUGHNESS)
        MEL.recompile_material(mat)
    except Exception as ex:
        log(f"WARNUNG: Bikini-Material-Nodes fehlgeschlagen: {ex}")
    EAL.save_asset(BIKINI_MAT)
    log(f"Bikini-Material erstellt: {BIKINI_MAT}")
    return mat


def assign_materials(sk, wanted):
    """Setzt Material-Slots per Slot-Name auf Platzhalter an Original-Pfaden."""
    by_slot = {m["slot"]: m["path"] for m in wanted}
    materials = list(sk.get_editor_property("materials"))
    rebuilt = []
    for m in materials:
        slot = str(m.get_editor_property("material_slot_name"))
        entry = unreal.SkeletalMaterial()
        entry.set_editor_property("material_slot_name", m.get_editor_property("material_slot_name"))
        if slot.lower().startswith("bikini"):
            entry.set_editor_property("material_interface", ensure_bikini_material())
        elif slot in by_slot:
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

    ok, errors = 0, []
    for job in jobs:
        dest_path, dest_name = job["assetPath"].rsplit("/", 1)
        log(f"=== {dest_name} ===")
        try:
            existing = None
            if EAL.does_asset_exist(job["skeletonPath"]):
                existing = unreal.load_asset(job["skeletonPath"])
            sk = import_fbx(job["fbx"], dest_path, dest_name, existing)
            if existing is None:
                relocate_skeleton(sk, job["skeletonPath"])
            assign_materials(sk, job["materials"])
            EAL.save_asset(job["assetPath"])
            log(f"Gespeichert: {job['assetPath']}")
            ok += 1
        except Exception as ex:
            errors.append(f"{dest_name}: {ex}")
            log(f"FEHLER bei {dest_name}: {ex}")

    log(f"Fertig: {ok}/{len(jobs)} Mesh(es) importiert")
    for e in errors:
        log(f"  FEHLGESCHLAGEN: {e}")


if __name__ == "__main__":
    main()
