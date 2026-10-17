# ada-api

A API da ADA: FastAPI + SSE na frente do cérebro. Quem consome é o app (`ada-app`).

O cérebro não mora aqui: a API importa o `1_ada/` do repo do core, que fica na pasta do lado
(`../core`; `ADA_CORE` troca o caminho). O modelo roda dentro do mesmo processo, então a API usa o venv do core.

## Organização

```
main.py              liga tudo: monta o app com as rotas, sobe o worker e o uvicorn
api/
  config.py          de onde vem cada config: o core, o .env, HOST, PORTA, FAKE
  identidade.py      IP -> victor / convidado / visitante
  worker.py          a thread dona do modelo: fila de entrada, Job, pronta, modo fake
  armazem.py         SQLite: conversas e mensagens, com dono
  rotas/
    info.py          GET /info
    conversas.py     CRUD das conversas + export
    chat.py          POST /chat (o stream)
dados/conversas.db   as conversas (fora do git)
```

## Rodar

```bash
../core/.venv/bin/python main.py                                          # só esta máquina -> http://127.0.0.1:8000
ADA_FAKE=1 ../core/.venv/bin/python main.py                               # sem o modelo (eventos de mentira)
ADA_HOST=$(tailscale ip -4) caffeinate -i ../core/.venv/bin/python main.py # na tailnet
python3 api/armazem.py [id]                                               # log das conversas no terminal
```

Config no `.env` do core: `ADA_HOST`, `ADA_PORT`, `ADA_IPS_VICTOR`, `ADA_IPS_CONVIDADO`, `ADA_ADAPTER`.
Nunca `0.0.0.0`: o portão é a tailnet.

## Quem é quem

Identidade pelo IP de origem: `victor` (a própria máquina + `ADA_IPS_VICTOR`), `convidado` (`ADA_IPS_CONVIDADO`)
e `visitante` (o resto da tailnet). Cada um tem a própria persona e só vê as próprias conversas.

## Rotas

| Rota | O quê |
|---|---|
| `GET /info` | `pronta`, `adapter`, `fake`, `fila`, `usuario`, `origem` |
| `GET /conversas` | as conversas de quem pede |
| `POST /conversas` | cria (`{"titulo"}`) |
| `GET /conversas/{id}` | a conversa com as mensagens (o `meta` do assistant traz think, tools e tempos) |
| `PATCH /conversas/{id}` | renomeia (`{"titulo"}`) |
| `DELETE /conversas/{id}` | apaga |
| `GET /conversas/{id}/export` | markdown |
| `POST /chat` | `{"conversa", "msg"}` -> stream SSE |

Eventos do `/chat`, um por linha `data: {...}`:

| `t` | Campos |
|---|---|
| `think` | `d`: pedaço do raciocínio |
| `tool` | `nome`, `args`, `res` |
| `resp` | `d`: pedaço da resposta |
| `fim` | — |
| `erro` | `d` |

As conversas ficam em `dados/conversas.db` (SQLite, fora do git).
