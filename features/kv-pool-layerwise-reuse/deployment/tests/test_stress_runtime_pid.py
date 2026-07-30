from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


BASE_CONFIG = Path(__file__).resolve().parents[1] / "10-runtime-config.yaml"
STRESS_CONFIG = (
    Path(__file__).resolve().parents[1] / "stress" / "10-runtime-config.yaml"
)
MASTER_CONFIG = Path(__file__).resolve().parents[1] / "30-mooncake-master.yaml"


def configmap_script(name: str, config: Path = STRESS_CONFIG) -> str:
    lines = config.read_text(encoding="utf-8").splitlines()
    marker = f"  {name}: |"
    start = lines.index(marker) + 1
    body = []
    for line in lines[start:]:
        if line.startswith("  ") and not line.startswith("    "):
            break
        if not line:
            body.append(line)
            continue
        if not line.startswith("    "):
            raise AssertionError(f"unexpected ConfigMap indentation: {line!r}")
        body.append(line[4:])
    return "\n".join(body) + "\n"


def pid_state(helper: Path, pid: int) -> str:
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; pid_process_state "$2"',
            "bash",
            str(helper),
            str(pid),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_pid_state_distinguishes_live_absent_and_zombie(tmp_path):
    helper = tmp_path / "pid-state.sh"
    helper.write_text(configmap_script("pid-state.sh"), encoding="utf-8")

    assert pid_state(helper, os.getpid()) == "live"
    assert pid_state(helper, 99999999) == "absent"

    child_pid = os.fork()
    if child_pid == 0:
        os._exit(0)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            process_stat = Path(f"/proc/{child_pid}/stat").read_text(encoding="utf-8")
            if process_stat.split()[2] == "Z":
                break
            time.sleep(0.01)
        else:
            raise AssertionError(f"PID {child_pid} did not become a zombie")
        assert pid_state(helper, child_pid) == "zombie"
    finally:
        os.waitpid(child_pid, 0)


def test_start_and_stop_scripts_use_state_helper_instead_of_kill_zero():
    for config_path in (BASE_CONFIG, STRESS_CONFIG):
        config = config_path.read_text(encoding="utf-8")
        assert "kill -0" not in config, config_path
        assert configmap_script("pid-state.sh", config_path)
        for name in ("start-prefill.sh", "start-decode.sh", "stop-engine.sh"):
            script = configmap_script(name, config_path)
            assert "source /opt/vllm-layerwise/pid-state.sh" in script
            assert "pid_process_state" in script


def test_master_lease_covers_long_layerwise_transfer():
    config = MASTER_CONFIG.read_text(encoding="utf-8")
    assert "--default_kv_lease_ttl=30s" in config
