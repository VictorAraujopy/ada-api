"""POST /chat: grava a mensagem, põe o pedido na fila do worker e repassa os eventos por SSE.
A resposta da ADA quem grava é o worker: se o stream cair no meio, ela entra no banco igual."""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api import armazem, identidade, limite, worker

rotas = APIRouter()


class PedidoChat(BaseModel):
    conversa: str
    msg: str = Field(max_length=limite.MAX_TEXTO)


# async de propósito: roda no loop, um pedido por vez, então ninguém fura o em_andamento entre o if e o pedir
@rotas.post("/chat")
async def chat(pedido: PedidoChat, req: Request):
    usuario = identidade.usuario_de(req)
    msg = pedido.msg.strip()
    if not msg or not armazem.existe(pedido.conversa, usuario):
        return JSONResponse({"erro": "faltou msg ou a conversa não existe"}, status_code=400)
    if not worker.pronta.is_set():
        return JSONResponse({"erro": "a ADA ainda está carregando"}, status_code=503)
    if usuario in worker.em_andamento:
        return JSONResponse({"erro": "a ADA ainda está respondendo o pedido anterior"}, status_code=409)

    armazem.gravar(pedido.conversa, "user", msg)
    # o histórico do modelo é remontado do banco: system DO USUÁRIO + turnos
    historico = ([{"role": "system", "content": worker.SYSTEMS[usuario]}] +
                 [{"role": m["role"], "content": m["content"]} for m in armazem.mensagens(pedido.conversa)])
    job = worker.Job(conversa=pedido.conversa, usuario=usuario, historico=historico)
    worker.pedir(job)

    def stream():
        while True:
            ev = job.saida.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
