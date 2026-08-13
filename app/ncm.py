"""Consulta por NCM: CST, cClassTrib e indOP aplicaveis a operacoes com bens.

A cadeia usada e:

    NCM -> anexo da LC 214/2025 que cita o codigo -> cClassTrib que remete aquele
    anexo (ex.: "Fornecimento dos alimentos ... (Anexo VII)" = 200034) -> CST.

Quando o NCM nao consta de nenhum anexo, o regime de referencia e a tributacao
integral (cClassTrib 000001, CST 000). O indOP nao depende do produto: e o
indicador que define o local do fornecimento do bem movel material.

O Anexo XVII e tratado a parte: ele lista os bens sujeitos ao Imposto Seletivo,
que nao tem cClassTrib proprio - vira alerta na consulta.
"""

from __future__ import annotations

import re

from .dados import base

CCLASSTRIB_PADRAO = "000001"
INDOPS_BENS = ["010101", "010102", "010103", "010104"]
ANEXO_IMPOSTO_SELETIVO = "XVII"


def formata_ncm(digitos: str) -> str:
    if len(digitos) == 8:
        return f"{digitos[:4]}.{digitos[4:6]}.{digitos[6:]}"
    if len(digitos) == 6:
        return f"{digitos[:4]}.{digitos[4:]}"
    if len(digitos) == 4:
        return f"{digitos[:2]}.{digitos[2:]}"
    return digitos


def _classes_do_anexo(anexo: str) -> list[dict]:
    return base().cclasstrib_por_anexo.get(anexo, [])


def _regimes_do_ncm(digitos: str) -> list[dict]:
    """Itens de anexo cujo codigo citado e prefixo do NCM consultado."""
    regimes: list[dict] = []
    for item in base().lc214_anexos:
        casados = [r for r in item["ncm_incluidos"] if digitos.startswith(r)]
        excecoes = [r for r in item["ncm_excecoes"] if digitos.startswith(r)]
        if not casados and not excecoes:
            continue
        # a referencia mais especifica prevalece na leitura do item
        melhor_inc = max((len(r) for r in casados), default=0)
        melhor_exc = max((len(r) for r in excecoes), default=0)
        regimes.append(
            {
                "anexo": item["anexo"],
                "anexo_titulo": item["anexo_titulo"],
                "item": item["item"],
                "descricao": item["descricao"],
                "referencias": [formata_ncm(r) for r in casados],
                "excecoes": [formata_ncm(r) for r in excecoes],
                "excluido": melhor_exc >= melhor_inc and melhor_exc > 0,
                "especificidade": max(melhor_inc, melhor_exc),
                "imposto_seletivo": item["anexo"] == ANEXO_IMPOSTO_SELETIVO,
                "cclasstrib": _classes_do_anexo(item["anexo"]),
            }
        )
    regimes.sort(key=lambda r: (r["excluido"], -r["especificidade"], r["anexo"]))
    return regimes


