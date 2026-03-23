#Requires -Version 5.1
<#
  이미지·동영상 용량 줄이기 (FFmpeg 필요: winget install ffmpeg)
  - MP4: H.264 CRF 28, 최대 너비 1280px, 오디오 제거(페이지에서 muted 재생)
  - WebP: 품질 82 (PNG/JPG)

  사용: 프로젝트 루트(요실금수술)에서
    pwsh -File .\scripts\optimize-media.ps1
#>

$ErrorActionPreference = "Stop"

$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffmpeg = if ($ffmpegCmd) { $ffmpegCmd.Source } else { $null }
if (-not $ffmpeg) {
  Write-Error "ffmpeg 가 PATH에 없습니다. winget install Gyan.FFmpeg 등으로 설치하세요."
}

$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent  # new_vagino
$localImages = (Resolve-Path (Join-Path (Split-Path $PSScriptRoot -Parent) "images")).Path
$parentImages = Join-Path $root "images"
if (-not (Test-Path $parentImages)) { $parentImages = $null }
else { $parentImages = (Resolve-Path $parentImages).Path }

function Compress-Video {
  param([string]$InputPath, [int]$MaxWidth = 1280, [int]$Crf = 28)
  if (-not (Test-Path $InputPath)) { Write-Warning "건너뜀 (없음): $InputPath"; return }
  $tmp = "$InputPath.tmp.mp4"
  $before = (Get-Item $InputPath).Length
  $vf = "scale=min({0}\,iw):-2" -f $MaxWidth
  $argList = @(
    "-hide_banner", "-y", "-i", $InputPath,
    "-c:v", "libx264", "-crf", "$Crf", "-preset", "medium",
    "-vf", $vf,
    "-an", "-movflags", "+faststart",
    $tmp
  )
  $ErrorActionPreference = "SilentlyContinue"
  & $ffmpeg @argList 2>&1 | Out-Null
  $ErrorActionPreference = "Stop"
  if (-not (Test-Path $tmp)) { throw "압축 실패: $InputPath" }
  Move-Item -Force $tmp $InputPath
  $after = (Get-Item $InputPath).Length
  $pct = [math]::Round(100 * (1 - $after / $before), 1)
  Write-Host ("VIDEO {0}: {1:N2} MB -> {2:N2} MB (-{3}%)" -f `
      (Split-Path $InputPath -Leaf), ($before/1MB), ($after/1MB), $pct)
}

function Convert-ToWebP {
  param([string]$InputPath, [int]$Quality = 82)
  if (-not (Test-Path $InputPath)) { return }
  $out = [System.IO.Path]::ChangeExtension($InputPath, "webp")
  $ErrorActionPreference = "SilentlyContinue"
  & $ffmpeg -hide_banner -y -i $InputPath -c:v libwebp -quality $Quality $out 2>&1 | Out-Null
  $ErrorActionPreference = "Stop"
  if (-not (Test-Path $out)) { throw "WebP 실패: $InputPath" }
  $before = (Get-Item $InputPath).Length
  $after = (Get-Item $out).Length
  $pct = [math]::Round(100 * (1 - $after / $before), 1)
  Write-Host ("WEBP  {0}: {1:N2} MB -> {2:N2} MB (-{3}%)" -f `
      (Split-Path $InputPath -Leaf), ($before/1MB), ($after/1MB), $pct)
}

Write-Host "=== 동영상 (로컬 images) ===" -ForegroundColor Cyan
@( "sui.mp4", "video1.mp4" ) | ForEach-Object {
  Compress-Video (Join-Path $localImages $_) -MaxWidth 1280
}

if ($parentImages) {
  Write-Host "`n=== 동영상 (상위 images) ===" -ForegroundColor Cyan
  @( "video1_1.mp4", "video1_2.mp4" ) | ForEach-Object {
    Compress-Video (Join-Path $parentImages $_) -MaxWidth 960 -Crf 30
  }
}

Write-Host "`n=== WebP (로컬 images, 용량 큰 순) ===" -ForegroundColor Cyan
$ext = "*.png", "*.jpg", "*.jpeg"
Get-ChildItem -LiteralPath $localImages -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Extension -match '\.(png|jpg|jpeg)$' -and $_.Length -gt 30KB } |
  Sort-Object Length -Descending |
  ForEach-Object { Convert-ToWebP $_.FullName }

if ($parentImages) {
  Write-Host "`n=== WebP (상위 images) ===" -ForegroundColor Cyan
  Get-ChildItem -LiteralPath $parentImages -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -match '\.(png|jpg|jpeg)$' -and $_.Length -gt 100KB } |
    Sort-Object Length -Descending |
    ForEach-Object { Convert-ToWebP $_.FullName }
}

Write-Host "`n완료. index.html 의 .jpg/.png 를 .webp 로 바꿨는지 확인하세요." -ForegroundColor Green
