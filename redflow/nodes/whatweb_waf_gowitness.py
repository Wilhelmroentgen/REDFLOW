from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json
import re
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

WAF_LINE_RE = re.compile(r"(?P<host>[a-z0-9\.\-:]+)\s+is(?:\s+behind)?\s+(?P<waf>.+)", re.IGNORECASE)

def _parse_whatweb_json(txt: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            data = [data]
        for entry in data:
            host = entry.get("target") or entry.get("url") or entry.get("hostname")
            if not host:
                continue
            plugins = entry.get("plugins") or entry.get("Plugin") or {}
            if isinstance(plugins, dict):
                for name in plugins.keys():
                    if name not in out[host]:
                        out[host].append(name)
            elif isinstance(plugins, list):
                for p in plugins:
                    name = p.get("Name") or p.get("name")
                    if name and name not in out[host]:
                        out[host].append(name)
    except Exception:
        pass
    return dict(out)

def _parse_whatweb_brief(txt: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    for line in txt.splitlines():
        line = line.strip()
        if not line or " " not in line:
            continue
        host = line.split(" ", 1)[0]
        inside = line[line.find("[")+1:line.rfind("]")]
        if inside:
            for tok in [t.strip() for t in inside.split(",")]:
                if tok and tok not in out[host]:
                    out[host].append(tok)
    return dict(out)

def _parse_wafw00f_json(txt: str) -> Dict[str, str]:
    """
    wafw00f --format json produce una lista de resultados; recogemos host->WAF.
    """
    out: Dict[str, str] = {}
    try:
        data = json.loads(txt)
        if isinstance(data, dict):
            data = [data]
        for entry in data:
            host = entry.get("hostname") or entry.get("host") or entry.get("target")
            waf  = entry.get("identified_waf") or entry.get("waf") or ""
            if host and waf:
                out[host] = waf
    except Exception:
        pass
    return out

def _collect_urls_for_screens(art: Path, state_httpx: List[Dict[str, Any]], alive_hosts: List[str]) -> List[str]:
    """
    Intenta construir una lista de URLs reales:
    1) Preferimos 'url' del JSONL de httpx (si existe en artifacts o en state["httpx"])
    2) Si no, construimos https://HOST para cada host vivo
    """
    urls: List[str] = []
    # 1) artifacts httpx jsonl
    for candidate in ("httpx.jsonl", "httpx_summary.jsonl"):
        f = art / candidate
        if f.exists():
            for ln in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    j = json.loads(ln)
                    u = j.get("url")
                    if u:
                        urls.append(u.rstrip("/"))
                except Exception:
                    continue
    # 2) state["httpx"]
    if not urls and state_httpx:
        for it in state_httpx:
            u = (it.get("url") or "").strip()
            if u:
                urls.append(u.rstrip("/"))
    # 3) fallback: hosts vivos
    if not urls and alive_hosts:
        urls = [f"https://{h}".rstrip("/") for h in alive_hosts]
    # dedupe conservando orden
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped

async def run(state: Dict[str, Any], gowitness_threads: int = 3) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"
    screens_dir = art / "screens"
    screens_dir.mkdir(parents=True, exist_ok=True)

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    ww_json = art / "whatweb.json"
    ww_txt = art / "whatweb.txt"
    waf_json = art / "waf.json"
    urls_for_screens = art / "urls_for_screens.txt"

    # --- WHATWEB (JSON preferido, fallback brief)
    if not (resume and not force and (ww_json.exists() or ww_txt.exists())):
        cmd_json = f'{TOOLS.get("whatweb","whatweb")} -i "{subs_alive}" --no-errors --log-json "{ww_json}"'
        res_json = await run_cmd(cmd_json, timeout=TIMEOUTS.get("whatweb", 600))
        if res_json.code != 0 or not ww_json.exists():
            cmd_brief = f'{TOOLS.get("whatweb","whatweb")} -i "{subs_alive}" --no-errors --log-brief "{ww_txt}"'
            res_brief = await run_cmd(cmd_brief, timeout=TIMEOUTS.get("whatweb", 600))
            if res_brief.code != 0:
                state.setdefault("errors", []).append({"node":"whatweb","stderr":res_brief.stderr or "empty_output"})

    ww_map: Dict[str, List[str]] = {}
    if ww_json.exists():
        ww_map = _parse_whatweb_json(ww_json.read_text(encoding="utf-8", errors="ignore"))
        append_artifact(state["run_id"], "whatweb.json", ww_json.read_text(encoding="utf-8", errors="ignore"))
    elif ww_txt.exists():
        ww_map = _parse_whatweb_brief(ww_txt.read_text(encoding="utf-8", errors="ignore"))
    state["whatweb"] = ww_map

    # --- Construir URLs para screenshots (clave para gowitness)
    urls = _collect_urls_for_screens(art, state.get("httpx") or [], state.get("alive_hosts") or [])
    if urls:
        urls_for_screens.write_text("\n".join(urls) + "\n", encoding="utf-8")
        append_artifact(state["run_id"], "urls_for_screens.txt", "\n".join(urls) + "\n")

    # --- WAFW00F (JSON, tolerante a sitios caídos)
    if not (resume and not force and waf_json.exists()):
        target_file = urls_for_screens if urls_for_screens.exists() else subs_alive
        cmd_waf = f'{TOOLS.get("wafw00f","wafw00f")} -i "{target_file}" --format json -o "{waf_json}"'
        res_waf = await run_cmd(cmd_waf, timeout=TIMEOUTS.get("wafw00f", 120))
        if res_waf.code != 0 and not waf_json.exists():
            state.setdefault("errors", []).append({"node":"wafw00f","stderr":res_waf.stderr or "empty_output"})

    waf_map: Dict[str, str] = {}
    if waf_json.exists():
        waf_map = _parse_wafw00f_json(waf_json.read_text(encoding="utf-8", errors="ignore"))
        append_artifact(state["run_id"], "waf.json", waf_json.read_text(encoding="utf-8", errors="ignore"))
    state["waf"] = waf_map

    # --- GOWITNESS (usar URLs reales)
    target_file = urls_for_screens if urls_for_screens.exists() else subs_alive
    cmd_gw = f'{TOOLS.get("gowitness","gowitness")} file -f "{target_file}" -P "{screens_dir}" --threads {gowitness_threads}'
    res_gw = await run_cmd(cmd_gw, timeout=TIMEOUTS.get("gowitness", 1800))
    if res_gw.code != 0:
        state.setdefault("errors", []).append({"node":"gowitness","stderr":res_gw.stderr or "failed"})
    state["screenshots_dir"] = str(screens_dir)

    return state
