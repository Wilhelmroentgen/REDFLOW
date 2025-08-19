# redflow/utils/ui.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
import threading
import time


class _UILiveCtx:
    """Wrapper de contexto que arranca/parará el ticker junto al Live."""
    def __init__(self, ui: "PipelineUI", refresh_per_second: int = 8, tick_seconds: float = 1.0):
        self.ui = ui
        self.refresh_per_second = refresh_per_second
        self.tick_seconds = tick_seconds
        self._live: Optional[Live] = None

    def __enter__(self):
        # auto_refresh=False: nosotros pulsamos las actualizaciones
        self._live = Live(self.ui.render(), console=self.ui.console,
                          refresh_per_second=self.refresh_per_second,
                          auto_refresh=False)
        self._live.__enter__()
        self.ui._live = self._live
        self.ui._start_ticker(self.tick_seconds)
        # primer pintado "vivo"
        self.ui._update()
        return self._live

    def __exit__(self, exc_type, exc, tb):
        # detener ticker y hacer última actualización
        self.ui._stop_ticker()
        try:
            self.ui._update()
        finally:
            if self._live:
                return self._live.__exit__(exc_type, exc, tb)
        return False


class PipelineUI:
    """
    UI en vivo para mostrar el avance del playbook (por nodos) con refresco periódico.
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
        self._tick_evt: Optional[threading.Event] = None
        self._tick_thread: Optional[threading.Thread] = None

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

    # ---- live render ---------------------------------------------------------

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
                # Mostrar hh:mm:ss (sin microsegundos)
                elapsed = str(end - start).split(".")[0]
            badge = {
                "pending": "⌛ pending",
                "running": "⏳ running",
                "ok": "✅ ok",
                "error": "❌ error",
                "skipped": "⤼ skipped",
            }.get(status, str(status))
            table.add_row(nid, badge, elapsed, st.get("error") or "")
        return Panel(table, border_style="blue")

    def live(self, refresh_per_second: int = 8, tick_seconds: float = 1.0):
        """
        Context manager: inicia Live y un ticker en background que actualiza
        la tabla cada `tick_seconds` (p. ej., 1.0s) para que 'Elapsed' avance.
        """
        return _UILiveCtx(self, refresh_per_second=refresh_per_second, tick_seconds=tick_seconds)

    # ---- interno -------------------------------------------------------------

    def _update(self):
        if self._live:
            self._live.update(self.render())

    def _start_ticker(self, tick_seconds: float = 1.0):
        if self._tick_thread and self._tick_thread.is_alive():
            return
        self._tick_evt = threading.Event()

        def _loop():
            while self._tick_evt and not self._tick_evt.is_set():
                # Redibuja aunque no haya cambios de estado (elapsed avanza)
                self._update()
                time.sleep(tick_seconds)

        self._tick_thread = threading.Thread(target=_loop, daemon=True)
        self._tick_thread.start()

    def _stop_ticker(self):
        if self._tick_evt:
            self._tick_evt.set()
        if self._tick_thread and self._tick_thread.is_alive():
            # no join bloqueante largo; el hilo es daemon
            try:
                self._tick_thread.join(timeout=0.5)
            except Exception:
                pass
        self._tick_evt = None
        self._tick_thread = None
