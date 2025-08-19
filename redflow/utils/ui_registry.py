# redflow/utils/ui_registry.py
from __future__ import annotations
from typing import Any, Dict, Optional

# Registro global muy simple: run_id -> objeto UI
_REGISTRY: Dict[str, Any] = {}

def set_ui(run_id: str, ui: Any) -> None:
    _REGISTRY[run_id] = ui

def get_ui(run_id: Optional[str]) -> Optional[Any]:
    if not run_id:
        return None
    return _REGISTRY.get(run_id)

def clear_ui(run_id: str) -> None:
    _REGISTRY.pop(run_id, None)