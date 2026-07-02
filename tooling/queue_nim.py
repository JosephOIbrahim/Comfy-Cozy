"""Queue the FLUX NIM workflow directly to ComfyUI /prompt (no wrapper ws monitoring).

Patches Load NIM to System-RAM offload + sets the generate params, then POSTs.
ComfyUI executes async (LoadNIM launches the container with its own creds);
we monitor the container out-of-band. Local diagnostic helper.
"""
import json
import urllib.error
import urllib.request

WF_PATH = r"G:\Comfy-Cozy\tooling\FLUX_Dev_NIM_Workflow.api.json"

wf = json.load(open(WF_PATH, encoding="utf-8"))
for nid, n in wf.items():
    ct = n.get("class_type")
    ins = n.setdefault("inputs", {})
    if ct == "LoadNIMNode":
        ins["operation"] = "Start"
        ins["offloading_policy"] = "System RAM"
    elif ct == "NIMFLUXNode":
        ins.update(prompt="a cinematic portrait, golden hour, 85mm",
                   seed=42, width=1024, height=1024, steps=20, cfg_scale=3.5)

body = json.dumps({"prompt": wf, "client_id": "direct-queue"}).encode()
req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=body,
                            headers={"Content-Type": "application/json"})
try:
    print("QUEUED:", urllib.request.urlopen(req, timeout=30).read().decode()[:300])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:500])
except Exception as e:
    print("ERR", repr(e))
