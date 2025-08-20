# redflow/nodes/urls_params.py
from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
from urllib.parse import urlparse

from ..utils.shell import run_cmd
from ..utils.io import run_dir, append_artifact
from ..settings import TOOLS, TIMEOUTS, KATANA_DEPTH

def _read_lines(p: Path) -> List[str]:
    if not p.exists(): return []
    return [x.strip() for x in p.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]

async def run(
    state: Dict[str, Any],
    katana_depth: int = KATANA_DEPTH,
    dedupe: bool = True,
    max_urls: int = 200,        # cap global
    per_host_max: int = 25,     # cap por host
    arjun_threads: int = 10,
    arjun_req_timeout: int = 10,
    arjun_budget: int = 480,    # budget global en segundos
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    urls_hist = art / "urls_historicas.txt"
    urls_crawl = art / "urls_crawl.txt"
    urls_total = art / "urls_total.txt"
    params_txt = art / "params.txt"

    if resume and not force and urls_total.exists():
        state["urls"] = _read_lines(urls_total)
        return state

    targets: List[str] = []
    if subs_alive.exists():
        targets = _read_lines(subs_alive)
    elif state.get("alive_hosts"):
        targets = list(state["alive_hosts"])
    elif state.get("target"):
        targets = [state["target"]]

    if not targets:
        return state

    # GAU
    payload = "\n".join(targets).replace('"', '\\"')
    res_gau = await run_cmd(f'echo "{payload}" | {TOOLS.get("gau","gau")} --subs', timeout=TIMEOUTS.get("gau", 240))
    if res_gau.code == 0 and res_gau.stdout:
        urls_hist.write_text(res_gau.stdout, encoding="utf-8")
    else:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"gau","stderr":res_gau.stderr or "empty"})

    # Katana
    tf = art / "subs_alive.txt"
    res_katana = await run_cmd(f'{TOOLS.get("katana","katana")} -list "{tf}" -d {katana_depth} -silent', timeout=TIMEOUTS.get("katana", 240))
    if res_katana.code == 0 and res_katana.stdout:
        urls_crawl.write_text(res_katana.stdout, encoding="utf-8")
    else:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"katana","stderr":res_katana.stderr or "empty"})

    # Merge + caps
    all_urls = _read_lines(urls_hist) + _read_lines(urls_crawl)
    if dedupe:
        all_urls = sorted(set(all_urls))
    # cap por host
    per_host = {}
    filtered = []
    for u in all_urls:
        if len(filtered) >= max_urls: break
        host = urlparse(u).netloc.lower()
        per_host[host] = per_host.get(host, 0) + 1
        if per_host[host] <= per_host_max:
            filtered.append(u)

    urls_total.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")
    state["urls"] = filtered

    # ARJUN con budget global (nuestro run_cmd impone timeout total)
    if not filtered:
        return state

    cmd_arjun = (
        f'{TOOLS.get("arjun","arjun")} -i "{urls_total}" '
        f'-t {arjun_threads} --timeout {arjun_req_timeout} -oT "{params_txt}"'
    )
    res_arjun = await run_cmd(cmd_arjun, timeout=min(TIMEOUTS.get("arjun", 600), arjun_budget))
    if res_arjun.code != 0:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"arjun","stderr":res_arjun.stderr or "timeout"})
    return state
