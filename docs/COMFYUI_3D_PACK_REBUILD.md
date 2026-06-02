# ComfyUI-3D-Pack — Re-enable / Rebuild Feasibility (Issue I2)

**Status:** scoped, NOT executed. Every rebuild step is code-executing (git clone +
nvcc compile) and gated on explicit human approval. This doc is the decision artifact
for "decide on 3D-Pack."

## Why it's disabled
`G:/COMFYUI_Database/Custom_Nodes/ComfyUI-3D-Pack.disabled` — its pinned wheels target
**torch 2.5.1 / cu124 / cp312** and reference another machine's file paths
(`my-reqs.txt`, e.g. `C:/Users/reall/...`). A blind re-enable (rename `.disabled` off)
would fail to import on the current runtime and can crash ComfyUI at startup.

## Environment reality (verified)
| | Python | torch | CUDA |
|---|---|---|---|
| **ComfyUI runtime** (build target) | **3.14.2** (`C:/Python314/python.exe`) | **2.9.1** | **13.0** |
| agent `.venv312` (NOT the target) | 3.12.10 | 2.12.0+cpu | none |
| stale `comfy3d_env` (NOT the target) | 3.12 | 2.7.0+cu128 | — |

RTX 4090 = Ada / **sm_89**. The pack must match the **runtime** triple.

## Dependency status (for py3.14 / cu130)
| Dep | Status | Note |
|---|---|---|
| slangtorch, nerfacc, kiui, utils3d | ✅ wheel | already installed on py3.14 (pure-python / JIT) |
| pytorch3d | 🔧 source-build | no cp314 wheel; heaviest nvcc compile |
| nvdiffrast | 🔧 source-build | no cp314; usually builds clean |
| diff_gaussian_rasterization | 🔧 source-build | gaussian-splatting CUDA ext |
| simple_knn | 🔧 source-build | build from pack source (PyPI `simple-knn` is a *different* package) |
| pointnet2_ops | 🔧 source-build | may need `TORCH_CUDA_ARCH_LIST=8.9` |
| torch_scatter | 🔧 source-build | a `2.1.2+shim` placeholder is currently installed; rebuild against live torch |
| **spconv-cu126** | ⛔ **blocked** | no cu130/cp314 channel; needs fragile `cumm`+`spconv` source build. **Hardest blocker** — if it fails, sparse-conv / TRELLIS-style nodes stay dead |
| cumm | 🔧 source-build | prereq for spconv |

**Verdict: FEASIBLE-WITH-SOURCE-BUILDS** (with `spconv` as the at-risk link).

## Key risks
1. **Mutating the live runtime** — source builds write into the *shared* site-packages
   the running ComfyUI uses. A bad build breaks ComfyUI itself, not just the pack.
   **Strong recommendation: build into an isolated venv that inherits the live torch.**
2. **CUDA skew** — installed toolkits are nvcc 13.1/13.2; torch is built for cu130 (13.0).
   13.0 toolkit is not installed; some extension setups assert an exact `CUDA_HOME`.
3. **spconv/cumm on cu130** — no published wheel; source build is the weakest link.
4. **py3.14 is very new (Oct 2025)** — non-CUDA deps (numpy 1.26.4 pin, pymeshlab, vtk,
   open3d, onnxruntime) may lack cp314 wheels and block `pip install -r requirements.txt`.
5. **Pre-existing hand-patches** — the `+shim` torch_scatter and JIT nerfacc suggest a
   prior partial patch; uninstall shims before a real build to avoid collisions.

## Rebuild plan (code-executing — approve before running; target = `C:/Python314/python.exe`)
0. Pre-flight (read-only): load MSVC x64 env; `nvcc --version`; set `TORCH_CUDA_ARCH_LIST="8.9"`, `CUDA_HOME` to the 13.x toolkit.
1. Snapshot for rollback: `pip freeze > comfy3dpack_preinstall_freeze.txt`.
2. Keep the pack **disabled** during the build (avoid auto-load crashes).
3. Install satisfied pure-python deps + build tools (kiui, slangtorch, nerfacc, utils3d, pccm, ccimport, ninja, cmake, pybind11).
4. Build `torch_scatter` from source against live torch (replaces the shim).
5. Build `cumm` → `spconv` from source (the cu130 blocker). Do NOT install `spconv-cu126`.
6. Build the 5 vendored CUDA extensions, `--no-build-isolation`, pytorch3d last (longest).
7. `pip install -r requirements.txt` (NOT `my-reqs.txt`); watch the numpy pin vs torch 2.9's numpy.
8. Smoke test: import all native modules in one line before re-enabling.
9. Re-enable the pack dir, launch ComfyUI, confirm nodes register clean. Rollback = `pip install -r <freeze> --force-reinstall`.

## Decision (locked — CTO best-practice ruling)
- **Blind re-enable: REJECTED** — the cp312/cu124/torch2.5.1 wheels cannot load on the
  py3.14/cu130 runtime; it would leave 3D broken or crash ComfyUI at startup.
- **Sanctioned path: ISOLATED-VENV rebuild.** Build into a fresh venv that *inherits the
  live torch 2.9.1+cu130* (do NOT `pip install` torch into it — use `--system-site-packages`
  or point at the runtime torch), compile the CUDA extensions there, smoke-test all imports
  in isolation, and only then wire the pack into ComfyUI. **Never mutate the live runtime's
  shared site-packages for a source build.**
- **Execution: on-demand, step-gated.** Each step is code-executing (git clone + nvcc) and
  requires explicit confirmation per step (rule 5 / mandate RED). Run it as its own focused
  provisioning session when 3D workflows are actually needed — it is independent of the four
  shipped remediation fixes. `spconv` remains the at-risk link; if it fails, the
  "Partial (skip spconv)" subset still yields most 3D nodes.

### Isolated-venv runbook (the sanctioned execution)
1. `C:/Python314/python.exe -m venv --system-site-packages G:/COMFY/comfy3d_build` (inherits live torch; isolates the new native builds).
2. Activate; verify `python -c "import torch;print(torch.__version__,torch.version.cuda)"` shows 2.9.1 / 13.0.
3. Run plan steps 0–8 above against THAT venv's python. Smoke-test imports there.
4. Only on a clean smoke test: make those built artifacts available to the runtime and re-enable the pack dir. Roll back by discarding the build venv — the live runtime was never touched.
