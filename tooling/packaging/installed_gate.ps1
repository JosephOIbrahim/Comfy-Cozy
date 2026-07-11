# Local mirror of the CI packaging gate (.github/workflows/packaging-gate.yml):
# build the wheel, install it with the dev extra into a scratch venv, then verify
# the installed package from a non-repo cwd. Run: pwsh tooling/packaging/installed_gate.ps1
param([string]$Python = "py -3.12")

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Work = Join-Path ([IO.Path]::GetTempPath()) ("cozy-gate-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $Work | Out-Null

$PyParts = $Python -split " "
$PyExe = $PyParts[0]
$PyArgs = @($PyParts | Select-Object -Skip 1)

function Assert-Ok([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GATE FAILED: $What (exit $LASTEXITCODE)"
        exit 1
    }
}

Write-Host "== Build wheel"
& $PyExe @PyArgs -m venv (Join-Path $Work "buildvenv"); Assert-Ok "create build venv"
$BuildPy = Join-Path $Work "buildvenv\Scripts\python.exe"
& $BuildPy -m pip install --quiet build; Assert-Ok "pip install build"
& $BuildPy -m build --wheel --outdir (Join-Path $Work "dist") $RepoRoot; Assert-Ok "build wheel"
$Wheel = (Get-ChildItem (Join-Path $Work "dist\*.whl") | Select-Object -First 1).FullName

Write-Host "== Install wheel[dev] into gate venv"
& $PyExe @PyArgs -m venv (Join-Path $Work "gatevenv"); Assert-Ok "create gate venv"
$GatePy = Join-Path $Work "gatevenv\Scripts\python.exe"
$GateBin = Join-Path $Work "gatevenv\Scripts"
& $GatePy -m pip install --quiet "$($Wheel)[dev]"; Assert-Ok "install wheel[dev]"

$RunDir = Join-Path $Work "run"
New-Item -ItemType Directory -Path $RunDir | Out-Null

Write-Host "== Wheel-import sanity (agent resolves from site-packages, not the checkout)"
Push-Location $RunDir
& $GatePy -c "import agent, pathlib, sys; p = pathlib.Path(agent.__file__).resolve(); sys.exit(0 if 'site-packages' in p.parts else 'agent imported from the checkout, not the wheel: ' + str(p))"
$SanityExit = $LASTEXITCODE
Pop-Location
if ($SanityExit -ne 0) {
    Write-Host "GATE FAILED: wheel-import sanity (exit $SanityExit)"
    exit 1
}

Write-Host "== Suite against the installed package (non-repo cwd)"
# --ignore: kept in parity with the release workflow's long-standing exclusion;
# not a wheel-specific carve-out.
$IgnorePath = Join-Path $RepoRoot "tests\test_provisioner.py"
Push-Location $RunDir
& $GatePy -m pytest (Join-Path $RepoRoot "tests") -m "not integration" -q --import-mode=importlib `
    "--ignore=$IgnorePath"
$PytestExit = $LASTEXITCODE
Pop-Location
if ($PytestExit -ne 0) {
    Write-Host "GATE FAILED: pytest (exit $PytestExit)"
    exit 1
}

Write-Host "== Pollution check (site-packages grew no writable state)"
Push-Location $RunDir
& $GatePy -c "import agent, pathlib, sys; sp = pathlib.Path(agent.__file__).resolve().parent.parent; bad = [n for n in ('sessions', 'logs', 'workflows') if (sp / n).exists()]; sys.exit('site-packages polluted: ' + ', '.join(bad) if bad else 0)"
$PollutionExit = $LASTEXITCODE
Pop-Location
if ($PollutionExit -ne 0) {
    Write-Host "GATE FAILED: pollution check (exit $PollutionExit)"
    exit 1
}

Write-Host "== Console-script smokes"
foreach ($Cmd in "comfy-cozy", "cozy", "agent") {
    & (Join-Path $GateBin "$Cmd.exe") --help | Out-Null
    Assert-Ok "$Cmd --help"
}
& (Join-Path $GateBin "comfy-cozy.exe") inspect --help | Out-Null
Assert-Ok "comfy-cozy inspect --help"

Write-Host "== Data families present in the wheel"
$DataCheck = @'
from importlib.resources import files
k = files("agent") / "knowledge"
assert (k / "triggers.yaml").is_file(), "agent/knowledge/triggers.yaml missing"
assert any(p.name.endswith(".md") for p in k.iterdir()), "agent/knowledge has no .md"
profiles = files("agent") / "profiles"
assert any(p.name.endswith(".yaml") for p in profiles.iterdir()), "agent/profiles has no .yaml"
templates = files("agent") / "templates"
assert any(p.name.endswith(".json") for p in templates.iterdir()), "agent/templates has no .json"
assert (files("agent") / "schemas").is_dir(), "agent/schemas missing"
ctempl = files("cognitive") / "templates"
assert any(p.name.endswith(".json") for p in ctempl.iterdir()), "cognitive/templates has no .json"
print("data families ok")
'@
$DataCheckPath = Join-Path $Work "datacheck.py"
Set-Content -Path $DataCheckPath -Value $DataCheck
& $GatePy $DataCheckPath; Assert-Ok "data families"

Write-Host "== Version single-source"
Push-Location $RunDir
& $GatePy -c "import agent, importlib.metadata as m; assert m.version('comfy-cozy') == agent.__version__, (m.version('comfy-cozy'), agent.__version__)"
$VersionExit = $LASTEXITCODE
Pop-Location
if ($VersionExit -ne 0) {
    Write-Host "GATE FAILED: version single-source (exit $VersionExit)"
    exit 1
}

$WheelName = Split-Path $Wheel -Leaf
Remove-Item -Recurse -Force $Work
Write-Host ""
Write-Host "PACKAGING GATE PASSED ($WheelName)"
