"""GET /info: se a ADA já carregou, o tamanho da fila e quem ela acha que você é."""
from pathlib import Path

from fastapi import APIRouter, Request

from api import config, identidade, worker

rotas = APIRouter()


@rotas.get("/info")
def info(req: Request):
    """O app consulta isto pra saber se já pode liberar o input."""
    return {"pronta": worker.pronta.is_set(), "adapter": Path(config.ADAPTER).name,
            "fake": config.FAKE, "fila": worker.entrada.qsize(),
            "usuario": identidade.usuario_de(req), "origem": req.client.host if req.client else "?"}
