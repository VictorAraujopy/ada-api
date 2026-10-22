"""POST /chat: grava a mensagem (e a foto, se veio), põe o pedido na fila do worker e repassa os eventos por SSE.
A resposta da ADA quem grava é o worker: se o stream cair no meio, ela entra no banco igual."""
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from api import armazem, fotos, limite, worker

rotas = APIRouter()


class PedidoChat(BaseModel):
    conversa: str
    msg: str = Field("", max_length=limite.MAX_TEXTO)
    foto: str | None = Field(None, max_length=limite.MAX_FOTO_BASE64)  # JPEG/PNG/WebP em base64


def historico_do_modelo(mensagens):
    """System + turnos; as últimas MAX_FOTOS_NO_CONTEXTO fotos entram como imagem pro cérebro ler."""
    com_foto = [m["n"] for m in mensagens if m["foto"]]
    fotos_que_entram = set(com_foto[-limite.MAX_FOTOS_NO_CONTEXTO:])
    historico = [{"role": "system", "content": worker.SYSTEM}]
    for m in mensagens:
        if m["n"] in fotos_que_entram:
            conteudo = [{"type": "image", "arquivo": str(fotos.caminho(m["foto"]))},
                        {"type": "text", "text": m["content"]}]
        else:
            conteudo = m["content"]
        historico.append({"role": m["role"], "content": conteudo})
    return historico


# async de propósito: roda no loop, um pedido por vez, então ninguém fura o respondendo entre o if e o pedir
@rotas.post("/chat")
async def chat(pedido: PedidoChat):
    msg = pedido.msg.strip()
    if not (msg or pedido.foto) or not armazem.existe(pedido.conversa):
        return JSONResponse({"erro": "faltou msg ou a conversa não existe"}, status_code=400)
    if not worker.pronta.is_set():
        return JSONResponse({"erro": "a ADA ainda está carregando"}, status_code=503)
    if worker.respondendo:
        return JSONResponse({"erro": "a ADA ainda está respondendo o pedido anterior"}, status_code=409)

    # a foto só é gravada depois dos ifs acima: pedido recusado não deixa arquivo solto no disco
    nome_da_foto = None
    if pedido.foto:
        try:
            nome_da_foto = fotos.gravar(pedido.foto)
        except fotos.FotoInvalida as motivo:
            return JSONResponse({"erro": str(motivo)}, status_code=400)

    armazem.gravar(pedido.conversa, "user", msg, foto=nome_da_foto)
    # o histórico do modelo é remontado do banco a cada pedido
    historico = historico_do_modelo(armazem.mensagens(pedido.conversa))
    job = worker.Job(conversa=pedido.conversa, historico=historico)
    worker.pedir(job)

    def stream():
        while True:
            ev = job.saida.get()
            if ev is None:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
