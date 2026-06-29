<#
  Terragravity Hermes — Windows installer
  Usage:  irm https://terragravity.cloud/install.ps1 | iex
          $env:TG_GATEWAY="https://api.terragravity.cloud"; irm https://terragravity.cloud/install.ps1 | iex

  Installs the launcher to %USERPROFILE%\.terragravity, adds a `tg` command,
  and creates a Desktop shortcut. Idempotent. No admin required.
#>
$ErrorActionPreference = "Stop"

# ── Config (overridable via env vars before piping to iex) ───────────
$Gateway = if ($env:TG_GATEWAY) { $env:TG_GATEWAY } else { "https://api.terragravity.cloud" }
$Base    = if ($env:TG_BASE)    { $env:TG_BASE }    else { "https://terragravity.cloud" }
$TgHome  = if ($env:TG_HOME)    { $env:TG_HOME }    else { Join-Path $env:USERPROFILE ".terragravity" }

function Say($m) { Write-Host "› $m" -ForegroundColor Cyan }
function Ok($m)  { Write-Host "✓ $m" -ForegroundColor Green }
function Die($m) { Write-Host "✗ $m" -ForegroundColor Red; exit 1 }

Say "Installing Terragravity Hermes for Windows"

# ── Prereqs: find python ─────────────────────────────────────────────
$py = $null
foreach ($cand in @("python","python3","py")) {
  $c = Get-Command $cand -ErrorAction SilentlyContinue
  if ($c) { $py = $c.Source; break }
}
if (-not $py) { Die "Python 3 is required but was not found. Install from https://python.org and re-run." }

# ── Layout ───────────────────────────────────────────────────────────
$bin = Join-Path $TgHome "bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null

Say "Fetching launcher → $bin\tg-launcher.py"
try {
  Invoke-WebRequest -UseBasicParsing -Uri "$Base/launcher.py" -OutFile (Join-Path $bin "tg-launcher.py")
} catch { Die "failed to download launcher from $Base/launcher.py" }

# ── Config file ──────────────────────────────────────────────────────
$cfg = Join-Path $TgHome "config.env"
@"
# Terragravity launcher config (edit freely)
TG_GATEWAY=$Gateway
# Paste your API key here (get one from the Terragravity dashboard):
TG_API_KEY=
"@ | Set-Content -Path $cfg -Encoding UTF8 -NoNewline

# ── tg.cmd wrapper ───────────────────────────────────────────────────
$launcher = Join-Path $bin "tg-launcher.py"
$tgCmd = Join-Path $bin "tg.cmd"
@"
@echo off
for /f "usebackq tokens=1,* delims==" %%A in ("$cfg") do (
  echo %%A| findstr /b /c:"#" >nul || set "%%A=%%B"
)
"$py" "$launcher" %*
"@ | Set-Content -Path $tgCmd -Encoding ASCII

# ── Add bin to user PATH (idempotent) ────────────────────────────────
$userPath = [Environment]::GetEnvironmentVariable("Path","User")
if ($userPath -notlike "*$bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$userPath;$bin", "User")
  Ok "Added $bin to your PATH (restart terminal to pick up `tg`)"
} else {
  Ok "PATH already contains $bin"
}

# ── Desktop shortcut (.lnk) ──────────────────────────────────────────
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = Join-Path $desktop "Terragravity Hermes.lnk"
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnk)
$sc.TargetPath = "$env:ComSpec"
$sc.Arguments  = "/k `"$tgCmd`" chat"
$sc.WorkingDirectory = $TgHome
$sc.IconLocation = "$env:ComSpec,0"
$sc.Description = "Talk to your Hermes agent from anywhere"
$sc.Save()
Ok "Desktop shortcut created → $lnk"

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Ok "Terragravity Hermes installed."
Write-Host ""
Write-Host "  Next steps:"
Write-Host "   1. Add your API key:  edit $cfg  (set TG_API_KEY=...)"
Write-Host "   2. Open a NEW terminal (PATH was updated)"
Write-Host "   3. Try it:            tg health   then   tg chat"
Write-Host ""
Write-Host "  Gateway: $Gateway"
Write-Host ""
