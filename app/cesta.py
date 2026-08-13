"""Cesta de consultas: acumula resultados de CNAE e de NCM em um relatorio unico.

Cada consulta feita nas telas (analise do cartao CNPJ ou consulta por NCM) pode ser
adicionada a uma cesta. As linhas das duas origens sao convertidas para um mesmo
conjunto de colunas, o que permite exportar tudo em uma planilha so - o entregavel
do trabalho de enquadramento.

A cesta vive em memoria e e identificada por um cookie; nao ha dado de contribuinte
gravado em disco pela ferramenta.
"""

from __future__ import annotations

import secrets
from collections import Counter, OrderedDict
from datetime import datetime

from .correlacao import linhas_detalhe as linhas_cnae
from .dados import base
from .ncm import linhas_detalhe as linhas_ncm

CESTAS: "OrderedDict[str, dict]" = OrderedDict()
LIMITE_CESTAS = 50
LIMITE_ITENS = 60

# a coluna "Regime / confianca" reune as duas origens; os rotulos abaixo evitam
# que "alta"/"media" (CNAE) fiquem ao lado de "Regime diferenciado" (NCM) sem contexto
ROTULO_CONFIANCA = {
    "alta": "Vínculo oficial",
    "media": "Sugestão a validar (média)",
    "baixa": "Sugestão a validar (baixa)",
    "referencia": "Referência (bens)",
}

COLUNAS = [
    "Consulta", "Tipo", "Código", "Descrição",
    "Item LC 116/03", "NBS", "Descrição NBS",
    "indOP", "cClassTrib", "Nome cClassTrib", "CST IBS/CBS",
    "Redução IBS (%)", "Redução CBS (%)",
    "Regime / confiança", "Fundamento", "Base legal", "Alertas",
]


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _reducoes(codigo: str) -> tuple[str, str, str]:
    """Percentuais de reducao e base legal a partir do cClassTrib."""
    registro = base().por_cclasstrib.get(codigo or "")
    if not registro:
        return "", "", ""
    return registro["p_red_ibs"], registro["p_red_cbs"], registro["lc214"]


def nova_cesta() -> tuple[str, dict]:
    ident = secrets.token_urlsafe(9)
    cesta = {"id": ident, "criada_em": _agora(), "itens": []}
    CESTAS[ident] = cesta
    while len(CESTAS) > LIMITE_CESTAS:
        CESTAS.popitem(last=False)
    return ident, cesta


def obter(ident: str | None) -> dict | None:
    return CESTAS.get(ident) if ident else None


def _guarda_item(cesta: dict, item: dict) -> dict:
    cesta["itens"].append(item)
    del cesta["itens"][:-LIMITE_ITENS]
    return item


# --------------------------------------------------------------------- entradas


def adicionar_cnae(cesta: dict, cartao: dict, resultados: list[dict]) -> dict:
    rotulo = cartao.get("cnpj") or cartao.get("nome_empresarial") or "Consulta de CNAEs"
    linhas = []
    for origem in linhas_cnae(resultados):
        p_ibs, p_cbs, lc214 = _reducoes(origem.get("cClassTrib", ""))
        linhas.append(
            {
                "Consulta": rotulo,
                "Tipo": "Serviço (CNAE)"
                if origem.get("Natureza", "").startswith("Serviço")
                else "Bem (CNAE)",
                "Código": origem.get("CNAE", ""),
                "Descrição": origem.get("Descrição CNAE", ""),
                "Item LC 116/03": origem.get("Item LC 116/03", ""),
                "NBS": origem.get("NBS", ""),
                "Descrição NBS": origem.get("Descrição NBS", ""),
                "indOP": origem.get("indOP", ""),
                "cClassTrib": origem.get("cClassTrib", ""),
                "Nome cClassTrib": origem.get("Nome cClassTrib", ""),
                "CST IBS/CBS": origem.get("CST IBS/CBS", ""),
                "Redução IBS (%)": p_ibs,
                "Redução CBS (%)": p_cbs,
                "Regime / confiança": ROTULO_CONFIANCA.get(
                    origem.get("Confiança", ""), origem.get("Confiança", "")
                ),
                "Fundamento": origem.get("Descrição item", "")
                or origem.get("Local de incidência", ""),
                "Base legal": lc214,
                "Alertas": origem.get("Alertas", ""),
            }
        )

    cnaes = {r["cnae_formatado"] for r in resultados}
    return _guarda_item(
        cesta,
        {
            "id": secrets.token_urlsafe(6),
            "tipo": "cnae",
            "rotulo": rotulo,
            "titulo": cartao.get("nome_empresarial", "") or "Correlação de CNAEs",
            "detalhe": f"{len(cnaes)} CNAE(s) · {len(linhas)} linha(s)",
            "adicionado_em": _agora(),
            "linhas": linhas,
        },
    )


