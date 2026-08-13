warning: in the working copy of '.claude/settings.local.json', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'README.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/dados.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/main.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/relatorio.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/static/estilo.css', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/templates/base.html', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/templates/ncm.html', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'app/templates/resultado.html', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/.claude/settings.local.json b/.claude/settings.local.json[m
[1mindex ab69253..41a88bb 100644[m
[1m--- a/.claude/settings.local.json[m
[1m+++ b/.claude/settings.local.json[m
[36m@@ -15,7 +15,8 @@[m
       "Bash(PYTHONIOENCODING=utf-8 python -c ' *)",[m
       "Bash(python scripts/atualizar_kb.py --checar)",[m
       "Bash(python scripts/atualizar_kb.py --checar --filtro nfe-rtc)",[m
[31m-      "Bash(python -)"[m
[32m+[m[32m      "Bash(python -)",[m
[32m+[m[32m      "Bash(PYTHONIOENCODING=utf-8 grep -n \"downloads\\\\|token\" app/templates/resultado.html)"[m
     ][m
   }[m
 }[m
[1mdiff --git a/README.md b/README.md[m
[1mindex a8721e6..90225e7 100644[m
[1m--- a/README.md[m
[1m+++ b/README.md[m
[36m@@ -55,7 +55,18 @@[m [mTelas:[m
 - **Análise do cartão CNPJ** — upload do PDF e correlação completa.[m
 - **Consulta por NCM** — CST, cClassTrib, redução e indOP do produto (com export).[m
 - **Consulta de tabelas** — busca por CNAE, item da LC 116, NBS, NCM, cClassTrib e indOP.[m
[32m+[m[32m- **Cesta** (`/cesta`) — acumula os resultados das consultas (cartão CNPJ e NCM) e gera **um[m
[32m+[m[32m  relatório consolidado**: as duas origens são convertidas para o mesmo conjunto de colunas,[m
[32m+[m[32m  com resumo por CST e cClassTrib, contagem de linhas por faixa de redução e destaque das[m
[32m+[m[32m  linhas que exigem conferência. Exporta XLSX (abas *Consolidado*, *Resumo*, *Consultas* e[m
[32m+[m[32m  *Fontes*), CSV e JSON. A cesta fica em memória, ligada a um cookie — nada de contribuinte[m
[32m+[m[32m  é gravado em disco.[m
 - **Fontes (KB)** — documentos usados, versão, data e SHA-256.[m
[32m+[m[32m- **Apresentação** (`/apresentacao`) — relatório para envio ao cliente: escopo, cobertura,[m
[32m+[m[32m  exemplos reais, critérios de confiança e fontes. Os números vêm dos datasets[m
[32m+[m[32m  (`Base.estatisticas()`), então a página nunca fica defasada; o botão *Imprimir / salvar PDF*[m
[32m+[m[32m  usa uma folha de estilo de impressão própria. Versão avulsa em[m
[32m+[m[32m  [`Docs/apresentacao.html`](Docs/apresentacao.html).[m
 [m
 ## Estrutura[m
 [m
[36m@@ -65,6 +76,7 @@[m [mapp/                aplicação Flask[m
   parser_cnpj.py    leitura do cartão CNPJ em PDF[m
   correlacao.py     motor de correlação por CNAE[m
   ncm.py            motor de consulta por NCM (anexos da LC 214/2025)[m
[32m+[m[32m  cesta.py          acúmulo das consultas e consolidação em colunas únicas[m
   relatorio.py      exportação XLSX / CSV / JSON[m
   main.py           rotas web[m
 scripts/[m
[1mdiff --git a/app/__pycache__/dados.cpython-314.pyc b/app/__pycache__/dados.cpython-314.pyc[m
[1mindex df07903..6047ebc 100644[m
Binary files a/app/__pycache__/dados.cpython-314.pyc and b/app/__pycache__/dados.cpython-314.pyc differ
[1mdiff --git a/app/__pycache__/main.cpython-314.pyc b/app/__pycache__/main.cpython-314.pyc[m
[1mindex 35572a4..58b1ab0 100644[m
Binary files a/app/__pycache__/main.cpython-314.pyc and b/app/__pycache__/main.cpython-314.pyc differ
[1mdiff --git a/app/__pycache__/relatorio.cpython-314.pyc b/app/__pycache__/relatorio.cpython-314.pyc[m
[1mindex 104ac67..419960c 100644[m
Binary files a/app/__pycache__/relatorio.cpython-314.pyc and b/app/__pycache__/relatorio.cpython-314.pyc differ
[1mdiff --git a/app/dados.py b/app/dados.py[m
[1mindex 3a8fa99..f7a44eb 100644[m
[1m--- a/app/dados.py[m
[1m+++ b/app/dados.py[m
[36m@@ -160,6 +160,30 @@[m [mclass Base:[m
     def versao_fontes(self) -> list[dict]:[m
         return self.manifesto.get("fontes", [])[m
 [m
[32m+[m[32m    def estatisticas(self) -> dict:[m
[32m+[m[32m        """Numeros de cobertura usados na pagina de apresentacao."""[m
[32m+[m[32m        return {[m
[32m+[m[32m            "ncm": len(self.ncm),[m
[32m+[m[32m            "ncm_vigentes": sum([m
[32m+[m[32m                1 for n in self.ncm if n.get("nivel") == 8 and n.get("vigente")[m
[32m+[m[32m            ),[m
[32m+[m[32m            "cnae": len(self.cnae),[m
[32m+[m[32m            "lc116": len(self.lc116),[m
[32m+[m[32m            "nbs": len(self.nbs),[m
[32m+[m[32m            "cclasstrib": len(self.cclasstrib),[m
[32m+[m[32m            "cst": len(self.cst),[m
[32m+[m[32m            "indop": len(self.indop),[m
[32m+[m[32m            "anexo_viii": len(self.anexo_viii),[m
[32m+[m[32m            "anexo_viii_itens": len({r["item"] for r in self.anexo_viii}),[m
[32m+[m[32m            "vinculos_cnae": len(self.cnae_lc116),[m
[32m+[m[32m            "cnaes_vinculados": len(self.itens_por_cnae),[m
[32m+[m[32m            "anexos_itens": len(self.lc214_anexos),[m
[32m+[m[32m            "anexos_ncm": sum(len(i["ncm_incluidos"]) for i in self.lc214_anexos),[m
[32m+[m[32m            "anexos_excecoes": sum(len(i["ncm_excecoes"]) for i in self.lc214_anexos),[m
[32m+[m[32m            "fontes": len(self.versao_fontes()),[m
[32m+[m[32m            "gerado_em": self.manifesto.get("gerado_em", "")[:10],[m
[32m+[m[32m        }[m
[32m+[m
 [m
 @lru_cache(maxsize=1)[m
 def base() -> Base:[m
[1mdiff --git a/app/main.py b/app/main.py[m
[1mindex c8b0f29..c751577 100644[m
[1m--- a/app/main.py[m
[1m+++ b/app/main.py[m
[36m@@ -10,18 +10,23 @@[m [mimport re[m
 import secrets[m
 from collections import OrderedDict[m
 [m
[31m-from flask import (Flask, Response, abort, render_template, request, url_for)[m
[32m+[m[32mfrom flask import (Flask, Response, abort, g, redirect, render_template, request,[m
[32m+[m[32m                   url_for)[m
 [m
[32m+[m[32mfrom . import cesta as mod_cesta[m
 from .correlacao import correlacionar, linhas_detalhe, resumo[m
 from .dados import base, normaliza[m
 from .ncm import consultar as consultar_ncm[m
 from .parser_cnpj import CartaoCNPJ, cnaes_de_texto_livre, ler_cartao, texto_do_pdf[m
[31m-from .relatorio import (gerar_csv, gerar_csv_ncm, gerar_json, gerar_json_ncm,[m
[31m-                        gerar_xlsx, gerar_xlsx_ncm)[m
[32m+[m[32mfrom .relatorio import (gerar_csv, gerar_csv_cesta, gerar_csv_ncm, gerar_json,[m
[32m+[m[32m                        gerar_json_cesta, gerar_json_ncm, gerar_xlsx,[m
[32m+[m[32m                        gerar_xlsx_cesta, gerar_xlsx_ncm)[m
 [m
 app = Flask(__name__)[m
 app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024[m
 [m
[32m+[m[32mCOOKIE_CESTA = "rtc_cesta"[m
[32m+[m
 # cache em memoria das ultimas analises (para download dos relatorios)[m
 ANALISES: "OrderedDict[str, dict]" = OrderedDict()[m
 CONSULTAS_NCM: "OrderedDict[str, dict]" = OrderedDict()[m
[36m@@ -36,6 +41,36 @@[m [mdef guardar(cartao: dict, resultados: list[dict]) -> str:[m
     return token[m
 [m
 [m
[32m+[m[32m# --------------------------------------------------------------------- cesta[m
[32m+[m
[32m+[m
[32m+[m[32mdef cesta_do_visitante(criar: bool = False) -> dict | None:[m
[32m+[m[32m    """Cesta ligada ao cookie do navegador; criada sob demanda."""[m
[32m+[m[32m    ident = getattr(g, "cesta_id", None) or request.cookies.get(COOKIE_CESTA)[m
[32m+[m[32m    cesta = mod_cesta.obter(ident)[m
[32m+[m[32m    if cesta is None and criar:[m
[32m+[m[32m        ident, cesta = mod_cesta.nova_cesta()[m
[32m+[m[32m        g.cesta_id = ident[m
[32m+[m[32m        g.cesta_nova = True[m
[32m+[m[32m    return cesta[m
[32m+[m
[32m+[m
[32m+[m[32m@app.after_request[m
[32m+[m[32mdef _grava_cookie_da_cesta(resposta):[m
[32m+[m[32m    if getattr(g, "cesta_nova", False):[m
[32m+[m[32m        resposta.set_cookie([m
[32m+[m[32m            COOKIE_CESTA, g.cesta_id, max_age=60 * 60 * 24 * 30,[m
[32m+[m[32m            httponly=True, samesite="Lax",[m
[32m+[m[32m        )[m
[32m+[m[32m    return resposta[m
[32m+[m
[32m+[m
[32m+[m[32m@app.context_processor[m
[32m+[m[32mdef _injeta_cesta():[m
[32m+[m[32m    cesta = cesta_do_visitante()[m
[32m+[m[32m    return {"cesta_qtd": len(cesta["itens"]) if cesta else 0}[m
[32m+[m
[32m+[m
 @app.route("/")[m
 def inicio():[m
     return render_template("index.html", manifesto=base().manifesto)[m
[36m@@ -240,6 +275,87 @@[m [mdef fontes():[m
     return render_template("fontes.html", manifesto=base().manifesto)[m
 [m
 [m
[32m+[m[32m@app.post("/cesta/adicionar")[m
[32m+[m[32mdef cesta_adicionar():[m
[32m+[m[32m    """Adiciona o resultado de uma consulta ja realizada a cesta do visitante."""[m
[32m+[m[32m    tipo = request.form.get("tipo", "")[m
[32m+[m[32m    token = request.form.get("token", "")[m
[32m+[m[32m    cesta = cesta_do_visitante(criar=True)[m
[32m+[m
[32m+[m[32m    if tipo == "cnae":[m
[32m+[m[32m        analise = ANALISES.get(token)[m
[32m+[m[32m        if not analise:[m
[32m+[m[32m            abort(404, "Análise expirada. Refaça o envio do cartão CNPJ.")[m
[32m+[m[32m        mod_cesta.adicionar_cnae(cesta, analise["cartao"], analise["resultados"])[m
[32m+[m[32m    elif tipo == "ncm":[m
[32m+[m[32m        consulta = CONSULTAS_NCM.get(token)[m
[32m+[m[32m        if not consulta:[m
[32m+[m[32m            abort(404, "Consulta expirada. Refaça a busca do NCM.")[m
[32m+[m[32m        mod_cesta.adicionar_ncm(cesta, consulta)[m
[32m+[m[32m    else:[m
[32m+[m[32m        abort(400)[m
[32m+[m
[32m+[m[32m    return redirect(url_for("cesta_ver", incluido=1))[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/cesta")[m
[32m+[m[32mdef cesta_ver():[m
[32m+[m[32m    cesta = cesta_do_visitante()[m
[32m+[m[32m    return render_template([m
[32m+[m[32m        "cesta.html",[m
[32m+[m[32m        cesta=cesta,[m
[32m+[m[32m        resumo=mod_cesta.resumo(cesta) if cesta else None,[m
[32m+[m[32m        incluido=request.args.get("incluido") == "1",[m
[32m+[m[32m        colunas=mod_cesta.COLUNAS,[m
[32m+[m[32m        previa=mod_cesta.linhas(cesta)[:40] if cesta else [],[m
[32m+[m[32m    )[m
[32m+[m
[32m+[m
[32m+[m[32m@app.post("/cesta/remover/<item_id>")[m
[32m+[m[32mdef cesta_remover(item_id: str):[m
[32m+[m[32m    cesta = cesta_do_visitante()[m
[32m+[m[32m    if cesta:[m
[32m+[m[32m        mod_cesta.remover(cesta, item_id)[m
[32m+[m[32m    return redirect(url_for("cesta_ver"))[m
[32m+[m
[32m+[m
[32m+[m[32m@app.post("/cesta/limpar")[m
[32m+[m[32mdef cesta_limpar():[m
[32m+[m[32m    cesta = cesta_do_visitante()[m
[32m+[m[32m    if cesta:[m
[32m+[m[32m        mod_cesta.limpar(cesta)[m
[32m+[m[32m    return redirect(url_for("cesta_ver"))[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/cesta/download/<formato>")[m
[32m+[m[32mdef cesta_download(formato: str):[m
[32m+[m[32m    cesta = cesta_do_visitante()[m
[32m+[m[32m    if not cesta or not cesta["itens"]:[m
[32m+[m[32m        abort(404, "A cesta está vazia.")[m
[32m+[m[32m    if formato == "xlsx":[m
[32m+[m[32m        conteudo = gerar_xlsx_cesta(cesta)[m
[32m+[m[32m        tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"[m
[32m+[m[32m    elif formato == "csv":[m
[32m+[m[32m        conteudo, tipo = gerar_csv_cesta(cesta), "text/csv; charset=utf-8"[m
[32m+[m[32m    elif formato == "json":[m
[32m+[m[32m        conteudo, tipo = gerar_json_cesta(cesta), "application/json"[m
[32m+[m[32m    else:[m
[32m+[m[32m        abort(404)[m
[32m+[m[32m    return Response([m
[32m+[m[32m        conteudo,[m
[32m+[m[32m        mimetype=tipo,[m
[32m+[m[32m        headers={[m
[32m+[m[32m            "Content-Disposition": f'attachment; filename="correlacao_consolidada.{formato}"'[m
[32m+[m[32m        },[m
[32m+[m[32m    )[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/apresentacao")[m
[32m+[m[32mdef apresentacao():[m
[32m+[m[32m    """Relatorio de apresentacao da ferramenta (uso comercial/cliente)."""[m
[32m+[m[32m    return render_template("apresentacao.html", est=base().estatisticas())[m
[32m+[m
[32m+[m
 def main() -> None:[m
     base()  # carrega datasets antes de subir o servidor[m
     app.run(host="127.0.0.1", port=5000, debug=False)[m
[1mdiff --git a/app/relatorio.py b/app/relatorio.py[m
[1mindex d2ecac4..54f4b63 100644[m
[1m--- a/app/relatorio.py[m
[1m+++ b/app/relatorio.py[m
[36m@@ -185,3 +185,131 @@[m [mdef gerar_json(cartao: dict, resultados: list[dict]) -> bytes:[m
         "fontes": base().versao_fontes(),[m
     }[m
     return json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")[m
[32m+[m
[32m+[m
[32m+[m[32m# ------------------------------------------------------------------ cesta[m
[32m+[m
[32m+[m[32mdef _aba_fontes(wb) -> None:[m
[32m+[m[32m    ws = wb.create_sheet("Fontes")[m
[32m+[m[32m    ws.append(["Arquivo (KB)", "Título", "Órgão", "Versão", "URL", "SHA-256", "Baixado em"])[m
[32m+[m[32m    for celula in ws[1]:[m
[32m+[m[32m        celula.font = Font(bold=True)[m
[32m+[m[32m        celula.fill = _CINZA[m
[32m+[m[32m    for fonte in base().versao_fontes():[m
[32m+[m[32m        ws.append([[m
[32m+[m[32m            fonte.get("arquivo", ""), fonte.get("titulo", ""), fonte.get("orgao", ""),[m
[32m+[m[32m            fonte.get("versao", ""), fonte.get("url", ""), fonte.get("sha256", "")[:16],[m
[32m+[m[32m            fonte.get("baixado_em", ""),[m
[32m+[m[32m        ])[m
[32m+[m[32m    _ajusta(ws, {1: 55, 2: 55, 3: 35, 4: 28, 5: 70, 6: 20, 7: 20})[m
[32m+[m
[32m+[m
[32m+[m[32mdef gerar_xlsx_cesta(cesta: dict) -> bytes:[m
[32m+[m[32m    """Planilha consolidada da cesta: linhas, resumo, consultas e fontes."""[m
[32m+[m[32m    from .cesta import COLUNAS, linhas as linhas_cesta, resumo as resumo_cesta[m
[32m+[m
[32m+[m[32m    wb = Workbook()[m
[32m+[m[32m    ws = wb.active[m
[32m+[m[32m    ws.title = "Consolidado"[m
[32m+[m[32m    ws.append(COLUNAS)[m
[32m+[m[32m    for celula in ws[1]:[m
[32m+[m[32m        celula.font = Font(bold=True, color="FFFFFF")[m
[32m+[m[32m        celula.fill = _AZUL[m
[32m+[m[32m        celula.alignment = Alignment(vertical="center", wrap_text=True)[m
[32m+[m[32m    for linha in linhas_cesta(cesta):[m
[32m+[m[32m        ws.append([linha.get(c, "") for c in COLUNAS])[m
[32m+[m[32m    ws.freeze_panes = "A2"[m
[32m+[m[32m    ws.auto_filter.ref = ws.dimensions[m
[32m+[m[32m    _ajusta(ws, {1: 26, 2: 16, 3: 14, 4: 45, 5: 14, 6: 15, 7: 45, 8: 22, 9: 12,[m
[32m+[m[32m                 10: 42, 11: 12, 12: 13, 13: 13, 14: 22, 15: 60, 16: 22, 17: 60})[m
[32m+[m
[32m+[m[32m    r = resumo_cesta(cesta)[m
[32m+[m[32m    wsr = wb.create_sheet("Resumo")[m
[32m+[m[32m    for chave, valor in [[m
[32m+[m[32m        ("Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")),[m
[32m+[m[32m        ("Cesta criada em", cesta.get("criada_em", "")),[m
[32m+[m[32m        ("", ""),[m
[32m+[m[32m        ("Consultas", r["consultas"]),[m
[32m+[m[32m        ("  cartão CNPJ / CNAE", r["consultas_cnae"]),[m
[32m+[m[32m        ("  NCM", r["consultas_ncm"]),[m
[32m+[m[32m        ("Linhas consolidadas", r["linhas"]),[m
[32m+[m[32m        ("Códigos distintos", r["codigos"]),[m
[32m+[m[32m        ("cClassTrib distintos", r["cclasstrib"]),[m
[32m+[m[32m        ("", ""),[m
[32m+[m[32m        ("Linhas com alíquota zero (redução 100%)", r["aliquota_zero"]),[m
[32m+[m[32m        ("Linhas com redução de 60%", r["reducao_60"]),[m
[32m+[m[32m        ("Linhas com redução de 30%", r["reducao_30"]),[m
[32m+[m[32m        ("Linhas de tributação integral (CST 000)", r["integral"]),[m
[32m+[m[32m        ("Linhas a validar (similaridade)", r["a_validar"]),[m
[32m+[m[32m        ("Linhas com Imposto Seletivo", r["imposto_seletivo"]),[m
[32m+[m[32m        ("Linhas em cláusula de exceção", r["excecoes"]),[m
[32m+[m[32m    ]:[m
[32m+[m[32m        wsr.append([chave, valor])[m
[32m+[m[32m    wsr.append([])[m
[32m+[m[32m    wsr.append(["CST", "Descrição", "Linhas"])[m
[32m+[m[32m    for celula in wsr[wsr.max_row]:[m
[32m+[m[32m        celula.font = Font(bold=True)[m
[32m+[m[32m        celula.fill = _CINZA[m
[32m+[m[32m    for grupo in r["top_cst"]:[m
[32m+[m[32m        wsr.append([grupo["cst"], grupo["descricao"], grupo["linhas"]])[m
[32m+[m[32m    wsr.append([])[m
[32m+[m[32m    wsr.append(["cClassTrib", "Nome", "Linhas"])[m
[32m+[m[32m    for celula in wsr[wsr.max_row]:[m
[32m+[m[32m        celula.font = Font(bold=True)[m
[32m+[m[32m        celula.fill = _CINZA[m
[32m+[m[32m    for grupo in r["top_cclasstrib"]:[m
[32m+[m[32m        wsr.append([grupo["cclasstrib"], grupo["nome"], grupo["linhas"]])[m
[32m+[m[32m    for linha in wsr.iter_rows(min_col=1, max_col=1):[m
[32m+[m[32m        if linha[0].value and str(linha[0].value)[0].isupper():[m
[32m+[m[32m            linha[0].font = Font(bold=True)[m
[32m+[m[32m    _ajusta(wsr, {1: 42, 2: 60, 3: 12})[m
[32m+[m
[32m+[m[32m    wsc = wb.create_sheet("Consultas")[m
[32m+[m[32m    wsc.append(["#", "Tipo", "Consulta", "Descrição", "Detalhe", "Adicionada em"])[m
[32m+[m[32m    for celula in wsc[1]:[m
[32m+[m[32m        celula.font = Font(bold=True)[m
[32m+[m[32m        celula.fill = _CINZA[m
[32m+[m[32m    for ordem, item in enumerate(cesta["itens"], start=1):[m
[32m+[m[32m        wsc.append([[m
[32m+[m[32m            ordem,[m
[32m+[m[32m            "Cartão CNPJ" if item["tipo"] == "cnae" else "NCM",[m
[32m+[m[32m            item["rotulo"], item["titulo"], item["detalhe"], item["adicionado_em"],[m
[32m+[m[32m        ])[m
[32m+[m[32m    _ajusta(wsc, {1: 5, 2: 14, 3: 26, 4: 55, 5: 30, 6: 18})[m
[32m+[m
[32m+[m[32m    _aba_fontes(wb)[m
[32m+[m
[32m+[m[32m    buffer = io.BytesIO()[m
[32m+[m[32m    wb.save(buffer)[m
[32m+[m[32m    return buffer.getvalue()[m
[32m+[m
[32m+[m
[32m+[m[32mdef gerar_csv_cesta(cesta: dict) -> bytes:[m
[32m+[m[32m    from .cesta import COLUNAS, linhas as linhas_cesta[m
[32m+[m
[32m+[m[32m    buffer = io.StringIO()[m
[32m+[m[32m    escritor = csv.DictWriter(buffer, fieldnames=COLUNAS, delimiter=";",[m
[32m+[m[32m                              extrasaction="ignore")[m
[32m+[m[32m    escritor.writeheader()[m
[32m+[m[32m    for linha in linhas_cesta(cesta):[m
[32m+[m[32m        escritor.writerow(linha)[m
[32m+[m[32m    return buffer.getvalue().encode("utf-8-sig")[m
[32m+[m
[32m+[m
[32m+[m[32mdef gerar_json_cesta(cesta: dict) -> bytes:[m
[32m+[m[32m    from .cesta import linhas as linhas_cesta, resumo as resumo_cesta[m
[32m+[m
[32m+[m[32m    payload = {[m
[32m+[m[32m        "gerado_em": datetime.now().isoformat(timespec="seconds"),[m
[32m+[m[32m        "cesta": {[m
[32m+[m[32m            "criada_em": cesta.get("criada_em", ""),[m
[32m+[m[32m            "consultas": [[m
[32m+[m[32m                {k: v for k, v in item.items() if k != "linhas"}[m
[32m+[m[32m                for item in cesta["itens"][m
[32m+[m[32m            ],[m
[32m+[m[32m        },[m
[32m+[m[32m        "resumo": resumo_cesta(cesta),[m
[32m+[m[32m        "linhas": linhas_cesta(cesta),[m
[32m+[m[32m        "fontes": base().versao_fontes(),[m
[32m+[m[32m    }[m
[32m+[m[32m    return json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")[m
[1mdiff --git a/app/static/estilo.css b/app/static/estilo.css[m
[1mindex 15a160f..29ddf7e 100644[m
[1m--- a/app/static/estilo.css[m
[1m+++ b/app/static/estilo.css[m
[36m@@ -129,3 +129,105 @@[m [mdetails summary { cursor: pointer; font-size: 13px; color: var(--azul-claro); }[m
 [m
 footer { border-top: 1px solid var(--borda); padding: 16px 28px; color: var(--suave); font-size: 12px; }[m
 .rodape-dados { color: var(--suave); font-size: 13px; }[m
[32m+[m
[32m+[m[32m/* ---------------------------------------------------- página de apresentação */[m
[32m+[m[32m.apresentacao { display: flex; flex-direction: column; gap: 26px; }[m
[32m+[m[32m.apresentacao .cartao { margin-bottom: 0; }  /* o espaçamento vem do gap */[m
[32m+[m[32m.apresentacao section { display: flex; flex-direction: column; gap: 12px; }[m
[32m+[m[32m.apresentacao h1 { font-size: 30px; line-height: 1.15; margin: 6px 0 10px; }[m
[32m+[m[32m.apresentacao h2 { font-size: 20px; margin: 2px 0 4px; }[m
[32m+[m[32m.apresentacao h3 { font-size: 16px; margin: 0 0 4px; }[m
[32m+[m[32m.apresentacao p { max-width: 78ch; }[m
[32m+[m[32m.apresentacao .eyebrow {[m
[32m+[m[32m  font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;[m
[32m+[m[32m  color: var(--azul-claro); margin: 0;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.apresentacao .capa { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap; }[m
[32m+[m[32m.apresentacao .linha-fina { font-size: 16px; color: var(--texto); max-width: 68ch; }[m
[32m+[m[32m.apresentacao .meta { display: flex; flex-wrap: wrap; gap: 6px 24px; margin-top: 12px; font-size: 13px; color: var(--suave); }[m
[32m+[m[32m.apresentacao .meta b { color: var(--texto); font-weight: 600; }[m
[32m+[m
[32m+[m[32m.apresentacao .trilhas { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }[m
[32m+[m[32m.apresentacao .trilha { margin: 0; }[m
[32m+[m[32m.apresentacao .cadeia { list-style: none; margin: 4px 0 6px; padding: 0; }[m
[32m+[m[32m.apresentacao .cadeia li { position: relative; padding: 8px 0 8px 20px; font-size: 14px; }[m
[32m+[m[32m.apresentacao .cadeia li::before {[m
[32m+[m[32m  content: ""; position: absolute; left: 3px; top: 15px;[m
[32m+[m[32m  width: 7px; height: 7px; border-radius: 50%; background: var(--azul-claro);[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .cadeia li:not(:last-child)::after {[m
[32m+[m[32m  content: ""; position: absolute; left: 6px; top: 22px; bottom: -1px; width: 1px; background: var(--borda);[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.apresentacao .casos { display: flex; flex-direction: column; gap: 14px; }[m
[32m+[m[32m.apresentacao .caso {[m
[32m+[m[32m  display: grid; grid-template-columns: minmax(180px, 230px) 1fr; gap: 18px 24px;[m
[32m+[m[32m  align-items: start; margin: 0;[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .caso .entrada { border-right: 1px solid var(--borda); padding-right: 20px; }[m
[32m+[m[32m.apresentacao .caso .rotulo {[m
[32m+[m[32m  display: block; font-size: 11px; letter-spacing: .1em; text-transform: uppercase;[m
[32m+[m[32m  color: var(--suave); font-weight: 700;[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .caso .valor {[m
[32m+[m[32m  display: block; font-family: Consolas, ui-monospace, monospace; font-size: 17px;[m
[32m+[m[32m  margin: 4px 0 6px; font-variant-numeric: tabular-nums;[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .caso .descr { display: block; font-size: 13px; color: var(--suave); }[m
[32m+[m[32m.apresentacao .caso dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; }[m
[32m+[m[32m.apresentacao .caso dt {[m
[32m+[m[32m  font-size: 11px; letter-spacing: .07em; text-transform: uppercase; color: var(--suave);[m
[32m+[m[32m  font-weight: 700; padding-top: 3px;[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .caso dd { margin: 0; font-size: 14px; }[m
[32m+[m
[32m+[m[32m.apresentacao .grade-fontes { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }[m
[32m+[m[32m.apresentacao .fonte { margin: 0; display: flex; flex-direction: column; gap: 6px; }[m
[32m+[m[32m.apresentacao .fonte .org {[m
[32m+[m[32m  font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--azul-claro); font-weight: 700;[m
[32m+[m[32m}[m
[32m+[m[32m.apresentacao .fonte p { font-size: 13.5px; }[m
[32m+[m
[32m+[m[32m.apresentacao ul.limpa { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 10px; }[m
[32m+[m[32m.apresentacao ul.limpa li { font-size: 14.5px; }[m
[32m+[m
[32m+[m[32m@media (max-width: 640px) {[m
[32m+[m[32m  .apresentacao .caso { grid-template-columns: 1fr; }[m
[32m+[m[32m  .apresentacao .caso .entrada { border-right: 0; border-bottom: 1px solid var(--borda); padding: 0 0 12px; }[m
[32m+[m[32m  .apresentacao .caso dl { grid-template-columns: 1fr; gap: 2px; }[m
[32m+[m[32m  .apresentacao .caso dt { padding-top: 8px; }[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m@media print {[m
[32m+[m[32m  .topo, footer, .acoes-impressao { display: none !important; }[m
[32m+[m[32m  body { background: #fff; font-size: 11pt; }[m
[32m+[m[32m  main { max-width: none; margin: 0; padding: 0; }[m
[32m+[m[32m  .apresentacao .cartao, .apresentacao .fonte, .apresentacao .caso {[m
[32m+[m[32m    border: 1px solid #c9ced8; break-inside: avoid; box-shadow: none;[m
[32m+[m[32m  }[m
[32m+[m[32m  .apresentacao section { break-inside: avoid; }[m
[32m+[m[32m  .apresentacao h1 { font-size: 22pt; }[m
[32m+[m[32m  .apresentacao h2 { font-size: 14pt; }[m
[32m+[m[32m  a { color: inherit; text-decoration: none; }[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m/* ------------------------------------------------------------------- cesta */[m
[32m+[m[32m.botao.secundario { background: #fff; color: var(--azul-claro); border: 1px solid var(--azul-claro); }[m
[32m+[m[32m.botao.secundario:hover { background: var(--azul-claro); color: #fff; }[m
[32m+[m[32m.downloads form { margin: 0; }[m
[32m+[m
[32m+[m[32m.link-cesta .contador {[m
[32m+[m[32m  display: inline-block; background: #fff; color: var(--azul);[m
[32m+[m[32m  border-radius: 999px; padding: 0 7px; font-size: 12px; font-weight: 700; margin-left: 2px;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.link-remover {[m
[32m+[m[32m  background: none; border: 0; padding: 0; color: var(--vermelho);[m
[32m+[m[32m  font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: underline;[m
[32m+[m[32m}[m
[32m+[m[32m.link-remover:hover { background: none; color: var(--vermelho); opacity: .8; }[m
[32m+[m[32m.acao-limpar { margin-top: 12px; }[m
[32m+[m
[32m+[m[32m.rolagem { overflow-x: auto; }[m
[32m+[m[32m.rolagem table { min-width: 900px; }[m
[1mdiff --git a/app/templates/base.html b/app/templates/base.html[m
[1mindex 4362d78..4ff2cbd 100644[m
[1m--- a/app/templates/base.html[m
[1m+++ b/app/templates/base.html[m
[36m@@ -20,6 +20,10 @@[m
       <a href="{{ url_for('ncm_busca') }}">Consulta por NCM</a>[m
       <a href="{{ url_for('consulta') }}">Consulta de tabelas</a>[m
       <a href="{{ url_for('fontes') }}">Fontes (KB)</a>[m
[32m+[m[32m      <a href="{{ url_for('apresentacao') }}">Apresentação</a>[m
[32m+[m[32m      <a href="{{ url_for('cesta_ver') }}" class="link-cesta">[m
[32m+[m[32m        Cesta{% if cesta_qtd %} <span class="contador">{{ cesta_qtd }}</span>{% endif %}[m
[32m+[m[32m      </a>[m
     </nav>[m
   </header>[m
 [m
[1mdiff --git a/app/templates/ncm.html b/app/templates/ncm.html[m
[1mindex ea0787d..ebe387e 100644[m
[1m--- a/app/templates/ncm.html[m
[1m+++ b/app/templates/ncm.html[m
[36m@@ -14,6 +14,11 @@[m
     <p class="ajuda">{{ c.descricao }}</p>[m
   </div>[m
   <div class="downloads">[m
[32m+[m[32m    <form method="post" action="{{ url_for('cesta_adicionar') }}">[m
[32m+[m[32m      <input type="hidden" name="tipo" value="ncm">[m
[32m+[m[32m      <input type="hidden" name="token" value="{{ token }}">[m
[32m+[m[32m      <button type="submit" class="botao secundario">+ Adicionar à cesta</button>[m
[32m+[m[32m    </form>[m
     <a class="botao" href="{{ url_for('download_ncm', token=token, formato='xlsx') }}">XLSX</a>[m
     <a class="botao" href="{{ url_for('download_ncm', token=token, formato='csv') }}">CSV</a>[m
     <a class="botao" href="{{ url_for('download_ncm', token=token, formato='json') }}">JSON</a>[m
[1mdiff --git a/app/templates/resultado.html b/app/templates/resultado.html[m
[1mindex 066fbfa..ae7a02c 100644[m
[1m--- a/app/templates/resultado.html[m
[1m+++ b/app/templates/resultado.html[m
[36m@@ -13,6 +13,11 @@[m
     </p>[m
   </div>[m
   <div class="downloads">[m
[32m+[m[32m    <form method="post" action="{{ url_for('cesta_adicionar') }}">[m
[32m+[m[32m      <input type="hidden" name="tipo" value="cnae">[m
[32m+[m[32m      <input type="hidden" name="token" value="{{ token }}">[m
[32m+[m[32m      <button type="submit" class="botao secundario">+ Adicionar à cesta</button>[m
[32m+[m[32m    </form>[m
     <a class="botao" href="{{ url_for('download', token=token, formato='xlsx') }}">XLSX</a>[m
     <a class="botao" href="{{ url_for('download', token=token, formato='csv') }}">CSV</a>[m
     <a class="botao" href="{{ url_for('download', token=token, formato='json') }}">JSON</a>[m
[1mdiff --git a/tests/__pycache__/test_ferramenta.cpython-314.pyc b/tests/__pycache__/test_ferramenta.cpython-314.pyc[m
[1mindex 086d975..f55305a 100644[m
Binary files a/tests/__pycache__/test_ferramenta.cpython-314.pyc and b/tests/__pycache__/test_ferramenta.cpython-314.pyc differ
[1mdiff --git a/tests/test_ferramenta.py b/tests/test_ferramenta.py[m
[1mindex ffa7d08..faaa486 100644[m
[1m--- a/tests/test_ferramenta.py[m
[1m+++ b/tests/test_ferramenta.py[m
[36m@@ -5,12 +5,15 @@[m [mExecucao:  python -m unittest discover -s tests -v[m
 [m
 from __future__ import annotations[m
 [m
[32m+[m[32mimport json[m
[32m+[m[32mimport re[m
 import sys[m
 import unittest[m
 from pathlib import Path[m
 [m
 sys.path.insert(0, str(Path(__file__).resolve().parents[1]))[m
 [m
[32m+[m[32mfrom app.cesta import COLUNAS  # noqa: E402[m
 from app.correlacao import correlacionar, linhas_detalhe, resumo  # noqa: E402[m
 from app.dados import base  # noqa: E402[m
 from app.main import app  # noqa: E402[m
[36m@@ -242,6 +245,96 @@[m [mclass TestApp(unittest.TestCase):[m
         self.assertEqual(self.cliente.get("/fontes").status_code, 200)[m
         self.assertEqual(self.cliente.get("/cnae/6201501").status_code, 200)[m
 [m
[32m+[m[32m    def test_apresentacao_usa_numeros_dos_datasets(self):[m
[32m+[m[32m        resposta = self.cliente.get("/apresentacao")[m
[32m+[m[32m        self.assertEqual(resposta.status_code, 200)[m
[32m+[m[32m        corpo = resposta.get_data(as_text=True)[m
[32m+[m[32m        est = base().estatisticas()[m
[32m+[m[32m        # os numeros da pagina vem dos datasets, nao do texto fixo[m
[32m+[m[32m        self.assertIn(f"{est['ncm']:,}".replace(",", "."), corpo)[m
[32m+[m[32m        self.assertIn(str(est["cclasstrib"]), corpo)[m
[32m+[m[32m        self.assertIn(f"{est['fontes']} documentos", corpo)[m
[32m+[m[32m        # a apresentacao fica acessivel pelo menu de todas as telas[m
[32m+[m[32m        self.assertIn("/apresentacao", self.cliente.get("/").get_data(as_text=True))[m
[32m+[m
[32m+[m
[32m+[m[32mclass TestCesta(unittest.TestCase):[m
[32m+[m[32m    """Rotina que acumula consultas e gera o relatorio consolidado."""[m
[32m+[m
[32m+[m[32m    def setUp(self) -> None:[m
[32m+[m[32m        app.config["TESTING"] = True[m
[32m+[m[32m        self.cliente = app.test_client()[m
[32m+[m
[32m+[m[32m    def _token_cnae(self, cnaes: str) -> str:[m
[32m+[m[32m        corpo = self.cliente.post("/analisar", data={"cnaes": cnaes}).get_data(as_text=True)[m
[32m+[m[32m        return corpo.split("/download/")[1].split("/")[0][m
[32m+[m
[32m+[m[32m    def _token_ncm(self, codigo: str) -> str:[m
[32m+[m[32m        corpo = self.cliente.get(f"/ncm/{codigo}").get_data(as_text=True)[m
[32m+[m[32m        return corpo.split("/download-ncm/")[1].split("/")[0][m
[32m+[m
[32m+[m[32m    def _adicionar(self, tipo: str, token: str):[m
[32m+[m[32m        return self.cliente.post([m
[32m+[m[32m            "/cesta/adicionar", data={"tipo": tipo, "token": token}, follow_redirects=True[m
[32m+[m[32m        )[m
[32m+[m
[32m+[m[32m    def test_cesta_vazia(self):[m
[32m+[m[32m        resposta = self.cliente.get("/cesta")[m
[32m+[m[32m        self.assertEqual(resposta.status_code, 200)[m
[32m+[m[32m        self.assertIn("Ainda não há consultas", resposta.get_data(as_text=True))[m
[32m+[m[32m        self.assertEqual(self.cliente.get("/cesta/download/xlsx").status_code, 404)[m
[32m+[m
[32m+[m[32m    def test_acumula_cnae_e_ncm_no_mesmo_relatorio(self):[m
[32m+[m[32m        self.assertEqual(self._adicionar("cnae", self._token_cnae("8630-5/01")).status_code, 200)[m
[32m+[m[32m        self.assertEqual(self._adicionar("ncm", self._token_ncm("10064000")).status_code, 200)[m
[32m+[m
[32m+[m[32m        payload = json.loads(self.cliente.get("/cesta/download/json").data)[m
[32m+[m[32m        self.assertEqual(payload["resumo"]["consultas"], 2)[m
[32m+[m[32m        self.assertEqual(payload["resumo"]["consultas_cnae"], 1)[m
[32m+[m[32m        self.assertEqual(payload["resumo"]["consultas_ncm"], 1)[m
[32m+[m[32m        self.assertGreater(payload["resumo"]["linhas"], 1)[m
[32m+[m
[32m+[m[32m        tipos = {linha["Tipo"] for linha in payload["linhas"]}[m
[32m+[m[32m        self.assertIn("Serviço (CNAE)", tipos)[m
[32m+[m[32m        self.assertIn("Bem (NCM)", tipos)[m
[32m+[m[32m        # as duas origens compartilham o mesmo conjunto de colunas[m
[32m+[m[32m        for linha in payload["linhas"]:[m
[32m+[m[32m            self.assertEqual(list(linha.keys()), COLUNAS)[m
[32m+[m
[32m+[m[32m        # o arroz do Anexo I entra como aliquota zero no consolidado[m
[32m+[m[32m        arroz = [l for l in payload["linhas"] if l["Código"] == "1006.40.00"][m
[32m+[m[32m        self.assertTrue(any(l["cClassTrib"] == "200003" for l in arroz))[m
[32m+[m[32m        self.assertTrue(any(l["Redução IBS (%)"] == "100" for l in arroz))[m
[32m+[m[32m        self.assertTrue(all(l["NBS"] == "Não aplicável" for l in arroz))[m
[32m+[m
[32m+[m[32m    def test_contador_no_menu_e_formatos(self):[m
[32m+[m[32m        self._adicionar("ncm", self._token_ncm("10064000"))[m
[32m+[m[32m        self.assertIn('class="contador"', self.cliente.get("/").get_data(as_text=True))[m
[32m+[m[32m        for formato, assinatura in (("xlsx", b"PK"), ("csv", b"Consulta"), ("json", b"{")):[m
[32m+[m[32m            resposta = self.cliente.get(f"/cesta/download/{formato}")[m
[32m+[m[32m            self.assertEqual(resposta.status_code, 200, formato)[m
[32m+[m[32m            inicio = resposta.data[:16].lstrip(b"\xef\xbb\xbf")[m
[32m+[m[32m            self.assertTrue(inicio.startswith(assinatura), f"{formato}: {inicio!r}")[m
[32m+[m
[32m+[m[32m    def test_remover_e_limpar(self):[m
[32m+[m[32m        self._adicionar("ncm", self._token_ncm("10064000"))[m
[32m+[m[32m        self._adicionar("ncm", self._token_ncm("30049099"))[m
[32m+[m[32m        pagina = self.cliente.get("/cesta").get_data(as_text=True)[m
[32m+[m[32m        item = re.search(r"/cesta/remover/([\w-]+)", pagina).group(1)[m
[32m+[m
[32m+[m[32m        self.cliente.post(f"/cesta/remover/{item}", follow_redirects=True)[m
[32m+[m[32m        payload = json.loads(self.cliente.get("/cesta/download/json").data)[m
[32m+[m[32m        self.assertEqual(payload["resumo"]["consultas"], 1)[m
[32m+[m
[32m+[m[32m        self.cliente.post("/cesta/limpar", follow_redirects=True)[m
[32m+[m[32m        self.assertEqual(self.cliente.get("/cesta/download/json").status_code, 404)[m
[32m+[m
[32m+[m[32m    def test_token_expirado_nao_entra_na_cesta(self):[m
[32m+[m[32m        self.assertEqual([m
[32m+[m[32m            self.cliente.post("/cesta/adicionar", data={"tipo": "ncm", "token": "xxx"}).status_code,[m
[32m+[m[32m            404,[m
[32m+[m[32m        )[m
[32m+[m
 [m
 if __name__ == "__main__":[m
     unittest.main()[m
