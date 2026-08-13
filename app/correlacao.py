"""Motor de correlacao CNAE -> item da LC 116/2003 -> NBS / indOP / cClassTrib.

Regras aplicadas:

1. CNAE com vinculo em tabela oficial municipal (de-para CNAE x item da lista de
   servicos) -> trilha de SERVICOS, confianca ALTA.
2. CNAE sem vinculo, em secao CNAE tipicamente de bens (A, B, C, G) -> trilha de
   BENS: NBS nao se aplica; sao indicados indOP e cClassTrib das operacoes com
   bens, com alerta de que o enquadramento fino depende do NCM.
3. CNAE sem vinculo nas demais secoes -> sugestao de item da LC 116 por
   similaridade textual (confianca MEDIA/BAIXA) e, em paralelo, a trilha de bens
   como alternativa quando a similaridade e fraca.

Para cada item da LC 116 as variantes de tratamento (indOP, cClassTrib, local de
incidencia e lista de NBS) vem do Anexo VIII da NFS-e nacional.
"""

from __future__ import annotations

from .dados import SECOES_BENS, base
from .parser_cnpj import Atividade

LIMITE_MEDIA = 0.35
LIMITE_BAIXA = 0.18

CCLASSTRIB_PADRAO_BENS = "000001"
INDOP_PADRAO_BENS = ["010101", "010103"]


def _info_indop(codigo: str) -> dict:
    registro = base().por_indop.get(codigo)
    if not registro:
        return {"indop": codigo, "tipo_operacao": "", "caracteristica": "",
                "local_fornecimento": "", "dispositivo_lc214": ""}
    return registro


def _info_cclasstrib(codigo: str) -> dict:
    registro = base().por_cclasstrib.get(codigo)
    if not registro:
        return {"cclasstrib": codigo, "nome": "", "descricao": "", "cst": "",
                "cst_descricao": "", "lc214": "", "tipo_aliquota": ""}
    return registro


def _variantes_do_item(item: str) -> list[dict]:
    variantes = []
    for registro in base().anexo_por_item.get(item, []):
        variantes.append(
            {
                "indops": [{**_info_indop(i["indop"]), **i} for i in registro["indops"]],
                "codigos_indop": [i["indop"] for i in registro["indops"]],
                "cclasstrib": registro["cclasstrib"],
                "cclasstrib_info": _info_cclasstrib(registro["cclasstrib"]),
                "local_incidencia": registro["local_incidencia"],
                "nbs": registro["nbs"],
            }
        )
    variantes.sort(key=lambda v: (not v["nbs"], v["cclasstrib"]))
    return variantes


def _item_correlacionado(item: str, origem: str, confianca: str, score: float,
                         fontes: list[str]) -> dict:
    descricao = base().por_item.get(item, {}).get("descricao", "")
    variantes = _variantes_do_item(item)
    return {
        "item": item,
        "descricao": descricao,
        "origem": origem,
        "confianca": confianca,
        "score": round(score, 3),
        "fontes": fontes,
        "variantes": variantes,
        "sem_anexo_viii": not variantes,
    }


def _trilha_bens() -> dict:
    b = base()
    alternativas = [
        {
            "cclasstrib": c["cclasstrib"],
            "cst": c["cst"],
            "nome": c["nome"],
            "cst_descricao": c["cst_descricao"],
        }
        for c in b.cclasstrib
        if c["usa_nfe"] and c["cst"] != "000"
    ]
    return {
        "aplicavel": True,
        "nbs": "Não aplicável — a NBS classifica serviços e intangíveis; "
               "operações com bens são identificadas pelo NCM.",
        "item_lc116": "Não aplicável — operação com bens não consta da lista da LC 116/2003.",
        "indops": [_info_indop(c) for c in INDOP_PADRAO_BENS],
        "cclasstrib_padrao": _info_cclasstrib(CCLASSTRIB_PADRAO_BENS),
        "alternativas": alternativas,
    }


