"""As conversas: listar, criar, abrir, ver as fotos, renomear, apagar e exportar em markdown."""
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from api import armazem, fotos, limite, worker

rotas = APIRouter()


class Titulo(BaseModel):
    titulo: str = Field("", max_length=limite.MAX_TEXTO)


@rotas.get("/conversas")
def listar_conversas():
    return armazem.listar()


@rotas.post("/conversas")
def criar_conversa(corpo: Titulo):
    return armazem.criar(corpo.titulo)


@rotas.get("/conversas/{cid}")
def abrir_conversa(cid: str):
    if not armazem.existe(cid):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    # gerando: a ADA ainda está respondendo aqui (o app caiu no meio e voltou); a resposta entra no banco quando acabar
    return {"id": cid, "titulo": armazem.titulo(cid), "mensagens": armazem.mensagens(cid),
            "gerando": worker.respondendo == cid}


@rotas.get("/conversas/{cid}/fotos/{nome}")
def ver_foto(cid: str, nome: str):
    """A foto de uma mensagem: só sai se ela é mesmo dessa conversa."""
    if not armazem.existe(cid) or nome not in armazem.fotos(cid):
        return JSONResponse({"erro": "foto não existe"}, status_code=404)
    return FileResponse(fotos.caminho(nome), media_type="image/jpeg")


@rotas.patch("/conversas/{cid}")
def renomear_conversa(cid: str, corpo: Titulo):
    if not armazem.existe(cid):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    novo = armazem.renomear(cid, corpo.titulo)
    if not novo:
        return JSONResponse({"erro": "título vazio"}, status_code=400)
    return {"ok": True, "titulo": novo}


@rotas.delete("/conversas/{cid}")
def apagar_conversa(cid: str):
    if not armazem.existe(cid):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    for nome in armazem.fotos(cid):
        fotos.apagar(nome)
    armazem.apagar(cid)
    return {"ok": True}


@rotas.get("/conversas/{cid}/export")
def exportar(cid: str):
    """Baixa a conversa em markdown (pra post, demo, arquivo)."""
    if not armazem.existe(cid):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    linhas = [f"# ADA — {armazem.titulo(cid)}", ""]
    for m in armazem.mensagens(cid):
        if m["role"] == "user":
            foto = "📷 [foto] " if m["foto"] else ""
            linhas += [f"**Victor:** {foto}{m['content']}", ""]
        else:
            for t in (m["meta"] or {}).get("tools", []):
                linhas.append(f"> 🔧 `{t['nome']}` → {t['res']}")
            linhas += [f"**ADA:** {m['content']}", ""]
    return Response("\n".join(linhas), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ada_{cid}.md"'})
