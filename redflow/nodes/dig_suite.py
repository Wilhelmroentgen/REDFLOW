# redflow/nodes/dig_suite.py
from typing import Dict, List

from ..utils.shell import run_cmd
from ..utils.io import run_dir, append_artifact


async def run(state: Dict, **kwargs) -> Dict:
    run_id = state["run_id"]
    domain = state["target"]
    rdir = run_dir(run_id)

    # ANY
    r_any = await run_cmd(f"dig {domain} any +noall +answer", timeout=120)
    append_artifact(run_id, "dig_any.txt", r_any.stdout or r_any.stderr or "")

    # SPF/DMARC/DKIM TXT
    r_spf = await run_cmd(f"dig txt {domain} +short", timeout=120)
    r_dmarc = await run_cmd(f"dig txt _dmarc.{domain} +short", timeout=120)
    r_dkim = await run_cmd(
        f"dig txt default._domainkey.{domain} +short", timeout=120
    )
    append_artifact(
        run_id,
        "spf_dmarc.txt",
        (r_spf.stdout or "")
        + ("\n" if r_spf.stdout else "")
        + (r_dmarc.stdout or "")
        + ("\n" if r_dmarc.stdout else "")
        + (r_dkim.stdout or ""),
    )

    # NS
    r_ns = await run_cmd(f"dig ns {domain} +short", timeout=120)
    append_artifact(run_id, "ns.txt", r_ns.stdout or r_ns.stderr or "")
    ns_list: List[str] = [
        x.strip().rstrip(".") for x in (r_ns.stdout or "").splitlines() if x.strip()
    ]

    # Attempt AXFR per NS
    axfr_all = []
    for ns in ns_list:
        r_ax = await run_cmd(f"dig AXFR {domain} @{ns}", timeout=120)
        if r_ax.stdout:
            axfr_all.append(f";; AXFR @{ns}\n{r_ax.stdout}")

    if axfr_all:
        append_artifact(run_id, "axfr.txt", "\n\n".join(axfr_all))

    return state
