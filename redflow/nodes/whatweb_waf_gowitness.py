# redflow/nodes/whatweb_waf_gowitness.py
from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import json, re
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import run_dir, append_artifact
from ..settings import TOOLS, TIMEOUTS

WAF_LINE_RE = re.compile(r"(?P<host>[a-z0-9\.\-:]+)\s+is(?:\s+behind)?\s+(?P<waf>.+)", re.IGNORECASE)

def _alive_targets(artifacts_dir: Path) -> List[str]:
    alive = artifacts_dir / "subs_alive.txt"
    if not alive.exists(): return []
    return [l.strip() for l in alive.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]

def _parse_whatweb_json(txt: str) -> Dict[str, List[str]]:
    out: DefaultDict[str, List[str]] = defaultdict(list)
    try:
        data = json.loads(txt)
        data = [data] if isinstance(data, dict) else (data or [])
        for entry in data:
            host = entry.get("target") or entry.get("url") or entry.get("hostname")
            plugins = entry.get("plugins") or entry.get("Plugin") or {}
            if not host: continue
            if isinstance(plugins, dict):
                for name in plugins.keys():
                    if name and name not in out[host]: out[host].append(name)
            elif isinstance(plugins, list):
                for p in plugins:
                    name = p.get("Name") or p.get("name")
                    if name and name not in out[host]: out[host].append(name)
    except Exception:
        pass
    return dict(out)

async def run(
    state: Dict[str, Any],
    gowitness_threads: int = 3,
    waf_timeout: int = 8,
    connect_timeout: int = 8,
    read_timeout: int = 12,
    max_hosts: int = 60,
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    targets = _alive_targets(art)[:max_hosts]

    # WHATWEB (json si puede, si no brief)
    ww_json = art / "whatweb.json"
    ww_res = await run_cmd(f'{TOOLS.get("whatweb","whatweb")} -i "{art/"subs_alive.txt"}" --no-errors --log-json "{ww_json}"',
                           timeout=TIMEOUTS.get("whatweb", 300))
    ww_map = {}
    if ww_json.exists() and ww_json.stat().st_size > 0:
        ww_map = _parse_whatweb_json(ww_json.read_text(encoding="utf-8", errors="ignore"))
        append_artifact(state["run_id"], "whatweb.json", ww_json.read_text(encoding="utf-8", errors="ignore"))
    else:
        # fallback breve
        ww_txt = art / "whatweb.txt"
        ww_res2 = await run_cmd(f'{TOOLS.get("whatweb","whatweb")} -i "{art/"subs_alive.txt"}" --no-errors --log-brief "{ww_txt}"',
                                timeout=TIMEOUTS.get("whatweb", 300))
        if ww_txt.exists():
            append_artifact(state["run_id"], "whatweb.txt", ww_txt.read_text(encoding="utf-8", errors="ignore"))
    state["whatweb"] = ww_map

    # WAFW00F por host (evita IndexError global)
    waf_lines: List[str] = []
    for u in targets:
        cmd = f'{TOOLS.get("wafw00f","wafw00f")} -a -t {waf_timeout} {u}'
        res = await run_cmd(cmd, timeout=waf_timeout + 4)
        line = (res.stdout or "").strip().splitlines()[-1:] or [f"{u} : unknown"]
        waf_lines.append(f"{u}\t{line[0]}")
        if res.code != 0 and not res.stdout:
            state.setdefault("errors", []).append({"node":"wafw00f","stderr":res.stderr[:300] if res.stderr else "empty","url":u})
    (art / "waf.txt").write_text("\n".join(waf_lines) + "\n", encoding="utf-8")

    # GOWITNESS con timeouts razonables
    shots = art / "screens"; shots.mkdir(parents=True, exist_ok=True)
    gw_cmd = (
        f'{TOOLS.get("gowitness","gowitness")} file -f "{art/"subs_alive.txt"}" -P "{shots}" '
        f'--threads {gowitness_threads} --open-timeout {connect_timeout} --conn-timeout {connect_timeout} '
        f'--read-timeout {read_timeout} --disable-gpu'
    )
    gw_res = await run_cmd(gw_cmd, timeout=TIMEOUTS.get("gowitness", 600))
    if gw_res.code != 0:
        state.setdefault("errors", []).append({"node":"gowitness","stderr":gw_res.stderr or "failed"})

    state["screenshots_dir"] = str(shots)
    return state
