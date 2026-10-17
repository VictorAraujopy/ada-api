"""GET /info: se a ADA já carregou, o tamanho da fila, quem ela acha que você é e se o terminal está aberto pra você."""
from pathlib import Path

from fastapi import APIRouter, Request

from api import config, identidade, worker

rotas = APIRouter()


@rotas.get("/info")
def info(req: Request):
    """O app consulta isto pra saber se já pode liberar o input."""
    usuario = identidade.usuario_de(req)
    return {"pronta": worker.pronta.is_set(), "adapter": Path(config.ADAPTER).name,
            "fake": config.FAKE, "fila": worker.entrada.qsize(),
            "usuario": usuario, "origem": req.client.host if req.client else "?",
            "terminal": config.TERMINAL and usuario == "victor"}
