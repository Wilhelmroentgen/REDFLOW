from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

def _parse_naabu_jsonl(txt: str) -> Dict[str, List[int]]:
    ports: DefaultDict[str, set] = defaultdict(set)
    for line in txt.splitlines():
        try:
            j = json.loads(line)
            host = j.get("host") or j.get("ip")
            port = j.get("port")
            if host and isinstance(port, int):
                ports[host].add(port)
        except Exception:
            continue
    return {h: sorted(list(ps)) for h, ps in ports.items()}

async def run(
    state: Dict[str, Any],
    top_ports: int = 100,
    jsonl: bool = True,
    silent: bool = True
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    out_json = art / "naabu_top.jsonl"
    out_txt = art / "naabu_top.txt"

    if resume and not force and out_json.exists():
        txt = out_json.read_text(encoding="utf-8", errors="ignore")
        found = _parse_naabu_jsonl(txt)
        merged = state.get("ports", {}) or {}
        for h, ps in found.items():
            merged.setdefault(h, [])
            merged[h] = sorted(set(merged[h] + ps))
        state["ports"] = merged
        return state

    if not subs_alive.exists():
        # Si no hay archivo, intenta con alive_hosts/target
        inputs: List[str] = []
        if state.get("alive_hosts"):
            inputs = state["alive_hosts"]
        elif state.get("target"):
            inputs = [state["target"]]
        if not inputs:
            return state
        payload = "\n".join(inputs).replace('"', '\\"')
        cmd = f'echo "{payload}" | {TOOLS.get("naabu","naabu")} --top-ports {top_ports}'
        if silent:
            cmd += " -silent"
        if jsonl:
            cmd += " -json"
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("naabu", 900))
    else:
        cmd = f'{TOOLS.get("naabu","naabu")} -l "{subs_alive}" --top-ports {top_ports}'
        if silent:
            cmd += " -silent"
        if jsonl:
            cmd += " -json"
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("naabu", 900))

    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"naabu","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "naabu_top.jsonl", res.stdout)

    # También graba un .txt host:port
    lines = []
    try:
        found = _parse_naabu_jsonl(res.stdout)
        for h, plist in found.items():
            for p in plist:
                lines.append(f"{h}:{p}")
        append_artifact(state["run_id"], "naabu_top.txt", "\n".join(lines) + ("\n" if lines else ""))
        merged = state.get("ports", {}) or {}
        for h, ps in found.items():
            merged.setdefault(h, [])
            merged[h] = sorted(set(merged[h] + ps))
        state["ports"] = merged
    except Exception as e:
        state.setdefault("errors", []).append({"node":"naabu","parse_error":str(e)})

    return state
