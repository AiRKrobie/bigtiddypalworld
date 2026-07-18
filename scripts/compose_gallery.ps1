# Baut aus den Batch-Renders (work/renders/SK_*_{before,after}_front.png)
# Vorher/Nachher-Vergleichskacheln fuer die README-Galerie.
#
# Ausgabe: docs/img/gallery/<code>.png  +  docs/img/gallery/index.json
#
# Aufruf:  .\scripts\compose_gallery.ps1

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Root      = Split-Path $PSScriptRoot -Parent
$RenderDir = "$Root\work\renders"
$OutDir    = "$Root\docs\img\gallery"
New-Item -ItemType Directory -Force $OutDir | Out-Null

# Mesh-Basename -> Anzeigename aus dem Manifest
$manifest = Get-Content "$Root\export\manifest.json" -Raw | ConvertFrom-Json
$nameByMesh = @{}
foreach ($e in $manifest) {
    foreach ($m in $e.meshes) {
        $base = [IO.Path]::GetFileNameWithoutExtension($m.file)
        $nameByMesh[$base] = $e.display
    }
}

# Meshes, die nicht im Pak sind (kein Vergleich sinnvoll)
$Exclude = @("SK_JellyfishFairy", "SK_QueenBee_spear", "SK_MoonQueen_moon")

$PanelW = 360; $PanelH = 540; $TitleH = 46; $LabelH = 30
$CardW = $PanelW * 2 + 6
$CardH = $TitleH + $LabelH + $PanelH

$titleFont = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
$labelFont = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Regular)
$fmt = New-Object System.Drawing.StringFormat
$fmt.Alignment = [System.Drawing.StringAlignment]::Center
$fmt.LineAlignment = [System.Drawing.StringAlignment]::Center

$bgCard   = [System.Drawing.Color]::FromArgb(255, 24, 26, 32)
$bgPanel  = [System.Drawing.Color]::FromArgb(255, 236, 238, 242)
$fgTitle  = [System.Drawing.Color]::FromArgb(255, 240, 242, 248)
$fgBefore = [System.Drawing.Color]::FromArgb(255, 150, 156, 168)
$fgAfter  = [System.Drawing.Color]::FromArgb(255, 120, 200, 140)

$index = [System.Collections.ArrayList]::new()

foreach ($file in Get-ChildItem $RenderDir -Filter "*_after_front.png") {
    $mesh = $file.Name -replace '_after_front\.png$', ''
    if ($Exclude -contains $mesh) { continue }
    $before = "$RenderDir\${mesh}_before_front.png"
    $after  = $file.FullName
    if (-not (Test-Path $before)) { continue }

    $display = if ($nameByMesh.ContainsKey($mesh)) { $nameByMesh[$mesh] } else { $mesh -replace '^SK_','' }

    $card = New-Object System.Drawing.Bitmap($CardW, $CardH)
    $g = [System.Drawing.Graphics]::FromImage($card)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.Clear($bgCard)

    $brTitle  = New-Object System.Drawing.SolidBrush($fgTitle)
    $brBefore = New-Object System.Drawing.SolidBrush($fgBefore)
    $brAfter  = New-Object System.Drawing.SolidBrush($fgAfter)
    $brPanel  = New-Object System.Drawing.SolidBrush($bgPanel)

    $px2 = [int]($PanelW + 6)
    $py  = [int]($TitleH + $LabelH)
    $rTitle  = New-Object System.Drawing.RectangleF 0, 0, $CardW, $TitleH
    $rBefore = New-Object System.Drawing.RectangleF 0, $TitleH, $PanelW, $LabelH
    $rAfter  = New-Object System.Drawing.RectangleF $px2, $TitleH, $PanelW, $LabelH
    $g.DrawString($display, $titleFont, $brTitle, $rTitle, $fmt)
    $g.DrawString("VORHER", $labelFont, $brBefore, $rBefore, $fmt)
    $g.DrawString("NACHHER", $labelFont, $brAfter, $rAfter, $fmt)

    $g.FillRectangle($brPanel, 0, $py, $PanelW, $PanelH)
    $g.FillRectangle($brPanel, $px2, $py, $PanelW, $PanelH)

    foreach ($pair in @(@($before, 0), @($after, $px2))) {
        $img = [System.Drawing.Image]::FromFile($pair[0])
        $rect = New-Object System.Drawing.Rectangle([int]$pair[1], $py, $PanelW, $PanelH)
        $g.DrawImage($img, $rect)
        $img.Dispose()
    }

    $g.Dispose()
    $out = "$OutDir\$mesh.png"
    $card.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $card.Dispose()
    [void]$index.Add([pscustomobject]@{ mesh = $mesh; display = $display; file = "docs/img/gallery/$mesh.png" })
    Write-Host "Kachel: $display ($mesh)"
}

$index = $index | Sort-Object display
$index | ConvertTo-Json | Set-Content "$OutDir\index.json" -Encoding utf8
Write-Host "`n$($index.Count) Kacheln erzeugt -> $OutDir"
