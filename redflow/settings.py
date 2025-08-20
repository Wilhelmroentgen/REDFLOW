# redflow/settings.py
from __future__ import annotations
import os
from pathlib import Path

# --------------------------------------------------------------------------------------
# Rutas base
# --------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
PLAYBOOKS_DIR = ROOT / "playbooks"
TEMPLATES_DIR = ROOT / "templates"   # opcional

# Directorio de runs fuera del paquete (sobre-escribible por env)
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
# Binarios requeridos
# --------------------------------------------------------------------------------------
TOOLS = {
    "whois":       _tool("whois", "whois"),
    "amass":       _tool("amass", "amass"),
    "subfinder":   _tool("subfinder", "subfinder"),
    "assetfinder": _tool("assetfinder", "assetfinder"),
    "dnsx":        _tool("dnsx", "dnsx"),
    "httpx":       _tool("httpx", "httpx"),
    "naabu":       _tool("naabu", "naabu"),
    "nmap":        _tool("nmap", "nmap"),
    "whatweb":     _tool("whatweb", "whatweb"),
    "wafw00f":     _tool("wafw00f", "wafw00f"),
    "gowitness":   _tool("gowitness", "gowitness"),
    "gau":         _tool("gau", "gau"),
    "katana":      _tool("katana", "katana"),
    "arjun":       _tool("arjun", "arjun"),
    "ffuf":        _tool("ffuf", "ffuf"),
    "tlsx":        _tool("tlsx", "tlsx"),
    "dig":         _tool("dig", "dig"),
}

# --------------------------------------------------------------------------------------
# Timeouts (segundos) – más conservadores para evitar “runs eternos”
# --------------------------------------------------------------------------------------
DEFAULT_TIMEOUT = int(_env("REDFLOW_TIMEOUT", "900"))
TIMEOUTS = {
    "whois":      int(_env("REDFLOW_TIMEOUT_WHOIS", "120")),
    "amass":      int(_env("REDFLOW_TIMEOUT_AMASS", "900")),
    "subfinder":  int(_env("REDFLOW_TIMEOUT_SUBFINDER", "600")),
    "assetfinder":int(_env("REDFLOW_TIMEOUT_ASSETFINDER", "300")),
    "dnsx":       int(_env("REDFLOW_TIMEOUT_DNSX", "600")),
    "httpx":      int(_env("REDFLOW_TIMEOUT_HTTPX", "900")),
    "naabu":      int(_env("REDFLOW_TIMEOUT_NAABU", "900")),
    "nmap":       int(_env("REDFLOW_TIMEOUT_NMAP", "3600")),
    "whatweb":    int(_env("REDFLOW_TIMEOUT_WHATWEB", "300")),   # ↓
    "wafw00f":    int(_env("REDFLOW_TIMEOUT_WAFW00F", "10")),    # ↓ por host (se aplica en nodo)
    "gowitness":  int(_env("REDFLOW_TIMEOUT_GOWITNESS", "600")),
    "gau":        int(_env("REDFLOW_TIMEOUT_GAU", "240")),       # ↓
    "katana":     int(_env("REDFLOW_TIMEOUT_KATANA", "240")),    # ↓
    "arjun":      int(_env("REDFLOW_TIMEOUT_ARJUN", "600")),     # ↓ (además usamos budget propio)
    "ffuf":       int(_env("REDFLOW_TIMEOUT_FFUF", "300")),      # techo por host si no se indica
    "tlsx":       int(_env("REDFLOW_TIMEOUT_TLSX", "120")),      # ↓
    "idp":        int(_env("REDFLOW_TIMEOUT_IDP", "300")),       # ↓
}

# --------------------------------------------------------------------------------------
# Límites de concurrencia
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

# Wordlists: por defecto “small” para rapidez; “medium” para modo agresivo
FFUF_SMALL_WORDLIST  = _env("REDFLOW_FFUF_SMALL",  f"{SECLISTS_DIR}/Discovery/Web-Content/raft-small-directories.txt")
FFUF_MEDIUM_WORDLIST = _env("REDFLOW_FFUF_MEDIUM", f"{SECLISTS_DIR}/Discovery/Web-Content/raft-medium-directories.txt")
FFUF_DEFAULT_WORDLIST = _env("REDFLOW_FFUF_WORDLIST", FFUF_SMALL_WORDLIST)

KATANA_DEPTH = int(_env("REDFLOW_KATANA_DEPTH", "2"))

# Prioridades para decidir dónde profundizar (fuzzing, screenshots, etc.)
HTTPX_PRIORITY_CODES = {200, 204, 301, 302, 401, 403}
PRIORITY_PORTS_WEB = {80, 443, 8080, 8443, 8000, 8888, 9000, 9443, 7001}  # ampliado

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
