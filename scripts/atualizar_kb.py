"""Rebaixa (redownload) as fontes catalogadas em KB/fontes.json.

Uso:
    python scripts/atualizar_kb.py            # baixa tudo e relata o que mudou
    python scripts/atualizar_kb.py --checar   # so verifica se o arquivo mudou

As tabelas da reforma tributaria sao revisadas com frequencia (o Anexo VIII da
NFS-e e a tabela de cClassTrib da NF-e mudam varias vezes por ano). Depois de
atualizar, rode novamente `python scripts/build_dataset.py`.

Observacao: o dominio planalto.gov.br pode estar bloqueado em algumas redes; por
isso os textos legais sao espelhados a partir do Legin da Camara dos Deputados.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import ssl
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "KB" / "fontes.json"
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compativel; correlacao-rtc/1.0)"}


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _abridor():
    """Opener com cookies: o portal da NF-e redireciona ate aceitar o cookie."""
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )


def baixar(url: str, tentativas: int = 3) -> bytes:
    ultimo = None
    for _ in range(tentativas):
        try:
            requisicao = urllib.request.Request(url, headers=CABECALHOS)
            with _abridor().open(requisicao, timeout=180) as resp:
                return resp.read()
        except Exception as exc:  # rede instavel / leitura incompleta
            ultimo = exc
    raise RuntimeError(str(ultimo))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checar", action="store_true",
                        help="nao grava; apenas informa se a fonte mudou")
    parser.add_argument("--filtro", default="",
                        help="baixa apenas fontes cujo caminho contenha este texto")
    args = parser.parse_args()

    fontes = json.loads(CATALOGO.read_text(encoding="utf-8"))
    mudou = inalterado = falhou = 0

    for fonte in fontes:
        destino = RAIZ / fonte["arquivo"]
        if args.filtro and args.filtro.lower() not in fonte["arquivo"].lower():
            continue
        try:
            dados = baixar(fonte["url"])
        except Exception as exc:
            print(f"FALHA   {fonte['arquivo']}: {exc}")
            falhou += 1
            continue

        atual = destino.read_bytes() if destino.exists() else b""
        if atual and sha256(atual) == sha256(dados):
            print(f"igual   {fonte['arquivo']}")
            inalterado += 1
            continue

        print(f"MUDOU   {fonte['arquivo']} ({len(dados)} bytes)")
        mudou += 1
        if not args.checar:
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)

    print(f"\nResumo: {mudou} alterada(s), {inalterado} sem mudanca, {falhou} falha(s).")
    if mudou and not args.checar:
        print("Rode agora: python scripts/build_dataset.py")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
