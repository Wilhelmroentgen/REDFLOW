# redflow/nodes/dnsx.py
import json
from pathlib import Path
from typing import Dict, List

from ..utils.shell import run_cmd
from ..utils.io import run_dir


async def run(state: Dict, resolver: str = "1.1.1.1", **kwargs) -> Dict:
    """
    Resolve subdomains with dnsx and populate:
      - artifacts/dnsx.jsonl
      - artifacts/subs_resolved.txt
      - artifacts/subs_alive.txt
    Updates state['resolved'] and state['alive_hosts'].
    """
    run_id = state["run_id"]
    rdir = run_dir(run_id)
    art = rdir / "artifacts"

    subs: List[str] = list(dict.fromkeys(state.get("subdomains", [])))
    subs_all = art / "subs_all.txt"
    subs_all.write_text("\n".join(subs), encoding="utf-8")

    out_jsonl = art / "dnsx.jsonl"
    cmd = f'dnsx -r {resolver} -l "{subs_all}" -json -o "{out_jsonl}" -silent'
    res = await run_cmd(cmd, timeout=1200)

    resolved: Dict[str, List[str]] = {}
    alive: List[str] = []

    if out_jsonl.exists():
        for line in out_jsonl.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
            except Exception:
                continue
            host = obj.get("host") or obj.get("input") or obj.get("fqdn")
            ips = obj.get("a") or obj.get("ips") or obj.get("ip")
            if not host:
                continue
            if isinstance(ips, str):
                ips = [ips]
            resolved[host] = ips or []
            alive.append(host)

    # Fallback: if dnsx produced nothing but we have subs, keep them as "alive" for next nodes
    if not alive and subs:
        alive = subs

    # Write artifacts
    (art / "subs_resolved.txt").write_text(
        "\n".join(f"{h} {' '.join(v)}" for h, v in resolved.items()),
        encoding="utf-8",
    )
    (art / "subs_alive.txt").write_text("\n".join(alive), encoding="utf-8")

    state["resolved"] = resolved
    state["alive_hosts"] = sorted(set(alive))
    return state
