#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, List, Tuple

import typer

from .graph import build_graph_from_playbook, init_state
from .settings import PLAYBOOKS_DIR, RUNS_DIR, TOOLS
from .utils.io import run_dir, save_json
from .utils.playbooks import load_playbook
from .utils.install import install_missing_tools
from .utils.ui_registry import set_ui, clear_ui

# UI en vivo (Rich). Si no está, seguimos sin UI.
try:
    from .utils.ui import PipelineUI  # redflow/utils/ui.py
except Exception:  # pragma: no cover
    PipelineUI = None  # type: ignore

LONG_APP_HELP = """
[bold]RedFlow[/] — Orchestrates recon/enum playbooks over a [bold]domain or IP[/],
wrapping popular tools and producing reproducible artifacts, charts, and a Markdown report.

[bold]Commands[/]
 • [cyan]list-playbooks[/]  – List bundled playbooks (YAML).
 • [cyan]check[/]           – Verify external binaries in PATH (optionally install missing ones).
 • [cyan]run[/]             – Execute a playbook against a target with live progress UI.
 • [cyan]resume[/]          – Resume a previous run_id from its saved state.
 • [cyan]show[/]            – Show key files of a run.

[bold]Examples[/]
  redflow check --install-missing -y
  redflow run example.com -p recon-full -y
  redflow run 192.0.2.10 -p /path/custom.yaml --no-check-tools
  redflow run corp.com -a scope.yaml --resume
  redflow resume <run_id>
  redflow show <run_id>

[bold]Output[/]
  ~/.local/share/redflow/runs/<run_id>/
    ├─ artifacts/   # tool outputs (txt/json/png/xml)
    ├─ graphs/      # charts (ports, tech, TLS, subdomain tree)
    ├─ report.md    # consolidated report
    └─ state.json   # final state (and state_after_*.json snapshots)

[bold]Exit codes[/]
  0 OK • 1 execution/build error • 2 missing tools • 130 interrupted by user
"""

