"""App web local: correlacao CNAE x NBS x cClassTrib x indOP x item da LC 116/03.

Execucao:
    python -m app.main            (http://127.0.0.1:5000)
"""

from __future__ import annotations

import os
import re
import secrets
from collections import OrderedDict

from flask import (Flask, Response, abort, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix

from . import auth
from . import cesta as mod_cesta
from . import lote as mod_lote
from .correlacao import correlacionar, linhas_detalhe, resumo
from .dados import base, normaliza
from .ncm import consultar as consultar_ncm
from .parser_cnpj import CartaoCNPJ, cnaes_de_texto_livre, ler_cartao, texto_do_pdf
from .relatorio import (gerar_csv, gerar_csv_cesta, gerar_csv_lote, gerar_csv_ncm,
                        gerar_json, gerar_json_cesta, gerar_json_lote,
                        gerar_json_ncm, gerar_xlsx, gerar_xlsx_cesta,
                        gerar_xlsx_lote, gerar_xlsx_ncm)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

COOKIE_CESTA = "rtc_cesta"

# Hospedado (Render e afins), a aplicacao fica atras de um proxy que termina o
# HTTPS: sem isso o Flask monta as URLs como http e marca o cookie da cesta como
# inseguro.
if os.environ.get("RTC_ATRAS_DE_PROXY", "1") != "0":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Sessao de login. Em servidor, defina RTC_SECRET_KEY para que as sessoes
# sobrevivam a um reinicio; sem ela, cada start invalida os logins abertos.
app.secret_key = os.environ.get("RTC_SECRET_KEY") or secrets.token_hex(32)

# Telas abertas (sem login) e acoes que consomem cota de consulta
LIVRES = {"entrar", "sair", "static"}
CONSOME_COTA = {"analisar", "ncm_detalhe", "ncm_lote", "detalhe_cnae"}


@app.before_request
def _exige_login():
    endpoint = request.endpoint or ""
    if endpoint in LIVRES:
        return None

    usuario = auth.obter(session.get("login", ""))
    if not usuario:
        session.clear()
        if request.method == "POST" or endpoint.startswith("download"):
            return redirect(url_for("entrar"))
        return redirect(url_for("entrar", proxima=request.full_path.rstrip("?")))

    # a consulta em lote so cobra cota no envio; a tela em si e livre
    cobra = endpoint in CONSOME_COTA and not (
        endpoint == "ncm_lote" and request.method == "GET"
    )
    if cobra and not auth.pode_consultar(usuario["login"]):
        return render_template("limite.html", usuario=usuario,
                               consumo=auth.consumo(usuario["login"])), 403

    g.usuario = usuario
    g.cobrar_consulta = cobra
    return None


@app.after_request
def _cobra_consulta(resposta):
    """Debita a cota apenas quando a consulta foi de fato executada."""
    if getattr(g, "cobrar_consulta", False) and resposta.status_code < 400:
        auth.registrar_consulta(g.usuario["login"])
        g.cobrar_consulta = False
    return resposta


@app.context_processor
def _injeta_usuario():
    usuario = getattr(g, "usuario", None)
    return {
        "usuario": usuario,
        "consultas_restantes": auth.restante(usuario["login"]) if usuario else None,
    }


@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    if request.method == "GET":
        if auth.obter(session.get("login", "")):
            return redirect(url_for("inicio"))
        return render_template("login.html", proxima=request.args.get("proxima", ""))

    usuario = auth.autenticar(request.form.get("login", ""), request.form.get("senha", ""))
    if not usuario:
        return render_template(
            "login.html",
            erro="Usuário ou senha inválidos.",
            login=request.form.get("login", ""),
            proxima=request.form.get("proxima", ""),
        ), 401

    session.clear()
    session["login"] = usuario["login"]
    session.permanent = False

    destino = request.form.get("proxima", "")
    if destino.startswith("/") and not destino.startswith("//"):
        return redirect(destino)
    return redirect(url_for("inicio"))


@app.get("/sair")
def sair():
    session.clear()
    return redirect(url_for("entrar"))


def _so_administrador():
    if g.usuario["papel"] != "administrador":
        abort(403)


def _tela_usuarios(erro: str = "", criado: str = "", formulario: dict | None = None,
                   status: int = 200):
    return render_template(
        "usuarios.html",
        linhas=auth.painel(),
        opcoes=auth.opcoes_de_limite(),
        erro=erro,
        criado=criado,
        formulario=formulario or {},
    ), status


@app.get("/usuarios")
def usuarios():
    """Painel de usuarios e uso - restrito ao administrador."""
    _so_administrador()
    return _tela_usuarios(criado=request.args.get("criado", ""))


@app.post("/usuarios/criar")
def usuarios_criar():
    _so_administrador()
    login = request.form.get("login", "")
    limite = request.form.get("limite", "")
    try:
        novo = auth.criar_usuario(
            login=login,
            senha=request.form.get("senha", ""),
            limite=None if limite == "ilimitado" else limite,
            nome=request.form.get("nome", ""),
        )
    except ValueError as exc:
        return _tela_usuarios(
            erro=str(exc),
            formulario={"login": login, "nome": request.form.get("nome", ""),
                        "limite": limite},
            status=400,
        )
    return redirect(url_for("usuarios", criado=novo["login"]))


@app.post("/usuarios/remover/<login>")
def usuarios_remover(login: str):
    _so_administrador()
    try:
        auth.remover_usuario(login)
    except ValueError as exc:
        return _tela_usuarios(erro=str(exc), status=400)
    return redirect(url_for("usuarios"))


@app.post("/usuarios/zerar/<login>")
def usuarios_zerar(login: str):
    _so_administrador()
    auth.zerar(login)
    return redirect(url_for("usuarios"))

# cache em memoria das ultimas analises (para download dos relatorios)
ANALISES: "OrderedDict[str, dict]" = OrderedDict()
CONSULTAS_NCM: "OrderedDict[str, dict]" = OrderedDict()
LOTES: "OrderedDict[str, dict]" = OrderedDict()
LIMITE_CACHE = 20


def guardar(cartao: dict, resultados: list[dict]) -> str:
    token = secrets.token_urlsafe(9)
    ANALISES[token] = {"cartao": cartao, "resultados": resultados}
    while len(ANALISES) > LIMITE_CACHE:
        ANALISES.popitem(last=False)
    return token


# --------------------------------------------------------------------- cesta


def cesta_do_visitante(criar: bool = False) -> dict | None:
    """Cesta ligada ao cookie do navegador; criada sob demanda."""
    ident = getattr(g, "cesta_id", None) or request.cookies.get(COOKIE_CESTA)
    cesta = mod_cesta.obter(ident)
    if cesta is None and criar:
        ident, cesta = mod_cesta.nova_cesta()
        g.cesta_id = ident
        g.cesta_nova = True
    return cesta


@app.after_request
def _grava_cookie_da_cesta(resposta):
    if getattr(g, "cesta_nova", False):
        resposta.set_cookie(
            COOKIE_CESTA, g.cesta_id, max_age=60 * 60 * 24 * 30,
            httponly=True, samesite="Lax",
        )
    return resposta


@app.context_processor
def _injeta_cesta():
    cesta = cesta_do_visitante()
    return {"cesta_qtd": len(cesta["itens"]) if cesta else 0}


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


@app.route("/ncm/lote", methods=["GET", "POST"])
def ncm_lote():
    """Consulta em lote: lista digitada ou planilha (.xlsx/.csv) com os NCM."""
    if request.method == "GET":
        return render_template("ncm_lote.html", limite=mod_lote.LIMITE_ITENS)

    itens: list[dict] = []
    avisos: list[str] = []
    arquivo = request.files.get("planilha")
    texto = request.form.get("ncms", "").strip()

    if arquivo and arquivo.filename:
        try:
            do_arquivo, avisos_arquivo = mod_lote.de_planilha(arquivo.filename, arquivo.read())
        except Exception as exc:
            return render_template(
                "ncm_lote.html", limite=mod_lote.LIMITE_ITENS, erro=str(exc)
            ), 400
        itens += do_arquivo
        avisos += avisos_arquivo
    if texto:
        itens += mod_lote.de_texto(texto)

    if not itens:
        return render_template(
            "ncm_lote.html",
            limite=mod_lote.LIMITE_ITENS,
            erro="Nenhum NCM foi identificado. Cole os códigos no campo ou envie uma "
                 "planilha com uma coluna de NCM.",
        ), 400

    lote = mod_lote.processar(itens)
    lote["avisos"] = avisos + lote["avisos"]

    token = secrets.token_urlsafe(9)
    LOTES[token] = lote
    while len(LOTES) > LIMITE_CACHE:
        LOTES.popitem(last=False)

    return render_template(
        "ncm_lote.html",
        limite=mod_lote.LIMITE_ITENS,
        lote=lote,
        linhas=mod_lote.linhas_resumo(lote),
        token=token,
    )


@app.get("/download-lote/<token>/<formato>")
def download_lote(token: str, formato: str):
    lote = LOTES.get(token)
    if not lote:
        abort(404, "Lote expirado. Refaça a consulta.")
    if formato == "xlsx":
        conteudo = gerar_xlsx_lote(lote)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "csv":
        conteudo, tipo = gerar_csv_lote(lote), "text/csv; charset=utf-8"
    elif formato == "json":
        conteudo, tipo = gerar_json_lote(lote), "application/json"
    else:
        abort(404)
    return Response(
        conteudo,
        mimetype=tipo,
        headers={"Content-Disposition": f'attachment; filename="lote_ncm.{formato}"'},
    )


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


@app.post("/cesta/adicionar")
def cesta_adicionar():
    """Adiciona o resultado de uma consulta ja realizada a cesta do visitante."""
    tipo = request.form.get("tipo", "")
    token = request.form.get("token", "")
    cesta = cesta_do_visitante(criar=True)

    if tipo == "cnae":
        analise = ANALISES.get(token)
        if not analise:
            abort(404, "Análise expirada. Refaça o envio do cartão CNPJ.")
        mod_cesta.adicionar_cnae(cesta, analise["cartao"], analise["resultados"])
    elif tipo == "ncm":
        consulta = CONSULTAS_NCM.get(token)
        if not consulta:
            abort(404, "Consulta expirada. Refaça a busca do NCM.")
        mod_cesta.adicionar_ncm(cesta, consulta)
    elif tipo == "lote":
        lote = LOTES.get(token)
        if not lote:
            abort(404, "Lote expirado. Refaça a consulta em lote.")
        mod_cesta.adicionar_lote(cesta, lote)
    else:
        abort(400)

    return redirect(url_for("cesta_ver", incluido=1))


@app.get("/cesta")
def cesta_ver():
    cesta = cesta_do_visitante()
    return render_template(
        "cesta.html",
        cesta=cesta,
        resumo=mod_cesta.resumo(cesta) if cesta else None,
        incluido=request.args.get("incluido") == "1",
        colunas=mod_cesta.COLUNAS,
        previa=mod_cesta.linhas(cesta)[:40] if cesta else [],
    )


@app.post("/cesta/remover/<item_id>")
def cesta_remover(item_id: str):
    cesta = cesta_do_visitante()
    if cesta:
        mod_cesta.remover(cesta, item_id)
    return redirect(url_for("cesta_ver"))


@app.post("/cesta/limpar")
def cesta_limpar():
    cesta = cesta_do_visitante()
    if cesta:
        mod_cesta.limpar(cesta)
    return redirect(url_for("cesta_ver"))


@app.get("/cesta/download/<formato>")
def cesta_download(formato: str):
    cesta = cesta_do_visitante()
    if not cesta or not cesta["itens"]:
        abort(404, "A cesta está vazia.")
    if formato == "xlsx":
        conteudo = gerar_xlsx_cesta(cesta)
        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "csv":
        conteudo, tipo = gerar_csv_cesta(cesta), "text/csv; charset=utf-8"
    elif formato == "json":
        conteudo, tipo = gerar_json_cesta(cesta), "application/json"
    else:
        abort(404)
    return Response(
        conteudo,
        mimetype=tipo,
        headers={
            "Content-Disposition": f'attachment; filename="correlacao_consolidada.{formato}"'
        },
    )


@app.get("/apresentacao")
def apresentacao():
    """Relatorio de apresentacao da ferramenta (uso comercial/cliente)."""
    return render_template("apresentacao.html", est=base().estatisticas())


def main() -> None:
    """Execucao local. Em servidor use o wsgi.py (gunicorn/waitress)."""
    base()  # carrega datasets antes de subir o servidor
    app.run(
        host=os.environ.get("RTC_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT") or 5000),
        debug=False,
    )


if __name__ == "__main__":
    main()
