from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

def _parse_tlsx_jsonl(txt: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            j = json.loads(ln)
            out.append({
                "host": j.get("host") or j.get("input"),
                "cn": j.get("subject_cn") or j.get("cn"),
                "san": j.get("dns_names") or j.get("san"),
                "issuer": j.get("issuer_cn") or j.get("issuer"),
                "version": j.get("tls_version") or j.get("version"),
                "alpn": j.get("alpn") or j.get("proto"),
                "valid_from": j.get("not_before"),
                "valid_to": j.get("not_after"),
            })
        except Exception:
            continue
    return out

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    out_jsonl = art / "tls_meta.jsonl"
    out_txt = art / "tls_meta.txt"

    if resume and not force and out_jsonl.exists():
        txt = out_jsonl.read_text(encoding="utf-8", errors="ignore")
        state["tls"] = (state.get("tls") or []) + _parse_tlsx_jsonl(txt)
        return state

    if not subs_alive.exists():
        hosts = state.get("alive_hosts") or []
        if not hosts:
            return state
        payload = "\n".join(hosts).replace('"','\\"')
        cmd = f'echo "{payload}" | {TOOLS.get("tlsx","tlsx")} -san -cn -issuer -version -alpn -silent -json'
    else:
        cmd = f'{TOOLS.get("tlsx","tlsx")} -l "{subs_alive}" -san -cn -issuer -version -alpn -silent -json'

    res = await run_cmd(cmd, timeout=TIMEOUTS.get("tlsx", 900))
    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"tlsx","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "tls_meta.jsonl", res.stdout)
    # también un TXT legible (issuer/version por host)
    try:
        parsed = _parse_tlsx_jsonl(res.stdout)
        lines = []
        for r in parsed:
            host = r.get("host") or ""
            issuer = r.get("issuer") or ""
            ver = r.get("version") or ""
            lines.append(f"{host}\t{ver}\t{issuer}")
        append_artifact(state["run_id"], "tls_meta.txt", "\n".join(lines) + ("\n" if lines else ""))
        state["tls"] = (state.get("tls") or []) + parsed
    except Exception as e:
        state.setdefault("errors", []).append({"node":"tlsx","parse_error":str(e)})

    return state
