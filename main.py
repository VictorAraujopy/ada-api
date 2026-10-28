"""Liga a API da ADA: monta o app com as rotas do api/, sobe o worker do modelo, o ouvido e o uvicorn.
    ../core/.venv/bin/python main.py   (ADA_HOST=$(tailscale ip -4) pra tailnet, ADA_FAKE=1 sem o modelo)"""
import uvicorn
from fastapi import Depends, FastAPI

from api import config, limite, senha, transcricao, worker
from api.rotas import chat, conversas, info, ouvir, terminal

app = FastAPI(dependencies=[Depends(limite.por_minuto)])  # o rate limit vale pra todas as rotas
app.add_middleware(limite.TamanhoDoCorpo)  # 413 pra corpo grande demais, antes de ler
app.include_router(info.rotas)
app.include_router(conversas.rotas)
app.include_router(chat.rotas)
app.include_router(ouvir.rotas)
app.include_router(terminal.rotas)

if __name__ == "__main__":
    if config.TERMINAL:
        print("[api] terminal LIGADO" + ("" if senha.existe() else
              " — sem senha ainda: o app pede pra criar na primeira vez"))
    worker.ligar()
    transcricao.ligar()  # o Whisper sobe junto, também no modo FAKE: dá pra testar a voz do app sem a ADA
    print(f"[api] escutando em {config.URL}")
    uvicorn.run(app, host=config.HOST, port=config.PORTA, log_level="warning")
