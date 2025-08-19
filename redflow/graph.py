from __future__ import annotations

from typing import TypedDict, List, Dict, Any, Callable, Awaitable, Optional
from importlib import import_module

from langgraph.graph import StateGraph, END

from .utils.playbooks import load_playbook
from .utils.io import new_run_id, save_json
from .reporters.markdown import write_report


# ---------------------------------------------------------------------
# Estado global del workflow (ajústalo según tus nodos)
# ---------------------------------------------------------------------
class RFState(TypedDict, total=False):
    run_id: str
    target: str

    # Flags de ejecución
    flags: Dict[str, Any]            # p.ej. {"resume": True, "force": False}

    # WHOIS / ASN / alcance
    whois: Dict[str, Any]
    asn: Dict[str, Any]              # {"number": "...", "org": "...", "prefixes": [...]}
    roots: List[str]                 # dominios raíz detectados
    providers: Dict[str, Any]        # CDN/Proveedores inferidos

    # Subdominios / DNS
    subdomains: List[str]
    resolved: Dict[str, Dict[str, List[str]]]  # {"sub": {"A":[...], "AAAA":[...], "CNAME":[...]} }
    alive_hosts: List[str]
    dns_surface: Dict[str, Any]      # dig outputs (spf, dkim, ns, axfr resultados)

    # Web / Puertos / Fingerprinting
    httpx: List[Dict[str, Any]]      # JSONL parseado
    ports: Dict[str, List[int]]      # {"host/ip":[80,443,...]}
    nmap: List[Dict[str, Any]]       # parse normalizado (opcional)
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

    # UI (inyectado por CLI si está disponible)
    __ui: Any


# ---------------------------------------------------------------------
# Carga dinámica de implementaciones: .nodes.<impl>.run(state, **params)
# Cada archivo en redflow/nodes/<impl>.py debe exponer: async def run(...)
# ---------------------------------------------------------------------
def _resolve_impl(impl: str) -> Optional[Callable[..., Awaitable[RFState]]]:
    """
    Resuelve 'impl' a una corrutina .run en redflow.nodes.<impl>.
    Si no existe el módulo/función, devuelve None y el wrapper lo manejará.
    """
    try:
        mod = import_module(f".nodes.{impl}", package=__package__)
        fn = getattr(mod, "run", None)
        return fn
    except Exception:
        return None


def _wrap_node(node_id: str, impl: str, params: Dict[str, Any]):
    """
    Envuelve cada nodo para:
    - notificar al UI (start/finish/fail),
    - ejecutar la corrutina del nodo,
    - capturar errores,
    - guardar snapshots del estado tras cada paso,
    - manejar el nodo 'report' como caso especial (sin módulo).
    """
    async def _runner(state: RFState) -> RFState:
        ui = state.get("__ui", None)

        # Nodo especial de reporte (no requiere módulo)
        if impl == "report":
            if ui:
                ui.start(node_id)
            try:
                write_report(state)
                save_json(state["run_id"], "state_final", dict(state))
                if ui:
                    ui.finish(node_id)
                return state
            except Exception as e:
                state.setdefault("errors", []).append({
                    "node": node_id,
                    "impl": impl,
                    "exception": str(e),
                })
                save_json(state["run_id"], f"state_after_{node_id}_error", dict(state))
                if ui:
                    ui.fail(node_id, str(e))
                return state

        # Nodo normal con implementación
        fn = _resolve_impl(impl)
        if fn is None:
            # No existe impl -> registrar error, snapshot y avisar UI
            err_msg = "impl_not_found"
            state.setdefault("errors", []).append({
                "node": node_id,
                "impl": impl,
                "error": err_msg
            })
            save_json(state["run_id"], f"state_after_{node_id}", dict(state))
            if ui:
                ui.fail(node_id, err_msg)
            return state

        # Ejecutar el nodo real
        if ui:
            ui.start(node_id)
        try:
            new_state = await fn(state, **(params or {}))
            # Guardar progreso tras éxito
            save_json(state["run_id"], f"state_after_{node_id}", dict(new_state))
            if ui:
                ui.finish(node_id)
            return new_state
        except Exception as e:
            state.setdefault("errors", []).append({
                "node": node_id,
                "impl": impl,
                "exception": str(e),
            })
            save_json(state["run_id"], f"state_after_{node_id}_error", dict(state))
            if ui:
                ui.fail(node_id, str(e))
            return state

    return _runner


# ---------------------------------------------------------------------
# Construcción del grafo desde un playbook YAML
#   - nodes: [{id, impl, params?}]
#   - edges: [{from, to}]
# El entry point será el primer 'id' en pb["nodes"].
# ---------------------------------------------------------------------
def build_graph_from_playbook(playbook_name: str, target: str):
    pb = load_playbook(playbook_name)
    g = StateGraph(RFState)

    # Registrar nodos
    nodes = pb.get("nodes", [])
    if not nodes:
        raise ValueError("El playbook no define nodos.")

    for n in nodes:
        node_id = n["id"]
        impl = n["impl"]
        params = n.get("params", {}) or {}
        g.add_node(node_id, _wrap_node(node_id, impl, params))

    # Entry y edges
    g.set_entry_point(nodes[0]["id"])

    for e in pb.get("edges", []):
        # Formato esperado: {from: <id>, to: <id>}
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            raise ValueError("Cada edge debe ser un objeto con claves 'from' y 'to'.")
        g.add_edge(e["from"], e["to"])

    # Asegura END tras el último nodo (por si el playbook no lo añade)
    last_id = nodes[-1]["id"]
    g.add_edge(last_id, END)

    return g.compile()


# ---------------------------------------------------------------------
# Estado inicial por target
# ---------------------------------------------------------------------
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
