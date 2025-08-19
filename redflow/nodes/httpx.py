from __future__ import annotations
from typing import Dict, Any, List
import json
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

def _parse_httpx_jsonl(txt: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
            # Campos de interés típicos
            items.append({
                "url": j.get("url"),
                "host": j.get("host") or j.get("input"),
                "port": j.get("port"),
                "scheme": j.get("scheme"),
                "status": j.get("status-code"),
                "title": j.get("title"),
                "tech": j.get("tech") or j.get("webserver"),
                "content_length": j.get("content-length"),
                "hash": j.get("hash"),
                "tls": j.get("tls"),
            })
        except Exception:
            continue
    return items

async def run(
    state: Dict[str, Any],
    jsonl: bool = True,
    silent: bool = True,
    include_title: bool = True,
    tech_detect: bool = True
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    out_file = art / "httpx_summary.jsonl"
    if resume and not force and out_file.exists():
        txt = out_file.read_text(encoding="utf-8", errors="ignore")
        parsed = _parse_httpx_jsonl(txt)
        state["httpx"] = (state.get("httpx") or []) + parsed
        return state

    # Entrada: archivo si existe; si no, intenta desde memoria/target
    inputs: List[str] = []
    if subs_alive.exists():
        inputs = [l.strip() for l in subs_alive.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    elif state.get("alive_hosts"):
        inputs = list(state["alive_hosts"])
    elif state.get("target"):
        inputs = [state["target"]]

    if not inputs:
        return state

    payload = "\n".join(inputs).replace('"', '\\"')
    cmd = f'echo "{payload}" | {TOOLS.get("httpx","httpx")} -td'
    if silent:
        cmd += " -silent"
    if include_title:
        cmd += " -title"
    if tech_detect:
        cmd += " -tech-detect"
    if jsonl:
        cmd += " -json"

    res = await run_cmd(cmd, timeout=TIMEOUTS.get("httpx", 900))
    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"httpx","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "httpx_summary.jsonl", res.stdout)
    parsed = _parse_httpx_jsonl(res.stdout)
    state["httpx"] = (state.get("httpx") or []) + parsed

    # Refuerza alive_hosts con lo que respondió
    hosts_from_httpx = [p["host"] for p in parsed if p.get("host")]
    state["alive_hosts"] = sorted(set((state.get("alive_hosts") or []) + hosts_from_httpx))

    return state