def adicionar_ncm(cesta: dict, consulta: dict) -> dict:
    rotulo = f"NCM {consulta['formatado']}"
    alertas = " | ".join(consulta["alertas"])
    linhas = []
    for origem in linhas_ncm(consulta):
        anexo = origem.get("Anexo LC 214/2025", "")
        item = origem.get("Item do anexo", "")
        linhas.append(
            {
                "Consulta": rotulo,
                "Tipo": "Bem (NCM)",
                "Código": origem.get("NCM", ""),
                "Descrição": origem.get("Descrição NCM", ""),
                "Item LC 116/03": "Não aplicável",
                "NBS": "Não aplicável",
                "Descrição NBS": "",
                "indOP": origem.get("indOP aplicáveis", ""),
                "cClassTrib": origem.get("cClassTrib", ""),
                "Nome cClassTrib": origem.get("Nome cClassTrib", ""),
                "CST IBS/CBS": origem.get("CST IBS/CBS", ""),
                "Redução IBS (%)": origem.get("Redução IBS (%)", ""),
                "Redução CBS (%)": origem.get("Redução CBS (%)", ""),
                "Regime / confiança": origem.get("Regime", ""),
                "Fundamento": " — ".join(
                    p for p in [f"{anexo} item {item}".strip() if anexo else "",
                                origem.get("Texto do anexo", "")] if p
                ),
                "Base legal": origem.get("Base legal", ""),
                "Alertas": alertas,
            }
        )

    return _guarda_item(
        cesta,
        {
            "id": secrets.token_urlsafe(6),
            "tipo": "ncm",
            "rotulo": rotulo,
            "titulo": consulta["descricao"],
            "detalhe": f"{len(consulta['regimes'])} regime(s) diferenciado(s) · "
                       f"{len(linhas)} linha(s)",
            "adicionado_em": _agora(),
            "linhas": linhas,
        },
    )


def adicionar_lote(cesta: dict, lote: dict, rotulo: str = "") -> dict:
    """Consulta em lote de NCM: entra na cesta como um item so."""
    from .lote import linhas_detalhe as linhas_lote

    resumo_lote = lote["resumo"]
    rotulo = rotulo or f"Lote de {resumo_lote['total']} NCM"
    linhas = []
    for origem in linhas_lote(lote):
        anexo = origem.get("Anexo LC 214/2025", "")
        item = origem.get("Item do anexo", "")
        referencia = origem.get("Referência", "")
        linhas.append(
            {
                "Consulta": rotulo,
                "Tipo": "Bem (NCM)",
                "Código": origem.get("NCM", ""),
                "Descrição": " — ".join(
                    p for p in [referencia, origem.get("Descrição NCM", "")] if p
                ),
                "Item LC 116/03": "Não aplicável",
                "NBS": "Não aplicável",
                "Descrição NBS": "",
                "indOP": origem.get("indOP aplicáveis", ""),
                "cClassTrib": origem.get("cClassTrib", ""),
                "Nome cClassTrib": origem.get("Nome cClassTrib", ""),
                "CST IBS/CBS": origem.get("CST IBS/CBS", ""),
                "Redução IBS (%)": origem.get("Redução IBS (%)", ""),
                "Redução CBS (%)": origem.get("Redução CBS (%)", ""),
                "Regime / confiança": origem.get("Regime", ""),
                "Fundamento": " — ".join(
                    p for p in [f"{anexo} item {item}".strip() if anexo else "",
                                origem.get("Texto do anexo", "")] if p
                ),
                "Base legal": origem.get("Base legal", ""),
                "Alertas": origem.get("Observação", ""),
            }
        )

    return _guarda_item(
        cesta,
        {
            "id": secrets.token_urlsafe(6),
            "tipo": "lote",
            "rotulo": rotulo,
            "titulo": f"{resumo_lote['com_regime']} com regime diferenciado · "
                      f"{resumo_lote['integral']} integral · "
                      f"{resumo_lote['nao_localizados']} não localizado(s)",
            "detalhe": f"{resumo_lote['total']} NCM · {len(linhas)} linha(s)",
            "adicionado_em": _agora(),
            "linhas": linhas,
        },
    )


# ---------------------------------------------------------------------- saidas


def remover(cesta: dict, item_id: str) -> bool:
    antes = len(cesta["itens"])
    cesta["itens"] = [i for i in cesta["itens"] if i["id"] != item_id]
    return len(cesta["itens"]) < antes


def limpar(cesta: dict) -> None:
    cesta["itens"] = []


def linhas(cesta: dict) -> list[dict]:
    return [linha for item in cesta["itens"] for linha in item["linhas"]]


def resumo(cesta: dict) -> dict:
    todas = linhas(cesta)
    por_cst = Counter(l["CST IBS/CBS"] for l in todas if l["CST IBS/CBS"])
    por_classe = Counter(l["cClassTrib"] for l in todas if l["cClassTrib"])
    reducoes = Counter(l["Redução IBS (%)"] for l in todas if l["Redução IBS (%)"])
    b = base()

    return {
        "consultas": len(cesta["itens"]),
        "consultas_cnae": sum(1 for i in cesta["itens"] if i["tipo"] == "cnae"),
        "consultas_ncm": sum(1 for i in cesta["itens"] if i["tipo"] in {"ncm", "lote"}),
        "linhas": len(todas),
        "codigos": len({l["Código"] for l in todas if l["Código"]}),
        "cclasstrib": len(por_classe),
        "aliquota_zero": reducoes.get("100", 0),
        "reducao_60": reducoes.get("60", 0),
        "reducao_30": reducoes.get("30", 0),
        "integral": sum(1 for l in todas if l["CST IBS/CBS"] == "000"),
        "a_validar": sum(
            1 for l in todas if l["Regime / confiança"].startswith("Sugestão")
        ),
        "imposto_seletivo": sum(
            1 for l in todas if l["Regime / confiança"] == "Imposto Seletivo"
        ),
        "excecoes": sum(
            1 for l in todas if l["Regime / confiança"] == "Exceção expressa"
        ),
        "top_cst": [
            {
                "cst": cst,
                "descricao": next(
                    (c["descricao"] for c in b.cst if c["cst"] == cst), ""
                ),
                "linhas": qtd,
            }
            for cst, qtd in por_cst.most_common(6)
        ],
        "top_cclasstrib": [
            {
                "cclasstrib": codigo,
                "nome": b.por_cclasstrib.get(codigo, {}).get("nome", ""),
                "linhas": qtd,
            }
            for codigo, qtd in por_classe.most_common(8)
        ],
    }
