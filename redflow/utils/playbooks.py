from __future__ import annotations
from typing import Dict, Any, List, Set
from pathlib import Path

from ..settings import PLAYBOOKS_DIR
from .io import load_playbook_file

REQUIRED_KEYS = ["name", "nodes", "edges"]

def _validate_nodes(nodes: List[Dict[str, Any]]) -> Set[str]:
    ids: Set[str] = set()
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            raise ValueError(f"nodes[{i}] no es un objeto")
        if "id" not in n or "impl" not in n:
            raise ValueError(f"nodes[{i}] requiere 'id' e 'impl'")
        nid = n["id"]
        if not isinstance(nid, str) or not nid:
            raise ValueError(f"nodes[{i}].id inválido")
        if nid in ids:
            raise ValueError(f"ID de nodo duplicado: '{nid}'")
        if not isinstance(n["impl"], str) or not n["impl"]:
            raise ValueError(f"nodes[{i}].impl inválido")
        params = n.get("params", {})
        if params and not isinstance(params, dict):
            raise ValueError(f"nodes[{i}].params debe ser objeto/dict")
        ids.add(nid)
    if not ids:
        raise ValueError("El playbook no define nodos")
    return ids

def _validate_edges(edges: List[Dict[str, Any]], node_ids: Set[str]) -> None:
    if not isinstance(edges, list):
        raise ValueError("edges debe ser una lista")
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            raise ValueError(f"edges[{i}] no es un objeto")
        if "from" not in e or "to" not in e:
            raise ValueError(f"edges[{i}] requiere 'from' y 'to'")
        f, t = e["from"], e["to"]
        if f not in node_ids or t not in node_ids:
            raise ValueError(f"edges[{i}] referencia nodos inexistentes: {f} -> {t}")

def load_playbook(name_or_path: str) -> Dict[str, Any]:
    # permite nombre (“recon-full”) o ruta absoluta/relativa a un YAML
    path: Path
    if name_or_path.endswith((".yaml", ".yml")):
        path = Path(name_or_path)
    else:
        path = PLAYBOOKS_DIR / f"{name_or_path}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"No se encontró el playbook: {path}")

    data = load_playbook_file(str(path))
    for k in REQUIRED_KEYS:
        if k not in data:
            raise ValueError(f"Playbook '{path.name}' sin llave requerida: '{k}'")

    if not isinstance(data["nodes"], list) or not isinstance(data["edges"], list):
        raise ValueError("Las llaves 'nodes' y 'edges' deben ser listas")

    node_ids = _validate_nodes(data["nodes"])
    _validate_edges(data["edges"], node_ids)
    return data
