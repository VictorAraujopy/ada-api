"""A senha do terminal: o banco guarda só o hash (scrypt com sal aleatório), nunca a senha.
Criar: o app cria na primeira vez que abre o terminal (sem senha no banco, o /terminal/entrar grava).
Trocar: só no próprio Mac, nunca pela rede:  ../core/.venv/bin/python -m api.senha  (de dentro do ada-api)"""
import getpass
import hashlib
import hmac
import secrets
import sys

from api import armazem

# custo do scrypt: 2^14 é o padrão pra senha digitada (dezenas de ms por tentativa, caro pra quem chuta em massa)
N, R, P = 2 ** 14, 8, 1
MINIMO = 8
NOME = "senha_terminal"


def _hash(senha, sal):
    return hashlib.scrypt(senha.encode(), salt=sal, n=N, r=R, p=P)


def definir(senha):
    sal = secrets.token_bytes(16)
    armazem.gravar_segredo(NOME, f"{sal.hex()}:{_hash(senha, sal).hex()}")


def existe():
    return armazem.segredo(NOME) is not None


def confere(senha):
    """A senha bate com o hash guardado? Sem senha criada, nada bate."""
    guardado = armazem.segredo(NOME)
    if not guardado:
        return False
    sal_hex, hash_hex = guardado.split(":")
    calculado = _hash(senha, bytes.fromhex(sal_hex)).hex()
    return hmac.compare_digest(calculado, hash_hex)  # tempo constante: não vaza quantos caracteres acertou


if __name__ == "__main__":
    nova = getpass.getpass("senha nova do terminal: ")
    if len(nova) < MINIMO:
        sys.exit(f"curta demais: mínimo {MINIMO} caracteres")
    if getpass.getpass("de novo: ") != nova:
        sys.exit("não bateu, nada mudou")
    definir(nova)
    print("senha do terminal gravada (só o hash fica no banco)")
