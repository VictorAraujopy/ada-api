"""Liga a API da ADA: monta o app com as rotas do api/, sobe o worker do modelo e o uvicorn.
    ../core/.venv/bin/python main.py   (ADA_HOST=$(tailscale ip -4) pra tailnet, ADA_FAKE=1 sem o modelo)"""
import uvicorn
from fastapi import Depends, FastAPI

from api import config, identidade, limite, senha, worker
from api.rotas import chat, conversas, info, terminal

app = FastAPI(dependencies=[Depends(limite.por_ip)])  # o rate limit vale pra todas as rotas
app.add_middleware(limite.TamanhoDoCorpo)  # 413 pra corpo grande demais, antes de ler
app.include_router(info.rotas)
app.include_router(conversas.rotas)
app.include_router(chat.rotas)
app.include_router(terminal.rotas)

if __name__ == "__main__":
    print(f"[api] victor: {sorted(identidade.IPS_VICTOR)} | convidado: {sorted(identidade.IPS_CONVIDADO)} "
          f"| resto = visitante")
    if config.TERMINAL:
        print("[api] terminal LIGADO (só o victor)" + ("" if senha.existe() else
              " — sem senha ainda: o app pede pra criar na primeira vez"))
    worker.ligar()
    print(f"[api] escutando em {config.URL}")
    uvicorn.run(app, host=config.HOST, port=config.PORTA, log_level="warning")
