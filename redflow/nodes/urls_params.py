from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS, KATANA_DEPTH

async def run(
    state: Dict[str, Any],
    katana_depth: int = KATANA_DEPTH,
    dedupe: bool = True,
    # nuevos/compatibles:
    max_urls: int = 800,          # límite para Arjun (evitar tiempos enormes)
    arjun_threads: int = 10,      # hilos de Arjun
    arjun_timeout: int = 15,      # timeout por request en Arjun (flag correcto: -T)
    **_: Any,                     # ignora params desconocidos para compatibilidad
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    urls_total = art / "urls_total.txt"
    params_txt = art / "params.txt"

    if resume and not force and urls_total.exists():
        lines = [l.strip() for l in urls_total.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
        state["urls"] = sorted(set((state.get("urls") or []) + lines))
        return state

    # determinar targets
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

    # gau
    cmd_gau = f'echo "{payload}" | {TOOLS.get("gau","gau")} --subs'
    res_gau = await run_cmd(cmd_gau, timeout=TIMEOUTS.get("gau", 900))
    if res_gau.code != 0:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"gau","stderr":res_gau.stderr or "empty"})
    urls_gau = [l.strip() for l in (res_gau.stdout or "").splitlines() if l.strip()]

    # katana
    tf = art / "subs_alive.txt"
    cmd_katana = f'{TOOLS.get("katana","katana")} -list "{tf}" -d {katana_depth} -silent'
    res_katana = await run_cmd(cmd_katana, timeout=TIMEOUTS.get("katana", 900))
    if res_katana.code != 0:
        state.setdefault("errors", []).append({"node":"urls_params","tool":"katana","stderr":res_katana.stderr or "empty"})
    urls_katana = [l.strip() for l in (res_katana.stdout or "").splitlines() if l.strip()]

    # merge & dedupe
    all_urls = urls_gau + urls_katana
    if dedupe:
        seen, merged = set(), []
        for u in all_urls:
            if u not in seen:
                seen.add(u); merged.append(u)
        all_urls = merged

    append_artifact(state["run_id"], "urls_total.txt", "\n".join(all_urls) + ("\n" if all_urls else ""))
    state["urls"] = sorted(set((state.get("urls") or []) + all_urls))

    # Arjun (usa -T, no --timeout) y cap de URLs
    if all_urls:
        capped = all_urls[: max_urls if max_urls and max_urls > 0 else 800]
        tmp_list = art / "urls_for_arjun.txt"
        tmp_list.write_text("\n".join(capped) + "\n", encoding="utf-8")
        cmd_arjun = (
            f'{TOOLS.get("arjun","arjun")} -i "{tmp_list}" -oT "{params_txt}" '
            f'-t {arjun_threads} -T {arjun_timeout} -q'
        )
        res_arjun = await run_cmd(cmd_arjun, timeout=TIMEOUTS.get("arjun", 1200))
        if res_arjun.code != 0:
            state.setdefault("errors", []).append({"node":"urls_params","tool":"arjun","stderr":res_arjun.stderr or "failed"})

    return state
