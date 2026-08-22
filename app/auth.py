"""Controle de acesso: usuarios, papeis e cota de consultas.

Usuarios previstos:

    admin     administrador, sem limitacao
    Cliente   uso normal, sem limitacao
    Teste     demonstracao, limitada a 10 consultas

As senhas ficam gravadas como hash (pbkdf2-sha256); o texto puro nao entra no
repositorio. Em servidor, cada senha pode ser trocada por variavel de ambiente
(RTC_SENHA_ADMIN, RTC_SENHA_TESTE, RTC_SENHA_CLIENTE) - util para publicar sem
usar as senhas de desenvolvimento.

Os usuarios criados no painel e a contagem de consultas vao para o destino
escolhido em `armazenamento` (banco PostgreSQL quando ha DATABASE_URL, arquivos
JSON em var/ caso contrario), de modo que sobrevivam a um novo deploy.

Contam como consulta as acoes que produzem enquadramento: analise do cartao CNPJ,
consulta de um NCM, consulta em lote e o detalhe de um CNAE. Navegar pelas telas,
buscar nas tabelas e baixar um relatorio ja gerado nao consomem cota.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from . import armazenamento

LIMITE_TESTE = 10
MULTIPLO_CONSULTAS = 50  # cotas criadas pelo administrador vao de 50 em 50
MINIMO_SENHA = 3

# Rotinas do sistema. O administrador escolhe quais ficam liberadas para cada
# usuario criado; "rotinas": None significa acesso a todas.
ROTINAS: dict[str, dict] = {
    "cartao": {
        "nome": "Análise do cartão CNPJ",
        "descricao": "Enquadramento das atividades a partir do PDF ou de CNAEs digitados",
        "rota": "inicio",
    },
    "ncm": {
        "nome": "Consulta por NCM",
        "descricao": "CST, cClassTrib, redução e indOP de um produto",
        "rota": "ncm_busca",
    },
    "lote": {
        "nome": "Consulta de NCM em lote",
        "descricao": "Lista ou planilha de produtos processada de uma vez",
        "rota": "ncm_lote",
    },
    "pgdas": {
        "nome": "Declaração PGDAS-D",
        "descricao": "Carga efetiva por tributo, estabelecimento e atividade do Simples Nacional",
        "rota": "pgdas",
    },
    "cesta": {
        "nome": "Cesta e relatório consolidado",
        "descricao": "Acúmulo das consultas e exportação consolidada",
        "rota": "cesta_ver",
    },
    "tabelas": {
        "nome": "Consulta de tabelas",
        "descricao": "Busca em CNAE, LC 116, NBS, NCM, cClassTrib e indOP",
        "rota": "consulta",
    },
    "fontes": {
        "nome": "Fontes (KB)",
        "descricao": "Documentos oficiais usados, com versão e hash",
        "rota": "fontes",
    },
    "apresentacao": {
        "nome": "Apresentação",
        "descricao": "Relatório de apresentação da ferramenta",
        "rota": "apresentacao",
    },
}

USUARIOS: dict[str, dict] = {
    "admin": {
        "nome": "Administrador",
        "papel": "administrador",
        "limite": None,
        "rotinas": None,
        "hash": "pbkdf2:sha256:600000$oflE0nGciW1cxFfK$"
                "6a8c6527eb05ad02fa725dceb6a6f4ad422eab3a812cdf8bf35ab0c7aa2188ef",
        "env": "RTC_SENHA_ADMIN",
    },
    "Cliente": {
        "nome": "Cliente",
        "papel": "cliente",
        "limite": None,
        "rotinas": None,
        "hash": "pbkdf2:sha256:600000$0tbachYHAUYg0EG6$"
                "5386a6bffb5cef49c1684bef3f341916a2ef6499e822daf2abfc534de7c4f052",
        "env": "RTC_SENHA_CLIENTE",
    },
    "Teste": {
        "nome": "Usuário de teste",
        "papel": "teste",
        "limite": LIMITE_TESTE,
        "rotinas": None,
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
    dados = armazenamento.armazem().ler("usuarios") or {}
    for login, registro in (dados.get("usuarios") or {}).items():
        if login in EMBUTIDOS:
            continue
        USUARIOS[login] = {
            "nome": registro.get("nome") or login,
            "papel": registro.get("papel", "cliente"),
            "limite": registro.get("limite"),
            "rotinas": registro.get("rotinas"),
            "hash": registro.get("hash", ""),
            "env": "",
            "criado_em": registro.get("criado_em", ""),
            "alterado_em": registro.get("alterado_em", ""),
        }


def _grava_usuarios() -> None:
    criados = {
        login: {k: v for k, v in dados.items() if k != "env"}
        for login, dados in USUARIOS.items()
        if login not in EMBUTIDOS
    }
    armazenamento.armazem().gravar(
        "usuarios",
        {
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            "usuarios": criados,
        },
    )


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


def validar_rotinas(rotinas) -> list[str] | None:
    """Normaliza a lista de rotinas liberadas. None = todas."""
    if rotinas is None:
        return None
    escolhidas = [r for r in rotinas if r in ROTINAS]
    if not escolhidas:
        raise ValueError("Selecione ao menos uma rotina para o usuário.")
    if len(escolhidas) == len(ROTINAS):
        return None  # todas liberadas
    return [r for r in ROTINAS if r in escolhidas]  # mantem a ordem do menu


def pode_acessar(usuario: dict | None, rotina: str) -> bool:
    """O administrador acessa tudo; os demais, apenas as rotinas liberadas."""
    if not usuario:
        return False
    if usuario.get("papel") == "administrador":
        return True
    liberadas = usuario.get("rotinas")
    return liberadas is None or rotina in liberadas


def rotinas_do_usuario(usuario: dict | None) -> list[str]:
    if not usuario:
        return []
    if usuario.get("papel") == "administrador" or usuario.get("rotinas") is None:
        return list(ROTINAS)
    return [r for r in ROTINAS if r in usuario["rotinas"]]


def criar_usuario(login: str, senha: str, limite: str | int | None,
                  nome: str = "", rotinas=None) -> dict:
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
    liberadas = validar_rotinas(rotinas)

    with _TRAVA:
        USUARIOS[login] = {
            "nome": (nome or "").strip() or login,
            "papel": "cliente",
            "limite": quantidade,
            "rotinas": liberadas,
            "hash": generate_password_hash(senha, method="pbkdf2:sha256:600000"),
            "env": "",
            "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        _grava_usuarios()
    return obter(login)


MANTER = object()  # sentinela: campo nao enviado no formulario de edicao


def editar_usuario(login: str, nome=MANTER, senha=MANTER, limite=MANTER,
                   rotinas=MANTER) -> dict:
    """Altera um usuario criado no painel. Campos omitidos ficam como estao.

    Senha em branco mantem a atual. Os usuarios de fabrica nao sao editaveis por
    aqui: eles vivem no codigo e mudam por variavel de ambiente.
    """
    nome_login = _busca_login(login)
    if not nome_login:
        raise ValueError("Usuário não encontrado.")
    if nome_login in EMBUTIDOS:
        raise ValueError(
            f"O usuário “{nome_login}” é fixo do sistema: a senha muda por variável de "
            f"ambiente e a cota e as rotinas são as de acesso total."
        )

    usuario = USUARIOS[nome_login]
    novos: dict = {}

    if nome is not MANTER:
        novos["nome"] = (nome or "").strip() or nome_login
    if limite is not MANTER:
        novos["limite"] = validar_limite(limite)
    if rotinas is not MANTER:
        novos["rotinas"] = validar_rotinas(rotinas)
    if senha is not MANTER and senha:
        if len(senha) < MINIMO_SENHA:
            raise ValueError(f"A senha deve ter ao menos {MINIMO_SENHA} caracteres.")
        novos["hash"] = generate_password_hash(senha, method="pbkdf2:sha256:600000")

    with _TRAVA:
        usuario.update(novos)
        usuario["alterado_em"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        _grava_usuarios()
    return obter(nome_login)


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
    dados = armazenamento.armazem().ler("uso") or {}
    for login, quantidade in (dados.get("consultas") or {}).items():
        try:
            _USO[login] = int(quantidade)
        except (TypeError, ValueError):
            continue


def _grava() -> None:
    armazenamento.armazem().gravar(
        "uso",
        {
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            "consultas": _USO,
        },
    )


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


def registrar_consulta(login: str, quantidade: int = 1) -> int:
    """Soma consultas ao usuario e devolve o total ja usado.

    A consulta em lote debita uma consulta por NCM processado.
    """
    if quantidade <= 0:
        return consumo(login)
    with _TRAVA:
        _carrega()
        _USO[login] = _USO.get(login, 0) + quantidade
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


def recarregar() -> None:
    """Descarta o que esta em memoria e le tudo de novo do armazenamento."""
    global _CARREGADO, _USUARIOS_CARREGADOS
    with _TRAVA:
        for login in [nome for nome in USUARIOS if nome not in EMBUTIDOS]:
            USUARIOS.pop(login, None)
        _USO.clear()
        _CARREGADO = False
        _USUARIOS_CARREGADOS = False


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
                "alterado_em": usuario.get("alterado_em", ""),
                "rotinas": rotinas_do_usuario({"papel": usuario["papel"],
                                               "rotinas": usuario.get("rotinas")}),
                "todas_rotinas": usuario["papel"] == "administrador"
                                 or usuario.get("rotinas") is None,
            }
        )
    return linhas


def opcoes_de_limite(maximo: int = 500) -> list[int]:
    """Cotas oferecidas na tela: 50, 100, 150 ... ate o maximo."""
    return list(range(MULTIPLO_CONSULTAS, maximo + 1, MULTIPLO_CONSULTAS))
