from __future__ import annotations

from typing import TypedDict, List, Dict, Any, Callable, Awaitable, Optional
from importlib import import_module

from langgraph.graph import StateGraph, END

from .utils.playbooks import load_playbook
from .utils.io import new_run_id, save_json
from .reporters.markdown import write_report
from .utils.ui_registry import get_ui


class RFState(TypedDict, total=False):
    run_id: str
    target: str
    flags: Dict[str, Any]

    # WHOIS / ASN / alcance
    whois: Dict[str, Any]
    asn: Dict[str, Any]
    roots: List[str]
    providers: Dict[str, Any]

    # Subdominios / DNS
    subdomains: List[str]
    resolved: Dict[str, Dict[str, List[str]]]
    alive_hosts: List[str]
    dns_surface: Dict[str, Any]

    # Web / Puertos / Fingerprinting
    httpx: List[Dict[str, Any]]
    ports: Dict[str, List[int]]
    nmap: List[Dict[str, Any]]
    whatweb: Dict[str, Any]
    waf: Dict[str, Any]
    screenshots_dir: str

    # URLs / Parámetros
    urls: List[str]
    params: List[Dict[str, Any]]

    # Fuzzing / Buckets / TLS / IdP
    ffuf_results: List[Dict[str, Any]]
    cloud: Dict[str, Any]
    tls: List[Dict[str, Any]]
    idp: List[Dict[str, Any]]

    # Otros
    artifacts: List[str]
    findings: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]


def _resolve_impl(impl: str) -> Optional[Callable[..., Awaitable[RFState]]]:
    try:
        mod = import_module(f".nodes.{impl}", package=__package__)
        return getattr(mod, "run", None)
    except Exception:
        return None


def _snapshot_safe(run_id: str, name: str, state: RFState) -> None:
    try:
        sanitized: Dict[str, Any] = {k: v for k, v in dict(state).items() if not str(k).startswith("__")}
        save_json(run_id, name, sanitized)
    except Exception:
        pass


def _wrap_node(node_id: str, impl: str, params: Dict[str, Any]):
    async def _runner(state: RFState) -> RFState:
        # UI del registry; si no está, fallback a state["__ui"] por compatibilidad
        ui = get_ui(state.get("run_id")) or state.get("__ui")  # type: ignore[assignment]

        # ---- nodo especial: reporte ----------------------------------------
        if impl == "report":
            if ui:
                ui.start(node_id)
            try:
                write_report(state)
                if ui:
                    ui.finish(node_id)          # finish ANTES del snapshot
                _snapshot_safe(state["run_id"], "state_final", state)
                return state
            except Exception as e:
                state.setdefault("errors", []).append({
                    "node": node_id, "impl": impl, "exception": str(e),
                })
                if ui:
                    ui.fail(node_id, str(e))
                _snapshot_safe(state["run_id"], f"state_after_{node_id}_error", state)
                return state

        # ---- nodo normal ----------------------------------------------------
        fn = _resolve_impl(impl)
        if fn is None:
            msg = "impl_not_found"
            state.setdefault("errors", []).append({"node": node_id, "impl": impl, "error": msg})
            if ui:
                ui.fail(node_id, msg)
            _snapshot_safe(state["run_id"], f"state_after_{node_id}", state)
            return state

        if ui:
            ui.start(node_id)
        try:
            new_state = await fn(state, **(params or {}))
            if ui:
                ui.finish(node_id)      # finish ANTES del snapshot
            _snapshot_safe(state["run_id"], f"state_after_{node_id}", new_state)
            return new_state
        except Exception as e:
            state.setdefault("errors", []).append({
                "node": node_id, "impl": impl, "exception": str(e),
            })
            if ui:
                ui.fail(node_id, str(e))
            _snapshot_safe(state["run_id"], f"state_after_{node_id}_error", state)
            return state

    return _runner


def build_graph_from_playbook(playbook_name: str, target: str):
    pb = load_playbook(playbook_name)
    nodes = pb.get("nodes", [])
    if not nodes:
        raise ValueError("El playbook no define nodos.")

    g = StateGraph(RFState)

    for n in nodes:
        node_id = n["id"]
        impl = n["impl"]
        params = n.get("params", {}) or {}
        g.add_node(node_id, _wrap_node(node_id, impl, params))

    g.set_entry_point(nodes[0]["id"])

    for e in pb.get("edges", []):
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            raise ValueError("Cada edge debe ser un objeto con claves 'from' y 'to'.")
        g.add_edge(e["from"], e["to"])

    g.add_edge(nodes[-1]["id"], END)
    return g.compile()


def init_state(target: str) -> RFState:
    return RFState(
        run_id=new_run_id(),
        target=target,
        flags={},

        whois={},
        asn={},
        roots=[],
        providers={},

        subdomains=[],
        resolved={},
        alive_hosts=[],
        dns_surface={},

        httpx=[],
        ports={},
        nmap=[],
        whatweb={},
        waf={},
        screenshots_dir="",

        urls=[],
        params=[],

        ffuf_results=[],
        cloud={},
        tls=[],
        idp=[],

        artifacts=[],
        findings=[],
        errors=[],
    )