app = typer.Typer(
    help=LONG_APP_HELP,
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

# ---------------------------------------------------------------------------
# Utilidades locales
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _validate_target(target: str) -> None:
    if not target or not target.strip():
        raise typer.BadParameter("Debes especificar un dominio o IP.")


def _copy_scope_to_run(scope: Optional[Path], run_path: Path) -> Optional[Path]:
    if not scope:
        return None
    dest = run_path / "scope.yaml"
    dest.write_text(Path(scope).read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _echo_kv(k: str, v: str):
    typer.echo(typer.style(k + ": ", bold=True) + v)


def _print_tools_status(extra: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
    """Imprime el estado de herramientas y devuelve (presentes, faltantes)."""
    import shutil
    req = {v for v in TOOLS.values() if v}
    if extra:
        req |= set(extra)
    present, missing = [], []
    typer.echo("Verificando herramientas en PATH:")
    for name in sorted(req):
        path = shutil.which(name)
        if path:
            present.append(name)
            typer.echo(f"  ✓ {name}  ->  {path}")
        else:
            missing.append(name)
            typer.echo(f"  ✗ {name}  (no encontrado)")
    return present, missing


def _check_or_install(interactive: bool, auto_yes: bool, extra: Optional[List[str]] = None) -> None:
    """Muestra estado, ofrece instalar faltantes y valida al final."""
    _, missing = _print_tools_status(extra)
    if not missing:
        return

    do_install = False
    if interactive and sys.stdout.isatty():
        do_install = typer.confirm(
            f"Faltan {len(missing)} herramientas ({', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}). ¿Instalarlas ahora?",
            default=True,
        )
    elif auto_yes:
        do_install = True

    if not do_install:
        typer.echo("\nFaltan herramientas. Instálalas o ajusta tu PATH.")
        raise typer.Exit(code=2)

    # Intenta instalar
    results = install_missing_tools(missing, auto_yes=auto_yes)
    ok = [r.tool for r in results if r.ok]
    bad = [r for r in results if not r.ok]

    if ok:
        typer.echo(typer.style(f"\nInstaladas: {', '.join(ok)}", fg=typer.colors.GREEN))
    if bad:
        typer.echo(typer.style("\nNo se pudieron instalar:", fg=typer.colors.RED, bold=True))
        for r in bad:
            typer.echo(f"  - {r.tool} ({r.method})")
            if r.stderr:
                last = r.stderr.strip().splitlines()[-1][:140]
                typer.echo(f"      {last}")

    # Re-chequear
    _, missing2 = _print_tools_status(extra)
    if missing2:
        raise typer.Exit(code=2)


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

@app.command(help="List bundled playbooks (*.yaml) found in PLAYBOOKS_DIR.")
def list_playbooks() -> None:
    p = Path(PLAYBOOKS_DIR)
    if not p.exists():
        typer.echo(f"No existe PLAYBOOKS_DIR: {p}")
        raise typer.Exit(code=1)
    items = [f.name for f in p.iterdir() if f.suffix.lower() in (".yaml", ".yml")]
    if not items:
        typer.echo("No hay playbooks (*.yaml) en PLAYBOOKS_DIR.")
        raise typer.Exit(code=1)
    typer.echo("Playbooks disponibles:")
    for f in sorted(items):
        typer.echo(f"  - {f}")


@app.command(
    name="check",
    help=(
        "Verify that required external binaries are in PATH.\n\n"
        "Tips:\n"
        "  • Use --install-missing to offer installation (interactive).\n"
        "  • Use -y/--yes to auto-confirm prompts.\n"
        "Examples:\n"
        "  redflow check --install-missing -y\n"
        "  redflow check --extra masscan --extra gowitness\n"
    ),
)
def check(
    extra: Optional[List[str]] = typer.Option(
        None,
        help="Nombres adicionales de binarios a verificar (además de TOOLS).",
    ),
    install_missing: bool = typer.Option(
        False,
        "--install-missing/--no-install-missing",
        help="Ofrecer instalar herramientas faltantes.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Responde 'sí' automáticamente a las confirmaciones.",
    ),
) -> None:
    """Verifica herramientas y (opcionalmente) instala las faltantes."""
    present, missing = _print_tools_status(extra)
    if missing and (install_missing or yes):
        _check_or_install(interactive=install_missing, auto_yes=yes, extra=extra)
    elif missing:
        typer.echo("\nFaltan herramientas. Usa --install-missing o instala manualmente.")
        raise typer.Exit(code=2)


@app.command(
    help=(
        "Run a playbook against a target domain/IP with live progress UI.\n\n"
        "Common examples:\n"
        "  redflow run example.com -p recon-full -y\n"
        "  redflow run 192.0.2.10 -p /path/custom.yaml --no-check-tools\n"
        "  redflow run corp.com -a scope.yaml --resume\n"
        "\n"
        "Exit codes: 0 OK · 1 error · 2 missing tools · 130 interrupted"
    )
)
def run(
    target: str = typer.Argument(..., help="Dominio o IP objetivo."),
    playbook: str = typer.Option(
        "recon-full", "--playbook", "-p", help="Nombre o ruta al playbook YAML."
    ),
    allowlist: Optional[Path] = typer.Option(
        None,
        "--allowlist",
        "-a",
        exists=True,
        readable=True,
        help="Archivo scope.yaml para limitar alcance.",
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Reusar artefactos/estado si existen."
    ),
    force: bool = typer.Option(
        False, "--force", help="Ignora artefactos previos si el nodo lo soporta."
    ),
    check_tools: bool = typer.Option(
        True,
        "--check-tools/--no-check-tools",
        help="Verificar/instalar binarios antes de ejecutar.",
    ),
    ui: bool = typer.Option(
        True,
        "--ui/--no-ui",
        help="Mostrar UI de progreso en vivo (Rich).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Responde 'sí' automáticamente a confirmaciones de instalación.",
    ),
) -> None:
    """
    Ejecuta un playbook contra el target. Crea un nuevo run_id y guarda estado/artefactos.
    """
    _validate_target(target)

    # Verificación e instalación opcional
    if check_tools:
        _check_or_install(interactive=True, auto_yes=yes)

    # Estado inicial
    state = init_state(target)
    state["flags"] = {"resume": resume, "force": force}

    # Crear carpeta de ejecución
    rdir = run_dir(state["run_id"])
    _copy_scope_to_run(allowlist, rdir)
    _echo_kv("Run ID", state["run_id"])
    _echo_kv("Carpeta", str(rdir))
    _echo_kv("Playbook", playbook)
    _echo_kv("Target", target)

    # Snapshot inicial
    save_json(state["run_id"], "state_init", dict(state))

    # Cargar playbook para conocer los nodos (para UI)
    try:
        pb = load_playbook(playbook)
        node_ids = [n["id"] for n in pb["nodes"]]
    except Exception as e:
        typer.echo(typer.style(f"Error cargando playbook: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

    # Compilar grafo
    try:
        wf = build_graph_from_playbook(playbook, target)
    except Exception as e:
        typer.echo(typer.style(f"Error al construir grafo/playbook: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)

    # UI en vivo — se registra por run_id; además (compat) se guarda en state["__ui"]
    use_ui = ui and sys.stdout.isatty() and PipelineUI is not None
    pipeline_ui = None
    if use_ui:
        pipeline_ui = PipelineUI(state["run_id"], target, playbook, node_ids)
        set_ui(state["run_id"], pipeline_ui)   # registry global
        state["__ui"] = pipeline_ui            # fallback por compatibilidad

    try:
        if pipeline_ui:
            with pipeline_ui.live():
                asyncio.run(wf.ainvoke(state))
        else:
            asyncio.run(wf.ainvoke(state))
    except KeyboardInterrupt:
        typer.echo(
            typer.style("\nEjecución interrumpida por el usuario.", fg=typer.colors.YELLOW, bold=True)
        )
        # evita serializar objetos UI si falló en medio
        state.pop("__ui", None)
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(typer.style(f"Fallo durante la ejecución: {e}", fg=typer.colors.RED))
        state.pop("__ui", None)
        _write_json(rdir / "state_error.json", dict(state))
        raise typer.Exit(code=1)
    finally:
        if use_ui:
            clear_ui(state["run_id"])
        # quita UI del estado antes de cualquier guardado final
        state.pop("__ui", None)

    # Guardar estado final
    _write_json(rdir / "state.json", dict(state))

    # Mensaje final
    report_md = rdir / "report.md"
    _echo_kv("Reporte", str(report_md if report_md.exists() else "(pendiente)"))
    typer.echo(typer.style("✔ Ejecución completada.", fg=typer.colors.GREEN, bold=True))


@app.command(
    help=(
        "Resume a previous run_id using its saved state.json (or last state_after_*.json).\n\n"
        "Example:\n"
        "  redflow resume abcd1234ef56\n"
    )
)
def resume(
    run_id: str = typer.Argument(..., help="ID de ejecución existente."),
    playbook: Optional[str] = typer.Option(
        None, "--playbook", "-p", help="Override del playbook si lo deseas."
    ),
) -> None:
    """
    Reanuda un run_id existente. Útil si se interrumpió la ejecución.
    """
    rdir = run_dir(run_id)  # asegura existencia
    state_path = Path(rdir) / "state.json"
    if not state_path.exists():
        candidates = (
            sorted(Path(rdir).glob("state_after_*.json"))
            or sorted(Path(rdir).glob("state_init.json"))
        )
        if candidates:
            state_path = candidates[-1]
        else:
            typer.echo(f"No hay estado previo en {rdir}")
            raise typer.Exit(code=1)

    state = _read_json(state_path)
    if not state.get("run_id"):
        state["run_id"] = run_id

    target = state.get("target")
    if not target:
        typer.echo("El estado no tiene 'target'. Imposible reanudar.")
        raise typer.Exit(code=1)

    _echo_kv("Run ID", run_id)
    _echo_kv("Carpeta", str(rdir))
    _echo_kv("Target", target)

    pb = playbook or "recon-full"
    try:
        wf = build_graph_from_playbook(pb, target)
    except Exception as e:
        typer.echo(
            typer.style(f"Error al construir grafo/playbook: {e}", fg=typer.colors.RED)
        )
        raise typer.Exit(code=1)

    try:
        asyncio.run(wf.ainvoke(state))
    except KeyboardInterrupt:
        typer.echo(
            typer.style("\nEjecución interrumpida por el usuario.", fg=typer.colors.YELLOW, bold=True)
        )
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(
            typer.style(f"Fallo durante la ejecución: {e}", fg=typer.colors.RED)
        )
        _write_json(Path(rdir) / "state_error.json", dict(state))
        raise typer.Exit(code=1)

    _write_json(Path(rdir) / "state.json", dict(state))
    report_md = Path(rdir) / "report.md"
    _echo_kv("Reporte", str(report_md if report_md.exists() else "(pendiente)"))
    typer.echo(typer.style("✔ Reanudación completada.", fg=typer.colors.GREEN, bold=True))


@app.command(
    help=(
        "Show key files/paths of a given run_id (artifacts, graphs, report, state).\n\n"
        "Example:\n"
        "  redflow show abcd1234ef56\n"
    )
)
def show(
    run_id: str = typer.Argument(..., help="ID de ejecución."),
) -> None:
    """Muestra paths y archivos clave de un run."""
    rdir = Path(RUNS_DIR) / run_id
    if not rdir.exists():
        typer.echo(f"No existe el run_id en {RUNS_DIR}: {run_id}")
        raise typer.Exit(code=1)

    _echo_kv("Carpeta", str(rdir))
    report = rdir / "report.md"
    state = rdir / "state.json"
    art = rdir / "artifacts"
    graphs = rdir / "graphs"

    _echo_kv("Reporte", str(report if report.exists() else "(no generado)"))
    _echo_kv("Estado", str(state if state.exists() else "(no disponible)"))

    if art.exists():
        typer.echo("\nArtifacts:")
        for p in sorted(art.rglob("*")):
            if p.is_file():
                typer.echo(f"  - {p.relative_to(rdir)}")
    else:
        typer.echo("\n(No hay artifacts)")

    if graphs.exists():
        typer.echo("\nGraphs:")
        for p in sorted(graphs.glob("*")):
            typer.echo(f"  - {p.name}")


if __name__ == "__main__":
    app()

