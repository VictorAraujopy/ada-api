"""POST /chat: grava a mensagem, põe o pedido na fila do worker e repassa os eventos por SSE.
A resposta da ADA só entra no banco se o stream chegar inteiro."""
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api import armazem, identidade, worker

rotas = APIRouter()


@rotas.post("/chat")
async def chat(req: Request):
    corpo = await req.json()
    cid = corpo.get("conversa", "")
    msg = (corpo.get("msg") or "").strip()
    usuario = identidade.usuario_de(req)
    if not msg or not armazem.existe(cid, usuario):
        return JSONResponse({"erro": "faltou msg ou a conversa não existe"}, status_code=400)
    if not worker.pronta.is_set():
        return JSONResponse({"erro": "a ADA ainda está carregando"}, status_code=503)

    armazem.gravar(cid, "user", msg)
    # o histórico do modelo é remontado do banco: system DO USUÁRIO + turnos
    historico = ([{"role": "system", "content": worker.SYSTEMS[usuario]}] +
                 [{"role": m["role"], "content": m["content"]} for m in armazem.mensagens(cid)])
    job = worker.Job(historico=historico)
    worker.entrada.put(job)

    def stream():
        resposta, think, tools = "", "", []
        t0, t_resp = time.time(), None
        while True:
            ev = job.saida.get()
            if ev is None:
                break
            if ev["t"] == "think":
                think += ev["d"]
            elif ev["t"] == "tool":
                tools.append({"nome": ev["nome"], "res": str(ev["res"])[:200]})
            elif ev["t"] == "resp":
                t_resp = t_resp or time.time()
                resposta += ev["d"]
            yield f"data: {json.dumps(ev)}\n\n"
        if resposta.strip():   # só entra na memória da conversa se chegou inteira
            meta = {"pensou_s": round((t_resp or time.time()) - t0, 1),
                    "respondeu_s": round(time.time() - (t_resp or time.time()), 1),
                    "tools": tools, "think": think.strip()}
            armazem.gravar(cid, "assistant", resposta.strip(), meta)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
