# redflow/utils/install.py
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .shell import run_cmd_sync


@dataclass
class InstallResult:
    tool: str
    ok: bool
    method: str
    stdout: str
    stderr: str


def _has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def detect_platform() -> str:
    # Muy simple: prioriza Debian/Kali si apt existe; macOS si brew; genérico si nada
    if _has_cmd("apt"):
        return "debian"
    if _has_cmd("brew"):
        return "macos"
    return "generic"


# Mapeo de herramientas -> receta de instalación por plataforma
# - Para Debian/Kali: apt cuando existe paquete conocido; si no, Go.
# - Go: usa 'go install ...@latest'
# - Pip: para utilidades Python como arjun
RECIPES: Dict[str, Dict[str, List[Tuple[str, str]]]] = {
    # tool: { platform: [(method, cmd), ...] }
    "amass": {
        "debian": [("apt", "sudo apt update && sudo apt install -y amass")],
    },
    "assetfinder": {
        "debian": [
            ("apt", "sudo apt update && sudo apt install -y assetfinder"),
            ("go", "go install github.com/tomnomnom/assetfinder@latest"),
        ],
    },
    "dig": {
        "debian": [("apt", "sudo apt update && sudo apt install -y dnsutils")],
    },
    "dnsx": {
        "debian": [("go", "go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest")],
    },
    "ffuf": {
        "debian": [
            ("apt", "sudo apt update && sudo apt install -y ffuf"),
            ("go", "go install github.com/ffuf/ffuf@latest"),
        ],
    },
    "gau": {
        "debian": [("go", "go install github.com/lc/gau/v2/cmd/gau@latest")],
    },
    "gowitness": {
        "debian": [("go", "go install github.com/sensepost/gowitness@latest")],
    },
    "httpx": {
        "debian": [("go", "go install github.com/projectdiscovery/httpx/cmd/httpx@latest")],
    },
    "katana": {
        "debian": [("go", "go install github.com/projectdiscovery/katana/cmd/katana@latest")],
    },
    "naabu": {
        "debian": [
            ("apt", "sudo apt update && sudo apt install -y naabu"),
            ("go", "go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"),
        ],
    },
    "nmap": {
        "debian": [("apt", "sudo apt update && sudo apt install -y nmap")],
    },
    "subfinder": {
        "debian": [("go", "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest")],
    },
    "tlsx": {
        "debian": [("go", "go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest")],
    },
    "wafw00f": {
        "debian": [("apt", "sudo apt update && sudo apt install -y wafw00f")],
    },
    "whatweb": {
        "debian": [("apt", "sudo apt update && sudo apt install -y whatweb")],
    },
    "whois": {
        "debian": [("apt", "sudo apt update && sudo apt install -y whois")],
    },
    "graphviz": {
        "debian": [("apt", "sudo apt update && sudo apt install -y graphviz")],
    },
    "arjun": {
        "debian": [("pip", "python -m pip install -U arjun")],
    },
}

# Herramientas que NO son estrictamente necesarias pero recomendadas (para gráficos/tareas extra)
OPTIONAL_TOOLS = ["graphviz"]


def _ensure_go_available(auto_yes: bool) -> bool:
    if _has_cmd("go"):
        return True
    # Intentar instalar go en Debian
    if detect_platform() == "debian":
        if auto_yes or _confirm("Go (golang) no está instalado. ¿Instalar con apt?"):
            res = run_cmd_sync("sudo apt update && sudo apt install -y golang-go")
            return res.returncode == 0
    return False


def _export_path_hint() -> str:
    return (
        '\n# Sugerencia: añade tu GOPATH/bin al PATH (si aún no lo está)\n'
        'echo \'export GOPATH="$HOME/go"\' >> ~/.zshrc\n'
        'echo \'export PATH="$PATH:$HOME/go/bin"\' >> ~/.zshrc\n'
        'source ~/.zshrc\n'
    )


def _confirm(msg: str) -> bool:
    # Evita dependencia circular con Typer importando localmente
    try:
        import typer
        return typer.confirm(msg, default=True)
    except Exception:
        # Non-interactive: por defecto NO
        return False


def install_missing_tools(missing: List[str], auto_yes: bool = False) -> List[InstallResult]:
    """
    Intenta instalar las herramientas faltantes según RECIPES.
    Devuelve la lista de resultados por herramienta (ok/errores).
    """
    pl = detect_platform()
    results: List[InstallResult] = []

    # Si habrá instalaciones Go, asegura 'go'
    needs_go = any(
        any(method == "go" for method, _ in RECIPES.get(tool, {}).get(pl, []))
        for tool in missing
    )
    if needs_go and not _ensure_go_available(auto_yes):
        results.append(InstallResult(tool="golang-go", ok=False, method="apt", stdout="", stderr="go no disponible"))
        # seguimos, quizá algunas herramientas se cubren por apt

    for tool in missing:
        recipes = RECIPES.get(tool, {}).get(pl, [])
        if not recipes:
            results.append(InstallResult(tool=tool, ok=False, method="none", stdout="", stderr=f"Sin receta para {pl}"))
            continue

        installed = False
        last_stdout = ""
        last_stderr = ""
        last_method = ""
        for method, cmd in recipes:
            last_method = method
            # En instalaciones Go, asegura GOPATH en entorno (runtime)
            env = os.environ.copy()
            if method == "go":
                env.setdefault("GOPATH", os.path.expanduser("~/go"))
                env["PATH"] = env.get("PATH", "") + os.pathsep + os.path.join(env["GOPATH"], "bin")
                # Ejecuta
                res = run_cmd_sync(cmd, timeout=1800)
            else:
                res = run_cmd_sync(cmd, timeout=1800)

            last_stdout, last_stderr = res.stdout, res.stderr
            # Si ahora existe el binario, lo damos por bueno
            if _has_cmd(tool):
                installed = True
                break

        results.append(InstallResult(tool=tool, ok=installed, method=last_method, stdout=last_stdout, stderr=last_stderr))

    # Mensaje de ayuda PATH para Go
    if any(r.method == "go" and r.ok for r in results):
        print(_export_path_hint())

    return results
