"""GET /info: se a ADA já carregou, se está respondendo agora, o tamanho da fila e se o terminal está ligado."""
from pathlib import Path

from fastapi import APIRouter

from api import config, worker

rotas = APIRouter()


@rotas.get("/info")
def info():
    """O app consulta isto pra saber se já pode liberar o input.
    respondendo: ela está gerando uma resposta agora (o pedido que está sendo atendido não conta na fila)."""
    return {"pronta": worker.pronta.is_set(), "respondendo": worker.respondendo is not None,
            "adapter": Path(worker.adapter_carregado or config.ADAPTER).name,
            "fake": config.FAKE, "fila": worker.entrada.qsize(), "terminal": config.TERMINAL}
