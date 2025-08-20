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

async def run(state: Dict[str, Any], **_: Any) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    out_jsonl = art / "tls_meta.jsonl"

    def _consume(stdout: str):
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

    if resume and not force and out_jsonl.exists():
        _consume(out_jsonl.read_text(encoding="utf-8", errors="ignore"))
        return state

    # filtra hosts que realmente tengan https (según httpx/urls)
    https_hosts: List[str] = []
    for it in (state.get("httpx") or []):
        u = (it.get("url") or "").strip().lower()
        if u.startswith("https://"):
            host = u.split("://",1)[1].split("/",1)[0]
            https_hosts.append(host)

    # fallback si no hay httpx: usa subs_alive pero no marques error si no hay salida
    use_list_file = False
    if https_hosts:
        payload = "\n".join(sorted(set(https_hosts)))
        cmd = f'echo "{payload}" | {TOOLS.get("tlsx","tlsx")} -san -cn -issuer -version -alpn -silent -json'
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("tlsx", 900))
        if res.code == 0 and res.stdout:
            _consume(res.stdout)
            return state
    elif subs_alive.exists():
        use_list_file = True

    if use_list_file:
        cmd = f'{TOOLS.get("tlsx","tlsx")} -l "{subs_alive}" -san -cn -issuer -version -alpn -silent -json'
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("tlsx", 900))
        if res.code == 0 and res.stdout:
            _consume(res.stdout)
            return state
        # sin TLS real: no lo tratamos como error “duro”
        return state

    # sin https hosts: no es error
    return state
