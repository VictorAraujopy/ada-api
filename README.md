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
  limite.py          os tetos: tamanho do texto e requisições por minuto por IP
  worker.py          a thread dona do modelo: fila de entrada, Job, pronta, modo fake; grava a resposta
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
| `GET /conversas/{id}` | a conversa com as mensagens (o `meta` do assistant traz think, tools e tempos) e `gerando` |
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

Quem grava a resposta é o worker, não o stream: se o app cair no meio, a ADA termina e grava igual.
Ao voltar, o `GET /conversas/{id}` diz `gerando: true` enquanto ela ainda responde ali.

## Erros e tetos

| Código | Quando |
|---|---|
| 400 | msg vazia, conversa que não existe (ou de outra pessoa), título vazio no PATCH |
| 404 | conversa que não existe (ou de outra pessoa) |
| 409 | `/chat` com a ADA ainda respondendo o pedido anterior da mesma pessoa (um por vez) |
| 422 | corpo fora do formato ou texto acima de 20 mil caracteres |
| 429 | mais de 120 requisições no último minuto vindas do mesmo IP |
| 503 | `/chat` antes da ADA terminar de carregar |

400, 404, 409 e 503 vêm como `{"erro": "..."}`; 422 e 429 no formato padrão do FastAPI, `{"detail": ...}`.

As conversas ficam em `dados/conversas.db` (SQLite, fora do git).
