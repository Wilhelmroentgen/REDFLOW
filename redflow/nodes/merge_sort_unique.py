from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
from ..utils.io import run_dir, append_artifact

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subfiles = [
        art / "subs_subfinder.txt",
        art / "subs_assetfinder.txt",
    ]
    all_subs = set(state.get("subdomains", []) or [])
    for f in subfiles:
        if f.exists():
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for line in txt.splitlines():
                s = line.strip()
                if s:
                    all_subs.add(s)

    merged = "\n".join(sorted(all_subs)) + ("\n" if all_subs else "")
    append_artifact(state["run_id"], "subs_all.txt", merged)
    state["subdomains"] = sorted(all_subs)
    return state
