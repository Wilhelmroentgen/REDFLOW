from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS, KATANA_DEPTH

async def run(
    state: Dict[str, Any],
    katana_depth: int = KATANA_DEPTH,
    dedupe: bool = True
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

    # Resume rápido
    if resume and not force and urls_total.exists():
        lines = [l.strip() for l in urls_total.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
        state["urls"] = sorted(set((state.get("urls") or []) + lines))
        if params_txt.exists():
            # no parseamos profundo params de arjun (texto plano)
            pass
        return state

    # Entradas
    targets: List[str] = []
    if subs_alive.exists():
        targets = [l.strip() for l in subs_alive.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    elif state.get("alive_hosts"):
        targets = list(state["alive_hosts"])
    elif state.get("target"):
        targets = [state["target"]]

    if not targets:
        return state

    payload = "\n".join(targets).replace('"', '\\"')

    # gau --subs
    cmd_gau = f'echo "{payload}" | {TOOLS.get("gau","gau")} --subs'
    res_gau = await run_cmd(cmd_gau, timeout=TIMEOUTS.get("gau", 1200))
    if res_gau.code == 0 and res_gau.stdout:
        append_artifact(state["run_id"], "urls_historicas.txt", res_gau.stdout)
    else:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"gau","stderr":res_gau.stderr or "empty"})

    # katana -list
    tf = art / "subs_alive.txt"
    cmd_katana = f'{TOOLS.get("katana","katana")} -list "{tf}" -d {katana_depth} -silent'
    res_katana = await run_cmd(cmd_katana, timeout=TIMEOUTS.get("katana", 1200))
    if res_katana.code == 0 and res_katana.stdout:
        append_artifact(state["run_id"], "urls_crawl.txt", res_katana.stdout)
    else:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"katana","stderr":res_katana.stderr or "empty"})

    # Merge & dedupe
    all_urls = []
    if res_gau.stdout:
        all_urls.extend([l.strip() for l in res_gau.stdout.splitlines() if l.strip()])
    if res_katana.stdout:
        all_urls.extend([l.strip() for l in res_katana.stdout.splitlines() if l.strip()])

    if dedupe:
        all_urls = sorted(set(all_urls))
    append_artifact(state["run_id"], "urls_total.txt", "\n".join(all_urls) + ("\n" if all_urls else ""))

    state["urls"] = sorted(set((state.get("urls") or []) + all_urls))

    # arjun -i urls_total.txt
    if all_urls:
        cmd_arjun = f'{TOOLS.get("arjun","arjun")} -i "{urls_total}" -oT "{params_txt}"'
        res_arjun = await run_cmd(cmd_arjun, timeout=TIMEOUTS.get("arjun", 1800))
        if res_arjun.code != 0:
            state.setdefault("errors", []).append({"node":"urls_params","tool":"arjun","stderr":res_arjun.stderr or "failed"})
    return state
