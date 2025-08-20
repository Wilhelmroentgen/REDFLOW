from __future__ import annotations
from typing import Dict, Any, List
import json

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

    def _append_and_parse(stdout: str):
        append_artifact(state["run_id"], "tls_meta.jsonl", stdout)
        parsed = _parse_tlsx_jsonl(stdout)
        lines = []
        for r in parsed:
            host = r.get("host") or ""
            issuer = r.get("issuer") or ""
            ver = r.get("version") or ""
            lines.append(f"{host}\t{ver}\t{issuer}")
        append_artifact(state["run_id"], "tls_meta.txt", "\n".join(lines) + ("\n" if lines else ""))
        state["tls"] = (state.get("tls") or []) + parsed

    # Reusar
    if resume and not force and out_jsonl.exists():
        _append_and_parse(out_jsonl.read_text(encoding="utf-8", errors="ignore"))
        return state

    # Modo lista
    stdout_all = ""
    if subs_alive.exists():
        cmd = f'{TOOLS.get("tlsx","tlsx")} -l "{subs_alive}" -san -cn -issuer -version -alpn -silent -json'
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("tlsx", 900))
        if res.code == 0 and res.stdout:
            stdout_all = res.stdout

    # Fallback por host si el batch devolvió vacío
    if not stdout_all:
        hosts = state.get("alive_hosts") or []
        if not hosts:
            return state
        chunk = hosts[:200]  # límite de cortesía
        outputs = []
        for h in chunk:
            cmd = f'{TOOLS.get("tlsx","tlsx")} -u "{h}" -san -cn -issuer -version -alpn -silent -json'
            res = await run_cmd(cmd, timeout=30)
            if res.code == 0 and res.stdout:
                outputs.append(res.stdout)
        stdout_all = "\n".join(outputs)

    if not stdout_all:
        state.setdefault("errors", []).append({"node":"tlsx","stderr":"empty_output"})
        return state

    _append_and_parse(stdout_all)
    return state
