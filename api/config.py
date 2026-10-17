"""Config da API: de onde vem o núcleo da ADA (o repo do core), o .env e o endereço onde ela escuta.
Importar este módulo já põe o 1_ada/ do core no sys.path e carrega o .env de lá."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent  # a pasta do ada-api
# núcleo da ADA: o repo do core, do lado deste (ADA_CORE troca o caminho)
CORE = Path(os.environ.get("ADA_CORE") or RAIZ.parent / "core").resolve()
if not (CORE / "1_ada" / "cerebro.py").exists():
    sys.exit(f"não achei o núcleo da ADA em {CORE} (ADA_CORE=<pasta do core>)")
sys.path.insert(0, str(CORE / "1_ada"))
load_dotenv(CORE / ".env")  # não sobrescreve variável que já veio do terminal

FAKE = os.environ.get("ADA_FAKE") == "1"

# ADA_HOST: 127.0.0.1 (so esta maquina) | IP do Tailscale (so a tailnet — modo convidado)
# NUNCA use 0.0.0.0 sem firewall: exporia a ADA pra rede local inteira.
# `or`: ADA_HOST vazio (ex.: $(tailscale ip) que falhou) NUNCA pode virar 0.0.0.0
HOST = os.environ.get("ADA_HOST") or "127.0.0.1"
PORTA = int(os.environ.get("ADA_PORT", 8000))
URL = f"http://{HOST}:{PORTA}"

# só pro /info — mesmo nome que o cerebro.py usa (ADA_ADAPTER="" roda o 27B cru)
ADAPTER = os.environ.get("ADA_ADAPTER", "ada_1_0_27b") or "qwen3.8_27b_cru"
