#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path
from typing import Optional, List

import typer

from .graph import build_graph_from_playbook, init_state
from .settings import PLAYBOOKS_DIR, RUNS_DIR, TOOLS
from .utils.io import run_dir, save_json

app = typer.Typer(help="RedFlow — CLI para reconocimiento y enumeración")

# ------- utilidades locales -------


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
    # Validación ligera; dominios/ips más complejas déjalas a los nodos.


def _copy_scope_to_run(scope: Optional[Path], run_path: Path) -> Optional[Path]:
    if not scope:
        return None
    dest = run_path / "scope.yaml"
    dest.write_text(Path(scope).read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def _echo_kv(k: str, v: str):
    typer.echo(typer.style(k + ": ", bold=True) + v)


# ------- comandos -------


@app.command()
def list_playbooks() -> None:
    """Lista playbooks disponibles en la carpeta configurada."""
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


@app.command()
def check(
    extra: Optional[List[str]] = typer.Option(
        None,
        help="Nombres adicionales de binarios a verificar (además de TOOLS).",
    )
) -> None:
    """Verifica que las herramientas de terceros estén en PATH."""
    import shutil

    req = set([v for v in TOOLS.values() if v])
    if extra:
        req |= set(extra)

    missing = []
    typer.echo("Verificando herramientas en PATH:")
    for name in sorted(req):
        path = shutil.which(name)
        if path:
            typer.echo(f"  ✓ {name}  ->  {path}")
        else:
            typer.echo(f"  ✗ {name}  (no encontrado)")
            missing.append(name)

    if missing:
        typer.echo("\nFaltan herramientas. Instálalas o ajusta tu PATH.")
        raise typer.Exit(code=2)


@app.command()
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
        help="Verificar binarios antes de ejecutar.",
    ),
) -> None:
    """
    Ejecuta un playbook contra el target. Crea un nuevo run_id y guarda estado/artefactos.
    """
    _validate_target(target)

    # Ejecuta el comando 'check' directamente con sus defaults (sin usar .callback)
    if check_tools:
        try:
            check()
        except typer.Exit as e:
            # Propaga tal cual el código de salida
            raise
        except SystemExit as e:
            # Normaliza SystemExit a Typer Exit
            raise typer.Exit(code=e.code)

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

    # Persistimos un primer snapshot
    save_json(state["run_id"], "state_init", dict(state))

    # Compilar y ejecutar el grafo
    try:
        wf = build_graph_from_playbook(playbook, target)
    except Exception as e:
        typer.echo(
            typer.style(
                f"Error al construir grafo/playbook: {e}", fg=typer.colors.RED
            )
        )
        raise typer.Exit(code=1)

    try:
        asyncio.run(wf.ainvoke(state))
    except KeyboardInterrupt:
        typer.echo(
            typer.style(
                "\nEjecución interrumpida por el usuario.",
                fg=typer.colors.YELLOW,
                bold=True,
            )
        )
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(
            typer.style(f"Fallo durante la ejecución: {e}", fg=typer.colors.RED)
        )
        # Guardar estado por si se quiere reanudar o depurar
        _write_json(rdir / "state_error.json", dict(state))
        raise typer.Exit(code=1)

    # Guardar estado final (por si el nodo de reporte no lo hizo)
    _write_json(rdir / "state.json", dict(state))

    # Mensaje final
    report_md = rdir / "report.md"
    _echo_kv("Reporte", str(report_md if report_md.exists() else "(pendiente)"))
    typer.echo(typer.style("✔ Ejecución completada.", fg=typer.colors.GREEN, bold=True))


@app.command()
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
        # intentar con algún snapshot
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
            typer.style(
                f"Error al construir grafo/playbook: {e}", fg=typer.colors.RED
            )
        )
        raise typer.Exit(code=1)

    try:
        asyncio.run(wf.ainvoke(state))
    except KeyboardInterrupt:
        typer.echo(
            typer.style(
                "\nEjecución interrumpida por el usuario.",
                fg=typer.colors.YELLOW,
                bold=True,
            )
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


@app.command()
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
