# redflow/nodes/amass_intel.py
from pathlib import Path
from typing import List, Dict

from ..utils.shell import run_cmd
from ..utils.io import run_dir, append_artifact


async def run(state: Dict, max_orgs: int = 6, **kwargs) -> Dict:
    """
    Collect root domains with amass intel.
    Accepts max_orgs to cap org roots if you later add WHOIS org parsing.
    For now, we run a generic amass intel on the target domain.
    """
    run_id = state["run_id"]
    target = state["target"]
    rdir = run_dir(run_id)

    # Basic intel (works even without ASN/WHOIS enrichment)
    # -silent prints roots/domains one per line
    cmd = f"amass intel -whois -d {target} -silent"
    res = await run_cmd(cmd, timeout=900)

    roots: List[str] = []
    if res.code == 0 and res.stdout:
        roots = [x.strip() for x in res.stdout.splitlines() if x.strip()]

    # de-dup and persist in state
    existing = set(state.get("roots", []))
    for r in roots[: max_orgs if max_orgs and max_orgs > 0 else None]:
        if r not in existing:
            existing.add(r)
    state["roots"] = sorted(existing)

    append_artifact(run_id, "amass_roots.txt", "\n".join(state["roots"]))
    return state
