"""
Nodos de RedFlow.

Cada módulo expone una corrutina:
    async def run(state: Dict[str, Any], **params) -> Dict[str, Any]
"""

# Lista informativa (no es obligatorio mantenerla al día para que funcione el loader dinámico)
__all__ = [
    "whois",
    "amass_intel",
    "subfinder",
    "assetfinder",
    "merge_sort_unique",
    "dnsx",
    "dig_suite",
    "httpx",
    "naabu",
    "nmap",
    "whatweb_waf_gowitness",
    "urls_params",
    "ffuf",
    "tlsx",
    "idp_probe",
    "render_graphs",
    # "nuclei",  # si lo activas más adelante
]