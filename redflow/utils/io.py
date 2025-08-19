# redflow/utils/io.py
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from ..settings import RUNS_DIR


def new_run_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "artifacts").mkdir(parents=True, exist_ok=True)
    (d / "graphs").mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write_text(path: Path, content: str) -> None:
    """
    Atomic-ish write: create temp file in the SAME directory, then replace.
    Avoids cross-device link errors when /tmp is a different filesystem.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, encoding="utf-8", dir=str(path.parent)
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    try:
        tmp_path.replace(path)  # atomic on same filesystem
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", delete=False, dir=str(path.parent)
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    try:
        tmp_path.replace(path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def save_json(run_id: str, name: str, data: Dict[str, Any]) -> str:
    path = run_dir(run_id) / f"{name}.json"
    _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
    return str(path)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_artifact(run_id: str, filename: str, content: str) -> str:
    p = run_dir(run_id) / "artifacts" / filename
    _atomic_write_text(p, content)
    return str(p)


def now_ts() -> int:
    import time
    return int(time.time())
