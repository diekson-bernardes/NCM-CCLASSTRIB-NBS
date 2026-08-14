"""Controle de acesso: usuarios, papeis e cota de consultas.

Usuarios previstos:

    admin     administrador, sem limitacao
    Cliente   uso normal, sem limitacao
    Teste     demonstracao, limitada a 10 consultas

As senhas ficam gravadas como hash (pbkdf2-sha256); o texto puro nao entra no
repositorio. Em servidor, cada senha pode ser trocada por variavel de ambiente
(RTC_SENHA_ADMIN, RTC_SENHA_TESTE, RTC_SENHA_CLIENTE) - util para publicar sem
usar as senhas de desenvolvimento.

Contam como consulta as acoes que produzem enquadramento: analise do cartao CNPJ,
consulta de um NCM, consulta em lote e o detalhe de um CNAE. Navegar pelas telas,
buscar nas tabelas e baixar um relatorio ja gerado nao consomem cota.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_USO = Path(os.environ.get("RTC_ARQUIVO_USO", RAIZ / "var" / "uso.json"))
ARQUIVO_USUARIOS = Path(
    os.environ.get("RTC_ARQUIVO_USUARIOS", RAIZ / "var" / "usuarios.json")
)

LIMITE_TESTE = 10
MULTIPLO_CONSULTAS = 50  # cotas criadas pelo administrador vao de 50 em 50
MINIMO_SENHA = 3

USUARIOS: dict[str, dict] = {
    "admin": {
        "nome": "Administrador",
        "papel": "administrador",
        "limite": None,
        "hash": "pbkdf2:sha256:600000$oflE0nGciW1cxFfK$"
                "6a8c6527eb05ad02fa725dceb6a6f4ad422eab3a812cdf8bf35ab0c7aa2188ef",
        "env": "RTC_SENHA_ADMIN",
    },
    "Cliente": {
        "nome": "Cliente",
        "papel": "cliente",
        "limite": None,
        "hash": "pbkdf2:sha256:600000$0tbachYHAUYg0EG6$"
                "5386a6bffb5cef49c1684bef3f341916a2ef6499e822daf2abfc534de7c4f052",
        "env": "RTC_SENHA_CLIENTE",
    },
    "Teste": {
        "nome": "Usuário de teste",
        "papel": "teste",
        "limite": LIMITE_TESTE,
        "hash": "pbkdf2:sha256:600000$NTiLb52dEhLUG7QS$"
                "1b65ede152b6970325fd93605908204ce13f0eaa093c1ede95ff71d2d7d10fdc",
        "env": "RTC_SENHA_TESTE",
    },
}

EMBUTIDOS = set(USUARIOS)  # usuarios de fabrica, que nao podem ser removidos

_TRAVA = threading.Lock()
_USO: dict[str, int] = {}
_CARREGADO = False
_USUARIOS_CARREGADOS = False


# ------------------------------------------------------------------ usuarios


def _carrega_usuarios() -> None:
    """Traz para a memoria os usuarios criados pelo administrador."""
    global _USUARIOS_CARREGADOS
    if _USUARIOS_CARREGADOS:
        return
    _USUARIOS_CARREGADOS = True
    try:
        dados = json.loads(ARQUIVO_USUARIOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for login, registro in (dados.get("usuarios") or {}).items():
        if login in EMBUTIDOS:
            continue
        USUARIOS[login] = {
            "nome": registro.get("nome") or login,
            "papel": registro.get("papel", "cliente"),
            "limite": registro.get("limite"),
            "hash": registro.get("hash", ""),
            "env": "",
            "criado_em": registro.get("criado_em", ""),
        }


def _grava_usuarios() -> None:
    criados = {
        login: {k: v for k, v in dados.items() if k != "env"}
        for login, dados in USUARIOS.items()
        if login not in EMBUTIDOS
    }
    try:
        ARQUIVO_USUARIOS.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_USUARIOS.write_text(
            json.dumps(
                {
                    "atualizado_em": datetime.now().isoformat(timespec="seconds"),
                    "usuarios": criados,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _busca_login(login: str) -> str | None:
    """Aceita o login sem diferenciar maiusculas (admin, Admin, ADMIN)."""
    _carrega_usuarios()
    alvo = (login or "").strip().casefold()
    for nome in USUARIOS:
        if nome.casefold() == alvo:
            return nome
    return None


def validar_limite(valor: str | int | None) -> int | None:
    """Converte o limite informado; None = ilimitado.

    Cotas criadas pelo administrador sao sempre multiplos de 50.
    """
    if valor in (None, "", "ilimitado", "Ilimitado"):
        return None
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError("Informe a quantidade de consultas em números.")
    if numero <= 0:
        raise ValueError("A quantidade de consultas deve ser maior que zero.")
    if numero % MULTIPLO_CONSULTAS:
        raise ValueError(
            f"A quantidade de consultas deve ser múltipla de {MULTIPLO_CONSULTAS} "
            f"(ex.: 50, 100, 150) ou ilimitada."
        )
    return numero


def criar_usuario(login: str, senha: str, limite: str | int | None,
                  nome: str = "") -> dict:
    """Cadastra um usuario novo. Levanta ValueError com a mensagem do problema."""
    _carrega_usuarios()
    login = (login or "").strip()
    if not login:
        raise ValueError("Informe o login do usuário.")
    if len(login) > 40 or any(c.isspace() for c in login):
        raise ValueError("O login deve ser uma palavra de até 40 caracteres, sem espaços.")
    if _busca_login(login):
        raise ValueError(f"Já existe um usuário com o login “{login}”.")
    if len(senha or "") < MINIMO_SENHA:
        raise ValueError(f"A senha deve ter ao menos {MINIMO_SENHA} caracteres.")

    quantidade = validar_limite(limite)

    with _TRAVA:
        USUARIOS[login] = {
            "nome": (nome or "").strip() or login,
            "papel": "cliente",
            "limite": quantidade,
            "hash": generate_password_hash(senha, method="pbkdf2:sha256:600000"),
            "env": "",
            "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        _grava_usuarios()
    return obter(login)


def remover_usuario(login: str) -> None:
    """Remove um usuario criado pelo administrador (os de fabrica ficam)."""
    nome = _busca_login(login)
    if not nome:
        raise ValueError("Usuário não encontrado.")
    if nome in EMBUTIDOS:
        raise ValueError(f"O usuário “{nome}” é fixo do sistema e não pode ser removido.")
    with _TRAVA:
        USUARIOS.pop(nome, None)
        _grava_usuarios()
    zerar(nome)


def autenticar(login: str, senha: str) -> dict | None:
    nome = _busca_login(login)
    if not nome:
        return None
    usuario = USUARIOS[nome]

    senha_ambiente = os.environ.get(usuario["env"], "")
    if senha_ambiente:
        confere = senha == senha_ambiente
    else:
        confere = check_password_hash(usuario["hash"], senha or "")
    if not confere:
        return None
    return {"login": nome, **{k: v for k, v in usuario.items() if k not in {"hash", "env"}}}


def obter(login: str) -> dict | None:
    nome = _busca_login(login)
    if not nome:
        return None
    return {"login": nome, **{k: v for k, v in USUARIOS[nome].items()
                              if k not in {"hash", "env"}}}


def definir_senha(login: str, senha: str) -> None:
    """Troca a senha em memoria (usado em teste e em scripts de manutencao)."""
    nome = _busca_login(login)
    if nome:
        USUARIOS[nome]["hash"] = generate_password_hash(senha, method="pbkdf2:sha256:600000")


# ----------------------------------------------------------------- cota de uso


def _carrega() -> None:
    global _CARREGADO
    if _CARREGADO:
        return
    _CARREGADO = True
    try:
        dados = json.loads(ARQUIVO_USO.read_text(encoding="utf-8"))
        _USO.update({k: int(v) for k, v in dados.get("consultas", {}).items()})
    except (OSError, ValueError):
        pass


def _grava() -> None:
    try:
        ARQUIVO_USO.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_USO.write_text(
            json.dumps(
                {
                    "atualizado_em": datetime.now().isoformat(timespec="seconds"),
                    "consultas": _USO,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
    except OSError:
        # sem permissao de escrita (host efemero): a contagem segue so em memoria
        pass


def consumo(login: str) -> int:
    _carrega()
    return _USO.get(login, 0)


def restante(login: str) -> int | None:
    """None quando o usuario nao tem limite."""
    usuario = obter(login)
    if not usuario or usuario["limite"] is None:
        return None
    return max(0, usuario["limite"] - consumo(login))


def pode_consultar(login: str) -> bool:
    disponivel = restante(login)
    return disponivel is None or disponivel > 0


def registrar_consulta(login: str) -> int:
    """Soma uma consulta ao usuario e devolve o total ja usado."""
    with _TRAVA:
        _carrega()
        _USO[login] = _USO.get(login, 0) + 1
        _grava()
        return _USO[login]


def zerar(login: str | None = None) -> None:
    """Zera a contagem de um usuario (ou de todos)."""
    with _TRAVA:
        _carrega()
        if login is None:
            _USO.clear()
        else:
            _USO.pop(login, None)
        _grava()


def painel() -> list[dict]:
    """Situacao de uso de cada usuario - exibida ao administrador."""
    _carrega()
    _carrega_usuarios()
    linhas = []
    for login, usuario in USUARIOS.items():
        usadas = _USO.get(login, 0)
        linhas.append(
            {
                "login": login,
                "nome": usuario["nome"],
                "papel": usuario["papel"],
                "limite": usuario["limite"],
                "consultas": usadas,
                "restante": None if usuario["limite"] is None
                            else max(0, usuario["limite"] - usadas),
                "embutido": login in EMBUTIDOS,
                "criado_em": usuario.get("criado_em", ""),
            }
        )
    return linhas


def opcoes_de_limite(maximo: int = 500) -> list[int]:
    """Cotas oferecidas na tela: 50, 100, 150 ... ate o maximo."""
    return list(range(MULTIPLO_CONSULTAS, maximo + 1, MULTIPLO_CONSULTAS))
