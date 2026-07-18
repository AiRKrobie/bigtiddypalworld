// PalExporter: Batch-Export von Pal-Skeletal-Meshes aus Palworld als glTF.
//
// Aufruf:
//   dotnet run --project src/PalExporter -- \
//       --paks "M:\...\Pal\Content\Paks" \
//       --usmap "tools\mappings\Palworld.usmap" \
//       --targets "data\target_pals.txt" \
//       --out "export"
//
// Ablauf:
//   1. Pak mounten (Palworld ist unverschluesselt)
//   2. Anzeigename -> interner Codename aus DT_PalNameText (L10N/en) aufloesen
//   3. Skeletal Meshes unter .../Model/Character/Monster/<Codename>/ finden
//   4. Als glTF nach export/<Codename>/ schreiben + manifest.json

using System.Text.Json;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Objects.Core.i18N;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Meshes;

var args_ = ParseArgs(args);
string paksDir = args_["paks"];
string usmapPath = args_["usmap"];

// --- 1. Mounten ---
var provider = new DefaultFileProvider(
    paksDir, SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE5_1));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmapPath);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey("0x0000000000000000000000000000000000000000000000000000000000000000"));
Console.WriteLine($"Gemountet: {provider.Files.Count} Dateien");

// --- Verify-Modus: Skelett eines Mod-Paks gegen das Original vergleichen ---
if (args_.TryGetValue("verify-pak", out var verifyPakDir))
{
    string meshAsset = args_["mesh"]; // z. B. Pal/Content/Pal/.../SK_PinkLizard
    var modProvider = new DefaultFileProvider(
        verifyPakDir, SearchOption.TopDirectoryOnly,
        new VersionContainer(EGame.GAME_UE5_1));
    modProvider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmapPath);
    modProvider.Initialize();
    modProvider.SubmitKey(new FGuid(), new FAesKey("0x0000000000000000000000000000000000000000000000000000000000000000"));
    Console.WriteLine($"Mod-Pak gemountet: {modProvider.Files.Count} Dateien");

    var orig = (USkeletalMesh)provider.LoadPackageObject(meshAsset);
    var mod = (USkeletalMesh)modProvider.LoadPackageObject(meshAsset);

    var ob = orig.ReferenceSkeleton.FinalRefBoneInfo;
    var mb = mod.ReferenceSkeleton.FinalRefBoneInfo;
    var op = orig.ReferenceSkeleton.FinalRefBonePose;
    var mp = mod.ReferenceSkeleton.FinalRefBonePose;
    Console.WriteLine($"Bones Original={ob.Length}  Mod={mb.Length}");

    for (int i = 0; i < Math.Min(6, Math.Min(ob.Length, mb.Length)); i++)
    {
        Console.WriteLine($"--- [{i}] {ob[i].Name.Text}");
        Console.WriteLine($"  orig T=({op[i].Translation.X:F2},{op[i].Translation.Y:F2},{op[i].Translation.Z:F2}) " +
                          $"Q=({op[i].Rotation.X:F4},{op[i].Rotation.Y:F4},{op[i].Rotation.Z:F4},{op[i].Rotation.W:F4}) " +
                          $"S=({op[i].Scale3D.X:F2},{op[i].Scale3D.Y:F2},{op[i].Scale3D.Z:F2})");
        Console.WriteLine($"  mod  T=({mp[i].Translation.X:F2},{mp[i].Translation.Y:F2},{mp[i].Translation.Z:F2}) " +
                          $"Q=({mp[i].Rotation.X:F4},{mp[i].Rotation.Y:F4},{mp[i].Rotation.Z:F4},{mp[i].Rotation.W:F4}) " +
                          $"S=({mp[i].Scale3D.X:F2},{mp[i].Scale3D.Y:F2},{mp[i].Scale3D.Z:F2})");
    }

    int n = Math.Max(ob.Length, mb.Length);
    for (int i = 0; i < n; i++)
    {
        string o = i < ob.Length ? $"{ob[i].Name.Text}(p{ob[i].ParentIndex})" : "-";
        string m = i < mb.Length ? $"{mb[i].Name.Text}(p{mb[i].ParentIndex})" : "-";
        bool nameDiff = o != m;
        bool poseDiff = false;
        if (i < ob.Length && i < mb.Length)
        {
            var dt = (op[i].Translation - mp[i].Translation).Size();
            var dq = Math.Abs(op[i].Rotation.W) - Math.Abs(mp[i].Rotation.W);
            poseDiff = dt > 0.1f || Math.Abs(dq) > 0.001f;
            if (nameDiff || poseDiff)
                Console.WriteLine($"[{i,3}] {o,-30} {m,-30} dT={dt:F3} dQw={dq:F4}");
        }
        else Console.WriteLine($"[{i,3}] {o,-30} {m,-30} FEHLT");
    }
    Console.WriteLine("Vergleich abgeschlossen.");
    return;
}

string targetsFile = args_["targets"];
string outDir = args_["out"];

// --- 2. Namenszuordnung aus den Spieldaten ---
// DT_PalNameText: Zeilen "PAL_NAME_<Codename>" -> lokalisierter Anzeigename
var nameTablePath = provider.Files.Keys.FirstOrDefault(k =>
    k.Contains("L10N/en/", StringComparison.OrdinalIgnoreCase) &&
    k.EndsWith("DT_PalNameText_Common.uasset", StringComparison.OrdinalIgnoreCase));
