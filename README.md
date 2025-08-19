# RedFlow — Recon/Enum Orchestrator for Red Team (WIP v0.1)

<!-- Core project status -->
![status](https://img.shields.io/badge/status-WIP-yellow)
![version](https://img.shields.io/badge/version-0.1-blue)
![python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)

<!-- Security domain / audience -->
![red-team](https://img.shields.io/badge/Red%20Team-Toolkit-critical)
![pentesting](https://img.shields.io/badge/Penetration_Testing-Tools-red)
![osint](https://img.shields.io/badge/OSINT-Recon-orange)
![offsec](https://img.shields.io/badge/Offensive%20Security-Automation-lightgrey)
![recon](https://img.shields.io/badge/Recon-Playbook--Driven-blueviolet)
![enum](https://img.shields.io/badge/Enumeration-Workflow-9cf)

<!-- Tech stack / ecosystem -->
![cli](https://img.shields.io/badge/CLI-Typer-0A7BBB)
![graphs](https://img.shields.io/badge/Graphs-Matplotlib-11557c)
![engine](https://img.shields.io/badge/Orchestrator-LangGraph-4b8bbe)
![projectdiscovery](https://img.shields.io/badge/ProjectDiscovery-Tools-0080FF)
![nmap](https://img.shields.io/badge/Nmap-Scan-2e6f40)
![ffuf](https://img.shields.io/badge/FFUF-Fuzzing-6f42c1)
![subfinder](https://img.shields.io/badge/Subfinder-Subs-0ea5e9)
![httpx](https://img.shields.io/badge/httpx-Probing-0ea5e9)
![dnsx](https://img.shields.io/badge/dnsx-Resolve-0ea5e9)
![naabu](https://img.shields.io/badge/naabu-Ports-0ea5e9)
![katana](https://img.shields.io/badge/katana-Crawl-0ea5e9)
![gau](https://img.shields.io/badge/gau-URLs-0ea5e9)
![arjun](https://img.shields.io/badge/arjun-Params-0ea5e9)
![tlsx](https://img.shields.io/badge/tlsx-TLS-0ea5e9)
![whatweb](https://img.shields.io/badge/whatweb-Fingerprint-0ea5e9)
![wafw00f](https://img.shields.io/badge/wafw00f-WAF-0ea5e9)
![gowitness](https://img.shields.io/badge/gowitness-Screenshots-0ea5e9)

<!-- Platforms -->
![kali](https://img.shields.io/badge/Kali-Linux-557C94?logo=kalilinux&logoColor=white)
![debian](https://img.shields.io/badge/Debian-Supported-A81D33?logo=debian&logoColor=white)
![ubuntu](https://img.shields.io/badge/Ubuntu-Supported-E95420?logo=ubuntu&logoColor=white)
![macos](https://img.shields.io/badge/macOS-Supported-000000?logo=apple&logoColor=white)

**RedFlow** is a playbook-driven CLI for reconnaissance (and early enumeration) on a **domain or IP**. It orchestrates well-known tools (`whois`, `amass`, `subfinder`, `assetfinder`, `dnsx`, `httpx`, `naabu`, `nmap`, `whatweb`, `wafw00f`, `gowitness`, `gau`, `katana`, `arjun`, `ffuf`, `tlsx`, `dig`) and produces **reproducible artifacts**, **charts**, and a **Markdown report**.

> ⚠️ **Responsible use**: RedFlow is dual-use. Run it **only** with explicit authorization (engagement, bug bounty, or your lab). Respect laws, acceptable-use policies, and agreed scope.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Option A) Development (editable)](#option-a-development-editable)
  - [Option B) Wheel (distribution)](#option-b-wheel-distribution)
  - [Installing external binaries (quick guide)](#installing-external-binaries-quick-guide)
- [Configuration (env vars)](#configuration-env-vars)
- [Output location (runs)](#output-location-runs)
- [Quick start](#quick-start)
- [Playbooks](#playbooks)
- [Optional: Scope allowlist](#optional-scope-allowlist)
- [Performance & permissions tips](#performance--permissions-tips)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)
- [License (MIT)](#license-mit)

---

## Features

- **Playbook-driven** pipeline (YAML) with **dynamic node loading**.
- **Idempotent** runs and `--resume` to reuse safe artifacts.
- **Automatic charts**: top ports, HTTP status, tech stack, TLS, WAF, subdomain tree (Graphviz optional).
- **Report** (`report.md`) linking evidence and metrics.
- Works with **domain** and **IP** targets (branches adapt accordingly).

---

## Requirements

- **Python 3.9+** (3.10+ recommended)
- Python dependencies (installed via `pip`):  
  `langgraph`, `typer`, `PyYAML`, `matplotlib`, `rich`
- Binaries available in your `$PATH` (varies by OS):  
  `whois`, `amass`, `subfinder`, `assetfinder`, `dnsx`, `httpx`, `naabu`, `nmap`,  
  `whatweb`, `wafw00f`, `gowitness`, `gau`, `katana`, `arjun`, `ffuf`, `tlsx`, `dig`  
  **Optional:** `dot` (Graphviz) for `subdomain_tree.svg`

---

## Installation

### Option A) Development (editable)

```bash
git clone <your-repo-url> redflow
cd redflow
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .
```

### Option B) Wheel (distribution)

```bash
python -m pip install build
python -m build
pip install dist/*.whl
```

### Installing external binaries (quick guide)

- Kali / Debian / Ubuntu
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip build-essential whois nmap wafw00f dnsutils graphviz ruby ruby-dev
# whatweb (if missing):
sudo gem install whatweb
# Go toolchain:
sudo apt install -y golang-go
# Add Go bin to PATH (bash/zsh):
echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
echo 'export PATH="$PATH:$GOPATH/bin"' >> ~/.bashrc
source ~/.bashrc
# ProjectDiscovery + others:
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest
go install github.com/tomnomnom/assetfinder@latest
go install github.com/lc/gau/v2/cmd/gau@latest
go install github.com/ffuf/ffuf@latest
go install github.com/sensepost/gowitness@latest
pip install --user arjun
```

- macOS (Homebrew)
```bash
brew install nmap graphviz wafw00f whatweb go
# Add Go bin to PATH if needed:
echo 'export PATH="$PATH:$(go env GOPATH)/bin"' >> ~/.zshrc && source ~/.zshrc
# Same go installs as above...
go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest
go install github.com/projectdiscovery/httpx/cmd/httpx@latest
go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install github.com/projectdiscovery/katana/cmd/katana@latest
go install github.com/projectdiscovery/tlsx/cmd/tlsx@latest
go install github.com/tomnomnom/assetfinder@latest
go install github.com/lc/gau/v2/cmd/gau@latest
go install github.com/ffuf/ffuf@latest
go install github.com/sensepost/gowitness@latest
pip3 install --user arjun
```

---

## Configuration (env vars)

```bash
# Change where runs are stored (default: ~/.local/share/redflow/runs)
export REDFLOW_RUNS_DIR="$HOME/redflow-runs"

# Point to non-standard binary locations
export REDFLOW_TOOL_NMAP="/opt/nmap/bin/nmap"
export REDFLOW_TOOL_FFUF="$HOME/go/bin/ffuf"

# Concurrency / timeouts
export REDFLOW_SEM_HTTP=16
export REDFLOW_TIMEOUT_NMAP=5400

# Wordlists / seclists
export REDFLOW_SECLISTS_DIR="/opt/seclists"
export REDFLOW_FFUF_WORDLIST="/opt/seclists/Discovery/Web-Content/raft-medium-directories.txt"

# Report title
export REDFLOW_REPORT_TITLE="Acme Corp Recon"
```

---

## Output location (runs)

By default, results are stored under:
- Linux/macOS: ~/.local/share/redflow/runs/<run_id>/
- override with REDFLOW_RUNS_DIR
Inside each run directory you'll find:
- artifacts/   # txt/json/xml/png generated by tools
- graphs/      # charts (.png) and optional .svg (graphviz)
- report.md    # consolidated report
- state.json   # final state (debug/resume)

---

## Quick start
- Check your environment
```bash
redflow check
# or: python -m redflow.cli check
```
- List available playbooks
```bash
redflow list-playbooks
# or: python -m redflow.cli list-playbooks
```
- Run full recon (safe smoke test with IANA domain)
```bash
redflow run example.com --playbook recon-full
# or: python -m redflow.cli run example.com --playbook recon-full
```
- Resume a run (use the run_id printed by run)
```bash
redflow resume <run_id>
# or: python -m redflow.cli resume <run_id>
```
- Show key files for a run
```bash
redflow show <run_id>
# or: python -m redflow.cli show <run_id>
```

---

## Playbooks

Playbooks live in redflow/playbooks/. The default recon-full.yaml chains:
  whois → amass_asn → subfinder → assetfinder → merge_subs → dnsx → dig_suite
  → httpx → naabu → nmap → whatweb/waf/gowitness
  → urls/params (gau/katana/arjun) → ffuf → tlsx → idp_probe → render_graphs → report
Create new playbooks copying recon-full.yaml and referencing your nodes with impl: <module_name> (the loader imports redflow.nodes<impl> and runs async def run(state, **params)).

---

## Optional: Scope allowlist

You can restrict scope with a YAML file and pass it to run (depending on how your nodes enforce it):
```bash
# scope.yaml
domains:
  - example.com
cidrs:
  - 203.0.113.0/24
hosts:
  - portal.example.com
notes: |
  Staging & dev only.
```
Run with:
```bash
redflow run example.com --playbook recon-full --allowlist scope.yaml
```

---

## Performance & permissions tips

- Nmap without privileges: if -sS fails, switch to connect scan: nmap.params.stealth: false.
- Fuzzing responsibly: RedFlow prioritizes hosts with httpx signals and web ports; adjust ffuf.params.max_hosts and per_host_minutes.
- Concurrency: reduce REDFLOW_SEM_HTTP / REDFLOW_SEM_FFUF for sensitive targets or limited hosts.
- Resume / force: --resume reuses artifacts; --force regenerates even if artifacts exist.

---

## Troubleshooting

- Missing binaries in PATH → redflow check shows what’s missing.
- Permission issues (nmap -sS) → use stealth: false or run with appropriate capabilities.
- Empty charts → not enough data; inspect runs/<run_id>/state_after_*.json.
- Graphviz not installed → .dot generated (no .svg).
- Node errors → see the Errors section in report.md and related artifacts (*.txt/*.jsonl).

---

## Uninstall

```bash
pip uninstall redflow-recon
```

---

## Licence (MIT)

MIT License

Copyright (c) 2025 Wilhelmroentgen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.


Project status: Work in progress — v0.1. Contributions and feedback are welcome.
