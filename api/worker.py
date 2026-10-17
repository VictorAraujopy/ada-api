"""A thread única dona do modelo: carrega a ADA uma vez e tira os pedidos da fila `entrada`, um por vez.
Cada pedido é um Job com a própria fila de saída; no modo FAKE os eventos são de mentira, sem carregar o modelo."""
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from api import config

# Config, system prompt e params de geração vivem TODOS no núcleo (1_ada/cerebro.py): aqui só importa e repassa.
# No modo FAKE o núcleo nem é carregado, então os systems ficam vazios (os eventos de mentira ignoram).
SYSTEMS = {"victor": "", "convidado": "", "visitante": ""}  # preenchidos quando o modelo carrega


@dataclass
class Job:
    historico: list                                          # snapshot da conversa
    saida: queue.Queue = field(default_factory=queue.Queue)  # eventos só deste job


entrada = queue.Queue()
pronta = threading.Event()


def _eventos_fake(historico):
    """Eventos de mentira (think -> tool -> resp) pra testar o app sem o modelo."""
    msg = historico[-1]["content"]
    pensamento = (f'O Victor mandou "{msg}". Modo fake ligado, então eu não penso de '
                  f'verdade — só finjo bem. Vou fingir uma tool também. ')
    for palavra in pensamento.split(" "):
        time.sleep(0.03)
        yield {"t": "think", "d": palavra + " "}
    yield {"t": "tool", "nome": "que_horas", "args": {}, "res": "segunda, 09/06/2026, 16:20"}
    resposta = ("Interface de ponta a ponta, com **negrito**, `código` e\n"
                "- até lista\n- funcionando.\n\nQuando for pra valer, tira o ADA_FAKE=1. ")
    for palavra in resposta.split(" "):
        time.sleep(0.04)
        yield {"t": "resp", "d": palavra + " "}
    yield {"t": "fim"}


def _rodar():
    """Carrega uma vez e processa um job por vez."""
    if config.FAKE:
        gerar = _eventos_fake
        print("[api] MODO FAKE — sem modelo, eventos de mentira")
    else:
        import cerebro  # núcleo da ADA (só carrega o modelo fora do modo FAKE)

        SYSTEMS["victor"] = cerebro.SYSTEM
        SYSTEMS["convidado"] = cerebro.SYSTEM_CONVIDADO
        SYSTEMS["visitante"] = cerebro.SYSTEM_VISITANTE
        print(f"[api] carregando a ADA ({Path(cerebro.ADAPTER).name})... (uns 30-60s)")
        model, processor, config_modelo = cerebro.carregar()

        def gerar(historico):
            return cerebro.responder_eventos(model, processor, config_modelo, historico, **cerebro.GEN)

    pronta.set()
    print(f"[api] PRONTA  ->  {config.URL}")

    while True:
        job = entrada.get()
        try:
            for ev in gerar(job.historico):
                job.saida.put(ev)
        except Exception as e:
            job.saida.put({"t": "erro", "d": f"{type(e).__name__}: {e}"})
        finally:
            job.saida.put(None)   # sinal de fim pro endpoint, aconteça o que acontecer


def ligar():
    """Sobe a thread do worker (daemon: morre junto com o servidor)."""
    threading.Thread(target=_rodar, daemon=True).start()
