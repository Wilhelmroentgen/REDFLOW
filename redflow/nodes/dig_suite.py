from __future__ import annotations
from typing import Dict, Any, List
from ..utils.shell import run_cmd
from ..utils.io import append_artifact
from ..settings import TOOLS, TIMEOUTS

async def _run(cmd: str, to_key: str, state: Dict[str, Any], timeout: int):
    res = await run_cmd(cmd, timeout=timeout)
    if res.stdout:
        append_artifact(state["run_id"], to_key, res.stdout)
        return res.stdout
    else:
        state.setdefault("errors", []).append({"node":"dig_suite","cmd":cmd,"stderr":res.stderr})
        return ""

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    domain = state.get("target", "")
    if not domain or "." not in domain:
        # Para IPs no aplica esta suite
        return state

    timeout = TIMEOUTS.get("dnsx", 600)
    dig = TOOLS.get("dig","dig")

    # ANY
    any_txt = await _run(f'{dig} {domain} any -noall -answer', "dig_any.txt", state, timeout)

    # TXT (SPF/DMARC)
    spf_dmarc = await _run(f'{dig} txt {domain} +short', "spf_dmarc.txt", state, timeout)

    # DKIM default
    dkim = await _run(f'{dig} txt default._domainkey.{domain} +short', "dkim_default.txt", state, timeout)

    # NS
    ns_raw = await _run(f'{dig} ns {domain} +short', "ns.txt", state, timeout)
    ns_list = [l.strip().rstrip(".") for l in ns_raw.splitlines() if l.strip()]

    # AXFR para cada NS
    axfr_results: List[Dict[str, Any]] = []
    for ns in ns_list:
        cmd = f'{dig} axfr {domain} @{ns}'
        out = await _run(cmd, f'axfr_{ns}.txt', state, timeout)
        axfr_results.append({"ns": ns, "ok": bool(out.strip()), "lines": len(out.splitlines()) if out else 0})

    # Guarda en state.dns_surface
    state["dns_surface"] = {
        "any": any_txt.splitlines() if any_txt else [],
        "spf_dmarc": spf_dmarc.splitlines() if spf_dmarc else [],
        "dkim_default": dkim.splitlines() if dkim else [],
        "ns": ns_list,
        "axfr": axfr_results
    }
    return state