def consultar(codigo: str) -> dict | None:
    """Monta o resultado da consulta para um codigo NCM (com ou sem mascara)."""
    b = base()
    digitos = re.sub(r"\D", "", codigo or "")
    if not digitos:
        return None

    registro = b.por_ncm.get(digitos)
    hierarquia = b.hierarquia_ncm(digitos)
    if registro is None and not hierarquia:
        return None

    regimes = _regimes_do_ncm(digitos)
    alertas: list[str] = []

    if registro is None:
        alertas.append(
            f"O código {formata_ncm(digitos)} não consta da tabela NCM vigente; "
            "a análise usou o nível mais próximo na hierarquia."
        )
    elif not registro["vigente"]:
        alertas.append(
            f"NCM com vigência encerrada em {registro['data_fim']} — confira a "
            "reclassificação do produto."
        )
    if len(digitos) < 8:
        alertas.append(
            "Consulta feita em nível de capítulo/posição: o enquadramento de "
            "IBS/CBS é definido pelo código completo de 8 dígitos."
        )

    aplicaveis = [r for r in regimes if not r["excluido"] and not r["imposto_seletivo"]]
    seletivo = [r for r in regimes if r["imposto_seletivo"] and not r["excluido"]]
    excluidos = [r for r in regimes if r["excluido"]]

    if not aplicaveis:
        alertas.append(
            "Nenhum anexo de regime diferenciado da LC 214/2025 cita este NCM: "
            "a referência é a tributação integral (CST 000 / cClassTrib 000001)."
        )
    else:
        alertas.append(
            "Regime diferenciado depende também das condições do próprio anexo "
            "(destinação, requisitos da legislação específica) — confira o texto do item."
        )
    if seletivo:
        alertas.append(
            "Bem listado no Anexo XVII: sujeito também ao Imposto Seletivo "
            "(art. 409 e seguintes da LC 214/2025), informado em grupo próprio do DF-e."
        )
    if excluidos:
        alertas.append(
            "Há anexo que cita este NCM em cláusula de exceção — verifique se o "
            "produto está excluído do benefício."
        )

    return {
        "ncm": digitos,
        "formatado": formata_ncm(digitos),
        "descricao": (registro or hierarquia[-1])["descricao"],
        "vigente": bool(registro and registro["vigente"]),
        "registro": registro,
        "hierarquia": hierarquia,
        "regimes": aplicaveis,
        "regimes_seletivo": seletivo,
        "regimes_excluidos": excluidos,
        "padrao": b.por_cclasstrib.get(CCLASSTRIB_PADRAO, {}),
        "indops": [b.por_indop[c] for c in INDOPS_BENS if c in b.por_indop],
        "alertas": alertas,
    }


def linhas_detalhe(resultado: dict) -> list[dict]:
    """Achata a consulta em linhas para exportacao (uma por cClassTrib)."""
    base_linha = {
        "NCM": resultado["formatado"],
        "Descrição NCM": resultado["descricao"],
        "Vigente": "Sim" if resultado["vigente"] else "Não",
    }
    codigos_indop = " | ".join(i["indop"] for i in resultado["indops"])
    linhas: list[dict] = []

    padrao = resultado["padrao"]
    linhas.append(
        {
            **base_linha,
            "Regime": "Tributação integral (referência)",
            "Anexo LC 214/2025": "",
            "Item do anexo": "",
            "Texto do anexo": "",
            "cClassTrib": padrao.get("cclasstrib", ""),
            "Nome cClassTrib": padrao.get("nome", ""),
            "CST IBS/CBS": padrao.get("cst", ""),
            "Descrição CST": padrao.get("cst_descricao", ""),
            "Redução IBS (%)": padrao.get("p_red_ibs", ""),
            "Redução CBS (%)": padrao.get("p_red_cbs", ""),
            "Base legal": padrao.get("lc214", ""),
            "indOP aplicáveis": codigos_indop,
            "Observação": "",
        }
    )

    grupos = [
        ("Regime diferenciado", resultado["regimes"], ""),
        ("Imposto Seletivo", resultado["regimes_seletivo"],
         "Anexo XVII — sem cClassTrib próprio; grupo de IS no DF-e"),
        ("Exceção expressa", resultado["regimes_excluidos"],
         "NCM citado em cláusula de exceção do anexo"),
    ]
    for rotulo, regimes, observacao in grupos:
        for regime in regimes:
            classes = regime["cclasstrib"] or [{}]
            for classe in classes:
                linhas.append(
                    {
                        **base_linha,
                        "Regime": rotulo,
                        "Anexo LC 214/2025": f"Anexo {regime['anexo']}",
                        "Item do anexo": regime["item"],
                        "Texto do anexo": regime["descricao"],
                        "cClassTrib": classe.get("cclasstrib", ""),
                        "Nome cClassTrib": classe.get("nome", ""),
                        "CST IBS/CBS": classe.get("cst", ""),
                        "Descrição CST": classe.get("cst_descricao", ""),
                        "Redução IBS (%)": classe.get("p_red_ibs", ""),
                        "Redução CBS (%)": classe.get("p_red_cbs", ""),
                        "Base legal": classe.get("lc214", ""),
                        "indOP aplicáveis": codigos_indop,
                        "Observação": observacao
                        or ("referências: " + ", ".join(regime["referencias"])),
                    }
                )
    return linhas