if (nameTablePath == null)
{
    Console.WriteLine("DT_PalNameText nicht am erwarteten Ort. Kandidaten:");
    foreach (var k in provider.Files.Keys.Where(k =>
        k.Contains("NameText", StringComparison.OrdinalIgnoreCase) ||
        (k.Contains("L10N", StringComparison.OrdinalIgnoreCase) &&
         k.Contains("DataTable", StringComparison.OrdinalIgnoreCase) &&
         k.Contains("/en", StringComparison.OrdinalIgnoreCase))).Take(40))
        Console.WriteLine("  " + k);
    throw new Exception("DT_PalNameText nicht gefunden");
}

var nameTable = provider.LoadPackageObject<UDataTable>(nameTablePath.Replace(".uasset", ""));
var displayToCode = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
foreach (var (rowName, row) in nameTable.RowMap)
{
    var key = rowName.Text; // z. B. PAL_NAME_CatMage
    if (!key.StartsWith("PAL_NAME_", StringComparison.OrdinalIgnoreCase)) continue;
    var code = key["PAL_NAME_".Length..];
    // Anzeigename steckt als FText in der Zeile (Property-Name variiert)
    string? display = null;
    try
    {
        display = row.Properties
            .Select(p => p.Tag?.GenericValue)
            .OfType<FText>()
            .FirstOrDefault()?.Text;
    }
    catch { /* Fallback unten */ }
    if (string.IsNullOrWhiteSpace(display)) continue;
    displayToCode[display.Trim()] = code;
}
Console.WriteLine($"Namenszuordnung: {displayToCode.Count} Pals");

// --- 3. Ziele aufloesen ---
var targets = File.ReadAllLines(targetsFile)
    .Select(l => l.Trim())
    .Where(l => l.Length > 0 && !l.StartsWith('#'))
    .ToList();

var resolved = new List<(string Display, string Code)>();
var missing = new List<string>();
foreach (var t in targets)
{
    if (displayToCode.TryGetValue(t, out var code)) resolved.Add((t, code));
    else missing.Add(t);
}
Console.WriteLine($"Aufgeloest: {resolved.Count}/{targets.Count}");
if (missing.Count > 0)
    Console.WriteLine("NICHT gefunden: " + string.Join(", ", missing));

// --- 4. Meshes finden und exportieren ---
var manifest = new List<object>();
var options = new ExporterOptions
{
    // ActorX/psk statt glTF: bleibt in UE-Koordinaten (linkshaendig, cm),
    // dadurch keine Spiegelungs-/Einheiten-Konvertierung im Roundtrip
    MeshFormat = EMeshFormat.ActorX,
    // Sockets nicht als Bones exportieren -- sie wuerden die
    // Skelett-Hierarchie gegenueber dem Original verschieben
    SocketFormat = ESocketFormat.None,
    ExportMorphTargets = true,
    ExportMaterials = false,
};

foreach (var (display, code) in resolved)
{
    var meshKeys = provider.Files.Keys.Where(k =>
        k.Contains($"/Model/Character/Monster/{code}/", StringComparison.OrdinalIgnoreCase) &&
        Path.GetFileName(k).StartsWith("SK_", StringComparison.OrdinalIgnoreCase) &&
        k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)).ToList();

    if (meshKeys.Count == 0)
    {
        Console.WriteLine($"[{display}] KEIN Mesh unter Monster/{code}/ gefunden");
        manifest.Add(new { display, code, meshes = Array.Empty<string>() });
        continue;
    }

    var exported = new List<object>();
    foreach (var key in meshKeys)
    {
        var objPath = key[..^".uasset".Length];
        try
        {
            var obj = provider.LoadPackageObject(objPath);
            if (obj is not USkeletalMesh sk) continue;
            var exporter = new MeshExporter(sk, options);
            var targetDir = new DirectoryInfo(Path.Combine(outDir, code));
            targetDir.Create();
            if (exporter.TryWriteToDir(targetDir, out _, out var savedPath))
            {
                // Metadaten fuer den UE-Reimport: Original-Pfade von Skeleton,
                // Materialien (inkl. Slot-Namen) und PhysicsAsset
                var slots = sk.SkeletalMaterials.Select((m, i) => new
                {
                    slot = m.MaterialSlotName.Text,
                    material = sk.Materials.ElementAtOrDefault(i)?.GetPathName(),
                }).ToList();
                exported.Add(new
                {
                    file = savedPath,
                    assetPath = "/Game/" + objPath["Pal/Content/".Length..],
                    skeleton = sk.Skeleton.ResolvedObject?.GetPathName(),
                    physicsAsset = sk.PhysicsAsset.ResolvedObject?.GetPathName(),
                    materials = slots,
                });
                Console.WriteLine($"[{display}] OK: {Path.GetFileName(savedPath)}");
            }
            else Console.WriteLine($"[{display}] Export fehlgeschlagen: {objPath}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[{display}] FEHLER bei {objPath}: {ex.Message}");
        }
    }
    manifest.Add(new { display, code, meshes = exported });
}

Directory.CreateDirectory(outDir);
File.WriteAllText(Path.Combine(outDir, "manifest.json"),
    JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"Manifest: {Path.Combine(outDir, "manifest.json")}");

static Dictionary<string, string> ParseArgs(string[] args)
{
    var d = new Dictionary<string, string>();
    for (int i = 0; i < args.Length - 1; i++)
        if (args[i].StartsWith("--")) d[args[i][2..]] = args[++i];
    foreach (var req in new[] { "paks", "usmap" })
        if (!d.ContainsKey(req)) throw new ArgumentException($"--{req} fehlt");
    return d;
}
