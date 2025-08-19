from __future__ import annotations
import os
from pathlib import Path

# --------------------------------------------------------------------------------------
# Rutas base
# --------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
PLAYBOOKS_DIR = ROOT / "playbooks"
TEMPLATES_DIR = ROOT / "templates"   # opcional
# Nuevo: directorio de runs fuera del paquete (sobre-escribible por env)
DEFAULT_RUNS = Path.home() / ".local" / "share" / "redflow" / "runs"
RUNS_DIR = Path(os.environ.get("REDFLOW_RUNS_DIR", DEFAULT_RUNS))
RUNS_DIR.mkdir(parents=True, exist_ok=True)

for d in (PLAYBOOKS_DIR, RUNS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Helpers para override por variables de entorno
#   Ej: export REDFLOW_TOOL_NMAP="/opt/nmap/bin/nmap"
# --------------------------------------------------------------------------------------
def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)

def _tool(name: str, default_bin: str) -> str:
    return _env(f"REDFLOW_TOOL_{name.upper()}", default_bin)

# --------------------------------------------------------------------------------------
# Binarios requeridos (núcleo del pipeline de recon)
#   El CLI 'check' verificará estos. Añade/quita según tu entorno.
# --------------------------------------------------------------------------------------
TOOLS = {
    "whois":      _tool("whois", "whois"),
    "amass":      _tool("amass", "amass"),
    "subfinder":  _tool("subfinder", "subfinder"),
    "assetfinder":_tool("assetfinder", "assetfinder"),
    "dnsx":       _tool("dnsx", "dnsx"),
    "httpx":      _tool("httpx", "httpx"),
    "naabu":      _tool("naabu", "naabu"),
    "nmap":       _tool("nmap", "nmap"),
    "whatweb":    _tool("whatweb", "whatweb"),
    "wafw00f":    _tool("wafw00f", "wafw00f"),
    "gowitness":  _tool("gowitness", "gowitness"),
    "gau":        _tool("gau", "gau"),
    "katana":     _tool("katana", "katana"),
    "arjun":      _tool("arjun", "arjun"),
    "ffuf":       _tool("ffuf", "ffuf"),
    "tlsx":       _tool("tlsx", "tlsx"),
    "dig":        _tool("dig", "dig"),
}

# --------------------------------------------------------------------------------------
# Timeouts (segundos). Cada nodo puede elegir el suyo; estos son valores razonables.
# --------------------------------------------------------------------------------------
DEFAULT_TIMEOUT = int(_env("REDFLOW_TIMEOUT", "900"))
TIMEOUTS = {
    "whois":     int(_env("REDFLOW_TIMEOUT_WHOIS", "60")),
    "amass":     int(_env("REDFLOW_TIMEOUT_AMASS", "900")),
    "subfinder": int(_env("REDFLOW_TIMEOUT_SUBFINDER", "600")),
    "assetfinder": int(_env("REDFLOW_TIMEOUT_ASSETFINDER", "300")),
    "dnsx":      int(_env("REDFLOW_TIMEOUT_DNSX", "600")),
    "httpx":     int(_env("REDFLOW_TIMEOUT_HTTPX", "900")),
    "naabu":     int(_env("REDFLOW_TIMEOUT_NAABU", "900")),
    "nmap":      int(_env("REDFLOW_TIMEOUT_NMAP", "3600")),
    "whatweb":   int(_env("REDFLOW_TIMEOUT_WHATWEB", "600")),
    "wafw00f":   int(_env("REDFLOW_TIMEOUT_WAFW00F", "600")),
    "gowitness": int(_env("REDFLOW_TIMEOUT_GOWITNESS", "1800")),
    "gau":       int(_env("REDFLOW_TIMEOUT_GAU", "1200")),
    "katana":    int(_env("REDFLOW_TIMEOUT_KATANA", "1200")),
    "arjun":     int(_env("REDFLOW_TIMEOUT_ARJUN", "1800")),
    "ffuf":      int(_env("REDFLOW_TIMEOUT_FFUF", "1800")),
    "tlsx":      int(_env("REDFLOW_TIMEOUT_TLSX", "900")),
    "idp":       int(_env("REDFLOW_TIMEOUT_IDP", "600")),
}

# --------------------------------------------------------------------------------------
# Límites de concurrencia (semaphores) por familia de tareas
#   Útiles para no saturar targets ni tu máquina. Ajusta a gusto.
# --------------------------------------------------------------------------------------
SEM_LIMITS = {
    "dns":      int(_env("REDFLOW_SEM_DNS", "16")),   # dnsx / dig
    "http":     int(_env("REDFLOW_SEM_HTTP", "32")),  # httpx / whatweb / katana / gau
    "ports":    int(_env("REDFLOW_SEM_PORTS", "6")),  # naabu / nmap
    "screens":  int(_env("REDFLOW_SEM_SCREENS", "3")),# gowitness
    "ffuf":     int(_env("REDFLOW_SEM_FFUF", "4")),   # fuzzing web
}

# --------------------------------------------------------------------------------------
# Defaults & heurísticas compartidas por nodos
# --------------------------------------------------------------------------------------
DEFAULT_RESOLVER = _env("REDFLOW_RESOLVER", "1.1.1.1")
SECLISTS_DIR = _env("REDFLOW_SECLISTS_DIR", "/usr/share/wordlists/seclists")
FFUF_DEFAULT_WORDLIST = _env(
    "REDFLOW_FFUF_WORDLIST",
    f"{SECLISTS_DIR}/Discovery/Web-Content/raft-medium-directories.txt"
)
KATANA_DEPTH = int(_env("REDFLOW_KATANA_DEPTH", "2"))

# Prioridades para decidir dónde profundizar (fuzzing, screenshots, etc.)
HTTPX_PRIORITY_CODES = {200, 204, 301, 302, 401, 403}
PRIORITY_PORTS_WEB = {80, 443, 8080, 8443}

# --------------------------------------------------------------------------------------
# Reportes / logging
# --------------------------------------------------------------------------------------
REPORT_TITLE = _env("REDFLOW_REPORT_TITLE", "RedFlow Recon Report")
LOG_LEVEL = _env("REDFLOW_LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR

# Nombre de archivo para restricción de alcance (si se usa --allowlist)
ALLOWLIST_FILENAME = "scope.yaml"

# Opcional: nombres de subcarpetas estándar dentro de cada run
ARTIFACTS_DIRNAME = "artifacts"
GRAPHS_DIRNAME = "graphs"
