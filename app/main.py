"""App web local: correlacao CNAE x NBS x cClassTrib x indOP x item da LC 116/03.

Execucao:
    python -m app.main            (http://127.0.0.1:5000)
"""

from __future__ import annotations

import re
import secrets
from collections import OrderedDict

from flask import (Flask, Response, abort, render_template, request, url_for)

from .correlacao import correlacionar, linhas_detalhe, resumo
from .dados import base, normaliza
from .ncm import consultar as consultar_ncm
from .parser_cnpj import CartaoCNPJ, cnaes_de_texto_livre, ler_cartao, texto_do_pdf
from .relatorio import (gerar_csv, gerar_csv_ncm, gerar_json, gerar_json_ncm,
                        gerar_xlsx, gerar_xlsx_ncm)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

# cache em memoria das ultimas analises (para download dos relatorios)
ANALISES: "OrderedDict[str, dict]" = OrderedDict()
CONSULTAS_NCM: "OrderedDict[str, dict]" = OrderedDict()
LIMITE_CACHE = 20


def guardar(cartao: dict, resultados: list[dict]) -> str:
    token = secrets.token_urlsafe(9)
    ANALISES[token] = {"cartao": cartao, "resultados": resultados}
    while len(ANALISES) > LIMITE_CACHE:
        ANALISES.popitem(last=False)
    return token


@app.route("/")
def inicio():
    return render_template("index.html", manifesto=base().manifesto)


@app.post("/analisar")
def analisar():
    arquivo = request.files.get("cartao")
    manual = request.form.get("cnaes", "").strip()

    cartao = CartaoCNPJ()
    if arquivo and arquivo.filename:
        if not arquivo.filename.lower().endswith(".pdf"):
            return render_template(
                "index.html", erro="Envie o cartao CNPJ em PDF.", manifesto=base().manifesto
            ), 400
        try:
            cartao = ler_cartao(texto_do_pdf(arquivo.read()))
        except Exception as exc:  # pdf corrompido, protegido etc.
            return render_template(
                "index.html",
                erro=f"Nao foi possivel ler o PDF: {exc}",
                manifesto=base().manifesto,
            ), 400

    if manual:
        extras = cnaes_de_texto_livre(manual)
        existentes = {a.cnae for a in cartao.atividades}
        for atividade in extras:
            if atividade.cnae not in existentes:
                atividade.principal = atividade.principal and not cartao.atividades
                cartao.atividades.append(atividade)

    if not cartao.atividades:
        return render_template(
            "index.html",
            erro="Nenhum CNAE identificado. Envie o cartao CNPJ em PDF (com texto "
                 "selecionavel) ou digite os CNAEs no campo manual.",
            manifesto=base().manifesto,
        ), 400

    resultados = correlacionar(cartao.atividades)
    dados_cartao = cartao.como_dict()
    token = guardar(dados_cartao, resultados)

    return render_template(
        "resultado.html",
        cartao=dados_cartao,
        resultados=resultados,
        resumo=resumo(resultados),
        total_linhas=len(linhas_detalhe(resultados)),
        token=token,
    )


@app.get("/ncm")
def ncm_busca():
    termo = request.args.get("q", "").strip()
    if not termo:
        return render_template("ncm_busca.html", termo="", achados=[], total=0)

    digitos = re.sub(r"\D", "", termo)
    if len(digitos) >= 8 or (digitos and base().por_ncm.get(digitos)):
        return ncm_detalhe(digitos)

    achados = base().buscar_ncm(termo)
    return render_template("ncm_busca.html", termo=termo, achados=achados,
                           total=len(achados))


@app.get("/ncm/<codigo>")
def ncm_detalhe(codigo: str):
    consulta = consultar_ncm(codigo)
    if not consulta:
        return render_template(
            "ncm_busca.html", termo=codigo, achados=[], total=0,
            erro=f"NCM {codigo} não localizado na tabela vigente.",
        ), 404
    token = secrets.token_urlsafe(9)
    CONSULTAS_NCM[token] = consulta
    while len(CONSULTAS_NCM) > LIMITE_CACHE:
        CONSULTAS_NCM.popitem(last=False)
    return render_template("ncm.html", c=consulta, token=token)


