from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path

from ..utils.io import run_dir
from ..settings import REPORT_TITLE, GRAPHS_DIRNAME, ARTIFACTS_DIRNAME

def _rel(p: Path, base: Path) -> str:
    try:
        return str(p.relative_to(base))
    except Exception:
        return str(p)

def _section(title: str) -> str:
    return f"\n## {title}\n"

def render_md(state: Dict[str, Any]) -> str:
    rdir = run_dir(state["run_id"])
    art = rdir / ARTIFACTS_DIRNAME
    gdir = rdir / GRAPHS_DIRNAME

    lines: List[str] = []
    lines.append(f"# {REPORT_TITLE}")
    lines.append(f"**Run:** `{state['run_id']}`  \n**Target:** `{state.get('target','')}`")

    # Índice
    lines.append("\n**Contenido:**")
    lines.append("- [Resumen](#resumen)")
    lines.append("- [Subdominios y DNS](#subdominios-y-dns)")
    lines.append("- [HTTP y Tecnologías](#http-y-tecnologías)")
    lines.append("- [Puertos y Servicios](#puertos-y-servicios)")
    lines.append("- [TLS/Certificados](#tlscertificados)")
    lines.append("- [WAF y Screenshots](#waf-y-screenshots)")
    lines.append("- [URLs y Parámetros](#urls-y-parámetros)")
    lines.append("- [Fuzzing de Rutas](#fuzzing-de-rutas)")
    lines.append("- [IdP / SSO Footprint](#idp--sso-footprint)")
    lines.append("- [Evidencias (Artifacts)](#evidencias-artifacts)")

    # ---------- Resumen ----------
    lines.append("\n### Resumen")
    subs = state.get("subdomains") or []
    alive = state.get("alive_hosts") or []
    httpx = state.get("httpx") or []
    ports = state.get("ports") or {}
    tls = state.get("tls") or []
    ffuf = state.get("ffuf_results") or []
    lines.append(f"- Subdominios: **{len(subs)}**")
    lines.append(f"- Hosts vivos (DNS): **{len(alive)}**")
    lines.append(f"- Endpoints HTTP analizados: **{len(httpx)}**")
    lines.append(f"- Hosts con puertos abiertos: **{len(ports)}**")
    lines.append(f"- Registros TLS: **{len(tls)}**")
    lines.append(f"- Hallazgos FFUF: **{len(ffuf)}**")

    # ---------- Subdominios y DNS ----------
    lines.append(_section("Subdominios y DNS"))
    if (gdir / "subdomain_tree.svg").exists():
        lines.append(f"![Árbol de subdominios]({_rel(gdir / 'subdomain_tree.svg', rdir)})")
    elif (gdir / "subdomain_tree.dot").exists():
        lines.append(f"> Árbol de subdominios en DOT: `{_rel(gdir / 'subdomain_tree.dot', rdir)}`")
    # DNS surface
    dns_surface = state.get("dns_surface") or {}
    ns_list = dns_surface.get("ns") or []
    axfr = dns_surface.get("axfr") or []
    if ns_list:
        lines.append(f"- NS: {', '.join(ns_list)}")
    if axfr:
        ok_ns = [a['ns'] for a in axfr if a.get('ok')]
        if ok_ns:
            lines.append(f"**¡Transferencia AXFR exitosa!** NS vulnerables: {', '.join(ok_ns)}")

    # ---------- HTTP y Tecnologías ----------
    lines.append(_section("HTTP y Tecnologías"))
    if (gdir / "http_status.png").exists():
        lines.append(f"![HTTP status]({_rel(gdir / 'http_status.png', rdir)})")
    if (gdir / "tech_stack.png").exists():
        lines.append(f"![Tech stack]({_rel(gdir / 'tech_stack.png', rdir)})")

    # ---------- Puertos y Servicios ----------
    lines.append(_section("Puertos y Servicios"))
    if (gdir / "ports_top.png").exists():
        lines.append(f"![Top ports]({_rel(gdir / 'ports_top.png', rdir)})")
    # top servicios (breve)
    nmap = state.get("nmap") or []
    svc_counter = {}
    for r in nmap:
        name = r.get("service") or "unknown"
        svc_counter[name] = svc_counter.get(name, 0) + 1
    if svc_counter:
        tops = sorted(svc_counter.items(), key=lambda x: (-x[1], x[0]))[:10]
        lines.append("- Servicios más comunes: " + ", ".join([f"{k} ({v})" for k,v in tops]))

    # ---------- TLS/Certificados ----------
    lines.append(_section("TLS/Certificados"))
    if (gdir / "tls_versions.png").exists():
        lines.append(f"![TLS versions]({_rel(gdir / 'tls_versions.png', rdir)})")

    # ---------- WAF y Screenshots ----------
    lines.append(_section("WAF y Screenshots"))
    if (gdir / "waf_presence.png").exists():
        lines.append(f"![WAF presence]({_rel(gdir / 'waf_presence.png', rdir)})")
    screens = (art / "screens")
    if screens.exists():
        imgs = sorted([p for p in screens.iterdir() if p.suffix.lower() in (".png",".jpg",".jpeg",".webp")])
        if imgs:
            lines.append("\n**Muestras de screenshots (primeros 6):**")
            for p in imgs[:6]:
                lines.append(f"![{p.name}]({_rel(p, rdir)})")

    # ---------- URLs y Parámetros ----------
    lines.append(_section("URLs y Parámetros"))
    urls_total = art / "urls_total.txt"
    params_txt = art / "params.txt"
    if urls_total.exists():
        total = sum(1 for _ in urls_total.read_text(encoding="utf-8", errors="ignore").splitlines() if _)
        lines.append(f"- URLs totales: **{total}** (`{_rel(urls_total, rdir)}`)")
    if params_txt.exists():
        lines.append(f"- Parámetros (Arjun): `{_rel(params_txt, rdir)}`")

    # ---------- Fuzzing de Rutas ----------
    lines.append(_section("Fuzzing de Rutas"))
    ff = state.get("ffuf_results") or []
    if ff:
        # muestra sólo algunos
        sample = ff[:20]
        for r in sample:
            lines.append(f"- {r.get('status')} {r.get('url')} (len={r.get('length')}, w={r.get('words')}, l={r.get('lines')})")
        if len(ff) > 20:
            lines.append(f"*… y {len(ff)-20} más*")

    # ---------- IdP / SSO Footprint ----------
    lines.append(_section("IdP / SSO Footprint"))
    idp_fp = (art / "idp_footprint.jsonl")
    if idp_fp.exists():
        lines.append(f"Resultados: `{_rel(idp_fp, rdir)}`  \n(Evaluar endpoints OIDC/ADFS/AzureAD/Okta según títulos/paths).")

    # ---------- Evidencias (Artifacts) ----------
    lines.append(_section("Evidencias (Artifacts)"))
    lines.append(f"- Carpeta de artifacts: `{_rel(art, rdir)}`")
    if (art / "whois_raw.txt").exists():
        lines.append(f"  - WHOIS: `{_rel(art / 'whois_raw.txt', rdir)}`")
    if (art / "asn_roots.txt").exists():
        lines.append(f"  - Amass ASN roots: `{_rel(art / 'asn_roots.txt', rdir)}`")
    if (art / "subs_all.txt").exists():
        lines.append(f"  - Subdominios (unificados): `{_rel(art / 'subs_all.txt', rdir)}`")
    if (art / "subs_alive.txt").exists():
        lines.append(f"  - Subdominios vivos: `{_rel(art / 'subs_alive.txt', rdir)}`")
    if (art / "httpx_summary.jsonl").exists():
        lines.append(f"  - HTTPX: `{_rel(art / 'httpx_summary.jsonl', rdir)}`")
    if (art / "naabu_top.jsonl").exists():
        lines.append(f"  - Naabu: `{_rel(art / 'naabu_top.jsonl', rdir)}`")
    if (art / "nmap_top.xml").exists():
        lines.append(f"  - Nmap XML: `{_rel(art / 'nmap_top.xml', rdir)}`")
    if (art / "whatweb.json").exists() or (art / "whatweb.txt").exists():
        lines.append(f"  - WhatWeb: `{_rel(art / ('whatweb.json' if (art / 'whatweb.json').exists() else 'whatweb.txt'), rdir)}`")
    if (art / "waf.txt").exists():
        lines.append(f"  - WAFW00F: `{_rel(art / 'waf.txt', rdir)}`")
    if (art / "urls_total.txt").exists():
        lines.append(f"  - URLs totales: `{_rel(art / 'urls_total.txt', rdir)}`")
    if (art / "tls_meta.jsonl").exists():
        lines.append(f"  - TLSX: `{_rel(art / 'tls_meta.jsonl', rdir)}`")

    # Errores
    errs = state.get("errors") or []
    if errs:
        lines.append(_section("Errores"))
        for e in errs[:50]:
            lines.append(f"- {e}")

    lines.append("\n---\n*Generado por RedFlow.*\n")
    return "\n".join(lines)

def write_report(state: Dict[str, Any]) -> str:
    out = render_md(state)
    path = run_dir(state["run_id"]) / "report.md"
    path.write_text(out, encoding="utf-8")
    return str(path)
