"""STATE_DIR resolution across install modes (WP-1.1 wheel-safety).

Constants are computed at agent.config import time, so each case probes a
fresh interpreter via subprocess instead of reloading modules in-process.
The probe imports whatever `agent` the interpreter resolves — the checkout
in editable runs, the wheel under the packaging gate — so assertions branch
on the probed install mode rather than assuming one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_PROBE = (
    "import json; from agent import config; "
    "print(json.dumps({'state': str(config.STATE_DIR), "
    "'editable': config.IS_EDITABLE_INSTALL, "
    "'sessions': str(config.SESSIONS_DIR), 'log': str(config.LOG_DIR)}))"
)


def _probe(extra_env: dict[str, str] | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "COMFY_COZY_HOME"}
    env.update(extra_env or {})
    out = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True, text=True, env=env, check=True,
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_state_dir_matches_install_mode():
    info = _probe()
    if info["editable"]:
        expected = Path(__file__).parent.parent
    else:
        expected = Path.home() / ".comfy-cozy"
    assert Path(info["state"]) == expected
    assert Path(info["sessions"]) == expected / "sessions"
    assert Path(info["log"]) == expected / "logs"


def test_comfy_cozy_home_overrides_state_dir(tmp_path):
    info = _probe({"COMFY_COZY_HOME": str(tmp_path)})
    assert Path(info["state"]) == tmp_path
    assert Path(info["sessions"]) == tmp_path / "sessions"
    assert Path(info["log"]) == tmp_path / "logs"


def test_empty_comfy_cozy_home_behaves_like_unset():
    # Path("") is Path(".") — an empty env var must not anchor state at CWD.
    assert _probe({"COMFY_COZY_HOME": ""}) == _probe()
