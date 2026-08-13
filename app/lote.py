"""Consulta em lote de NCM: lista digitada ou planilha importada.

Entradas aceitas:
  * texto livre - um NCM por linha, com ou sem mascara; o que vier depois do
    codigo na mesma linha e guardado como referencia do item (codigo interno,
    descricao do produto etc.);
  * planilha .xlsx/.xlsm - procura a coluna cujo cabecalho contenha "NCM"; se nao
    houver cabecalho reconhecivel, varre as celulas atras de codigos validos;
  * arquivo .csv/.txt - mesma logica, detectando separador e codificacao.

A saida traz, para cada NCM, o enquadramento candidato (anexo da LC 214/2025,
cClassTrib, CST e reducoes) e o que exige conferencia: codigos nao localizados,
bens do Imposto Seletivo e citacoes em clausula de excecao.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter

from .dados import base
from .ncm import CCLASSTRIB_PADRAO, consultar, formata_ncm
from .ncm import linhas_detalhe as linhas_ncm

LIMITE_ITENS = 500

# 8 digitos, aceitando 1234.56.78 / 1234.5678 / 12345678
RE_NCM = re.compile(r"(?<![\d.])(\d{4}\.?\d{2}\.?\d{2})(?![\d.])")


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _limpa(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return re.sub(r"\s+", " ", str(valor)).strip()


# ------------------------------------------------------------------- entradas


def de_texto(texto: str) -> list[dict]:
    """Cada linha vira {ncm, referencia}; o resto da linha e a referencia."""
    itens: list[dict] = []
    for linha in (texto or "").replace(";", "\n").replace(",", "\n").splitlines():
        achado = RE_NCM.search(linha)
        if not achado:
            continue
        resto = (linha[: achado.start()] + " " + linha[achado.end():]).strip(" -–—\t|")
        itens.append({"ncm": _digitos(achado.group(1)), "referencia": _limpa(resto)})
    return itens


def _linhas_de_planilha(dados: bytes) -> list[list[str]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
    linhas: list[list[str]] = []
    for aba in wb.worksheets:
        for linha in aba.iter_rows(values_only=True):
            linhas.append([_limpa(c) for c in linha])
    return linhas


def _linhas_de_csv(dados: bytes) -> list[list[str]]:
    texto = None
    for codificacao in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = dados.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        return []
    amostra = texto[:4000]
    separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    return [[_limpa(c) for c in linha] for linha in csv.reader(io.StringIO(texto),
                                                               delimiter=separador)]


def de_planilha(nome_arquivo: str, dados: bytes) -> tuple[list[dict], list[str]]:
    """Devolve (itens, avisos). Reconhece .xlsx/.xlsm e .csv/.txt."""
    avisos: list[str] = []
    nome = (nome_arquivo or "").lower()

    if nome.endswith((".xlsx", ".xlsm")):
        linhas = _linhas_de_planilha(dados)
    elif nome.endswith((".csv", ".txt")):
        linhas = _linhas_de_csv(dados)
    elif nome.endswith(".xls"):
        raise ValueError(
            "Formato .xls (Excel antigo) não é lido: salve como .xlsx ou .csv."
        )
    else:
        raise ValueError("Envie uma planilha .xlsx ou um arquivo .csv.")

    if not linhas:
        return [], ["A planilha está vazia."]

    # procura a coluna de NCM pelo cabecalho, nas primeiras linhas
    col_ncm = None
    cols_ref: list[int] = []
    for linha in linhas[:10]:
        for indice, celula in enumerate(linha):
            if "ncm" in celula.lower() and len(celula) <= 40:
                col_ncm = indice
                break
        if col_ncm is not None:
            # demais colunas de texto viram a referencia do item (codigo interno,
            # descricao do produto); duas bastam para identificar a linha
            cols_ref = [
                i for i, c in enumerate(linha)
                if i != col_ncm and c and not c.isdigit()
            ][:2]
            break

    itens: list[dict] = []
    if col_ncm is not None:
        for linha in linhas:
            if col_ncm >= len(linha):
                continue
            achado = RE_NCM.search(linha[col_ncm])
            if not achado:
                continue
            referencia = " · ".join(
                linha[i] for i in cols_ref if i < len(linha) and linha[i]
            )
            itens.append({"ncm": _digitos(achado.group(1)), "referencia": referencia})
    else:
        avisos.append(
            "Nenhuma coluna com cabeçalho 'NCM' foi encontrada; os códigos foram "
            "reconhecidos pelo formato, célula a célula."
        )
        for linha in linhas:
            for celula in linha:
                achado = RE_NCM.search(celula)
                if achado:
                    itens.append(
                        {"ncm": _digitos(achado.group(1)), "referencia": ""}
                    )
                    break

    return itens, avisos


# ---------------------------------------------------------------- processamento


def _classes_do_resultado(consulta: dict) -> list[dict]:
    """cClassTrib candidatos, do regime mais especifico ao padrao."""
    classes: list[dict] = []
    vistos: set[str] = set()
    for regime in consulta["regimes"]:
        for classe in regime["cclasstrib"]:
            if classe["cclasstrib"] in vistos:
                continue
            vistos.add(classe["cclasstrib"])
            classes.append({**classe, "anexo": regime["anexo"], "item": regime["item"]})
    if not classes:
        padrao = base().por_cclasstrib.get(CCLASSTRIB_PADRAO, {})
        classes.append({**padrao, "anexo": "", "item": ""})
    return classes


def processar(itens: list[dict]) -> dict:
    """Consulta cada NCM uma vez e monta o resultado do lote."""
    avisos: list[str] = []
    vistos: dict[str, dict] = {}
    duplicados = 0

    for item in itens:
        codigo = item["ncm"]
        if codigo in vistos:
            duplicados += 1
            if item["referencia"] and not vistos[codigo]["referencia"]:
                vistos[codigo]["referencia"] = item["referencia"]
            continue
        vistos[codigo] = dict(item)

    if len(vistos) > LIMITE_ITENS:
        avisos.append(
            f"O lote tem {len(vistos)} códigos; foram processados os primeiros "
            f"{LIMITE_ITENS}. Divida o arquivo para conferir o restante."
        )
        vistos = dict(list(vistos.items())[:LIMITE_ITENS])
    if duplicados:
        avisos.append(f"{duplicados} código(s) repetido(s) foram consultados uma vez só.")

    resultados: list[dict] = []
    for codigo, item in vistos.items():
        consulta = consultar(codigo)
        if consulta is None:
            resultados.append(
                {
                    "ncm": codigo,
                    "formatado": formata_ncm(codigo),
                    "referencia": item["referencia"],
                    "encontrado": False,
                    "descricao": "",
                    "vigente": False,
                    "enquadramento": "Não localizado",
                    "anexos": [],
                    "cclasstrib": [],
                    "imposto_seletivo": False,
                    "excecoes": False,
                    "alertas": ["Código não encontrado na tabela NCM vigente."],
                    "consulta": None,
                }
            )
            continue

        classes = _classes_do_resultado(consulta)
        resultados.append(
            {
                "ncm": codigo,
                "formatado": consulta["formatado"],
                "referencia": item["referencia"],
                "encontrado": True,
                "descricao": consulta["descricao"],
                "vigente": consulta["vigente"],
                "enquadramento": "Regime diferenciado" if consulta["regimes"]
                                 else "Tributação integral",
                "anexos": [
                    f"Anexo {r['anexo']} item {r['item']}" for r in consulta["regimes"]
                ],
                "cclasstrib": classes,
                "imposto_seletivo": bool(consulta["regimes_seletivo"]),
                "excecoes": bool(consulta["regimes_excluidos"]),
                "alertas": consulta["alertas"],
                "consulta": consulta,
            }
        )

    return {"resultados": resultados, "avisos": avisos, "resumo": resumo(resultados)}


def resumo(resultados: list[dict]) -> dict:
    def reducao(resultado: dict, alvo: str) -> bool:
        return any(c.get("p_red_ibs") == alvo for c in resultado["cclasstrib"])

    anexos = Counter(
        a.split(" item ")[0] for r in resultados for a in r["anexos"]
    )
    return {
        "total": len(resultados),
        "encontrados": sum(1 for r in resultados if r["encontrado"]),
        "nao_localizados": sum(1 for r in resultados if not r["encontrado"]),
        "com_regime": sum(1 for r in resultados if r["enquadramento"] == "Regime diferenciado"),
        "integral": sum(1 for r in resultados if r["enquadramento"] == "Tributação integral"),
        "aliquota_zero": sum(1 for r in resultados if reducao(r, "100")),
        "reducao_60": sum(1 for r in resultados if reducao(r, "60")),
        "reducao_30": sum(1 for r in resultados if reducao(r, "30")),
        "imposto_seletivo": sum(1 for r in resultados if r["imposto_seletivo"]),
        "excecoes": sum(1 for r in resultados if r["excecoes"]),
        "nao_vigentes": sum(1 for r in resultados if r["encontrado"] and not r["vigente"]),
        "por_anexo": [
            {"anexo": anexo, "ncms": qtd} for anexo, qtd in anexos.most_common(10)
        ],
    }


# --------------------------------------------------------------------- saidas

COLUNAS_RESUMO = [
    "NCM", "Referência", "Descrição", "Vigente", "Enquadramento",
    "Anexos da LC 214/2025", "cClassTrib", "CST IBS/CBS",
    "Redução IBS (%)", "Redução CBS (%)", "Imposto Seletivo", "Exceção em anexo",
]


def linhas_resumo(lote: dict) -> list[dict]:
    """Uma linha por NCM - visao gerencial do lote."""
    linhas = []
    for r in lote["resultados"]:
        linhas.append(
            {
                "NCM": r["formatado"],
                "Referência": r["referencia"],
                "Descrição": r["descricao"],
                "Vigente": "" if not r["encontrado"] else ("Sim" if r["vigente"] else "Não"),
                "Enquadramento": r["enquadramento"],
                "Anexos da LC 214/2025": " | ".join(r["anexos"]),
                "cClassTrib": " | ".join(c["cclasstrib"] for c in r["cclasstrib"] if c.get("cclasstrib")),
                "CST IBS/CBS": " | ".join(
                    dict.fromkeys(c["cst"] for c in r["cclasstrib"] if c.get("cst"))
                ),
                "Redução IBS (%)": " | ".join(
                    dict.fromkeys(str(c.get("p_red_ibs", "")) for c in r["cclasstrib"])
                ),
                "Redução CBS (%)": " | ".join(
                    dict.fromkeys(str(c.get("p_red_cbs", "")) for c in r["cclasstrib"])
                ),
                "Imposto Seletivo": "Sim" if r["imposto_seletivo"] else "",
                "Exceção em anexo": "Sim" if r["excecoes"] else "",
            }
        )
    return linhas


def linhas_detalhe(lote: dict) -> list[dict]:
    """Uma linha por NCM x cClassTrib - mesma estrutura da consulta individual."""
    linhas: list[dict] = []
    for r in lote["resultados"]:
        if not r["consulta"]:
            linhas.append(
                {
                    "Referência": r["referencia"],
                    "NCM": r["formatado"],
                    "Descrição NCM": "Código não encontrado na tabela NCM vigente",
                    "Regime": "Não localizado",
                }
            )
            continue
        for linha in linhas_ncm(r["consulta"]):
            linhas.append({"Referência": r["referencia"], **linha})
    return linhas
