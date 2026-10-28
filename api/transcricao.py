"""O ouvido da ADA dentro da API: o Whisper do core (1_ada/voz) aberto uma vez numa thread, e uma transcrição por vez.
A rota POST /ouvir (rotas/ouvir.py) só traduz o HTTP e chama daqui; ela não importa nada do core."""
import threading

from api import config  # noqa: F401  (importar o config põe o 1_ada do core no sys.path)
from voz import ouvido

AudioInvalido = ouvido.AudioInvalido  # áudio fora do formato: a rota devolve 400

whisper = None  # o Whisper que o ligar() abre; None enquanto carrega ou se não abriu
abriu_com_erro = False  # o Whisper não abriu (sem rede na 1ª vez, Hugging Face fora, disco cheio): o motivo vai no log
# duas transcrições juntas dividiriam os mesmos 4 núcleos e as duas demorariam o dobro
_um_por_vez = threading.Lock()
# o pedido espera a vez até isto (um pedaço leva 4-7 s); o app desiste do dele em 45 s
ESPERA_PELA_VEZ_S = 30


class Ocupado(Exception):
    """Esperou ESPERA_PELA_VEZ_S e a transcrição anterior ainda não acabou."""


def _abrir_o_whisper():
    """Carrega o Whisper (uns 2 s; na primeira vez baixa ~1,6 GB do Hugging Face); se falhar, o motivo vai pro log."""
    global whisper, abriu_com_erro
    print("[api] carregando o ouvido (Whisper turbo)...")
    try:
        whisper = ouvido.carregar()
    except Exception as erro:
        abriu_com_erro = True
        print(f"[api] o ouvido não abriu: {type(erro).__name__}: {erro}")
        return
    print("[api] ouvido pronto")


def ligar():
    """Abre o Whisper numa thread: a API sobe na hora e o /ouvir responde 503 até ele ficar pronto."""
    threading.Thread(target=_abrir_o_whisper, daemon=True).start()


def pronto():
    return whisper is not None


def transcrever(wav):
    """Transcreve um pedaço e devolve (texto sem o comando, comando ou None). Com outra transcrição andando, espera
    a vez até ESPERA_PELA_VEZ_S (senão levanta Ocupado); áudio fora do formato levanta AudioInvalido."""
    if not _um_por_vez.acquire(timeout=ESPERA_PELA_VEZ_S):
        raise Ocupado()
    try:
        texto = ouvido.transcrever(whisper, wav)
    finally:
        _um_por_vez.release()
    return ouvido.separar_comando(texto)
