# redflow/utils/ui.py
from datetime import datetime
from typing import Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table


class PipelineUI:
    """
    UI en vivo para mostrar el avance del playbook (por nodos).
    """

    def __init__(self, run_id: str, target: str, playbook: str, nodes: List[str]):
        self.console = Console()
        self.header = f"RedFlow • target: {target} • playbook: {playbook} • run: {run_id}"
        self.nodes = nodes
        self.state: Dict[str, Dict[str, Optional[datetime]]] = {
            nid: {"status": "pending", "started": None, "ended": None, "error": None}
            for nid in nodes
        }
        self._live: Optional[Live] = None

    # ---- eventos -------------------------------------------------------------

    def start(self, node_id: str):
        s = self.state.get(node_id)
        if s and s["status"] in ("pending", "skipped"):
            s["status"] = "running"
            s["started"] = datetime.now()
            s["error"] = None
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

    # ---- live render --------------------------------------------------------

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
                elapsed = str(end - start).split(".")[0]
            badge = {
                "pending": "⌛ pending",
                "running": "⏳ running",
                "ok": "✅ ok",
                "error": "❌ error",
                "skipped": "⤼ skipped",
            }.get(status, status)
            table.add_row(nid, badge, elapsed, st.get("error") or "")

        return Panel(table, border_style="blue")

    def live(self):
        # Context manager p/ usar: with ui.live(): ...
        self._live = Live(self.render(), console=self.console, refresh_per_second=8)
        return self._live

    def _update(self):
        if self._live:
            self._live.update(self.render())
