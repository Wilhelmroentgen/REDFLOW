from __future__ import annotations
from typing import Dict, Any, List
import json
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS, DEFAULT_RESOLVER

def _alive_hosts_from_jsonl(jsonl: str) -> List[str]:
    alive = set()
    for line in jsonl.splitlines():
        try:
            j = json.loads(line)
            host = j.get("host") or j.get("input") or j.get("hostname")
            if not host:
                continue
            if j.get("a") or j.get("aaaa"):
                alive.add(host)
        except Exception:
            continue
    return sorted(alive)

def _resolved_text_from_jsonl(jsonl: str) -> str:
    out_lines = []
    for line in jsonl.splitlines():
        try:
            j = json.loads(line)
        except Exception:
            continue
        host = j.get("host") or j.get("input") or j.get("hostname")
        if not host:
            continue
        if j.get("a"):
            for ip in j["a"]:
                out_lines.append(f"{host} A {ip}")
        if j.get("aaaa"):
            for ip6 in j["aaaa"]:
                out_lines.append(f"{host} AAAA {ip6}")
        if j.get("cname"):
            out_lines.append(f"{host} CNAME {j['cname']}")
    return "\n".join(out_lines) + ("\n" if out_lines else "")

async def run(
    state: Dict[str, Any],
    resolver: str = DEFAULT_RESOLVER,
    resp: bool = True,
    json_output: bool = True
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_all = art / "subs_all.txt"
    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    # Resume: si ya existen outputs y no force, recárgalos
    dnsx_json = art / "dnsx.jsonl"
    subs_resolved = art / "subs_resolved.txt"
    subs_alive = art / "subs_alive.txt"
    if resume and not force and dnsx_json.exists() and subs_resolved.exists() and subs_alive.exists():
        # reconstruye state desde archivos
        try:
            jtxt = dnsx_json.read_text(encoding="utf-8", errors="ignore")
            state.setdefault("resolved", {})
            # (Opcional) podrías volver a llenar state["resolved"] aquí si quieres detalle.
            alive = [l.strip() for l in subs_alive.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
            state["alive_hosts"] = sorted(set(state.get("alive_hosts", []) + alive))
        except Exception:
            pass
        return state

    if not subs_all.exists():
        # no hay subdominios para resolver
        return state

    inp = subs_all.read_text(encoding="utf-8", errors="ignore")
    if not inp.strip():
        return state

    # dnsx con salida JSON (más fácil de parsear)
    cmd = f'echo "{inp.replace(\'"\', r\'\\\"\')}" | {TOOLS.get("dnsx","dnsx")} -r {resolver} -silent -json'
    res = await run_cmd(cmd, timeout=TIMEOUTS.get("dnsx", 600))
    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"dnsx","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "dnsx.jsonl", res.stdout)
    # subs_resolved.txt legible
    append_artifact(state["run_id"], "subs_resolved.txt", _resolved_text_from_jsonl(res.stdout))
    # subs_alive.txt
    alive = _alive_hosts_from_jsonl(res.stdout)
    append_artifact(state["run_id"], "subs_alive.txt", "\n".join(alive) + ("\n" if alive else ""))

    state["alive_hosts"] = sorted(set(state.get("alive_hosts", []) + alive))
    return state
