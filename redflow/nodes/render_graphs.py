from __future__ import annotations
import os
import re
from typing import Dict, Any, List, DefaultDict
from collections import Counter, defaultdict
from pathlib import Path

# matplotlib para PNGs (backend headless)
import matplotlib
matplotlib.use("Agg")  # importante para entornos sin display
import matplotlib.pyplot as plt

from ..utils.io import run_dir
from ..settings import GRAPHS_DIRNAME

def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _bar_chart(save_to: Path, labels: List[str], values: List[int], title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(len(values)), values)  # sin colores específicos
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(save_to)
    plt.close(fig)

def _pie_or_bar_tls(save_to: Path, counts: Dict[str, int]):
    # si hay pocos items, pie; si hay muchos, bar
    items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    labels = [k for k,_ in items]
    values = [v for _,v in items]
    if len(labels) <= 6 and sum(values) > 0:
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.pie(values, labels=labels, autopct=lambda p: f"{p:.0f}%")
        ax.set_title("TLS versions")
        fig.tight_layout()
        fig.savefig(save_to)
        plt.close(fig)
    else:
        _bar_chart(save_to, labels, values, "TLS versions", "Version", "Count")

def _domain_levels(domain: str) -> List[str]:
    # ejemplo: a.b.c.example.com -> ["example.com","c.example.com","b.c.example.com","a.b.c.example.com"]
    parts = domain.split(".")
    if len(parts) < 2:
        return []
    levels = []
    for i in range(len(parts)-2, -1, -1):
        levels.append(".".join(parts[i:]))
    return levels

def _build_subdomain_tree(subs: List[str]) -> Dict[str, List[str]]:
    # simple árbol: padre -> [hijos]
    tree: DefaultDict[str, set] = defaultdict(set)
    for s in subs:
        lvls = _domain_levels(s)
        for i in range(len(lvls)-1):
            parent = lvls[i+1]
            child = lvls[i]
            if parent != child:
                tree[parent].add(child)
    return {k: sorted(list(v)) for k, v in tree.items()}

def _write_dot(tree: Dict[str, List[str]], save_to: Path):
    # DOT directed graph
    lines = ["digraph subdomains {", '  rankdir=LR;']
    for parent, children in tree.items():
        p = parent.replace("-", "_").replace(":", "_")
        for ch in children:
            c = ch.replace("-", "_").replace(":", "_")
            lines.append(f'  "{parent}" -> "{ch}";')
    lines.append("}")
    save_to.write_text("\n".join(lines), encoding="utf-8")

def _try_graphviz(dot_path: Path, svg_path: Path) -> bool:
    # intenta usar 'dot' del paquete graphviz para generar svg
    try:
        import subprocess
        r = subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(svg_path)], capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and svg_path.exists()
    except Exception:
        return False

async def run(state: Dict[str, Any], top_ports: int = 12, top_tech: int = 20) -> Dict[str, Any]:
    rdir = run_dir(state["run_id"])
    gdir = _ensure_dir(rdir / GRAPHS_DIRNAME)

    # ---------- Ports chart ----------
    port_counter = Counter()
    for host, plist in (state.get("ports") or {}).items():
        for p in plist:
            if isinstance(p, int):
                port_counter[p] += 1
            else:
                # por si quedó texto
                try:
                    port_counter[int(p)] += 1
                except Exception:
                    pass
    if port_counter:
        items = port_counter.most_common(top_ports)
        labels = [str(k) for k, _ in items]
        values = [v for _, v in items]
        _bar_chart(gdir / "ports_top.png", labels, values, "Top open ports", "Port", "Hosts")

    # ---------- HTTP status chart ----------
    status_counter = Counter()
    for it in (state.get("httpx") or []):
        st = it.get("status")
        if isinstance(st, int):
            status_counter[st] += 1
    if status_counter:
        items = sorted(status_counter.items(), key=lambda x: x[0])
        labels = [str(k) for k,_ in items]
        values = [v for _,v in items]
        _bar_chart(gdir / "http_status.png", labels, values, "HTTP status distribution", "Status", "Count")

    # ---------- Tech stack (whatweb + httpx tech) ----------
    tech_counter = Counter()
    # whatweb
    for host, techs in (state.get("whatweb") or {}).items():
        for t in techs or []:
            if isinstance(t, str) and t:
                tech_counter[t] += 1
    # httpx tech/webserver puede venir como str/list/dict
    for it in (state.get("httpx") or []):
        tech = it.get("tech")
        if isinstance(tech, str):
            tech_counter[tech] += 1
        elif isinstance(tech, list):
            for t in tech:
                if isinstance(t, str):
                    tech_counter[t] += 1
        elif isinstance(tech, dict):
            for k in tech.keys():
                tech_counter[k] += 1
    if tech_counter:
        items = tech_counter.most_common(top_tech)
        labels = [k[:30] + ("…" if len(k) > 30 else "") for k,_ in items]
        values = [v for _,v in items]
        _bar_chart(gdir / "tech_stack.png", labels, values, "Detected technologies", "Tech", "Hosts")

    # ---------- TLS versions ----------
    tls_counter = Counter()
    for r in (state.get("tls") or []):
        v = r.get("version")
        if isinstance(v, str) and v:
            tls_counter[v] += 1
    if tls_counter:
        _pie_or_bar_tls(gdir / "tls_versions.png", dict(tls_counter))

    # ---------- WAF presence ----------
    waf_counter = Counter()
    waf_map: Dict[str, str] = state.get("waf") or {}
    if isinstance(waf_map, dict):
        for host, waf in waf_map.items():
            if waf and isinstance(waf, str):
                waf_counter[waf] += 1
    if waf_counter:
        items = waf_counter.most_common(12)
        labels = [k for k,_ in items]
        values = [v for _,v in items]
        _bar_chart(gdir / "waf_presence.png", labels, values, "WAF presence", "WAF", "Hosts")

    # ---------- Subdomain tree (DOT + SVG si hay graphviz) ----------
    subs = state.get("subdomains") or []
    if subs:
        tree = _build_subdomain_tree(subs)
        dot_path = gdir / "subdomain_tree.dot"
        _write_dot(tree, dot_path)
        svg_path = gdir / "subdomain_tree.svg"
        if not _try_graphviz(dot_path, svg_path):
            # si no hay graphviz, al menos deja el .dot
            pass

    # no escribimos nada concreto al estado; el reporte los referenciará por nombre
    return state
