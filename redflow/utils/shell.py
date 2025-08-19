from __future__ import annotations
import asyncio, os, signal, subprocess
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class CmdResult:
    cmd: str
    code: int
    stdout: str
    stderr: str

async def run_cmd(
    cmd: str,
    timeout: int = 900,
    input_data: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> CmdResult:
    """
    Ejecuta un comando (vía shell) de forma asíncrona.
    - Mata el grupo de procesos si expira el timeout (start_new_session=True).
    - Puedes inyectar stdin con input_data.
    - Puedes ajustar env y cwd.
    """
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE if input_data is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **(env or {})},
        cwd=cwd,
        start_new_session=True,  # crea un nuevo PGID
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input_data.encode("utf-8") if input_data is not None else None),
            timeout=timeout
        )
        return CmdResult(cmd, proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore"))
    except asyncio.TimeoutError:
        # mata todo el grupo (Linux/macOS); fallback a kill del proceso principal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        return CmdResult(cmd, -1, "", f"Timeout after {timeout}s")

def run_cmd_sync(
    cmd: str,
    timeout: int = 900,
    input_data: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> CmdResult:
    """
    Versión síncrona con el mismo comportamiento de entorno y timeout.
    """
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            input=(input_data.encode("utf-8") if input_data is not None else None),
            capture_output=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
            cwd=cwd,
        )
        return CmdResult(cmd, p.returncode, p.stdout.decode(errors="ignore"), p.stderr.decode(errors="ignore"))
    except subprocess.TimeoutExpired:
        return CmdResult(cmd, -1, "", f"Timeout after {timeout}s")
