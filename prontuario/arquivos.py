"""
Validação e armazenamento de arquivos enviados ao prontuário (exames, laudos, fotos).

Regras:
- Só tipos permitidos (PDF, JPEG, PNG, WEBP), conferidos pela extensão E pela assinatura
  binária do arquivo (magic bytes). Um .exe renomeado para .pdf é recusado.
- Tamanho máximo configurável em settings.ANEXO_TAMANHO_MAX_MB.
- O nome salvo em disco é um UUID. O nome original fica só no banco, como texto.
"""

import os
import uuid
from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

# extensão -> (tipo MIME, assinaturas aceitas no início do arquivo)
TIPOS_PERMITIDOS = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".webp": ("image/webp", (b"RIFF",)),
}


def tamanho_maximo_bytes():
    return getattr(settings, "ANEXO_TAMANHO_MAX_MB", 10) * 1024 * 1024


def nome_original_seguro(nome):
    """Remove caminhos e caracteres estranhos do nome enviado pelo usuário."""
    base = PurePath(nome or "arquivo").name
    limpo = "".join(c for c in base if c.isalnum() or c in " ._-()")
    return (limpo or "arquivo")[:200]


def validar_arquivo(arquivo):
    """Levanta ValidationError se o arquivo não for aceito. Retorna (mime, extensão)."""
    nome = arquivo.name or ""
    extensao = os.path.splitext(nome)[1].lower()
    if extensao not in TIPOS_PERMITIDOS:
        permitidos = ", ".join(sorted(TIPOS_PERMITIDOS))
        raise ValidationError(f"Tipo de arquivo não permitido. Envie: {permitidos}.")

    if arquivo.size > tamanho_maximo_bytes():
        raise ValidationError(
            f"Arquivo maior que {settings.ANEXO_TAMANHO_MAX_MB} MB."
        )
    if arquivo.size == 0:
        raise ValidationError("O arquivo está vazio.")

    mime, assinaturas = TIPOS_PERMITIDOS[extensao]
    arquivo.seek(0)
    cabecalho = arquivo.read(16)
    arquivo.seek(0)
    if not any(cabecalho.startswith(a) for a in assinaturas):
        raise ValidationError("O conteúdo do arquivo não corresponde ao tipo informado.")
    if extensao == ".webp" and cabecalho[8:12] != b"WEBP":
        raise ValidationError("O conteúdo do arquivo não corresponde ao tipo informado.")
    return mime, extensao


def caminho_anexo(clinica_id, extensao):
    """Caminho relativo a MEDIA_ROOT: <clinica>/<ano>/<mes>/<uuid><extensão>."""
    agora = timezone.now()
    return f"clinica_{clinica_id}/{agora:%Y}/{agora:%m}/{uuid.uuid4().hex}{extensao}"
