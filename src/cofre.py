"""Cofre dos dados de seguidores (08/11/2026, revisão de segurança).

O repositório é público: os arquivos com @ e texto das conversas (busca_ze.json, respondidos.json)
são gravados trancados com a senha do segredo DADOS_CHAVE. Sem a senha ninguém lê; o robô lê normal.

- Sem DADOS_CHAVE: grava aberto, como antes (nada quebra enquanto o segredo não é cadastrado).
- Arquivo trancado e sem DADOS_CHAVE: PARA com erro (nunca sobrescreve e perde os dados).

Só biblioteca padrão do Python (o workflow 3 instala só "requests"): HMAC-SHA256 em modo contador
para cifrar e HMAC-SHA256 para conferir que o arquivo não foi mexido (cifra-depois-autentica).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets

PREFIXO = "GVCOFRE1:"


def _chave():
    return os.getenv("DADOS_CHAVE", "").strip()


def _chaves(senha):
    base = hashlib.sha256(senha.encode("utf-8")).digest()
    return (hmac.new(base, b"cifrar", hashlib.sha256).digest(),
            hmac.new(base, b"conferir", hashlib.sha256).digest())


def _fluxo(k_cifra, nonce, tamanho):
    blocos = []
    for i in range((tamanho + 31) // 32):
        blocos.append(hmac.new(k_cifra, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest())
    return b"".join(blocos)[:tamanho]


def trancar(texto, senha):
    k_cifra, k_conf = _chaves(senha)
    dados = texto.encode("utf-8")
    nonce = secrets.token_bytes(16)
    cifrado = bytes(a ^ b for a, b in zip(dados, _fluxo(k_cifra, nonce, len(dados))))
    selo = hmac.new(k_conf, nonce + cifrado, hashlib.sha256).digest()
    return PREFIXO + base64.b64encode(nonce + cifrado + selo).decode("ascii") + "\n"


def abrir(texto, senha):
    k_cifra, k_conf = _chaves(senha)
    bruto = base64.b64decode(texto[len(PREFIXO):].strip())
    nonce, cifrado, selo = bruto[:16], bruto[16:-32], bruto[-32:]
    if not hmac.compare_digest(selo, hmac.new(k_conf, nonce + cifrado, hashlib.sha256).digest()):
        raise RuntimeError("DADOS_CHAVE não confere com o arquivo trancado (senha trocada ou arquivo mexido).")
    return bytes(a ^ b for a, b in zip(cifrado, _fluxo(k_cifra, nonce, len(cifrado)))).decode("utf-8")


def ler_json(arq, padrao):
    if not arq.exists():
        return padrao
    texto = arq.read_text(encoding="utf-8")
    if texto.startswith(PREFIXO):
        senha = _chave()
        if not senha:
            raise RuntimeError(f"{arq.name} está trancado e falta o segredo DADOS_CHAVE neste workflow.")
        texto = abrir(texto, senha)
    return json.loads(texto)


def gravar_json(arq, dados, indent=1):
    texto = json.dumps(dados, ensure_ascii=False, indent=indent)
    senha = _chave()
    arq.parent.mkdir(parents=True, exist_ok=True)
    if senha and arq.exists():   # nada mudou: não regrava (trancar sorteia de novo e viraria commit à toa)
        atual = arq.read_text(encoding="utf-8")
        try:
            if atual.startswith(PREFIXO) and abrir(atual, senha) == texto:
                return
        except RuntimeError:
            pass
    arq.write_text(trancar(texto, senha) if senha else texto, encoding="utf-8")


def oculto(usuario):
    """@ abreviado para os logs públicos das Actions (ex.: fredericosn → fr…sn)."""
    u = str(usuario or "?").lstrip("@")
    return u if len(u) <= 4 else f"{u[:2]}…{u[-2:]}"
