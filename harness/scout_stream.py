"""SCOUT: T_stream / perceptual latency — time to first VISIBLE preview frame.

Subscribes to ComfyUI's ws, queues a varied-seed SDXL prompt, and timestamps
(relative to queue):
  execution_start  — ComfyUI accepted + began
  first progress   — first sampler step (something is happening)
  first preview    — first BINARY ws frame = first frame the user could SEE
  complete         — final ("executing" node=None)

Perceptual latency = first preview (if previews enabled) else complete (only the
final image is ever visible). Read-only measurement; no forge.

Usage:  .venv312\\Scripts\\python.exe harness\\scout_stream.py [N]
"""
import json
import sys
import time
import urllib.request

HOST = "127.0.0.1:8188"
_CID = "streamscout"
_CUE = "a cinematic portrait of a fox, golden hour"


def _wf(seed):
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sdxl_v10VAEFix.safetensors"}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": _CUE, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["4", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                         "scheduler": "normal", "denoise": 1.0,
                         "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "scout"}},
    }


def _post(wf, cid):
    body = json.dumps({"prompt": wf, "client_id": cid}).encode()
    req = urllib.request.Request(f"http://{HOST}/prompt", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("prompt_id")


def one(seed):
    from websockets.sync.client import connect  # the lib the engine uses
    t = {"start": None, "first_progress": None, "first_preview": None, "complete": None}
    with connect(f"ws://{HOST}/ws?clientId={_CID}", max_size=16 * 1024 * 1024, open_timeout=10) as ws:
        pid = _post(_wf(seed), _CID)
        t0 = time.perf_counter()
        deadline = t0 + 90
        while t["complete"] is None and time.perf_counter() < deadline:
            try:
                msg = ws.recv(timeout=60)
            except TimeoutError:
                break
            now = time.perf_counter() - t0
            if isinstance(msg, (bytes, bytearray)):
                if t["first_preview"] is None:
                    t["first_preview"] = now
                continue
            d = json.loads(msg)
            ty = d.get("type")
            data = d.get("data", {})
            if data.get("prompt_id") not in (None, pid):
                continue
            if ty == "execution_start" and t["start"] is None:
                t["start"] = now
            elif ty == "progress" and t["first_progress"] is None:
                t["first_progress"] = now
            elif ty == "executing" and data.get("node") is None and data.get("prompt_id") == pid:
                t["complete"] = now
    return t


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    rows = []
    for i in range(n):
        try:
            t = one(2000 + i)
        except Exception as exc:
            print(f"  run {i} err: {exc}")
            continue
        rows.append(t)
        prev = t["first_preview"]
        print(f"  run {i}: start={_r(t['start'])}s first_progress={_r(t['first_progress'])}s "
              f"first_preview={_r(prev)}s complete={_r(t['complete'])}s "
              f"PERCEPTUAL={'preview '+_r(prev)+'s' if prev else 'NO PREVIEW -> final '+_r(t['complete'])+'s'}")
    if rows:
        import statistics
        def med(key):
            vs = [r[key] for r in rows if r[key] is not None]
            return round(statistics.median(vs), 3) if vs else None
        print(f"\n  median: start={med('start')}s first_progress={med('first_progress')}s "
              f"first_preview={med('first_preview')}s complete={med('complete')}s")
        previews = sum(1 for r in rows if r["first_preview"] is not None)
        print(f"  preview frames seen in {previews}/{len(rows)} runs")


def _r(v):
    return str(round(v, 3)) if isinstance(v, (int, float)) else "None"


if __name__ == "__main__":
    main()
