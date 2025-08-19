# redflow/utils/ui.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class PipelineUI:
    """
    UI en vivo para mostrar el avance del playbook (por nodos).
    Se apoya en auto_refresh de Rich (sin hilos propios).
    """

    def __init__(self, run_id: str, target: str, playbook: str, nodes: List[str]):
        self.console = Console()
        self.header = f"RedFlow • target: {target} • playbook: {playbook} • run: {run_id}"
        self.nodes = nodes
        self.state: Dict[str, Dict[str, Optional[datetime] | str]] = {
            nid: {"status": "pending", "started": None, "ended": None, "error": ""}
            for nid in nodes
        }
        self._live: Optional[Live] = None

    # ---- eventos -------------------------------------------------------------

    def start(self, node_id: str):
        s = self.state.get(node_id)
        if s:
            s["status"] = "running"
            s["started"] = datetime.now()
            s["ended"] = None
            s["error"] = ""
            self._update()

    def finish(self, node_id: str):
        s = self.state.get(node_id)
        if s:
            s["status"] = "ok"
            s["ended"] = datetime.now()
            self._update()

    def fail(self, node_id: str, err: str):
        s = self.state.get(node_id)
        if s:
            s["status"] = "error"
            s["ended"] = datetime.now()
            s["error"] = (err or "")[:140]
            self._update()

    def skip(self, node_id: str, note: str = ""):
        s = self.state.get(node_id)
        if s:
            s["status"] = "skipped"
            s["ended"] = datetime.now()
            s["error"] = (note or "")[:140]
            self._update()

    # ---- render --------------------------------------------------------------

    def render(self):
        table = Table(expand=True)
        table.title = self.header
        table.add_column("Step", style="cyan", no_wrap=True)
        table.add_column("Status", style="magenta")
        table.add_column("Elapsed", justify="right")
        table.add_column("Note", overflow="fold")

        now = datetime.now()
        for nid in self.nodes:
            st = self.state[nid]
            status = st["status"]
            start = st["started"]
            end = st["ended"] or now
            elapsed = ""
            if start:
                elapsed = str(end - start).split(".")[0]  # hh:mm:ss
            badge = {
                "pending": "⌛ pending",
                "running": "🔄 running...",
                "ok": "✅ ok",
                "error": "❌ error",
                "skipped": "⤼ skipped",
            }.get(status, str(status))
            table.add_row(nid, badge, elapsed, st.get("error") or "")
        return Panel(table, border_style="blue")

    def live(self, refresh_per_second: int = 8):
        """
        Context manager. Usa auto_refresh=True para que Rich
        re-renderice en segundo plano y el 'Elapsed' avance solo.
        """
        self._live = Live(
            self.render(),
            console=self.console,
            refresh_per_second=refresh_per_second,
            auto_refresh=True,  # << clave: sin hilos nuestros
        )
        return self._live

    def _update(self):
        if self._live:
            # update desde el MISMO hilo que creó el Live (main thread)
            self._live.update(self.render())


