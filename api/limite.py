"""Os tetos da API: o tamanho do texto que entra e quantas requisições cada IP faz por minuto.
A tailnet já é o portão; isto segura um aparelho com bug (ou mal-intencionado) lá dentro."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# 20 mil caracteres ~ 5 a 7 mil tokens: cabe um arquivo de código colado e ainda sobra contexto
# (N_CTX=16384 no cerebro.py) pro system, pro histórico e pros 4096 da resposta
MAX_TEXTO = 20_000

# o app faz poucas por ação (lista, abre, manda); 120 dá folga até pra perguntar a cada segundo se a resposta saiu
POR_MINUTO = 120

_recentes = defaultdict(deque)  # ip -> horários das requisições do último minuto


async def por_ip(req: Request):
    """Dependência de todas as rotas: passou de POR_MINUTO no último minuto, 429."""
    ip = req.client.host if req.client else ""
    agora = time.monotonic()
    horarios = _recentes[ip]
    while horarios and agora - horarios[0] > 60:
        horarios.popleft()
    if len(horarios) >= POR_MINUTO:
        raise HTTPException(429, "requisições demais: espera um pouco")
    horarios.append(agora)
