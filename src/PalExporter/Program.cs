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
string targetsFile = args_["targets"];
string outDir = args_["out"];

// --- 1. Mounten ---
var provider = new DefaultFileProvider(
    paksDir, SearchOption.TopDirectoryOnly,
    new VersionContainer(EGame.GAME_UE5_1));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmapPath);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey("0x0000000000000000000000000000000000000000000000000000000000000000"));
Console.WriteLine($"Gemountet: {provider.Files.Count} Dateien");

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
    MeshFormat = EMeshFormat.Gltf2,
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

    var exported = new List<string>();
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
                exported.Add(savedPath);
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
    foreach (var req in new[] { "paks", "usmap", "targets", "out" })
        if (!d.ContainsKey(req)) throw new ArgumentException($"--{req} fehlt");
    return d;
}
