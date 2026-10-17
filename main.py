"""Liga a API da ADA: monta o app com as rotas do api/, sobe o worker do modelo e o uvicorn.
    ../core/.venv/bin/python main.py   (ADA_HOST=$(tailscale ip -4) pra tailnet, ADA_FAKE=1 sem o modelo)"""
import uvicorn
from fastapi import FastAPI

from api import config, identidade, worker
from api.rotas import chat, conversas, info

app = FastAPI()
app.include_router(info.rotas)
app.include_router(conversas.rotas)
app.include_router(chat.rotas)

if __name__ == "__main__":
    print(f"[api] victor: {sorted(identidade.IPS_VICTOR)} | convidado: {sorted(identidade.IPS_CONVIDADO)} "
          f"| resto = visitante")
    worker.ligar()
    print(f"[api] escutando em {config.URL}")
    uvicorn.run(app, host=config.HOST, port=config.PORTA, log_level="warning")
