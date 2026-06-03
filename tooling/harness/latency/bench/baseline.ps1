<#
  baseline.ps1 — Comfy-Cozy LTX 2.3 latency baseline (the re-runnable measurement / P2 floor).

  Drives the POLL-PATH execute via bench\run_once.py (which calls the agent's
  execute_workflow handler = _queue_prompt + 1.0s _poll_completion). We do NOT use
  `agent orchestrate`: its Step-2 validate_before_execute false-positives on this graph's
  ComfyMathExpression `values.a` dynamic inputs and Exit(1)s before executing (Line B bug,
  logged; not fixed this run — no source mutation).

  Per run it captures:
    process_wall_s  = Measure-Command around a FRESH python process (incl. interpreter+import)
    handler_wall_s  = time inside execute_workflow (printed by run_once.py as RESULT_JSON)
    inference_s     = ComfyUI's own exec time from GET /history (execution_start->success ms)
  Derived:
    dispatch_s      = handler_wall_s - inference_s          (agent queue+poll, incl. <=1.0s tail)
    import_s        = process_wall_s - handler_wall_s       (python startup+agent import; A2-ish)

  The split (champion):
    INFERENCE   = inference_s
    DISPATCH    = dispatch_s
    COLD-START  = cold handler_wall_s - median(warm handler_wall_s)   (model load/offload delta)

  HONESTY: the /history timestamp keys (execution_start / execution_success, ms epoch) are the
  recent ComfyUI shape but were VERIFIED against the live cold response before being trusted.
  COLD requires a freshly-(re)started ComfyUI; this script does NOT restart it. OS file-cache may
  keep the 61GB warm across a ComfyUI restart (understating true-cold disk read) — noted in LOG.

  USAGE:
    # after a FRESH ComfyUI start, one cold run:
    .\baseline.ps1 -Cold -WarmRuns 0
    # warm runs (model resident), e.g. 5 for the noise band:
    .\baseline.ps1 -WarmRuns 5
#>
[CmdletBinding()]
param(
  [string]$Wf       = "G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_t2v_STABLE.json",
  [string]$Py       = "G:\Comfy-Cozy\.venv312\Scripts\python.exe",
  [string]$Runner   = "G:\Comfy-Cozy\tooling\harness\latency\bench\run_once.py",
  [string]$ComfyUrl = "http://127.0.0.1:8188",
  [int]$WarmRuns    = 5,
  [int]$TimeoutS    = 900,
  [switch]$Cold,
  [string]$OutDir   = "G:\Comfy-Cozy\tooling\harness\latency\bench"
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$runsFile = Join-Path $OutDir "runs.jsonl"

function Test-Comfy {
  try { Invoke-RestMethod -Uri "$ComfyUrl/system_stats" -TimeoutSec 8 | Out-Null; return $true } catch { return $false }
}

function Get-Inference {
  param([string]$PromptId, [string]$Tag)
  $raw = Invoke-RestMethod -Uri "$ComfyUrl/history/$PromptId" -TimeoutSec 30
  $rawPath = Join-Path $OutDir "history_$Tag.json"
  $raw | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $rawPath -Encoding utf8
  $entry = $raw.$PromptId
  if (-not $entry) { return [pscustomobject]@{ inference_s=$null; note="prompt_id absent in /history" } }
  $tStart=$null; $tEnd=$null
  foreach ($m in $entry.status.messages) {
    if ($m[0] -eq "execution_start")   { $tStart = $m[1].timestamp }
    if ($m[0] -eq "execution_success") { $tEnd   = $m[1].timestamp }
  }
  if ($null -ne $tStart -and $null -ne $tEnd) {
    return [pscustomobject]@{ inference_s=[math]::Round(($tEnd-$tStart)/1000.0,3); note="ok"; raw=$rawPath }
  }
  return [pscustomobject]@{ inference_s=$null; note="TO-VERIFY: timestamps not found - inspect $rawPath"; raw=$rawPath }
}

function Run-One {
  param([string]$Tag)
  $log = Join-Path $OutDir "$Tag.log"
  Write-Host "=== run [$Tag] ===" -ForegroundColor Cyan
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  & $Py $Runner $Wf $TimeoutS *>&1 | Tee-Object -FilePath $log | Out-Null
  $sw.Stop()
  $procWall = [math]::Round($sw.Elapsed.TotalSeconds, 3)
  $line = (Select-String -Path $log -Pattern '^RESULT_JSON ' | Select-Object -First 1).Line
  $h = $null
  if ($line) { $h = ($line -replace '^RESULT_JSON ', '') | ConvertFrom-Json }
  $promptId = if ($h) { $h.prompt_id } else { $null }
  $handlerWall = if ($h) { $h.handler_wall_s } else { $null }
  $status = if ($h) { $h.status } else { "NO RESULT_JSON (see $log)" }
  $inf = if ($promptId) { Get-Inference -PromptId $promptId -Tag $Tag } else { [pscustomobject]@{ inference_s=$null; note="no prompt_id" } }
  $dispatch = if ($handlerWall -and $inf.inference_s) { [math]::Round($handlerWall - $inf.inference_s, 3) } else { $null }
  $import   = if ($handlerWall) { [math]::Round($procWall - $handlerWall, 3) } else { $null }
  $rec = [pscustomobject]@{
    ts=(Get-Date).ToString("o"); tag=$Tag; status=$status; prompt_id=$promptId
    process_wall_s=$procWall; handler_wall_s=$handlerWall; inference_s=$inf.inference_s
    dispatch_s=$dispatch; import_s=$import; note=$inf.note
  }
  ($rec | ConvertTo-Json -Compress) | Add-Content -LiteralPath $runsFile -Encoding utf8
  $rec | Format-List
  return $rec
}

if (-not (Test-Comfy)) { Write-Host "ComfyUI not reachable at $ComfyUrl - start it first." -ForegroundColor Red; exit 1 }
if (-not (Test-Path $Wf)) { Write-Host "Workflow not found: $Wf" -ForegroundColor Red; exit 1 }

$results = @()
if ($Cold) { Write-Host "COLD run (fresh ComfyUI; weights not resident)" -ForegroundColor Yellow; $results += (Run-One -Tag "cold") }
for ($i=1; $i -le $WarmRuns; $i++) { $results += (Run-One -Tag ("warm{0}" -f $i)) }

$warm = $results | Where-Object { $_.tag -like 'warm*' -and $_.handler_wall_s }
if ($warm.Count -ge 1) {
  $w = ($warm.handler_wall_s | Sort-Object)
  $median = $w[[int]([math]::Floor($w.Count/2))]
  Write-Host ("`nWARM handler_wall_s  min/median/max = {0} / {1} / {2}  (N={3})" -f $w[0],$median,$w[-1],$w.Count) -ForegroundColor Green
  $infs = ($warm | Where-Object { $_.inference_s }).inference_s | Sort-Object
  if ($infs) { Write-Host ("WARM inference_s     min/median/max = {0} / {1} / {2}" -f $infs[0],$infs[[int]([math]::Floor($infs.Count/2))],$infs[-1]) -ForegroundColor Green }
}
Write-Host "`nRuns appended to $runsFile ; per-run /history saved as history_<tag>.json" -ForegroundColor DarkGray
