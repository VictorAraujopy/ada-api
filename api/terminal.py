"""O terminal do Mac pelo app: a senha abre uma sessão, um comando roda por vez, a saída sai em eventos e o parar é Ctrl+C.
Quem barra (ADA_TERMINAL=1 e só o victor) é a rota, em api/rotas/terminal.py. Cada comando vai pro dados/terminal.log."""
import codecs
import os
import queue
import secrets
import shlex
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from api import config, senha

SESSAO_MAX_PARADA = 5 * 60  # a sessão morre com 5 min sem uso, igual à trava do app
TENTATIVAS = 5  # senhas erradas seguidas até travar
TRAVA = 15 * 60
TETO_COMANDO = 30 * 60  # nenhum comando passa disso
LOG = config.RAIZ / "dados" / "terminal.log"
CASA = str(Path.home())

_sessoes = {}  # sessao -> último uso (monotonic)
_erradas = 0
_travado_ate = 0.0
_atual = None  # o último Comando; rodando enquanto não acabou


def curta(pasta):
    """/Users/fulano/x -> ~/x (é o que o app mostra e devolve)."""
    return "~" + pasta[len(CASA):] if pasta == CASA or pasta.startswith(CASA + "/") else pasta


def travado_por():
    """Segundos que ainda faltam de trava por senha errada (0 = destravado)."""
    return max(0, int(_travado_ate - time.monotonic()))


def tentativas_restantes():
    return TENTATIVAS - _erradas


def _abrir_sessao():
    sessao = secrets.token_urlsafe(32)
    _sessoes[sessao] = time.monotonic()
    return sessao


def criar_senha(nova):
    """A primeira vez: grava a senha (só o hash) e já abre a sessão."""
    senha.definir(nova)
    return _abrir_sessao()


def tentar_senha(tentativa):
    """Senha certa abre uma sessão nova e zera os erros; errada conta, e a quinta seguida trava."""
    global _erradas, _travado_ate
    if senha.confere(tentativa):
        _erradas = 0
        return _abrir_sessao()
    _erradas += 1
    if _erradas >= TENTATIVAS:
        _erradas = 0
        _travado_ate = time.monotonic() + TRAVA
    return None


def sessao_valida(sessao):
    """A sessão existe e foi usada nos últimos 5 min; usar renova o prazo."""
    ultimo_uso = _sessoes.get(sessao)
    if ultimo_uso is None or time.monotonic() - ultimo_uso > SESSAO_MAX_PARADA:
        _sessoes.pop(sessao, None)
        return False
    _sessoes[sessao] = time.monotonic()
    return True


def sair(sessao):
    _sessoes.pop(sessao, None)


def rodando():
    """O comando em andamento, ou None."""
    return _atual if _atual and not _atual.acabou.is_set() else None


def comecar(texto, pasta):
    global _atual
    _atual = Comando(texto, pasta)
    return _atual


def _registrar(linha):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {linha}\n")


class Comando:
    """Um comando no zsh de login, com stdout e stderr juntos (na ordem em que saem) virando eventos na fila `saida`:
    {"t": "saida", "d": texto} ... {"t": "fim", "codigo", "s", "pasta"} e por último None."""

    def __init__(self, texto, pasta):
        self.texto = texto
        self.pasta = pasta
        self.saida = queue.Queue()
        self.acabou = threading.Event()
        self.pedidos_de_parar = 0
        self._inicio = time.monotonic()
        # o zsh escreve aqui a pasta onde o comando terminou: é o que faz um `cd` valer pro próximo comando
        descritor, self._arquivo_pasta = tempfile.mkstemp(prefix="ada-pasta-")
        os.close(descritor)
        script = f"{texto}\n__codigo=$?\npwd > {shlex.quote(self._arquivo_pasta)}\nexit $__codigo"
        self.processo = subprocess.Popen(
            ["/bin/zsh", "-lc", script], cwd=pasta,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            start_new_session=True,  # grupo de processos próprio: o Ctrl+C chega nos filhos também
            env={**os.environ, "PYTHONUNBUFFERED": "1"})
        _registrar(f"$ {texto}    [{curta(pasta)}]")
        self._teto = threading.Timer(TETO_COMANDO, self._mandar, args=(signal.SIGKILL,))
        self._teto.start()
        # quem lê a saída é uma thread, não o stream: se o app cair, o pipe continua sendo esvaziado e o comando não trava
        threading.Thread(target=self._ler, daemon=True).start()

    def parar(self):
        """O primeiro pedido é o Ctrl+C (SIGINT no grupo todo); o segundo mata na marra (SIGKILL)."""
        self.pedidos_de_parar += 1
        sinal = signal.SIGINT if self.pedidos_de_parar == 1 else signal.SIGKILL
        self._mandar(sinal)
        return sinal.name

    def _mandar(self, sinal):
        try:
            os.killpg(self.processo.pid, sinal)
        except ProcessLookupError:
            pass  # já tinha acabado

    def _ler(self):
        decodificador = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while pedaco := self.processo.stdout.read1(4096):
            self.saida.put({"t": "saida", "d": decodificador.decode(pedaco)})
        retorno = self.processo.wait()
        self._teto.cancel()
        codigo = 128 - retorno if retorno < 0 else retorno  # morto por sinal vira 128+sinal, como no shell (Ctrl+C = 130)
        segundos = round(time.monotonic() - self._inicio, 1)
        pasta_final = Path(self._arquivo_pasta).read_text().strip() or self.pasta
        os.unlink(self._arquivo_pasta)
        _registrar(f"  saiu {codigo} em {segundos}s")
        self.saida.put({"t": "fim", "codigo": codigo, "s": segundos, "pasta": curta(pasta_final)})
        self.acabou.set()
        self.saida.put(None)
