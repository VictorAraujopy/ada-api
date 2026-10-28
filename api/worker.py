"""A thread única dona do modelo: carrega a ADA uma vez e tira os pedidos da fila `entrada`, um por vez.
Cada pedido é um Job com a própria fila de saída; no modo FAKE os eventos são de mentira, sem carregar o modelo.
Quem grava a pergunta e a resposta no banco é o worker, juntas, pela guardar do core: se o cliente cair no meio
do stream, elas ficam salvas igual."""
import queue
import threading
import time
from dataclasses import dataclass, field

from api import config
from conhecimento.conhecimento import guardar  # 1_ada do core: o config acima põe ele no sys.path

# Config, system prompt e params de geração vivem TODOS no núcleo (1_ada/cerebro.py): aqui só importa e repassa.
# No modo FAKE o núcleo nem é carregado, então o system fica vazio (os eventos de mentira ignoram).
SYSTEM = ""  # preenchido quando o modelo carrega


@dataclass
class Job:
    conversa: str                                            # onde a resposta vai ser gravada
    historico: list                                          # snapshot da conversa
    saida: queue.Queue = field(default_factory=queue.Queue)  # eventos só deste job


entrada = queue.Queue()
pronta = threading.Event()
respondendo = None  # a conversa que a ADA está respondendo agora (um pedido por vez)
adapter_carregado = None  # o que o cerebro.carregar() escolheu (a de 4 bits com o PC, ou a do Mac)


def pedir(job):
    """Marca a conversa como sendo respondida e põe o job na fila; o worker desmarca quando termina."""
    global respondendo
    respondendo = job.conversa
    entrada.put(job)


def _eventos_fake(historico):
    """Eventos de mentira (think -> tool -> resp) pra testar o app sem o modelo."""
    ultima = historico[-1]["content"]
    # com foto, o conteúdo vem em partes (imagem + texto): o fake só repete o texto
    msg = ultima if isinstance(ultima, str) else "[foto] " + ultima[-1]["text"]
    pensamento = (f'O Victor mandou "{msg}". Modo fake ligado, então eu não penso de '
                  f'verdade — só finjo bem. Vou fingir uma tool também. ')
    for palavra in pensamento.split(" "):
        time.sleep(0.03)
        yield {"t": "think", "d": palavra + " "}
    yield {"t": "tool", "nome": "calcular", "args": {"expressao": "6*7"}, "res": "6*7 = 42"}
    resposta = ("Interface de ponta a ponta, com **negrito**, `código` e\n"
                "- até lista\n- funcionando.\n\nQuando for pra valer, tira o ADA_FAKE=1. ")
    for palavra in resposta.split(" "):
        time.sleep(0.04)
        yield {"t": "resp", "d": palavra + " "}
    yield {"t": "fim"}


def _atender(job, gerar):
    """Repassa cada evento pra saída do job e grava a pergunta e a resposta antes do fim:
    quem recarrega a conversa depois do fim já acha as duas lá."""
    resposta, think, tools = "", "", []
    t0, t_resp = time.time(), None
    for ev in gerar(job.historico):
        if ev["t"] == "think":
            think += ev["d"]
        elif ev["t"] == "tool":
            tools.append({"nome": ev["nome"], "res": str(ev["res"])[:200]})
        elif ev["t"] == "resp":
            t_resp = t_resp or time.time()
            resposta += ev["d"]
        elif ev["t"] == "fim" and resposta.strip():   # só entra na memória da conversa se a geração terminou
            meta = {"pensou_s": round((t_resp or time.time()) - t0, 1),
                    "respondeu_s": round(time.time() - (t_resp or time.time()), 1),
                    "tools": tools, "think": think.strip()}
            historico_com_resposta = job.historico + [{"role": "assistant", "content": resposta.strip()}]
            guardar(job.conversa, historico_com_resposta, meta)
        job.saida.put(ev)


def _rodar():
    """Carrega uma vez e processa um job por vez."""
    global SYSTEM, respondendo, adapter_carregado
    if config.FAKE:
        gerar = _eventos_fake
        print("[api] MODO FAKE — sem modelo, eventos de mentira")
    else:
        import cerebro  # núcleo da ADA (só carrega o modelo fora do modo FAKE)

        config_modelo = cerebro.configurar()
        SYSTEM = config_modelo.system
        print(f"[api] carregando a ADA ({config_modelo.adapter})... (uns 30-60s)")
        model, processor, config_modelo = cerebro.carregar(config_modelo)
        adapter_carregado = config_modelo.adapter
        onde = f"dividida com o PC ({config_modelo.servidor_rpc})" if config_modelo.servidor_rpc else "só no Mac"
        print(f"[api] carregou {adapter_carregado}, {onde}")

        def gerar(historico):
            return cerebro.responder_eventos(model, processor, config_modelo, historico, **config_modelo.geracao)

    pronta.set()
    print(f"[api] PRONTA  ->  {config.URL}")

    while True:
        job = entrada.get()
        try:
            _atender(job, gerar)
        except Exception as e:
            job.saida.put({"t": "erro", "d": f"{type(e).__name__}: {e}"})
        finally:
            respondendo = None
            job.saida.put(None)   # sinal de fim pro endpoint, aconteça o que acontecer


def ligar():
    """Sobe a thread do worker (daemon: morre junto com o servidor)."""
    threading.Thread(target=_rodar, daemon=True).start()
