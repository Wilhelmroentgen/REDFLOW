from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json
import re
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS, SEM_LIMITS

WAF_LINE_RE = re.compile(r"(?P<host>[a-z0-9\.\-:]+)\s+is(?:\s+behind)?\s+(?P<waf>.+)", re.IGNORECASE)

def _parse_whatweb_json(txt: str) -> Dict[str, List[str]]:
    """
    whatweb --log-json produce una lista de objetos; cada objeto puede contener
    'target' y 'plugins' con claves como {"Name":"Title", ...}
    Diferentes versiones varían; esta función intenta ser tolerante.
    """
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
            # plugins puede ser dict(str -> detalles) o lista
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
    # Formato típico: "http://host [Plugin1, Plugin2, ...]"
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

def _parse_wafw00f_txt(txt: str) -> Dict[str, str]:
    """
    Intenta detectar líneas tipo: "<host> is behind <WAF>" o "<host> ... WAF: <Name>"
    """
    result: Dict[str, str] = {}
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = WAF_LINE_RE.search(ln)
        if m:
            host = m.group("host")
            waf = m.group("waf").strip().strip(".")
            result[host] = waf
        elif "WAF" in ln and ":" in ln:
            # fallback
            parts = ln.split(":", 1)
            if len(parts) == 2:
                maybe_host, maybe_waf = parts[0].strip(), parts[1].strip()
                if maybe_host and maybe_waf and maybe_host not in result:
                    result[maybe_host] = maybe_waf
    return result

async def run(
    state: Dict[str, Any],
    gowitness_threads: int = 3
) -> Dict[str, Any]:
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
    waf_txt = art / "waf.txt"

    # ---- WHATWEB (intenta JSON, si no, brief) ----
    if not (resume and not force and (ww_json.exists() or ww_txt.exists())):
        # Preferimos JSON si está disponible en tu versión
        cmd_json = f'{TOOLS.get("whatweb","whatweb")} -i "{subs_alive}" --no-errors --log-json "{ww_json}"'
        res_json = await run_cmd(cmd_json, timeout=TIMEOUTS.get("whatweb", 600))
        if res_json.code != 0 or not ww_json.exists():
            # Fallback: brief
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
        # ya es artifact
    state["whatweb"] = ww_map

    # ---- WAFW00F ----
    if not (resume and not force and waf_txt.exists()):
        cmd_waf = f'{TOOLS.get("wafw00f","wafw00f")} -i "{subs_alive}" -o "{waf_txt}"'
        res_waf = await run_cmd(cmd_waf, timeout=TIMEOUTS.get("wafw00f", 600))
        if res_waf.code != 0:
            state.setdefault("errors", []).append({"node":"wafw00f","stderr":res_waf.stderr or "empty_output"})

    waf_map: Dict[str, str] = {}
    if waf_txt.exists():
        waf_map = _parse_wafw00f_txt(waf_txt.read_text(encoding="utf-8", errors="ignore"))
    state["waf"] = waf_map

    # ---- GOWITNESS (screenshots) ----
    # Este comando crea PNGs en screens_dir; lo dejamos como side-effect.
    cmd_gw = f'{TOOLS.get("gowitness","gowitness")} file -f "{subs_alive}" -P "{screens_dir}" --threads {gowitness_threads}'
    res_gw = await run_cmd(cmd_gw, timeout=TIMEOUTS.get("gowitness", 1800))
    if res_gw.code != 0:
        state.setdefault("errors", []).append({"node":"gowitness","stderr":res_gw.stderr or "failed"})

    state["screenshots_dir"] = str(screens_dir)
    return state
