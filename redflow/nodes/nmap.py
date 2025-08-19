from __future__ import annotations
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict
import xml.etree.ElementTree as ET

from ..utils.shell import run_cmd
from ..utils.io import append_artifact, run_dir
from ..settings import TOOLS, TIMEOUTS

def _parse_nmap_xml(xml_text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    root = ET.fromstring(xml_text)
    for host in root.findall("host"):
        addr_el = host.find("address")
        if addr_el is None:
            continue
        ip = addr_el.attrib.get("addr")
        if not ip:
            continue
        for p in host.findall("./ports/port"):
            proto = p.attrib.get("protocol", "tcp")
            portid = p.attrib.get("portid")
            st = p.find("state")
            if st is None or st.attrib.get("state") != "open":
                continue
            svc = p.find("service")
            entry = {
                "host": ip,
                "protocol": proto,
                "port": int(portid) if portid and portid.isdigit() else portid,
                "service": svc.attrib.get("name") if svc is not None else None,
                "product": svc.attrib.get("product") if svc is not None else None,
                "version": svc.attrib.get("version") if svc is not None else None,
                "extrainfo": svc.attrib.get("extrainfo") if svc is not None else None,
            }
            out.append(entry)
    return out

async def run(
    state: Dict[str, Any],
    top_ports: int = 100,
    stealth: bool = True,
    service_fp: bool = True,
    treat_down_as_up: bool = True
) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    art = rdir / "artifacts"
    subs_alive = art / "subs_alive.txt"

    flags = state.get("flags", {})
    resume = bool(flags.get("resume"))
    force = bool(flags.get("force"))

    out_xml = art / "nmap_top.xml"
    out_norm = art / "nmap_top.nmap"

    if resume and not force and out_xml.exists():
        xml_text = out_xml.read_text(encoding="utf-8", errors="ignore")
        try:
            parsed = _parse_nmap_xml(xml_text)
            state["nmap"] = (state.get("nmap") or []) + parsed
            # Refuerza state.ports
            merged = state.get("ports", {}) or {}
            by_host: DefaultDict[str, set] = defaultdict(set)
            for r in parsed:
                by_host[r["host"]].add(int(r["port"]))
            for h, ps in by_host.items():
                merged.setdefault(h, [])
                merged[h] = sorted(set(merged[h] + list(ps)))
            state["ports"] = merged
        except Exception as e:
            state.setdefault("errors", []).append({"node":"nmap","parse_error":str(e)})
        return state

    # Entrada
    if not subs_alive.exists():
        inputs: List[str] = []
        if state.get("alive_hosts"):
            inputs = state["alive_hosts"]
        elif state.get("target"):
            inputs = [state["target"]]
        if not inputs:
            return state
        targets = " ".join(inputs)
        cmd = f'{TOOLS.get("nmap","nmap")} --top-ports {top_ports} {targets}'
    else:
        cmd = f'{TOOLS.get("nmap","nmap")} -iL "{subs_alive}" --top-ports {top_ports}'

    if stealth:
        cmd += " -sS -T2"
    if service_fp:
        cmd += " -sV"
    if treat_down_as_up:
        cmd += " -Pn"
    # Salidas: XML a stdout, normal a archivo
    cmd += f' -oX - -oN "{out_norm}"'

    res = await run_cmd(cmd, timeout=TIMEOUTS.get("nmap", 3600))
    if res.code != 0 or not res.stdout:
        state.setdefault("errors", []).append({"node":"nmap","stderr":res.stderr or "empty_output"})
        return state

    append_artifact(state["run_id"], "nmap_top.xml", res.stdout)

    try:
        parsed = _parse_nmap_xml(res.stdout)
        state["nmap"] = (state.get("nmap") or []) + parsed
        merged = state.get("ports", {}) or {}
        by_host: DefaultDict[str, set] = defaultdict(set)
        for r in parsed:
            by_host[r["host"]].add(int(r["port"]))
        for h, ps in by_host.items():
            merged.setdefault(h, [])
            merged[h] = sorted(set(merged[h] + list(ps)))
        state["ports"] = merged
    except Exception as e:
        state.setdefault("errors", []).append({"node":"nmap","parse_error":str(e)})

    return state
