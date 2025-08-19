from __future__ import annotations
import json, uuid, time, tempfile, os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..settings import RUNS_DIR, ARTIFACTS_DIRNAME, GRAPHS_DIRNAME

# ---------------------------- Básicos ----------------------------

def new_run_id() -> str:
    # 12 hex chars, cómodo para carpetas/CLI
    return uuid.uuid4().hex[:12]

def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    (d / ARTIFACTS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (d / GRAPHS_DIRNAME).mkdir(parents=True, exist_ok=True)
    return d

def artifacts_dir(run_id: str) -> Path:
    return run_dir(run_id) / ARTIFACTS_DIRNAME

def graphs_dir(run_id: str) -> Path:
    return run_dir(run_id) / GRAPHS_DIRNAME

# ------------------------- Escrituras seguras ---------------------

def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)

def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)

def save_json(run_id: str, name: str, data: Dict[str, Any]) -> str:
    path = run_dir(run_id) / f"{name}.json"
    _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
    return str(path)

def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

# --------------------------- Artifacts ---------------------------

def artifact_path(run_id: str, filename: str) -> Path:
    return artifacts_dir(run_id) / filename

def write_artifact(run_id: str, filename: str, content: str) -> str:
    p = artifact_path(run_id, filename)
    _atomic_write_text(p, content)
    return str(p)

def write_artifact_bin(run_id: str, filename: str, content: bytes) -> str:
    p = artifact_path(run_id, filename)
    _atomic_write_bytes(p, content)
    return str(p)

# Compatibilidad con tu código previo:
def append_artifact(run_id: str, filename: str, content: str) -> str:
    # Realmente “write/replace”, no append de stream. Mantengo el nombre por compat.
    return write_artifact(run_id, filename, content)

def append_lines(run_id: str, filename: str, lines: Iterable[str]) -> str:
    p = artifact_path(run_id, filename)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for ln in lines:
            if ln.endswith("\n"):
                f.write(ln)
            else:
                f.write(ln + "\n")
    return str(p)

# ----------------------------- Utils -----------------------------

def load_playbook_file(path: str) -> Dict[str, Any]:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def list_artifacts(run_id: str) -> List[str]:
    base = artifacts_dir(run_id)
    if not base.exists():
        return []
    return [str(p.relative_to(base)) for p in base.rglob("*") if p.is_file()]

def now_ts() -> int:
    return int(time.time())
