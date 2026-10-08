"""Renova o token do Instagram e grava em um arquivo para o workflow atualizar o segredo."""
import os
import sys

from . import instagram

if __name__ == "__main__":
    if not instagram.tem_token():
        print("⏸️  IG_ACCESS_TOKEN não configurado — nada a renovar.")
        sys.exit(0)
    try:
        novo, expira = instagram.renovar_token()
    except Exception as e:
        print(f"::error::{e}")
        sys.exit(1)
    print(f"::add-mask::{novo}")
    destino = os.path.join(os.getenv("RUNNER_TEMP", "."), "ig_token.txt")
    with open(destino, "w") as f:
        f.write(novo)
    dias = int(expira or 0) // 86400
    print(f"✅ Token renovado; vale por mais {dias} dias.")
