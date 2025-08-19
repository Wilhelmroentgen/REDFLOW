from typing import Dict, Any
from .base import exec_and_collect
from ..settings import TOOLS
from ..utils.io import append_artifact

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    alive = state.get("alive_hosts", [])
    if not alive:
        return state
    input_list = "\n".join(alive)
    cmd = f'echo "{input_list}" | {TOOLS["nuclei"]} -silent -json'
    res = await exec_and_collect(cmd)
    findings = state.get("findings", [])
    if res.code == 0 and res.stdout:
        append_artifact(state["run_id"], "nuclei.jsonl", res.stdout)
        import json
        for line in res.stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except Exception:
                pass
    else:
        state.setdefault("errors", []).append({"node":"nuclei","stderr":res.stderr})
    state["findings"] = findings
    return state