@app.get("/download-ncm/<token>/<formato>")
def download_ncm(token: str, formato: str):
    consulta = CONSULTAS_NCM.get(token)
    if not consulta:
        abort(404, "Consulta expirada. Refaça a busca do NCM.")
    if formato == "xlsx":
        conteudo = gerar_xlsx_ncm(consulta)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "csv":
        conteudo, tipo = gerar_csv_ncm(consulta), "text/csv; charset=utf-8"
    elif formato == "json":
        conteudo, tipo = gerar_json_ncm(consulta), "application/json"
    else:
        abort(404)
    return Response(
        conteudo,
        mimetype=tipo,
        headers={
            "Content-Disposition": f'attachment; filename="ncm_{consulta["ncm"]}.{formato}"'
        },
    )


@app.get("/download/<token>/<formato>")
def download(token: str, formato: str):
    analise = ANALISES.get(token)
    if not analise:
        abort(404, "Analise expirada. Refaca o envio do cartao CNPJ.")
    cartao, resultados = analise["cartao"], analise["resultados"]
    apelido = (cartao.get("cnpj") or "correlacao").replace("/", "-").replace(".", "")

    if formato == "xlsx":
        conteudo = gerar_xlsx(cartao, resultados)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "csv":
        conteudo, tipo = gerar_csv(resultados), "text/csv; charset=utf-8"
    elif formato == "json":
        conteudo, tipo = gerar_json(cartao, resultados), "application/json"
    else:
        abort(404)

    return Response(
        conteudo,
        mimetype=tipo,
        headers={
            "Content-Disposition": f'attachment; filename="correlacao_{apelido}.{formato}"'
        },
    )


@app.get("/consulta")
def consulta():
    b = base()
    termo = request.args.get("q", "").strip()
    alvo = request.args.get("tipo", "cnae")
    achados: list[dict] = []

    if termo:
        chave = normaliza(termo)
        if alvo == "cnae":
            for c in b.cnae:
                if chave in normaliza(c["descricao"]) or chave in c["cnae"]:
                    achados.append({"codigo": c["cnae_formatado"], "descricao": c["descricao"],
                                    "extra": f"Secao {c['secao']} - {c['secao_descricao']}",
                                    "link": url_for("detalhe_cnae", cnae=c["cnae"])})
        elif alvo == "nbs":
            for n in b.nbs:
                if chave in normaliza(n["descricao"]) or chave in n["nbs"]:
                    achados.append({"codigo": n["nbs"], "descricao": n["descricao"],
                                    "extra": n["nivel"], "link": ""})
        elif alvo == "lc116":
            for i in b.lc116:
                if chave in normaliza(i["descricao"]) or chave in i["item"]:
                    achados.append({"codigo": i["item"], "descricao": i["descricao"],
                                    "extra": "", "link": ""})
        elif alvo == "cclasstrib":
            for c in b.cclasstrib:
                if chave in normaliza(c["nome"]) or chave in c["cclasstrib"] or chave in normaliza(c["descricao"]):
                    achados.append({"codigo": c["cclasstrib"], "descricao": c["nome"],
                                    "extra": f"CST {c['cst']} - {c['cst_descricao']} | {c['lc214']}",
                                    "link": ""})
        elif alvo == "ncm":
            for n in b.buscar_ncm(termo, limite=200):
                achados.append({"codigo": n["codigo"], "descricao": n["descricao"],
                                "extra": ("vigente" if n["vigente"] else "revogado")
                                + f" · nível {n['nivel']} dígitos",
                                "link": url_for("ncm_detalhe", codigo=n["ncm"])})
        elif alvo == "indop":
            for i in b.indop:
                if chave in normaliza(i["caracteristica"]) or chave in i["indop"] or chave in normaliza(i["tipo_operacao"]):
                    achados.append({"codigo": i["indop"], "descricao": f"{i['tipo_operacao']} - {i['caracteristica']}",
                                    "extra": i["local_fornecimento"], "link": ""})

    return render_template("consulta.html", termo=termo, tipo=alvo, achados=achados[:200],
                           total=len(achados))


@app.get("/cnae/<cnae>")
def detalhe_cnae(cnae: str):
    from .parser_cnpj import Atividade

    registro = base().por_cnae.get(cnae)
    if not registro:
        abort(404)
    atividade = Atividade(cnae=cnae, descricao=registro["descricao"], principal=True)
    resultados = correlacionar([atividade])
    cartao = {"nome_empresarial": f"Consulta avulsa - CNAE {atividade.formatado}"}
    token = guardar(cartao, resultados)
    return render_template(
        "resultado.html", cartao=cartao, resultados=resultados,
        resumo=resumo(resultados), total_linhas=len(linhas_detalhe(resultados)), token=token,
    )


@app.get("/fontes")
def fontes():
    return render_template("fontes.html", manifesto=base().manifesto)


def main() -> None:
    base()  # carrega datasets antes de subir o servidor
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
