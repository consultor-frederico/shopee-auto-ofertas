"""Mercado Livre (afiliado do Garimpo VIP), 04/11/2026. Ainda NÃO posta nada: só conecta e testa a busca.

Segredos (o Fred cadastra): ML_CLIENT_ID, ML_CLIENT_SECRET e ML_REFRESH_TOKEN (este sai do workflow 29).
Atenção: no Mercado Livre o refresh token só vale UMA vez. Toda troca devolve um novo, que o workflow
salva sozinho no segredo ML_REFRESH_TOKEN com o GH_PAT. Se uma rodada falhar antes de salvar, é só
conectar de novo pelo workflow 29.

Link de afiliado: o painel gera links cifrados (/social/<perfil>?...&ref=...), que não dá para gerar daqui.
O robô monta o endereço limpo do produto + a etiqueta (link_afiliado). Teste de 04/11: abre o produto;
falta confirmar se o clique conta no painel.

Uso:
  python -m src.mercadolivre conectar   → sem ML_CODIGO: imprime o link de autorização
                                          com ML_CODIGO: troca o código pelo refresh token
  python -m src.mercadolivre status     → confere o token e mostra a conta conectada
  python -m src.mercadolivre busca TERMO → testa a busca com token e mostra 5 resultados
                                          (sem ML_REFRESH_TOKEN tenta Client Credentials; se a busca
                                          recusar, imprime o link para conectar a conta)
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests

API = "https://api.mercadolibre.com"
AUTH = "https://auth.mercadolivre.com.br/authorization"
REDIRECT = "https://garimpovipbr.github.io/"   # página pública sem o nome do Fred
ETIQUETA = os.getenv("ML_ETIQUETA", "garimpovip").strip() or "garimpovip"
MATT_TOOL = os.getenv("ML_MATT_TOOL", "42691474").strip() or "42691474"
ARQ_NOVO_TOKEN = Path(os.getenv("RUNNER_TEMP", "/tmp")) / "ml_refresh.txt"


def _env(nome):
    return os.getenv(nome, "").strip()


def ligado():
    return all(_env(n) for n in ("ML_CLIENT_ID", "ML_CLIENT_SECRET"))


def _token(dados):
    r = requests.post(f"{API}/oauth/token", timeout=30, data={
        "client_id": _env("ML_CLIENT_ID"), "client_secret": _env("ML_CLIENT_SECRET"), **dados},
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
    j = r.json() if r.content else {}
    if "access_token" not in j:
        raise RuntimeError(f"Mercado Livre recusou o token ({r.status_code}): {j.get('error')} {j.get('message')}")
    if j.get("refresh_token"):   # vale uma vez só: o workflow salva o novo no segredo
        ARQ_NOVO_TOKEN.write_text(j["refresh_token"])
    return j


_cache = {}


def access_token():
    """Com ML_REFRESH_TOKEN usa o token da conta; sem ele tenta Client Credentials (só ID + chave secreta)."""
    if "tok" not in _cache:
        if _env("ML_REFRESH_TOKEN"):
            dados = {"grant_type": "refresh_token", "refresh_token": _env("ML_REFRESH_TOKEN")}
        else:
            dados = {"grant_type": "client_credentials"}
        _cache["tok"] = _token(dados)["access_token"]
    return _cache["tok"]


def _get(caminho, **params):
    r = requests.get(f"{API}{caminho}", params=params, timeout=30,
                     headers={"Authorization": f"Bearer {access_token()}", "Accept": "application/json"})
    return r


def link_afiliado(url):
    """Endereço limpo do produto (/p/MLB... ou MLB-...) + etiqueta do Garimpo."""
    m = re.search(r"/p/(MLB\d+)", url)
    if m:
        base = f"https://www.mercadolivre.com.br/p/{m.group(1)}"
    else:
        p = urlparse(url)
        base = f"{p.scheme or 'https'}://{p.netloc}{p.path}"
    return f"{base}?matt_word={ETIQUETA}&matt_tool={MATT_TOOL}"


def _codigo():
    bruto = unquote(_env("ML_CODIGO"))
    if "code=" in bruto:   # o Fred pode colar o endereço inteiro da página
        bruto = parse_qs(urlparse(bruto).query).get("code", [bruto])[0]
    return bruto.strip()


def _conectar():
    if not _env("ML_CLIENT_ID"):
        sys.exit("Falta o segredo ML_CLIENT_ID.")
    codigo = _codigo()
    if not codigo:
        print("1) Abra este link no navegador logado na conta do Mercado Livre do afiliado e autorize:")
        print(f"{AUTH}?response_type=code&client_id={_env('ML_CLIENT_ID')}&redirect_uri={quote(REDIRECT, safe='')}")
        print("2) Vai abrir a página do Garimpo com ?code=TG-... no endereço. Copie o endereço inteiro e rode")
        print("   este workflow de novo colando no campo do código (vale ~10 min).")
        return
    j = _token({"grant_type": "authorization_code", "code": codigo, "redirect_uri": REDIRECT})
    print(f"✅ Conectado (escopos: {j.get('scope')}). O refresh token vai ser salvo no segredo ML_REFRESH_TOKEN.")


def _status():
    if not _env("ML_REFRESH_TOKEN"):
        access_token()
        print("✅ Entrou só com ID + chave secreta (Client Credentials).")
        return
    r = _get("/users/me")
    if r.status_code != 200:
        sys.exit(f"❌ /users/me respondeu {r.status_code}: {r.text[:300]}")
    u = r.json()
    print(f"✅ Token ok. Conta: {u.get('nickname')} (id {u.get('id')}).")


def _busca(termo):
    r = _get("/sites/MLB/search", q=termo, limit=5)
    if r.status_code != 200:
        print(f"❌ Busca respondeu {r.status_code}: {r.text[:300]}")
        if not _env("ML_REFRESH_TOKEN"):
            print("Próximo passo: conectar a conta. Abra o link abaixo, autorize e rode o 29 de novo colando o endereço.")
            _conectar()
        return
    itens = r.json().get("results", [])
    print(f"✅ Busca com token funcionou: {termo} · {len(itens)} resultados")
    for it in itens:
        print(f"• {it.get('title', '')[:70]} · R$ {it.get('price')} · vendidos: {it.get('sold_quantity', 'n/d')}"
              f" · {link_afiliado(it.get('permalink', ''))}")
    if itens:
        print("Campos:", ", ".join(sorted(itens[0].keys())))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "status"
    if acao == "conectar":
        _conectar()
    elif acao == "busca":
        _status()
        _busca(" ".join(sys.argv[2:]) or "garrafa termica")
    else:
        _status()
