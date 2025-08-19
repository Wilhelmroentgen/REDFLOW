from __future__ import annotations
from typing import Dict, Any, List

from ..utils.shell import run_cmd
from ..utils.io import append_artifact
from ..settings import TOOLS, TIMEOUTS

def _is_domain(s: str) -> bool:
    # filtro rápido (no perfecto) para dominios
    if " " in s or "/" in s:
        return False
    parts = s.strip().split(".")
    return len(parts) >= 2 and all(p and p.isalnum() or "-" in p for p in parts)

async def run(state: Dict[str, Any], timeout: int = None) -> Dict[str, Any]:
    timeout = timeout or TIMEOUTS.get("amass", 900)

    asn = state.get("asn", {})
    nums: List[str] = asn.get("numbers", []) if isinstance(asn, dict) else []
    if not nums:
        # nada que hacer (no rompe pipeline)
        return state

    asn_arg = ",".join(nums)
    cmd = f'{TOOLS.get("amass","amass")} intel -asn {asn_arg} -silent'
    res = await run_cmd(cmd, timeout=timeout)

    roots_found: List[str] = []
    if res.stdout:
        append_artifact(state["run_id"], "asn_roots.txt", res.stdout)
        for line in res.stdout.splitlines():
            d = line.strip().lower()
            if _is_domain(d):
                roots_found.append(d)
    else:
        state.setdefault("errors", []).append({"node":"amass_intel","stderr":res.stderr or "empty_output"})

    # une con roots existentes
    roots = set(state.get("roots", []))
    roots.update(roots_found)
    state["roots"] = sorted(roots)
    return state
