# redflow/nodes/ffuf.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import json, urllib.parse
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import (
    TOOLS, TIMEOUTS, FFUF_DEFAULT_WORDLIST, FFUF_MEDIUM_WORDLIST,
    HTTPX_PRIORITY_CODES, PRIORITY_PORTS_WEB
)

def _infer_exts(state: Dict[str, Any], host: str) -> str:
    # Mirar tech de httpx/whatweb para decidir extensiones probables
    techs = []
    for r in state.get("httpx", []) or []:
        if (r.get("host") or "") == host or (r.get("url") or "").find(host) != -1:
            t = r.get("tech") or r.get("webserver") or ""
            if isinstance(t, list):
                techs += t
            elif isinstance(t, str):
                techs += [t]
    for k, v in (state.get("whatweb") or {}).items():
        if host in k:
            techs += v

    s = " ".join(techs).lower()
    exts = []
    if any(x in s for x in ("php","wordpress","laravel","drupal","joomla")):
        exts.append("php")
    if any(x in s for x in ("asp.net","iis")):
        exts += ["aspx","ashx","asmx","axd"]
    if any(x in s for x in ("java","jsp","tomcat","spring")):
        exts += ["jsp","do","action"]
    # dedupe
    exts = sorted(set(exts))
    return ",".join(exts) if exts else ""

def _pick_targets(state: Dict[str, Any], limit: int = 12) -> List[str]:
    pri: List[str] = []
    seen = set()

    # 1) httpx “buenos” primero
    for it in state.get("httpx") or []:
        url = it.get("url"); code = it.get("status") or it.get("status_code")
        if url and int(code or 0) in HTTPX_PRIORITY_CODES:
            base = url.rstrip("/")
            host = it.get("host") or ""
            key = host or base
            if key not in seen:
                pri.append(base)
                seen.add(key)

    # 2) Puertos web de naabu/nmap
    ports = state.get("ports") or {}
    for host, plist in ports.items():
        if any(p in PRIORITY_PORTS_WEB for p in plist):
            if host not in seen:
                pri.append(f"https://{host}")
                seen.add(host)

    # 3) Fallback a alive_hosts
    if not pri:
        for h in (state.get("alive_hosts") or [])[:limit]:
            if ":" in h:
                host, port = h.rsplit(":",1)
                scheme = "https" if port == "443" else "http"
                pri.append(f"{scheme}://{host}")
            else:
                pri.append(f"https://{h}")

    return pri[:limit]

async def run(
    state: Dict[str, Any],
    wordlist: str = FFUF_DEFAULT_WORDLIST,  # usa raft-small por defecto (rápido)
    threads: int = 30,
    match_codes: str = "200,204,301,302,401,403",
    filter_size: int = 0,
    per_host_minutes: int = 5,             # antes 10 -> baja a 5 (o menos)
    max_hosts: int = 12,                   # antes 30 -> menos hosts, más foco
    request_timeout: int = 4,              # -timeout por request
    follow_redirects: bool = True,         # seguir 301/302 ayuda a no perder hits
    aggressive: bool = False,              # si True, cambiar a wordlist “medium” solo para hosts seleccionados
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))
    if resume and not force:
        return state

    targets = _pick_targets(state, limit=max_hosts)
    if not targets:
        return state

    results: List[Dict[str, Any]] = state.get("ffuf_results") or []
    ffuf_bin = TOOLS.get("ffuf","ffuf")
    wl = FFUF_MEDIUM_WORDLIST if aggressive else wordlist

    for base in targets:
        # host “limpio” para inferir extensiones
        host = base.split("://",1)[-1].split("/",1)[0]
        exts = _infer_exts(state, host)  # "" si no hay señal

        safe = urllib.parse.quote(base, "")
        out_json = art / f"ffuf_{safe}.json"
        cmd = [
            ffuf_bin,
            "-w", wl,
            "-u", f"{base}/FUZZ",
            "-t", str(threads),
            "-mc", match_codes,
            "-fs", str(filter_size),
            "-timeout", str(request_timeout),
            "-ac", "-s",
            "-of", "json",
            "-o", str(out_json),
        ]
        if follow_redirects:
            cmd.append("-fr")
        if exts:
            cmd += ["-e", exts]

        # límite duro por host (segundos)
        budget = min(TIMEOUTS.get("ffuf", 300), per_host_minutes * 60)
        res = await run_cmd(" ".join(cmd), timeout=budget)
        if res.code != 0 and not out_json.exists():
            state.setdefault("errors", []).append({"node":"ffuf","url":base,"stderr":res.stderr or f"timeout/{budget}s"})
            continue

        if out_json.exists():
            # guardar/parsear resultados
            txt = out_json.read_text(encoding="utf-8", errors="ignore")
            append_artifact(state["run_id"], out_json.name, txt)
            try:
                data = json.loads(txt)
                for r in data.get("results", []):
                    results.append({
                        "base": base,
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
