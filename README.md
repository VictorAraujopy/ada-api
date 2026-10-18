# ada-api

A API da ADA: FastAPI + SSE na frente do cérebro. Quem consome é o app (`ada-app`).

O cérebro não mora aqui: a API importa o `1_ada/` do repo do core, que fica na pasta do lado
(`../core`; `ADA_CORE` troca o caminho). O modelo roda dentro do mesmo processo, então a API usa o venv do core.

## Organização

```
main.py              liga tudo: monta o app com as rotas, sobe o worker e o uvicorn
api/
  config.py          de onde vem cada config: o core, o .env, HOST, PORTA, FAKE, TERMINAL, ADAPTER
  identidade.py      IP -> victor / convidado / visitante
  limite.py          os tetos: tamanho do texto e requisições por minuto por IP
  senha.py           a senha do terminal: só o hash (scrypt) no banco; trocar pelo Mac
  terminal.py        o terminal do Mac: sessão, trava por senha errada, o comando e o Ctrl+C
  worker.py          a thread dona do modelo: fila de entrada, Job, pronta, modo fake; grava a resposta
  armazem.py         SQLite: conversas e mensagens, com dono
  rotas/
    info.py          GET /info
    conversas.py     CRUD das conversas + export
    chat.py          POST /chat (o stream)
    terminal.py      /terminal/* (só o victor, só com ADA_TERMINAL=1)
dados/conversas.db   as conversas e o hash da senha do terminal (fora do git)
dados/terminal.log   cada comando rodado pelo app, com o código de saída (fora do git)
```

## Rodar

```bash
../core/.venv/bin/pip install -r requirements.txt                         # uma vez: fastapi, uvicorn e python-dotenv no venv do core
../core/.venv/bin/python main.py                                          # só esta máquina -> http://127.0.0.1:8000
ADA_FAKE=1 ../core/.venv/bin/python main.py                               # sem o modelo (eventos de mentira)
ADA_HOST=$(tailscale ip -4) caffeinate -i ../core/.venv/bin/python main.py # na tailnet
python3 api/armazem.py [id]                                               # log das conversas no terminal
```

Config no `.env` do core: `ADA_HOST`, `ADA_PORT`, `ADA_IPS_VICTOR`, `ADA_IPS_CONVIDADO`, `ADA_ADAPTER`,
`ADA_TERMINAL` (ver Terminal do Mac), `ADA_DB` (outro banco no lugar do `dados/conversas.db`).
Nunca `0.0.0.0`: o portão é a tailnet.

Carregar a ADA leva uns 30-60s (até lá o `/info` diz `pronta: false` e o `/chat` responde 503). Depois, a 1ª
mensagem leva ~24s até o primeiro token e as seguintes ~1-2s: o cérebro retoma das memórias que guarda em disco.
Config, system de cada usuário e geração vêm do `cerebro.configurar()` do core; aqui só se repassa.

## Quem é quem

Identidade pelo IP de origem: `victor` (a própria máquina + `ADA_IPS_VICTOR`), `convidado` (`ADA_IPS_CONVIDADO`)
e `visitante` (o resto da tailnet). Cada um tem a própria persona e só vê as próprias conversas.

## Rotas

| Rota | O quê |
|---|---|
| `GET /info` | `pronta`, `adapter`, `fake`, `fila`, `usuario`, `origem`, `terminal` (aberto pra quem pede?) |
| `GET /conversas` | as conversas de quem pede, com a `previa` (começo da última resposta) |
| `POST /conversas` | cria (`{"titulo"}`, encurtado em 46 caracteres) -> `id`, `titulo` |
| `GET /conversas/{id}` | a conversa com as mensagens (o `meta` do assistant traz think, tools e tempos) e `gerando` |
| `PATCH /conversas/{id}` | renomeia (`{"titulo"}`) |
| `DELETE /conversas/{id}` | apaga |
| `GET /conversas/{id}/export` | markdown |
| `POST /chat` | `{"conversa", "msg"}` -> stream SSE |
| `GET /terminal/estado` | `tem_senha` |
| `POST /terminal/entrar` | `{"senha"}` -> `sessao`, `pasta` (sem senha no banco, cria esta) |
| `POST /terminal/rodar` | `{"cmd", "pasta"}` -> stream SSE: `saida` (`d`) ... `fim` (`codigo`, `s`, `pasta` onde terminou) |
| `POST /terminal/parar` | Ctrl+C no comando (o segundo pedido mata) -> `sinal` |
| `POST /terminal/sair` | encerra a sessão |

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
| 400 | msg vazia, conversa que não existe (ou de outra pessoa), título vazio no PATCH, senha nova curta, pasta que não existe |
| 401 | terminal: senha errada (diz quantas faltam) ou sessão expirada |
| 404 | conversa que não existe (ou de outra pessoa); terminal desligado ou pedido de quem não é o `victor` |
| 409 | `/chat` com a ADA ainda respondendo o pedido anterior da mesma pessoa (um por vez); terminal com comando rodando, ou parar sem nada rodando |
| 423 | terminal travado por 5 senhas erradas seguidas (15 min) |
| 422 | corpo fora do formato ou texto acima de 20 mil caracteres (no terminal: comando até 4 mil, pasta até mil, senha até 200) |
| 429 | mais de 120 requisições no último minuto vindas do mesmo IP |
| 503 | `/chat` antes da ADA terminar de carregar |

400, 401, 404, 409, 423 e 503 vêm como `{"erro": "..."}`; 422 e 429 no formato padrão do FastAPI, `{"detail": ...}`.
A exceção é o 404 do terminal barrado: vem como `{"detail": "Not Found"}`, igual ao de uma rota que não existe.

## Terminal do Mac

Roda comandos no Mac pelo app. Executa qualquer coisa como o dono do Mac, então vem em camadas:

1. **Desligado por padrão.** Só existe com `ADA_TERMINAL=1` (no `.env` do core ou na linha de comando).
   Desligado, ou pedido de quem não é o `victor`, as rotas respondem 404 como se não existissem.
2. **Digital** no celular a cada abertura da tela (conferida pelo Android, a API não vê).
3. **Senha** a cada abertura. Na primeira vez o app pede pra criar e a API grava só o hash (scrypt com sal)
   na tabela `segredos`. Depois disso o app só confere: nunca sobrescreve. Trocar é só no Mac, de dentro do
   ada-api: `../core/.venv/bin/python -m api.senha` (pede a nova duas vezes, mínimo 8 caracteres).
4. **Sessão de 5 min.** A senha certa abre uma sessão que morre com 5 min parada; os comandos usam a sessão
   (`Authorization: Bearer <sessao>`), não a senha.
5. **5 senhas erradas seguidas** travam o terminal por 15 min.
6. **Um comando por vez**, no zsh de login, com teto de 30 min. O parar manda SIGINT pro grupo do processo
   (o Ctrl+C); o segundo pedido manda SIGKILL. Cada comando vai pro `dados/terminal.log`.

Programa interativo (vim, top, REPL, sudo pedindo senha) não roda: não tem terminal de verdade (PTY) por trás.

As conversas ficam em `dados/conversas.db` (SQLite, fora do git). `ADA_DB=<arquivo>` troca o banco, por exemplo
por um de demonstração: a senha do terminal mora no banco, então lá ela é outra.
