from __future__ import annotations
from typing import Dict, Any, List
import json

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

WELL_KNOWN_PATHS = [
    "/.well-known/openid-configuration",
    "/.well-known/oauth-authorization-server",
    "/.well-known/host-meta",
    "/.well-known/security.txt",
    "/adfs/ls/IdpInitiatedSignOn.aspx",
    "/auth/realms/master/.well-known/openid-configuration",  # Keycloak común
    "/oauth2/v2.0/authorize",  # ADFS/AzureAD endpoints
]
# Señales adicionales por host (MX/SPF ya están en state["dns_surface"])

def _parse_httpx_jsonl(txt: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            j = json.loads(ln)
            out.append({
                "url": j.get("url"),
                "status": j.get("status-code"),
                "title": j.get("title"),
                "tech": j.get("tech") or j.get("webserver"),
                "cn": j.get("tls") and j["tls"].get("dns_names"),
            })
        except Exception:
            continue
    return out

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"
    out_file = art / "idp_footprint.jsonl"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    if resume and not force and out_file.exists():
        # no reprocesamos
        return state

    # httpx con paths conocidos
    httpx = TOOLS.get("httpx","httpx")
    path_flags = " ".join(f"-path {p}" for p in WELL_KNOWN_PATHS)
    if subs_alive.exists():
        cmd = f'{httpx} -l "{subs_alive}" {path_flags} -tech-detect -title -status-code -silent -json'
    else:
        hosts = state.get("alive_hosts") or []
        if not hosts:
            hosts = [state.get("target")] if state.get("target") else []
        if not hosts:
            return state
        payload = "\n".join(hosts).replace('"','\\"')
        cmd = f'echo "{payload}" | {httpx} {path_flags} -tech-detect -title -status-code -silent -json'

    res = await run_cmd(cmd, timeout=TIMEOUTS.get("idp", 600))
    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"idp_probe","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "idp_footprint.jsonl", res.stdout)

    # (Opcional) puedes agregar lógica para etiquetar O365/Okta/etc. según títulos/paths.
    # Por simplicidad, dejamos la detección al reporte o a un post-procesamiento ligero.

    # No rellenamos state["idp"] en detalle aquí; puedes parsearlo si quieres:
    # state["idp"] = _parse_httpx_jsonl(res.stdout)
    return state
