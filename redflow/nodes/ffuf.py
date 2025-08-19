from __future__ import annotations
from typing import Dict, Any, List, Tuple
import json
import urllib.parse
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import (
    TOOLS, TIMEOUTS, FFUF_DEFAULT_WORDLIST,
    HTTPX_PRIORITY_CODES, PRIORITY_PORTS_WEB
)

def _pick_targets(state: Dict[str, Any], limit: int = 50) -> List[str]:
    """Elige hosts prioritarios para fuzzing.
       1) URLs/hosts con httpx status en HTTPX_PRIORITY_CODES
       2) Hosts con puertos web abiertos (nmap/naabu)
       3) Quita duplicados, conserva orden aproximado por relevancia.
    """
    pri: List[str] = []

    # 1) httpx señales
    seen = set()
    for it in state.get("httpx") or []:
        url = it.get("url"); host = it.get("host")
        status = it.get("status")
        if status in HTTPX_PRIORITY_CODES and url:
            base = url.split("://", 1)[-1].rstrip("/")
            if base not in seen:
                pri.append(url.rstrip("/"))
                seen.add(base)

    # 2) puertos
    ports = state.get("ports") or {}
    for host, plist in ports.items():
        if any(p in PRIORITY_PORTS_WEB for p in plist):
            # default schema https→http fallback lo decide ffuf (o podrías tocar aquí)
            url = f"https://{host}"
            base = host
            if base not in seen:
                pri.append(url)
                seen.add(base)

    # fallback: si no hay nada
    if not pri:
        alive = state.get("alive_hosts") or []
        pri = [f"https://{h}" for h in alive[:limit]]

    # limita
    return pri[:limit]

async def run(
    state: Dict[str, Any],
    wordlist: str = FFUF_DEFAULT_WORDLIST,
    threads: int = 20,
    match_codes: str = "200,204,301,302,401,403",
    filter_size: int = 0,
    per_host_minutes: int = 10,
    max_hosts: int = 30
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    # Si ya existen resultados y estamos en resume, no rehacer
    if resume and not force:
        # No re-parseamos; se asume que otro nodo/gráficos leerán artifacts/ffuf_*.json
        return state

    targets = _pick_targets(state, limit=max_hosts)
    if not targets:
        return state

    results: List[Dict[str, Any]] = state.get("ffuf_results") or []

    for base_url in targets:
        safe = urllib.parse.quote(base_url, "")
        out_json = art / f"ffuf_{safe}.json"
        cmd = (
            f'{TOOLS.get("ffuf","ffuf")} -w "{wordlist}" -u "{base_url}/FUZZ" '
            f'-t {threads} -mc {match_codes} -fs {filter_size} -json -o "{out_json}"'
        )
        # timeout por host
        timeout = min(TIMEOUTS.get("ffuf", 1800), per_host_minutes * 60)
        res = await run_cmd(cmd, timeout=timeout)
        if res.code != 0:
            state.setdefault("errors", []).append({"node":"ffuf","url":base_url,"stderr":res.stderr or "failed"})
            continue

        # guarda también como artifact (ffuf ya escribe el archivo, pero lo aseguramos)
        if out_json.exists():
            append_artifact(state["run_id"], out_json.name, out_json.read_text(encoding="utf-8", errors="ignore"))

            # parse parcial
            try:
                data = json.loads(out_json.read_text(encoding="utf-8", errors="ignore"))
                for r in data.get("results", []):
                    results.append({
                        "base": base_url,
                        "url": r.get("url"),
                        "status": r.get("status"),
                        "length": r.get("length"),
                        "words": r.get("words"),
                        "lines": r.get("lines"),
                    })
            except Exception as e:
                state.setdefault("errors", []).append({"node":"ffuf","parse_error":str(e),"file":out_json.name})

    state["ffuf_results"] = results
    return state
