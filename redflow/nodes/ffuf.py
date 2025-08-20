from __future__ import annotations
from typing import Dict, Any, List
import json
import urllib.parse

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import (
    TOOLS, TIMEOUTS, FFUF_DEFAULT_WORDLIST,
    HTTPX_PRIORITY_CODES, PRIORITY_PORTS_WEB
)

def _pick_targets(state: Dict[str, Any], limit: int = 30) -> List[str]:
    pri: List[str] = []
    seen = set()

    for it in state.get("httpx") or []:
        url = (it.get("url") or "").rstrip("/")
        status = it.get("status") or it.get("status-code")
        if url and (status in HTTPX_PRIORITY_CODES):
            base = url.split("://", 1)[-1]
            if base not in seen:
                pri.append(url); seen.add(base)

    ports = state.get("ports") or {}
    for host, plist in ports.items():
        if any(p in PRIORITY_PORTS_WEB for p in plist):
            base = host
            if base not in seen:
                pri.append(f"https://{host}".rstrip("/")); seen.add(base)

    if not pri:
        for h in (state.get("alive_hosts") or [])[:limit]:
            base = h
            if base not in seen:
                pri.append(f"https://{h}".rstrip("/")); seen.add(base)

    return pri[:limit]

async def run(
    state: Dict[str, Any],
    wordlist: str = FFUF_DEFAULT_WORDLIST,
    threads: int = 20,
    match_codes: str = "200,204,301,302,401,403",
    filter_size: int = 0,
    per_host_minutes: int = 5,
    max_hosts: int = 15,
    request_timeout: int = 5,   # timeout por request (ffuf -timeout). No confundir con TIMEOUTS global
    rate: int = 0                # throttling opcional (req/s). 0 = sin límite
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    if resume and not force:
        return state

    targets = _pick_targets(state, limit=max_hosts)
    if not targets:
        return state

    results: List[Dict[str, Any]] = state.get("ffuf_results") or []

    for base_url in targets:
        safe = urllib.parse.quote(base_url, "")
        out_json = art / f"ffuf_{safe}.json"
        rate_flag = f"-rate {rate}" if rate and rate > 0 else ""
        cmd = (
            f'{TOOLS.get("ffuf","ffuf")} -w "{wordlist}" -u "{base_url}/FUZZ" '
            f'-t {threads} -mc {match_codes} -fs {filter_size} -timeout {request_timeout} -ac {rate_flag} '
            f'-json -o "{out_json}"'
        )
        timeout = min(TIMEOUTS.get("ffuf", 600), per_host_minutes * 60)
        res = await run_cmd(cmd, timeout=timeout)
        if res.code != 0:
            state.setdefault("errors", []).append({"node":"ffuf","url":base_url,"stderr":res.stderr or "failed"})
            continue

        if out_json.exists():
            txt = out_json.read_text(encoding="utf-8", errors="ignore")
            append_artifact(state["run_id"], out_json.name, txt)
            try:
                data = json.loads(txt)
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
