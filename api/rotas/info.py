"""GET /info: se a ADA já carregou, o tamanho da fila e se o terminal está ligado."""
from pathlib import Path

from fastapi import APIRouter

from api import config, worker

rotas = APIRouter()


@rotas.get("/info")
def info():
    """O app consulta isto pra saber se já pode liberar o input."""
    return {"pronta": worker.pronta.is_set(), "adapter": Path(config.ADAPTER).name,
            "fake": config.FAKE, "fila": worker.entrada.qsize(), "terminal": config.TERMINAL}
