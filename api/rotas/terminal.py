"""O terminal do Mac: GET /terminal/estado, POST /terminal/entrar (senha -> sessão), /rodar (stream), /parar (Ctrl+C) e /sair.
Desligado (sem ADA_TERMINAL=1) ou pedido de quem não é o victor: 404, como se a rota não existisse.
Depois de entrar, a sessão vai no cabeçalho:  Authorization: Bearer <sessao>"""
import json
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api import config, identidade, senha, terminal

rotas = APIRouter()


class Entrada(BaseModel):
    senha: str = Field(max_length=200)


class PedidoComando(BaseModel):
    cmd: str = Field(min_length=1, max_length=4000)
    pasta: str = Field("~", max_length=1000)


def _barrado(req):
    """A resposta de barrado (404 igual ao de rota inexistente), ou None quando pode passar."""
    if not config.TERMINAL or identidade.usuario_de(req) != "victor":
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return None


def _sessao_de(req):
    return req.headers.get("authorization", "").removeprefix("Bearer ").strip()


# as rotas são async de propósito (como o /chat): rodam no loop, uma por vez, então contador de senha
# errada e "já tem comando rodando" não têm corrida entre duas requisições
@rotas.get("/terminal/estado")
async def estado(req: Request):
    """O app pergunta antes de mostrar o campo: sem senha no banco, ele pede pra criar (digitada duas vezes)."""
    if barrado := _barrado(req):
        return barrado
    return {"tem_senha": senha.existe()}


@rotas.post("/terminal/entrar")
async def entrar(corpo: Entrada, req: Request):
    if barrado := _barrado(req):
        return barrado
    # primeira vez: o app só CRIA quando não tem senha nenhuma; trocar a que existe é só no Mac (python -m api.senha)
    if not senha.existe():
        if len(corpo.senha) < senha.MINIMO:
            return JSONResponse({"erro": f"senha curta: mínimo {senha.MINIMO} caracteres"}, status_code=400)
        return {"sessao": terminal.criar_senha(corpo.senha), "pasta": terminal.curta(terminal.CASA)}
    if espera := terminal.travado_por():
        return JSONResponse({"erro": f"travado por senha errada: tenta de novo em {espera // 60 + 1} min"},
                            status_code=423)
    sessao = terminal.tentar_senha(corpo.senha)
    if not sessao:
        if terminal.travado_por():
            return JSONResponse({"erro": "senha errada: terminal travado por 15 min"}, status_code=423)
        return JSONResponse({"erro": f"senha errada (mais {terminal.tentativas_restantes()} antes de travar)"},
                            status_code=401)
    return {"sessao": sessao, "pasta": terminal.curta(terminal.CASA)}


@rotas.post("/terminal/rodar")
async def rodar(pedido: PedidoComando, req: Request):
    if barrado := _barrado(req):
        return barrado
    if not terminal.sessao_valida(_sessao_de(req)):
        return JSONResponse({"erro": "sessão expirada: abre o terminal de novo"}, status_code=401)
    if em_andamento := terminal.rodando():
        return JSONResponse({"erro": f"ainda rodando: {em_andamento.texto}"}, status_code=409)
    pasta = os.path.expanduser(pedido.pasta)
    if not os.path.isdir(pasta):
        return JSONResponse({"erro": f"pasta não existe: {pedido.pasta}"}, status_code=400)

    comando = terminal.comecar(pedido.cmd, pasta)

    def stream():
        while True:
            ev = comando.saida.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@rotas.post("/terminal/parar")
async def parar(req: Request):
    if barrado := _barrado(req):
        return barrado
    if not terminal.sessao_valida(_sessao_de(req)):
        return JSONResponse({"erro": "sessão expirada: abre o terminal de novo"}, status_code=401)
    comando = terminal.rodando()
    if not comando:
        return JSONResponse({"erro": "nada rodando"}, status_code=409)
    return {"sinal": comando.parar()}


@rotas.post("/terminal/sair")
async def sair(req: Request):
    if barrado := _barrado(req):
        return barrado
    terminal.sair(_sessao_de(req))
    return {"ok": True}
