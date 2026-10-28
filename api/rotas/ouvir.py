"""POST /ouvir: um pedaço da fala do usuário (WAV em base64) vira texto no ouvido da API (api/transcricao.py), com
o "enviar" ou o "apagar" do fim separado. O áudio só passa pela memória: nada vai pro disco."""
import base64
import binascii

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api import limite, transcricao

rotas = APIRouter()


class PedidoOuvir(BaseModel):
    audio: str = Field(..., max_length=limite.MAX_AUDIO_BASE64)  # WAV 16 kHz, mono, 16 bits


# def e não async: a transcrição leva ~4 s de CPU e roda numa thread do FastAPI, sem travar o stream do /chat
@rotas.post("/ouvir")
def ouvir(pedido: PedidoOuvir):
    if transcricao.abriu_com_erro:  # o motivo fica só no log do servidor (pode ter caminho de pasta do Mac)
        return JSONResponse({"erro": "o ouvido não abriu (o motivo está no log da API)"}, status_code=503)
    if not transcricao.pronto():
        return JSONResponse({"erro": "o ouvido ainda está carregando"}, status_code=503)
    # binascii.Error: caractere fora do base64; ValueError: caractere que nem é ASCII
    try:
        wav = base64.b64decode(pedido.audio, validate=True)
    except (binascii.Error, ValueError):
        return JSONResponse({"erro": "o áudio não veio em base64"}, status_code=400)
    try:
        texto, comando = transcricao.transcrever(wav)
    except transcricao.AudioInvalido as motivo:
        return JSONResponse({"erro": str(motivo)}, status_code=400)
    except transcricao.Ocupado:
        return JSONResponse({"erro": "o ouvido ficou ocupado demais com o pedaço anterior"}, status_code=409)
    return {"texto": texto, "comando": comando}
