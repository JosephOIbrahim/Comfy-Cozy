import json
import sys

p = sys.argv[1] if len(sys.argv) > 1 else r"G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_i2v.json"
g = json.load(open(p, encoding="utf-8"))
print("TOP-LEVEL KEYS:", list(g.keys()))
defs = g.get("definitions", {})
print("definitions keys:", list(defs.keys()) if isinstance(defs, dict) else type(defs).__name__)
subs = defs.get("subgraphs", []) if isinstance(defs, dict) else []
print("num subgraphs:", len(subs))
for s in subs:
    nodes = s.get("nodes", [])
    print("  subgraph id=%s name=%r nodes=%d links=%d"
          % (str(s.get("id"))[:13], s.get("name"), len(nodes), len(s.get("links", []))))
    for n in nodes:
        if n.get("type") == "CheckpointLoaderSimple":
            print("    CKPT id=%s widgets=%s outputs=%s"
                  % (n.get("id"), n.get("widgets_values"),
                     [(o.get("name"), o.get("links")) for o in n.get("outputs", [])]))
    if nodes:
        print("    NODE KEYS:", list(nodes[0].keys()))
    if s.get("links"):
        print("    LINK sample (first 3):", s["links"][:3])
