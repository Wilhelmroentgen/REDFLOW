# ==== Configuración ====
PY ?= python
VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Variables de ejecución
TARGET ?= ejemplo.com
PLAYBOOK ?= recon-full
RUN ?=
FLAGS ?=

# ==== Helpers ====
.PHONY: help
help:
	@echo "Targets:"
	@echo "  venv             - crea el entorno virtual (.venv)"
	@echo "  install          - instala dependencias (requirements.txt)"
	@echo "  install-dev      - instala deps de dev (requirements-dev.txt)"
	@echo "  check            - verifica herramientas externas en PATH"
	@echo "  list-playbooks   - lista playbooks disponibles"
	@echo "  run              - ejecuta el playbook (TARGET=$(TARGET), PLAYBOOK=$(PLAYBOOK))"
	@echo "  resume           - reanuda un run (RUN=<run_id>)"
	@echo "  show             - muestra archivos clave de un run (RUN=<run_id>)"
	@echo "  fmt              - formatea con black (opcional)"
	@echo "  lint             - lint con ruff (opcional)"
	@echo "  clean            - borra la venv"
	@echo "  clean-runs       - borra la carpeta runs/"
	@echo "  open-report      - abre el reporte del RUN (Linux/macOS)"

# ==== Entorno ====
.PHONY: venv
venv:
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install -U pip

.PHONY: install
install: venv
	$(PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: venv
	$(PIP) install -r requirements-dev.txt

# ==== Operaciones RedFlow ====
.PHONY: check
check:
	$(PYTHON) -m redflow.cli check

.PHONY: list-playbooks
list-playbooks:
	$(PYTHON) -m redflow.cli list-playbooks

.PHONY: run
run:
	@if [ -z "$(TARGET)" ]; then echo "Falta TARGET=<dominio|IP>"; exit 1; fi
	$(PYTHON) -m redflow.cli run $(TARGET) --playbook $(PLAYBOOK) $(FLAGS)

.PHONY: resume
resume:
	@if [ -z "$(RUN)" ]; then echo "Falta RUN=<run_id>"; exit 1; fi
	$(PYTHON) -m redflow.cli resume $(RUN) $(if $(PLAYBOOK),--playbook $(PLAYBOOK),)

.PHONY: show
show:
	@if [ -z "$(RUN)" ]; then echo "Falta RUN=<run_id>"; exit 1; fi
	$(PYTHON) -m redflow.cli show $(RUN)

# ==== Dev (opcional) ====
.PHONY: fmt
fmt:
	@if [ -f "$(VENV)/bin/black" ]; then $(VENV)/bin/black redflow; else echo "black no instalado (make install-dev)"; fi

.PHONY: lint
lint:
	@if [ -f "$(VENV)/bin/ruff" ]; then $(VENV)/bin/ruff check redflow; else echo "ruff no instalado (make install-dev)"; fi

# ==== Limpieza ====
.PHONY: clean
clean:
	rm -rf $(VENV)

.PHONY: clean-runs
clean-runs:
	rm -rf redflow/runs

# ==== Conveniencia ====
.PHONY: open-report
open-report:
	@if [ -z "$(RUN)" ]; then echo "Falta RUN=<run_id>"; exit 1; fi
	@if [ -f "redflow/runs/$(RUN)/report.md" ]; then \
		if command -v xdg-open >/dev/null 2>&1; then xdg-open redflow/runs/$(RUN)/report.md; \
		elif command -v open >/dev/null 2>&1; then open redflow/runs/$(RUN)/report.md; \
		else echo "Abre manualmente: redflow/runs/$(RUN)/report.md"; fi; \
	else echo "No existe report.md para RUN=$(RUN)"; fi
