"""Leitura do Cartao CNPJ (Comprovante de Inscricao e de Situacao Cadastral - RFB).

Extrai identificacao da empresa e as atividades economicas (CNAE principal e
secundarias). O layout do comprovante varia pouco entre versoes, entao a leitura
e feita por ancoras de secao com tolerancia a acentuacao e quebras de linha.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c))


# 62.01-5-01 | 6201-5/01 | 6201-5-01 | 6201501
RE_CNAE = re.compile(
    r"(?<![\d./-])(?:"
    r"(\d{2})\.(\d{2})-(\d)[-/](\d{2})"
    r"|(\d{4})-(\d)[-/](\d{2})"
    r"|(\d{7})"
    r")(?![\d./-])"
)
RE_CNPJ = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")


def codigo_cnae(m: re.Match) -> str:
    """Normaliza qualquer uma das mascaras aceitas para 7 digitos."""
    grupos = [g for g in m.groups() if g]
    return "".join(grupos)


@dataclass
class Atividade:
    cnae: str
    descricao: str
    principal: bool

    @property
    def formatado(self) -> str:
        c = self.cnae
        return f"{c[0:4]}-{c[4]}/{c[5:7]}"


@dataclass
class CartaoCNPJ:
    cnpj: str = ""
    nome_empresarial: str = ""
    nome_fantasia: str = ""
    abertura: str = ""
    porte: str = ""
    natureza_juridica: str = ""
    situacao: str = ""
    municipio: str = ""
    uf: str = ""
    matriz_filial: str = ""
    atividades: list[Atividade] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        d = asdict(self)
        d["atividades"] = [
            {**asdict(a), "formatado": a.formatado} for a in self.atividades
        ]
        return d


def texto_do_pdf(dados: bytes) -> str:
    import io

    import pdfplumber

    partes = []
    with pdfplumber.open(io.BytesIO(dados)) as pdf:
        for pagina in pdf.pages:
            partes.append(pagina.extract_text() or "")
    return "\n".join(partes)


def _campo(texto_norm: str, texto: str, rotulo: str, limite_linhas: int = 3) -> str:
    """Devolve o conteudo que segue um rotulo do comprovante."""
    idx = texto_norm.find(_sem_acento(rotulo).upper())
    if idx < 0:
        return ""
    resto = texto[idx + len(rotulo):]
    linhas = [l.strip() for l in resto.splitlines()]
    for linha in linhas[: limite_linhas + 1]:
        if not linha:
            continue
        if re.fullmatch(r"[A-ZÁÂÃÉÊÍÓÔÕÚÇ \-()/.]{8,}", linha) and linha.isupper() and (
            "CODIGO" in _sem_acento(linha) or "DESCRICAO" in _sem_acento(linha)
        ):
            return ""
        return linha
    return ""


def _bloco(texto_norm: str, texto: str, inicio: str, fins: list[str]) -> str:
    ini = texto_norm.find(_sem_acento(inicio).upper())
    if ini < 0:
        return ""
    ini += len(inicio)
    fim = len(texto)
    for f in fins:
        pos = texto_norm.find(_sem_acento(f).upper(), ini)
        if pos > 0:
            fim = min(fim, pos)
    return texto[ini:fim]


def _atividades_do_bloco(bloco: str, principal: bool) -> list[Atividade]:
    atividades: list[Atividade] = []
    vistos: set[str] = set()
    for linha in bloco.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = RE_CNAE.search(linha)
        if not m:
            # descricao continuada da atividade anterior
            if atividades and len(linha) > 3 and not linha.isupper():
                atividades[-1].descricao = f"{atividades[-1].descricao} {linha}".strip()
            continue
        codigo = codigo_cnae(m)
        descricao = linha[m.end():].strip(" -–—\t")
        if codigo in vistos:
            continue
        vistos.add(codigo)
        atividades.append(Atividade(cnae=codigo, descricao=descricao, principal=principal))
    return atividades


def ler_cartao(texto: str) -> CartaoCNPJ:
    cartao = CartaoCNPJ()
    if not texto or len(texto.strip()) < 40:
        cartao.avisos.append(
            "Nao foi possivel extrair texto do PDF (provavelmente e uma imagem "
            "digitalizada). Informe os CNAEs manualmente."
        )
        return cartao

    texto_norm = _sem_acento(texto).upper()

    m = RE_CNPJ.search(texto)
    if m:
        cartao.cnpj = m.group(1)

    cartao.nome_empresarial = _campo(texto_norm, texto, "NOME EMPRESARIAL")
    cartao.nome_fantasia = _campo(
        texto_norm, texto, "TÍTULO DO ESTABELECIMENTO (NOME DE FANTASIA)"
    ) or _campo(texto_norm, texto, "NOME FANTASIA")
    cartao.abertura = _campo(texto_norm, texto, "DATA DE ABERTURA")
    cartao.porte = _campo(texto_norm, texto, "PORTE")
    cartao.natureza_juridica = _campo(
        texto_norm, texto, "CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA"
    )
    cartao.situacao = _campo(texto_norm, texto, "SITUAÇÃO CADASTRAL")
    cartao.municipio = _campo(texto_norm, texto, "MUNICÍPIO")
    cartao.uf = _campo(texto_norm, texto, "UF")[:2]
    if "MATRIZ" in texto_norm:
        cartao.matriz_filial = "MATRIZ"
    elif "FILIAL" in texto_norm:
        cartao.matriz_filial = "FILIAL"

    bloco_principal = _bloco(
        texto_norm,
        texto,
        "CÓDIGO E DESCRIÇÃO DA ATIVIDADE ECONÔMICA PRINCIPAL",
        [
            "CÓDIGO E DESCRIÇÃO DAS ATIVIDADES ECONÔMICAS SECUNDÁRIAS",
            "CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA",
        ],
    )
    bloco_secundarias = _bloco(
        texto_norm,
        texto,
        "CÓDIGO E DESCRIÇÃO DAS ATIVIDADES ECONÔMICAS SECUNDÁRIAS",
        ["CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA", "LOGRADOURO"],
    )

    cartao.atividades = _atividades_do_bloco(bloco_principal, principal=True)
    principais = {a.cnae for a in cartao.atividades}
    for atividade in _atividades_do_bloco(bloco_secundarias, principal=False):
        if atividade.cnae not in principais:
            cartao.atividades.append(atividade)

    if not cartao.atividades:
        # ultimo recurso: varre o documento inteiro
        cartao.atividades = _atividades_do_bloco(texto, principal=False)
        if cartao.atividades:
            cartao.avisos.append(
                "As secoes de atividade economica nao foram localizadas; os CNAEs "
                "foram extraidos do texto completo do PDF. Confira a lista."
            )
        else:
            cartao.avisos.append("Nenhum CNAE foi encontrado no PDF enviado.")

    return cartao


def cnaes_de_texto_livre(texto: str) -> list[Atividade]:
    """Aceita CNAEs digitados manualmente (um por linha, com ou sem mascara)."""
    atividades: list[Atividade] = []
    vistos: set[str] = set()
    for linha in (texto or "").replace(";", "\n").replace(",", "\n").splitlines():
        m = RE_CNAE.search(linha)
        if not m:
            continue
        codigo = codigo_cnae(m)
        if codigo in vistos:
            continue
        vistos.add(codigo)
        atividades.append(
            Atividade(
                cnae=codigo,
                descricao=linha[m.end():].strip(" -–—\t"),
                principal=not atividades,
            )
        )
    return atividades
