"""Conversas da API no SQLite local (conversas.db): conversas + mensagens, com o meta do app no assistant
e o nome da foto (api/fotos.py) na mensagem do usuário que mandou uma.
As mensagens quem grava é a guardar do core (1_ada/conhecimento/conhecimento.py), com a conexão dela.
Aqui, uma conexão só, com lock: os endpoints rodam em threads do Starlette.
Rodado direto vira log no terminal:  python3 api/armazem.py [id]"""
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

DB = Path(os.environ.get("ADA_DB") or Path(__file__).resolve().parent.parent / "dados" / "conversas.db")
DB.parent.mkdir(exist_ok=True)

_con = sqlite3.connect(DB, check_same_thread=False)
_con.row_factory = sqlite3.Row
_trava = threading.Lock()

with _trava, _con:
    _con.execute("""CREATE TABLE IF NOT EXISTS conversas (
        id TEXT PRIMARY KEY, titulo TEXT, criada REAL, atualizada REAL)""")
    # migração: a coluna dono sai (a API tem um usuário só)
    if "dono" in [c[1] for c in _con.execute("PRAGMA table_info(conversas)")]:
        _con.execute("ALTER TABLE conversas DROP COLUMN dono")
    _con.execute("""CREATE TABLE IF NOT EXISTS mensagens (
        n INTEGER PRIMARY KEY AUTOINCREMENT, conversa TEXT NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, meta TEXT, criada REAL)""")
    # migração: coluna foto (mensagens antigas ficam sem)
    if "foto" not in [c[1] for c in _con.execute("PRAGMA table_info(mensagens)")]:
        _con.execute("ALTER TABLE mensagens ADD COLUMN foto TEXT")
    # segredos: só hash (ex.: a senha do terminal, ver api/senha.py)
    _con.execute("CREATE TABLE IF NOT EXISTS segredos (nome TEXT PRIMARY KEY, valor TEXT NOT NULL)")


def _sql(query, args=()):
    with _trava, _con:
        return _con.execute(query, args).fetchall()


def criar(primeira_msg):
    """Cria a conversa (título = primeira mensagem encurtada)."""
    titulo = " ".join((primeira_msg or "conversa").split())
    if len(titulo) > 46:
        titulo = titulo[:46].rstrip() + "…"
    cid = uuid.uuid4().hex[:12]
    agora = time.time()
    _sql("INSERT INTO conversas (id, titulo, criada, atualizada) VALUES (?,?,?,?)", (cid, titulo, agora, agora))
    return {"id": cid, "titulo": titulo}


def listar():
    """As conversas, da mais recente pra mais antiga. A prévia é o começo da última resposta da ADA."""
    rs = _sql("""SELECT c.id, c.titulo, c.atualizada,
                 (SELECT COUNT(*) FROM mensagens m WHERE m.conversa = c.id) AS n,
                 (SELECT substr(m.content, 1, 90) FROM mensagens m
                  WHERE m.conversa = c.id AND m.role = 'assistant' ORDER BY m.n DESC LIMIT 1) AS previa
                 FROM conversas c ORDER BY c.atualizada DESC""")
    return [dict(r) for r in rs]


def existe(cid):
    return bool(_sql("SELECT 1 FROM conversas WHERE id=?", (cid,)))


def titulo(cid):
    r = _sql("SELECT titulo FROM conversas WHERE id=?", (cid,))
    return r[0]["titulo"] if r else None


def mensagens(cid):
    rs = _sql("SELECT n, role, content, meta, foto FROM mensagens WHERE conversa=? ORDER BY n", (cid,))
    return [{"n": r["n"], "role": r["role"], "content": r["content"],
             "meta": json.loads(r["meta"]) if r["meta"] else None, "foto": r["foto"]} for r in rs]


def fotos(cid):
    """Os nomes das fotos mandadas nessa conversa."""
    return [r["foto"] for r in _sql("SELECT foto FROM mensagens WHERE conversa=? AND foto IS NOT NULL", (cid,))]


def renomear(cid, novo):
    novo = " ".join((novo or "").split())[:60]
    if novo:
        _sql("UPDATE conversas SET titulo=? WHERE id=?", (novo, cid))
    return novo


def apagar(cid):
    _sql("DELETE FROM mensagens WHERE conversa=?", (cid,))
    _sql("DELETE FROM conversas WHERE id=?", (cid,))


def gravar_segredo(nome, valor):
    _sql("INSERT OR REPLACE INTO segredos VALUES (?,?)", (nome, valor))


def segredo(nome):
    r = _sql("SELECT valor FROM segredos WHERE nome=?", (nome,))
    return r[0]["valor"] if r else None


if __name__ == "__main__":
    # log no terminal: sem argumento lista todas; com o id, mostra a conversa inteira
    import sys

    if len(sys.argv) < 2:
        for c in listar():
            quando = time.strftime("%d/%m %H:%M", time.localtime(c["atualizada"]))
            print(f"{c['id']}  {quando}  {c['n']:>3} msgs  {c['titulo']}")
    elif not titulo(sys.argv[1]):
        sys.exit("conversa não existe")
    else:
        print(f"# {titulo(sys.argv[1])}\n")
        for m in mensagens(sys.argv[1]):
            for t in (m["meta"] or {}).get("tools", []):
                print(f"  🔧 {t['nome']} → {t['res']}")
            if m["foto"]:
                print(f"  📷 dados/fotos/{m['foto']}")
            print(f"{'ADA' if m['role'] == 'assistant' else 'user'}: {m['content']}\n")
