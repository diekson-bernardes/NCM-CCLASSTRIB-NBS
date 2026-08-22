"""Onde ficam gravados o cadastro de usuarios e a contagem de consultas.

O disco do Render gratuito e efemero: a cada deploy, reinicio ou saida da
hibernacao a maquina volta ao conteudo do repositorio, e tudo que a aplicacao
gravou em `var/` desaparece - inclusive os usuarios criados pelo administrador.
Por isso o estado tem dois destinos possiveis, escolhidos por variavel de
ambiente:

    DATABASE_URL definida   banco PostgreSQL (Render, Neon, Supabase...).
                            Sobrevive a deploy, reinicio e troca de maquina.
    sem DATABASE_URL        arquivos JSON em var/ - padrao no uso local.

Os dois destinos guardam exatamente o mesmo conteudo (um documento JSON por
chave), entao a troca nao exige conversao: na primeira subida com banco, o que
existir nos arquivos e copiado para la (ver `_migrar`).

Chaves gravadas:

    usuarios   {"atualizado_em": ..., "usuarios": {login: {...}}}
    uso        {"atualizado_em": ..., "consultas": {login: quantidade}}
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

CHAVES = ("usuarios", "uso")
TABELA = "rtc_estado"
ESPERA_CONEXAO = 10  # segundos; sem isso um banco fora do ar pendura a requisicao


def _arquivos() -> dict[str, Path]:
    """Caminhos dos arquivos JSON (as variaveis servem aos testes)."""
    return {
        "uso": Path(os.environ.get("RTC_ARQUIVO_USO", RAIZ / "var" / "uso.json")),
        "usuarios": Path(
            os.environ.get("RTC_ARQUIVO_USUARIOS", RAIZ / "var" / "usuarios.json")
        ),
    }


def _url() -> str:
    """URL do banco, se houver. RTC_DATABASE_URL tem prioridade sobre DATABASE_URL."""
    url = (os.environ.get("RTC_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres://"):  # forma antiga, recusada pelo psycopg 3
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _acrescenta(url: str, **parametros: str) -> str:
    """Completa a URL com parametros que ela ainda nao traga."""
    for chave, valor in parametros.items():
        if f"{chave}=" not in url:
            url += ("&" if "?" in url else "?") + f"{chave}={valor}"
    return url


def _conectar():
    """Devolve a funcao connect do driver instalado (psycopg 3 ou psycopg2)."""
    try:
        import psycopg  # noqa: PLC0415
        return psycopg.connect
    except ImportError:
        pass
    try:
        import psycopg2  # noqa: PLC0415
        return psycopg2.connect
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            "DATABASE_URL definida, mas nenhum driver PostgreSQL instalado. "
            "Acrescente psycopg[binary] ao requirements.txt."
        ) from exc


# ------------------------------------------------------------------ arquivos


class ArmazemArquivo:
    """Um arquivo JSON por chave. Some junto com o disco do host."""

    persistente = False
    destino = "arquivos JSON"

    def __init__(self, caminhos: dict[str, Path]):
        self.caminhos = caminhos
        self.erro = ""

    @property
    def detalhe(self) -> str:
        return str(self.caminhos["usuarios"].parent)

    def ler(self, chave: str) -> dict | None:
        try:
            return json.loads(self.caminhos[chave].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def gravar(self, chave: str, dados: dict) -> bool:
        alvo = self.caminhos[chave]
        try:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text(
                json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError as exc:
            # host somente-leitura: a contagem segue apenas em memoria
            self.erro = f"não foi possível gravar {alvo.name}: {exc}"
            return False
        return True


# ------------------------------------------------------------------ postgres


class ArmazemPostgres:
    """Uma linha por chave numa tabela unica; o valor e o mesmo JSON do arquivo."""

    persistente = True
    destino = "banco PostgreSQL"

    def __init__(self, url: str):
        self.url = url
        self.erro = ""
        self._connect = _conectar()
        self._executar(
            f"CREATE TABLE IF NOT EXISTS {TABELA} ("
            " chave TEXT PRIMARY KEY,"
            " valor TEXT NOT NULL,"
            " atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now())"
        )

    @property
    def detalhe(self) -> str:
        """Identifica o banco sem revelar a senha da URL."""
        resto = self.url.split("://", 1)[-1]
        if "@" in resto:
            resto = resto.split("@", 1)[1]
        return resto.split("?", 1)[0]

    def _abrir(self):
        # o limite de espera evita que o site fique pendurado se o banco sumir
        url = _acrescenta(self.url, connect_timeout=str(ESPERA_CONEXAO))
        try:
            return self._connect(url)
        except Exception:
            # bancos externos (Neon, Supabase, URL externa do Render) exigem TLS
            if "sslmode=" in url:
                raise
            return self._connect(_acrescenta(url, sslmode="require"))

    def _executar(self, sql: str, parametros: tuple = (), busca: bool = False):
        conexao = self._abrir()
        try:
            with conexao.cursor() as cursor:
                cursor.execute(sql, parametros)
                linha = cursor.fetchone() if busca else None
            conexao.commit()
            return linha
        finally:
            conexao.close()

    def ler(self, chave: str) -> dict | None:
        try:
            linha = self._executar(
                f"SELECT valor FROM {TABELA} WHERE chave = %s", (chave,), busca=True
            )
        except Exception as exc:
            self.erro = f"falha ao ler “{chave}” no banco: {exc}"
            return None
        if not linha:
            return None
        try:
            return json.loads(linha[0])
        except ValueError:
            return None

    def gravar(self, chave: str, dados: dict) -> bool:
        try:
            self._executar(
                f"INSERT INTO {TABELA} (chave, valor, atualizado_em)"
                " VALUES (%s, %s, now())"
                " ON CONFLICT (chave) DO UPDATE SET"
                " valor = EXCLUDED.valor, atualizado_em = now()",
                (chave, json.dumps(dados, ensure_ascii=False)),
            )
        except Exception as exc:
            self.erro = f"falha ao gravar “{chave}” no banco: {exc}"
            return False
        self.erro = ""
        return True


# -------------------------------------------------------------- escolha do destino

_TRAVA = threading.Lock()
_ARMAZEM = None


def _migrar(arquivos: dict[str, Path], banco: ArmazemPostgres) -> None:
    """Leva para o banco o que ja existia em arquivo, sem sobrescrever o banco."""
    origem = ArmazemArquivo(arquivos)
    for chave in CHAVES:
        if banco.ler(chave) is not None:
            continue
        dados = origem.ler(chave)
        if dados:
            banco.gravar(chave, dados)


def _montar():
    arquivos = _arquivos()
    url = _url()
    if not url:
        return ArmazemArquivo(arquivos)
    try:
        banco = ArmazemPostgres(url)
    except Exception as exc:
        # sem o banco a aplicacao continua de pe, mas avisa no painel do admin
        reserva = ArmazemArquivo(arquivos)
        reserva.erro = (
            f"DATABASE_URL definida, mas o banco não respondeu ({exc}). "
            "Os dados seguem em arquivo e serão perdidos no próximo deploy."
        )
        return reserva
    _migrar(arquivos, banco)
    return banco


def armazem():
    global _ARMAZEM
    if _ARMAZEM is None:
        with _TRAVA:
            if _ARMAZEM is None:
                _ARMAZEM = _montar()
    return _ARMAZEM


def redefinir(novo=None) -> None:
    """Troca o destino (testes) ou forca uma nova escolha na proxima leitura."""
    global _ARMAZEM
    with _TRAVA:
        _ARMAZEM = novo


def situacao() -> dict:
    """Resumo mostrado ao administrador: onde os dados estao e se sobrevivem."""
    atual = armazem()
    return {
        "destino": atual.destino,
        "detalhe": atual.detalhe,
        "persistente": atual.persistente,
        "erro": atual.erro,
    }
