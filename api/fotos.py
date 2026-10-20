"""As fotos do chat: confere que é imagem de verdade, endireita, encolhe e grava um JPEG novo, sem os metadados
da câmera (GPS, modelo do celular). Ficam em dados/fotos/, do lado do banco, e saem junto com a conversa."""
import base64
import binascii
import uuid
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from api import armazem, limite

PASTA = armazem.DB.parent / "fotos"
PASTA.mkdir(exist_ok=True)
FORMATOS_ACEITOS = {"JPEG", "PNG", "WEBP"}


class FotoInvalida(ValueError):
    """A foto não passou na conferência; a mensagem vai pro app como está."""


def gravar(foto_em_base64):
    """Decodifica, confere, endireita pela orientação da câmera, encolhe pra MAX_LADO_DA_FOTO e devolve o nome do arquivo."""
    try:
        bruto = base64.b64decode(foto_em_base64, validate=True)
    except (binascii.Error, ValueError):
        raise FotoInvalida("a foto não veio em base64")
    if len(bruto) > limite.MAX_FOTO_BYTES:
        raise FotoInvalida("foto grande demais")
    try:
        imagem = Image.open(BytesIO(bruto))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise FotoInvalida("isso não é uma imagem que eu consiga abrir")
    if imagem.format not in FORMATOS_ACEITOS:
        raise FotoInvalida("só aceito foto em JPEG, PNG ou WebP")
    if imagem.width * imagem.height > limite.MAX_PIXELS_DA_FOTO:
        raise FotoInvalida("foto com pixels demais")
    try:
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except Exception:
        raise FotoInvalida("a imagem está corrompida")
    imagem.thumbnail((limite.MAX_LADO_DA_FOTO, limite.MAX_LADO_DA_FOTO))
    nome = f"{uuid.uuid4().hex}.jpg"
    imagem.save(PASTA / nome, "JPEG", quality=90)
    return nome


def caminho(nome):
    """Onde a foto está no disco (o nome vem sempre do banco, nunca direto do pedido)."""
    return PASTA / nome


def apagar(nome):
    """Tira a foto do disco; se já não estava lá, tudo bem."""
    caminho(nome).unlink(missing_ok=True)
