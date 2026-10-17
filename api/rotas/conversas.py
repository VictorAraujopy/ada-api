"""As conversas de quem pede: listar, criar, abrir, renomear, apagar e exportar em markdown.
Conversa de outra pessoa responde 404, igual a uma que não existe."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from api import armazem, identidade

rotas = APIRouter()


@rotas.get("/conversas")
def listar_conversas(req: Request):
    return armazem.listar(identidade.usuario_de(req))


@rotas.post("/conversas")
async def criar_conversa(req: Request):
    corpo = await req.json()
    return armazem.criar(corpo.get("titulo", ""), dono=identidade.usuario_de(req))


@rotas.get("/conversas/{cid}")
def abrir_conversa(cid: str, req: Request):
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    return {"id": cid, "titulo": armazem.titulo(cid), "mensagens": armazem.mensagens(cid)}


@rotas.patch("/conversas/{cid}")
async def renomear_conversa(cid: str, req: Request):
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    novo = armazem.renomear(cid, (await req.json()).get("titulo", ""))
    if not novo:
        return JSONResponse({"erro": "título vazio"}, status_code=400)
    return {"ok": True, "titulo": novo}


@rotas.delete("/conversas/{cid}")
def apagar_conversa(cid: str, req: Request):
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    armazem.apagar(cid)
    return {"ok": True}


@rotas.get("/conversas/{cid}/export")
def exportar(cid: str, req: Request):
    """Baixa a conversa em markdown (pra post, demo, arquivo)."""
    if not armazem.existe(cid, identidade.usuario_de(req)):
        return JSONResponse({"erro": "conversa não existe"}, status_code=404)
    linhas = [f"# ADA — {armazem.titulo(cid)}", ""]
    for m in armazem.mensagens(cid):
        if m["role"] == "user":
            linhas += [f"**Victor:** {m['content']}", ""]
        else:
            for t in (m["meta"] or {}).get("tools", []):
                linhas.append(f"> 🔧 `{t['nome']}` → {t['res']}")
            linhas += [f"**ADA:** {m['content']}", ""]
    return Response("\n".join(linhas), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ada_{cid}.md"'})
