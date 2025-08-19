# redflow/nodes/subfinder.py
from __future__ import annotations
from typing import Dict, Any, List
from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

def _is_domain(s: str) -> bool:
    return "." in s and " " not in s and "/" not in s

async def run(
    state: Dict[str, Any],
    all: bool = True,
    silent: bool = True,
    extra: str = ""   # flags extra si quieres
) -> Dict[str, Any]:
    target = state.get("target", "")
    roots: List[str] = state.get("roots", []) or []
    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    # Asegura que el target dominio esté en roots
    if _is_domain(target) and target not in roots:
        roots.append(target)
        state["roots"] = roots

    # Resume: si ya existe el artifact y no force, lo reusamos
    rdir = run_dir(state["run_id"])
    out_file = rdir / "artifacts" / "subs_subfinder.txt"
    if resume and not force and out_file.exists():
        txt = out_file.read_text(encoding="utf-8", errors="ignore")
        found = [l.strip() for l in txt.splitlines() if l.strip()]
        state["subdomains"] = sorted(set(state.get("subdomains", []) + found))
        return state

    if not roots:
        return state

    found_all: List[str] = []
    base_cmd = f'{TOOLS.get("subfinder","subfinder")}'
    base_cmd += " -all" if all else ""
    base_cmd += " -silent" if silent else ""
    if extra:
        base_cmd += f" {extra}"

    for root in roots:
        cmd = f"{base_cmd} -d {root}"
        res = await run_cmd(cmd, timeout=TIMEOUTS.get("subfinder", 600))
        if res.code == 0 and res.stdout:
            found_all.extend([l.strip() for l in res.stdout.splitlines() if l.strip()])
        else:
            state.setdefault("errors", []).append({"node":"subfinder","root":root,"stderr":res.stderr})

    if found_all:
        append_artifact(state["run_id"], "subs_subfinder.txt", "\n".join(sorted(set(found_all))) + "\n")
        state["subdomains"] = sorted(set(state.get("subdomains", []) + found_all))
    return state