def correlacionar_atividade(atividade: Atividade) -> dict:
    b = base()
    cnae = atividade.cnae
    oficial = b.por_cnae.get(cnae)
    alertas: list[str] = []

    if not oficial:
        alertas.append(
            "CNAE não localizado na tabela de subclasses do IBGE — confira o código."
        )
    descricao_oficial = oficial["descricao"] if oficial else ""
    secao = oficial["secao"] if oficial else ""

    texto_busca = " ".join(
        filter(None, [descricao_oficial, atividade.descricao,
                      (oficial or {}).get("classe_descricao", "")])
    )

    itens: list[dict] = []
    natureza = ""
    bens = {"aplicavel": False}

    vinculos = b.itens_por_cnae.get(cnae, [])
    if vinculos:
        natureza = "servico"
        for vinculo in vinculos:
            itens.append(
                _item_correlacionado(
                    vinculo["item"],
                    origem="Tabela oficial municipal CNAE x lista de serviços",
                    confianca="alta",
                    score=1.0,
                    fontes=vinculo["fontes"],
                )
            )
    elif secao in SECOES_BENS:
        natureza = "bens"
        bens = _trilha_bens()
        alertas.append(
            "Seção CNAE tipicamente de bens: o enquadramento definitivo do "
            "cClassTrib depende do NCM do produto (reduções, alíquota zero, "
            "monofasia, exportação)."
        )
    else:
        natureza = "servico_sugerido"
        for item, score in b.itens_semelhantes(texto_busca, limite=3):
            if score < LIMITE_BAIXA:
                continue
            confianca = "media" if score >= LIMITE_MEDIA else "baixa"
            itens.append(
                _item_correlacionado(
                    item,
                    origem="Sugestão por similaridade textual (validar)",
                    confianca=confianca,
                    score=score,
                    fontes=[],
                )
            )
        melhor = itens[0]["score"] if itens else 0.0
        if melhor < LIMITE_MEDIA:
            bens = _trilha_bens()
            alertas.append(
                "Sem vínculo em tabela oficial e similaridade fraca: avalie se a "
                "atividade é serviço (LC 116) ou operação com bens."
            )
        else:
            alertas.append(
                "Item da LC 116 sugerido por similaridade — requer validação do "
                "responsável tributário."
            )

    if natureza in ("servico", "servico_sugerido"):
        sem_anexo = [i["item"] for i in itens if i["sem_anexo_viii"]]
        if sem_anexo:
            alertas.append(
                "Sem correlação no Anexo VIII para o(s) item(ns) "
                + ", ".join(sem_anexo)
                + " — a versão atual do anexo ainda está em evolução."
            )

    return {
        "cnae": cnae,
        "cnae_formatado": atividade.formatado,
        "principal": atividade.principal,
        "descricao_cartao": atividade.descricao,
        "descricao_oficial": descricao_oficial,
        "secao": secao,
        "secao_descricao": (oficial or {}).get("secao_descricao", ""),
        "divisao": (oficial or {}).get("divisao", ""),
        "natureza": natureza,
        "itens": itens,
        "bens": bens,
        "alertas": alertas,
    }


def correlacionar(atividades: list[Atividade]) -> list[dict]:
    return [correlacionar_atividade(a) for a in atividades]


