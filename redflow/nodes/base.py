from typing import Dict, Any, List
from ..utils.shell import run_cmd, CmdResult
from ..settings import DEFAULT_TIMEOUT

async def exec_and_collect(cmd: str, timeout: int = DEFAULT_TIMEOUT) -> CmdResult:
    return await run_cmd(cmd, timeout=timeout)

def normalize_targets(target: str) -> List[str]:
    # admite dominio o archivo
    import os
    if target and os.path.isfile(target):
        return [l.strip() for l in open(target, "r", encoding="utf-8") if l.strip()]
    return [target] if target else []