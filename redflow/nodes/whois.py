from __future__ import annotations
import re
from typing import Dict, Any, List

from ..utils.shell import run_cmd
from ..utils.io import append_artifact
from ..settings import TOOLS, TIMEOUTS

ASN_RE = re.compile(r"\bAS(\d{1,10})\b", re.IGNORECASE)
# Variantes comunes en whois (ARIN, RIPE, LACNIC, APNIC, AFRINIC)
ORGANIZATION_KEYS = [
    "OrgName", "org-name", "organisation", "owner", "descr", "responsible",
    "org", "OrgId", "netname"
]
CIDR_KEYS = ["CIDR", "cidr", "route", "route6", "inetnum", "NetRange", "inet6num"]
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)

def _kv(line: str):
    if ":" in line:
        k, v = line.split(":", 1)
        return k.strip(), v.strip()
    return None, None

def _normalize_prefix(v: str) -> List[str]:
    # puede contener múltiples valores, rutas, etc.
    parts = re.split(r"[,\s]+", v.strip())
    return [p for p in parts if p and ("/" in p or p.count(".") == 3 or ":" in p)]

async def run(state: Dict[str, Any], timeout: int = None) -> Dict[str, Any]:
    timeout = timeout or TIMEOUTS.get("whois", 60)
    target = state.get("target", "")
    if not target:
        state.setdefault("errors", []).append({"node":"whois","error":"missing_target"})
        return state

    cmd = f'{TOOLS.get("whois","whois")} {target}'
    res = await run_cmd(cmd, timeout=timeout)

    if res.stdout:
        append_artifact(state["run_id"], "whois_raw.txt", res.stdout)
    else:
        state.setdefault("errors", []).append({"node":"whois","stderr":res.stderr or "empty_output"})
        return state

    lines = [l.rstrip() for l in res.stdout.splitlines() if l.strip()]
    asns: List[str] = []
    orgs: List[str] = []
    prefixes: List[str] = []
    emails: List[str] = []
    kv_map: Dict[str, List[str]] = {}

    # recolecta claves y valores
    for ln in lines:
        k, v = _kv(ln)
        if k:
            kv_map.setdefault(k, []).append(v)
        # captura ASN en cualquier lado
        for m in ASN_RE.finditer(ln):
            asns.append(m.group(1))
        # emails
        for m in EMAIL_RE.finditer(ln):
            emails.append(m.group(0))

    # organización
    for ok in ORGANIZATION_KEYS:
        if ok in kv_map:
            for vv in kv_map[ok]:
                if vv and vv not in orgs:
                    orgs.append(vv)

    # prefijos / rutas / rangos
    for ck in CIDR_KEYS:
        if ck in kv_map:
            for vv in kv_map[ck]:
                prefixes.extend(_normalize_prefix(vv))

    asns = sorted(set(asns))
    prefixes = sorted(set(prefixes))
    emails = sorted(set(emails))

    # actualiza estado
    state["whois"] = {
        "raw_saved": True,
        "emails": emails,
        "fields": {k: v for k, v in kv_map.items()},
    }
    state["asn"] = {
        "numbers": asns,
        "org": (orgs[0] if orgs else ""),
        "orgs": orgs,
        "prefixes": prefixes,
    }

    # si el target parece dominio, agrégalo a roots como punto de partida
    roots = state.get("roots", [])
    if target and "." in target and target not in roots:
        roots.append(target)
    state["roots"] = roots

    return state