def linhas_detalhe(resultados: list[dict]) -> list[dict]:
    """Achata o resultado em linhas (uma por NBS) para exportacao."""
    linhas: list[dict] = []
    for r in resultados:
        base_linha = {
            "CNAE": r["cnae_formatado"],
            "Tipo": "Principal" if r["principal"] else "Secundaria",
            "Descrição CNAE": r["descricao_oficial"] or r["descricao_cartao"],
            "Seção CNAE": f"{r['secao']} - {r['secao_descricao']}".strip(" -"),
            "Natureza": {
                "servico": "Serviço (LC 116)",
                "servico_sugerido": "Serviço (sugerido)",
                "bens": "Operação com bens",
            }.get(r["natureza"], r["natureza"]),
        }

        if not r["itens"] and r["bens"].get("aplicavel"):
            padrao = r["bens"]["cclasstrib_padrao"]
            for indop in r["bens"]["indops"]:
                linhas.append(
                    {
                        **base_linha,
                        "Item LC 116/03": "Não aplicável",
                        "Descrição item": "",
                        "NBS": "Não aplicável",
                        "Descrição NBS": "Classificação de bens é feita por NCM",
                        "indOP": indop["indop"],
                        "Descrição indOP": f"{indop['tipo_operacao']} - {indop['caracteristica']}",
                        "Local de incidência": indop["local_fornecimento"],
                        "cClassTrib": padrao["cclasstrib"],
                        "Nome cClassTrib": padrao["nome"],
                        "CST IBS/CBS": padrao["cst"],
                        "Confiança": "referencia",
                        "Origem": "Anexo VII (indOP) + Tabela cClassTrib NF-e",
                        "Alertas": " | ".join(r["alertas"]),
                    }
                )
            continue

        for item in r["itens"]:
            if not item["variantes"]:
                linhas.append(
                    {
                        **base_linha,
                        "Item LC 116/03": item["item"],
                        "Descrição item": item["descricao"],
                        "NBS": "",
                        "Descrição NBS": "",
                        "indOP": "",
                        "Descrição indOP": "",
                        "Local de incidência": "",
                        "cClassTrib": "",
                        "Nome cClassTrib": "",
                        "CST IBS/CBS": "",
                        "Confiança": item["confianca"],
                        "Origem": item["origem"],
                        "Alertas": " | ".join(r["alertas"]),
                    }
                )
                continue
            for variante in item["variantes"]:
                cclass = variante["cclasstrib_info"]
                indops = variante["indops"]
                codigos = " | ".join(variante["codigos_indop"])
                descricoes = " | ".join(
                    f"{i['indop']} {i.get('tipo_operacao','')} ({i.get('local_fornecimento','')})"
                    for i in indops
                )
                locais = variante["local_incidencia"] or " | ".join(
                    dict.fromkeys(i.get("local_fornecimento", "") for i in indops)
                )
                nbs_lista = variante["nbs"] or [{"nbs": "", "descricao": ""}]
                for nbs in nbs_lista:
                    linhas.append(
                        {
                            **base_linha,
                            "Item LC 116/03": item["item"],
                            "Descrição item": item["descricao"],
                            "NBS": nbs["nbs"],
                            "Descrição NBS": nbs["descricao"],
                            "indOP": codigos,
                            "Descrição indOP": descricoes,
                            "Local de incidência": locais,
                            "cClassTrib": variante["cclasstrib"],
                            "Nome cClassTrib": cclass.get("nome", ""),
                            "CST IBS/CBS": cclass.get("cst", ""),
                            "Confiança": item["confianca"],
                            "Origem": item["origem"]
                            + (f" | fontes: {', '.join(item['fontes'])}" if item["fontes"] else ""),
                            "Alertas": " | ".join(r["alertas"]),
                        }
                    )
    return linhas


def resumo(resultados: list[dict]) -> dict:
    return {
        "cnaes": len(resultados),
        "servicos": sum(1 for r in resultados if r["natureza"] == "servico"),
        "servicos_sugeridos": sum(1 for r in resultados if r["natureza"] == "servico_sugerido"),
        "bens": sum(1 for r in resultados if r["natureza"] == "bens"),
        "itens_lc116": len({i["item"] for r in resultados for i in r["itens"]}),
        "nbs": len(
            {
                n["nbs"]
                for r in resultados
                for i in r["itens"]
                for v in i["variantes"]
                for n in v["nbs"]
            }
        ),
        "cclasstrib": len(
            {v["cclasstrib"] for r in resultados for i in r["itens"] for v in i["variantes"]}
        ),
    }
