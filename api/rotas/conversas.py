"""As conversas de quem pede: listar, criar, abrir, ver as fotos, renomear, apagar e exportar em markdown.
Conversa de outra pessoa responde 404, igual a uma que não existe."""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from api import armazem, fotos, identidade, limite, worker

rotas = APIRouter()


class Titulo(BaseModel):
    titulo: str = Field("", max_length=limite.MAX_TEXTO)


@rotas.get("/conversas")
def listar_conversas(req: Request):
    return armazem.listar(identidade.usuario_de(req))


@rotas.post("/conversas")
def criar_conversa(corpo: Titulo, req: Request):
    return armazem.criar(corpo.titulo, dono=identidade.usuario_de(req))


@rotas.get("/conversas/{cid}")
def abrir_conversa(cid: str, req: Request):
    usuario = identidade.usuario_de(req)
    if not armazem.existe(cid, usuario):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    # gerando: a ADA ainda está respondendo aqui (o app caiu no meio e voltou); a resposta entra no banco quando acabar
    return {"id": cid, "titulo": armazem.titulo(cid), "mensagens": armazem.mensagens(cid),
            "gerando": worker.em_andamento.get(usuario) == cid}


@rotas.get("/conversas/{cid}/fotos/{nome}")
def ver_foto(cid: str, nome: str, req: Request):
    """A foto de uma mensagem: só sai se ela é mesmo dessa conversa, e a conversa é de quem pede."""
    if not armazem.existe(cid, identidade.usuario_de(req)) or nome not in armazem.fotos(cid):
        return JSONResponse({"erro": "foto não existe"}, status_code=404)
    return FileResponse(fotos.caminho(nome), media_type="image/jpeg")


@rotas.patch("/conversas/{cid}")
def renomear_conversa(cid: str, corpo: Titulo, req: Request):
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    novo = armazem.renomear(cid, corpo.titulo)
    if not novo:
        return JSONResponse({"erro": "título vazio"}, status_code=400)
    return {"ok": True, "titulo": novo}


@rotas.delete("/conversas/{cid}")
def apagar_conversa(cid: str, req: Request):
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    for nome in armazem.fotos(cid):
        fotos.apagar(nome)
    armazem.apagar(cid)
    return {"ok": True}


@rotas.get("/conversas/{cid}/export")
def exportar(cid: str, req: Request):
    """Baixa a conversa em markdown (pra post, demo, arquivo)."""
    usuario = identidade.usuario_de(req)
    if not armazem.existe(cid, usuario):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    linhas = [f"# ADA — {armazem.titulo(cid)}", ""]
    for m in armazem.mensagens(cid):
        if m["role"] == "user":
            foto = "📷 [foto] " if m["foto"] else ""
            linhas += [f"**{usuario.capitalize()}:** {foto}{m['content']}", ""]
        else:
            for t in (m["meta"] or {}).get("tools", []):
                linhas.append(f"> 🔧 `{t['nome']}` → {t['res']}")
            linhas += [f"**ADA:** {m['content']}", ""]
    return Response("\n".join(linhas), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ada_{cid}.md"'})
