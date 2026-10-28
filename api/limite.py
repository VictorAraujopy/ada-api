"""Os tetos da API: o tamanho do texto e da foto que entram e quantas requisições entram por minuto.
A tailnet já é o portão; isto segura um aparelho com bug (ou mal-intencionado) lá dentro."""
import time
from collections import deque

from fastapi import HTTPException
from fastapi.responses import JSONResponse

# 20 mil caracteres ~ 5 a 7 mil tokens: cabe um arquivo de código colado e ainda sobra contexto
# (N_CTX=16384 no cerebro.py) pro system, pro histórico e pros 4096 da resposta
MAX_TEXTO = 20_000

# a foto chega em base64 (4 caracteres a cada 3 bytes); 10 MB cobre foto de celular sem encolher
MAX_FOTO_BYTES = 10 * 1024 * 1024
MAX_FOTO_BASE64 = MAX_FOTO_BYTES * 4 // 3 + 4
# o corpo inteiro de um pedido: a foto, o texto (até 4 bytes por caractere) e folga pro JSON em volta
MAX_CORPO = MAX_FOTO_BASE64 + 4 * MAX_TEXTO + 64 * 1024
# acima disso o Pillow nem decodifica: 50 milhões de pixels passa de qualquer câmera de celular
MAX_PIXELS_DA_FOTO = 50_000_000
# a ADA lê cada pedaço de 32x32 pixels como um token: 1024 de lado dá no máximo 1024 tokens
# (uns 25 s pra ler no Mac) e ainda deixa legível letra de nota e de print
MAX_LADO_DA_FOTO = 1024
# só as últimas fotos da conversa entram como imagem (4 x 1024 tokens cabem no N_CTX com folga);
# as mais antigas ficam no histórico só pelo texto
MAX_FOTOS_NO_CONTEXTO = 4

# um pedaço de fala do app: WAV de 16 kHz, mono, 16 bits, até 30 s (a janela do Whisper) mais o cabeçalho
# de 44 bytes, ~960 KB; chega em base64. Cabe folgado no MAX_CORPO, que é o da foto
MAX_AUDIO_BYTES = 30 * 16_000 * 2 + 44
MAX_AUDIO_BASE64 = MAX_AUDIO_BYTES * 4 // 3 + 4

# o app faz poucas por ação (lista, abre, manda); 120 dá folga até pra perguntar a cada segundo se a resposta saiu
POR_MINUTO = 120

_recentes = deque()  # horários das requisições do último minuto


async def por_minuto():
    """Dependência de todas as rotas: passou de POR_MINUTO no último minuto, 429."""
    agora = time.monotonic()
    while _recentes and agora - _recentes[0] > 60:
        _recentes.popleft()
    if len(_recentes) >= POR_MINUTO:
        raise HTTPException(429, "requisições demais: espera um pouco")
    _recentes.append(agora)


class TamanhoDoCorpo:
    """Middleware ASGI puro: corpo declarado acima de MAX_CORPO volta 413 antes do FastAPI ler tudo pra memória, e
    corpo em pedaços (chunked) volta 411, mesmo com Content-Length junto (o servidor lê os pedaços e ignora o tamanho
    declarado; o app sempre manda só o Content-Length). Só olha o cabeçalho do pedido e passa o resto intocado: não
    embrulha a resposta (o stream do /chat)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            cabecalhos = dict(scope["headers"])
            if b"transfer-encoding" in cabecalhos:
                await JSONResponse({"erro": "o pedido tem que vir inteiro, com o tamanho (Content-Length)"},
                                   status_code=411)(scope, receive, send)
                return
            declarado = cabecalhos.get(b"content-length", b"0")
            if not declarado.isdigit() or int(declarado) > MAX_CORPO:
                await JSONResponse({"erro": "pedido grande demais"}, status_code=413)(scope, receive, send)
                return
        await self.app(scope, receive, send)
