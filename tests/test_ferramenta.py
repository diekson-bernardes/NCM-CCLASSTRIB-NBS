"""Testes da leitura do cartao CNPJ e do motor de correlacao.

Execucao:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import io
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# a cota dos testes vive num arquivo temporario, fora de var/uso.json
import os, tempfile  # noqa: E402
_TEMP = Path(tempfile.mkdtemp())
os.environ.setdefault("RTC_ARQUIVO_USO", str(_TEMP / "uso_teste.json"))
os.environ.setdefault("RTC_ARQUIVO_USUARIOS", str(_TEMP / "usuarios_teste.json"))

from app import auth, lote  # noqa: E402
from app.cesta import COLUNAS  # noqa: E402
from app.correlacao import correlacionar, linhas_detalhe, resumo  # noqa: E402
from app.dados import base  # noqa: E402
from app.main import app  # noqa: E402
from app.ncm import consultar as consultar_ncm  # noqa: E402
from app.parser_cnpj import cnaes_de_texto_livre, ler_cartao  # noqa: E402

CARTAO_EXEMPLO = """
REPÚBLICA FEDERATIVA DO BRASIL
CADASTRO NACIONAL DA PESSOA JURÍDICA
NÚMERO DE INSCRIÇÃO
11.222.333/0001-81
MATRIZ
COMPROVANTE DE INSCRIÇÃO E DE SITUAÇÃO CADASTRAL
DATA DE ABERTURA
15/03/2010
NOME EMPRESARIAL
EMPRESA MODELO DE TECNOLOGIA LTDA
TÍTULO DO ESTABELECIMENTO (NOME DE FANTASIA)
MODELO TECH
PORTE
EPP
CÓDIGO E DESCRIÇÃO DA ATIVIDADE ECONÔMICA PRINCIPAL
62.01-5-01 - Desenvolvimento de programas de computador sob encomenda
CÓDIGO E DESCRIÇÃO DAS ATIVIDADES ECONÔMICAS SECUNDÁRIAS
62.09-1-00 - Suporte técnico, manutenção e outros serviços em tecnologia da
informação
47.51-2-01 - Comércio varejista especializado de equipamentos e suprimentos de
informática
CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA
206-2 - Sociedade Empresária Limitada
LOGRADOURO
AV EXEMPLO
MUNICÍPIO
GOIANIA
UF
GO
SITUAÇÃO CADASTRAL
ATIVA
"""


def cliente_logado(login: str = "admin", senha: str = "2026"):
    """Cliente de teste ja autenticado - o site exige login em todas as telas."""
    app.config["TESTING"] = True
    cliente = app.test_client()
    cliente.post("/entrar", data={"login": login, "senha": senha})
    return cliente


class TestLeituraCartao(unittest.TestCase):
    def setUp(self) -> None:
        self.cartao = ler_cartao(CARTAO_EXEMPLO)

    def test_identificacao(self):
        self.assertEqual(self.cartao.cnpj, "11.222.333/0001-81")
        self.assertEqual(self.cartao.nome_empresarial, "EMPRESA MODELO DE TECNOLOGIA LTDA")
        self.assertEqual(self.cartao.nome_fantasia, "MODELO TECH")
        self.assertEqual(self.cartao.matriz_filial, "MATRIZ")
        self.assertEqual(self.cartao.uf, "GO")

    def test_atividades(self):
        codigos = [a.cnae for a in self.cartao.atividades]
        self.assertEqual(codigos[0], "6201501")
        self.assertIn("6209100", codigos)
        self.assertIn("4751201", codigos)
        self.assertTrue(self.cartao.atividades[0].principal)
        self.assertFalse(self.cartao.atividades[1].principal)

    def test_cnpj_nao_vira_cnae(self):
        self.assertNotIn("1122233", [a.cnae for a in self.cartao.atividades])

    def test_entrada_manual(self):
        atividades = cnaes_de_texto_livre("62.01-5-01\n6202-3/00; 4711302")
        self.assertEqual([a.cnae for a in atividades], ["6201501", "6202300", "4711302"])


class TestCorrelacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cartao = ler_cartao(CARTAO_EXEMPLO)
        cls.resultados = correlacionar(cls.cartao.atividades)

    def test_servico_com_vinculo_oficial(self):
        ti = next(r for r in self.resultados if r["cnae"] == "6201501")
        self.assertEqual(ti["natureza"], "servico")
        itens = {i["item"] for i in ti["itens"]}
        self.assertIn("01.01", itens)
        item = next(i for i in ti["itens"] if i["item"] == "01.01")
        self.assertEqual(item["confianca"], "alta")
        variante = item["variantes"][0]
        self.assertTrue(variante["nbs"])
        self.assertTrue(variante["codigos_indop"])
        for codigo in variante["codigos_indop"]:
            self.assertRegex(codigo, r"^\d{6}$")
        self.assertTrue(all(i["tipo_operacao"] for i in variante["indops"]))
        self.assertRegex(variante["cclasstrib"], r"^\d{6}$")
        self.assertTrue(variante["cclasstrib_info"]["nome"])

    def test_item_com_multiplos_indop(self):
        """04.01 (medicina) admite atendimento presencial, nao presencial e a distancia."""
        variantes = base().anexo_por_item["04.01"]
        self.assertTrue(any(len(v["indops"]) > 1 for v in variantes))

    def test_comercio_vira_trilha_de_bens(self):
        comercio = next(r for r in self.resultados if r["cnae"] == "4751201")
        self.assertEqual(comercio["natureza"], "bens")
        self.assertTrue(comercio["bens"]["aplicavel"])
        self.assertIn("Não aplicável", comercio["bens"]["nbs"])
        self.assertEqual(comercio["bens"]["cclasstrib_padrao"]["cclasstrib"], "000001")
        self.assertTrue(comercio["bens"]["indops"])
        self.assertTrue(comercio["alertas"])

    def test_linhas_e_resumo(self):
        linhas = linhas_detalhe(self.resultados)
        self.assertTrue(linhas)
        obrigatorias = {"CNAE", "Item LC 116/03", "NBS", "indOP", "cClassTrib"}
        self.assertTrue(obrigatorias.issubset(linhas[0].keys()))
        r = resumo(self.resultados)
        self.assertEqual(r["cnaes"], 3)
        self.assertGreaterEqual(r["bens"], 1)

    def test_similaridade_gera_sugestao(self):
        from app.parser_cnpj import Atividade

        # CNAE de servico sem vinculo municipal conhecido
        alvo = next(
            (c["cnae"] for c in base().cnae
             if c["secao"] not in {"A", "B", "C", "G"}
             and c["cnae"] not in base().itens_por_cnae),
            None,
        )
        self.assertIsNotNone(alvo)
        registro = base().por_cnae[alvo]
        r = correlacionar([Atividade(alvo, registro["descricao"], True)])[0]
        self.assertIn(r["natureza"], {"servico_sugerido"})
        for item in r["itens"]:
            self.assertIn(item["confianca"], {"media", "baixa"})


class TestConsultaNCM(unittest.TestCase):
    def test_ncm_da_cesta_basica(self):
        """Arroz do Anexo I: aliquota zero via cClassTrib 200003."""
        r = consultar_ncm("1006.40.00")
        self.assertIsNotNone(r)
        self.assertEqual(r["ncm"], "10064000")
        self.assertTrue(r["vigente"])
        anexos = {x["anexo"] for x in r["regimes"]}
        self.assertIn("I", anexos)
        codigos = {c["cclasstrib"] for x in r["regimes"] for c in x["cclasstrib"]}
        self.assertIn("200003", codigos)
        self.assertEqual(r["padrao"]["cclasstrib"], "000001")
        self.assertTrue(r["indops"])

    def test_ncm_sem_regime_diferenciado(self):
        r = consultar_ncm("84713012")  # notebooks
        self.assertIsNotNone(r)
        self.assertEqual(r["regimes"], [])
        self.assertEqual(r["padrao"]["cst"], "000")

    def test_ncm_do_imposto_seletivo(self):
        r = consultar_ncm("87032310")  # automovel de passageiros
        self.assertTrue(r["regimes_seletivo"])
        self.assertTrue(any("Seletivo" in a for a in r["alertas"]))

    def test_excecao_expressa_do_anexo(self):
        """9018.11.00 entra pelo item 1.1 do Anexo XII e e excluido do item 1.3."""
        r = consultar_ncm("90181100")
        self.assertTrue(any(x["item"] == "1.1" for x in r["regimes"]))
        self.assertTrue(any(x["item"] == "1.3" for x in r["regimes_excluidos"]))

    def test_hierarquia_e_codigo_inexistente(self):
        r = consultar_ncm("1006")
        self.assertTrue(r["hierarquia"])
        self.assertTrue(any("8 dígitos" in a for a in r["alertas"]))
        self.assertIsNone(consultar_ncm("abc"))

    def test_linhas_para_exportacao(self):
        from app.ncm import linhas_detalhe as linhas_ncm

        linhas = linhas_ncm(consultar_ncm("04011010"))
        self.assertTrue(linhas)
        obrigatorias = {"NCM", "cClassTrib", "CST IBS/CBS", "indOP aplicáveis"}
        self.assertTrue(obrigatorias.issubset(linhas[0].keys()))
        self.assertTrue(any(l["cClassTrib"] == "200003" for l in linhas))


class TestApp(unittest.TestCase):
    def setUp(self) -> None:
        self.cliente = cliente_logado()

    def test_pagina_inicial(self):
        self.assertEqual(self.cliente.get("/").status_code, 200)

    def test_fluxo_manual_e_downloads(self):
        resposta = self.cliente.post("/analisar", data={"cnaes": "62.01-5-01\n4751-2/01"})
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.get_data(as_text=True)
        self.assertIn("6201-5/01", corpo)
        self.assertIn("cClassTrib", corpo)

        token = corpo.split("/download/")[1].split("/")[0]
        for formato, assinatura in (("xlsx", b"PK"), ("csv", b"CNAE"), ("json", b"{")):
            arq = self.cliente.get(f"/download/{token}/{formato}")
            self.assertEqual(arq.status_code, 200, formato)
            inicio = arq.data[:16].lstrip(b"\xef\xbb\xbf")
            self.assertTrue(inicio.startswith(assinatura), f"{formato}: {inicio!r}")

    def test_analise_sem_dados(self):
        self.assertEqual(self.cliente.post("/analisar", data={"cnaes": ""}).status_code, 400)

    def test_rotas_de_ncm(self):
        self.assertEqual(self.cliente.get("/ncm").status_code, 200)

        lista = self.cliente.get("/ncm?q=arroz")
        self.assertEqual(lista.status_code, 200)
        self.assertIn("10.06", lista.get_data(as_text=True))

        detalhe = self.cliente.get("/ncm?q=1006.40.00")
        corpo = detalhe.get_data(as_text=True)
        self.assertEqual(detalhe.status_code, 200)
        self.assertIn("200003", corpo)
        self.assertIn("010101", corpo)

        token = corpo.split("/download-ncm/")[1].split("/")[0]
        for formato, assinatura in (("xlsx", b"PK"), ("csv", b"NCM"), ("json", b"{")):
            arq = self.cliente.get(f"/download-ncm/{token}/{formato}")
            self.assertEqual(arq.status_code, 200, formato)
            inicio = arq.data[:16].lstrip(b"\xef\xbb\xbf")
            self.assertTrue(inicio.startswith(assinatura), f"{formato}: {inicio!r}")

        self.assertEqual(self.cliente.get("/ncm/99999999").status_code, 404)
        self.assertEqual(self.cliente.get("/consulta?tipo=ncm&q=arroz").status_code, 200)

    def test_consulta_e_fontes(self):
        self.assertEqual(self.cliente.get("/consulta?tipo=nbs&q=hospedagem").status_code, 200)
        self.assertEqual(self.cliente.get("/fontes").status_code, 200)
        self.assertEqual(self.cliente.get("/cnae/6201501").status_code, 200)

    def test_apresentacao_usa_numeros_dos_datasets(self):
        resposta = self.cliente.get("/apresentacao")
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.get_data(as_text=True)
        est = base().estatisticas()
        # os numeros da pagina vem dos datasets, nao do texto fixo
        self.assertIn(f"{est['ncm']:,}".replace(",", "."), corpo)
        self.assertIn(str(est["cclasstrib"]), corpo)
        self.assertIn(f"{est['fontes']} documentos", corpo)
        # a apresentacao fica acessivel pelo menu de todas as telas
        self.assertIn("/apresentacao", self.cliente.get("/").get_data(as_text=True))


class TestAcesso(unittest.TestCase):
    """Login, papeis e cota de consultas."""

    def setUp(self) -> None:
        app.config["TESTING"] = True
        self.cliente = app.test_client()
        auth.zerar()

    def tearDown(self) -> None:
        auth.zerar()

    def test_sem_login_redireciona_guardando_o_destino(self):
        resposta = self.cliente.get("/ncm")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/entrar", resposta.headers["Location"])
        self.assertIn("proxima", resposta.headers["Location"])
        self.assertEqual(self.cliente.get("/entrar").status_code, 200)

    def test_credenciais(self):
        self.assertIsNone(auth.autenticar("admin", "senha errada"))
        self.assertIsNone(auth.autenticar("inexistente", "2026"))
        for login, senha, papel in (
            ("admin", "2026", "administrador"),
            ("Teste", "123", "teste"),
            ("Cliente", "Cliente", "cliente"),
        ):
            usuario = auth.autenticar(login, senha)
            self.assertIsNotNone(usuario, login)
            self.assertEqual(usuario["papel"], papel)
        # o login nao diferencia maiusculas, a senha sim
        self.assertIsNotNone(auth.autenticar("ADMIN", "2026"))
        self.assertIsNone(auth.autenticar("admin", "2026 "))

    def test_senha_invalida_na_tela(self):
        resposta = self.cliente.post("/entrar", data={"login": "admin", "senha": "x"})
        self.assertEqual(resposta.status_code, 401)
        self.assertIn("inválidos", resposta.get_data(as_text=True))

    def test_painel_de_usuarios_e_do_administrador(self):
        self.assertEqual(cliente_logado("admin", "2026").get("/usuarios").status_code, 200)
        self.assertEqual(cliente_logado("Cliente", "Cliente").get("/usuarios").status_code, 403)
        self.assertEqual(cliente_logado("Teste", "123").get("/usuarios").status_code, 403)

    def test_usuarios_sem_limite(self):
        for login, senha in (("admin", "2026"), ("Cliente", "Cliente")):
            cliente = cliente_logado(login, senha)
            for _ in range(12):
                self.assertEqual(cliente.get("/ncm/10064000").status_code, 200)
            self.assertIsNone(auth.restante(login))

    def test_usuario_teste_para_na_decima_consulta(self):
        cliente = cliente_logado("Teste", "123")
        for numero in range(1, 11):
            self.assertEqual(cliente.get("/ncm/10064000").status_code, 200, numero)
            self.assertEqual(auth.restante("Teste"), 10 - numero)

        bloqueada = cliente.get("/ncm/10064000")
        self.assertEqual(bloqueada.status_code, 403)
        self.assertIn("Limite de consultas", bloqueada.get_data(as_text=True))
        self.assertEqual(cliente.post("/analisar", data={"cnaes": "6201-5/01"}).status_code, 403)

        # navegar, buscar e ver a cesta continuam liberados
        for rota in ("/", "/consulta?tipo=nbs&q=hospedagem", "/cesta", "/fontes"):
            self.assertEqual(cliente.get(rota).status_code, 200, rota)

    def test_consulta_que_falha_nao_consome_cota(self):
        cliente = cliente_logado("Teste", "123")
        self.assertEqual(cliente.post("/ncm/lote", data={"ncms": "nada aqui"}).status_code, 400)
        self.assertEqual(auth.restante("Teste"), 10)

    def test_administrador_zera_a_contagem(self):
        cliente_logado("Teste", "123").get("/ncm/10064000")
        self.assertEqual(auth.consumo("Teste"), 1)
        admin = cliente_logado("admin", "2026")
        self.assertEqual(admin.post("/usuarios/zerar/Teste", follow_redirects=True).status_code, 200)
        self.assertEqual(auth.consumo("Teste"), 0)

    def test_sair_encerra_a_sessao(self):
        cliente = cliente_logado("Cliente", "Cliente")
        self.assertEqual(cliente.get("/").status_code, 200)
        cliente.get("/sair")
        self.assertEqual(cliente.get("/").status_code, 302)


class TestGestaoDeUsuarios(unittest.TestCase):
    """Criacao de usuarios pelo administrador, com cota multipla de 50."""

    def setUp(self) -> None:
        app.config["TESTING"] = True
        self.admin = cliente_logado("admin", "2026")
        self._criados: list[str] = []

    def tearDown(self) -> None:
        for login in self._criados:
            try:
                auth.remover_usuario(login)
            except ValueError:
                pass
        auth.zerar()

    def _criar(self, login, senha="segredo123", limite="100", rotinas=None, **extra):
        self._criados.append(login)
        dados = {"login": login, "senha": senha, "limite": limite, **extra}
        dados["rotinas"] = rotinas if rotinas is not None else list(auth.ROTINAS)
        return self.admin.post("/usuarios/criar", data=dados, follow_redirects=True)

    def test_cria_com_cota_multipla_de_50(self):
        resposta = self._criar("escritorio_alfa", limite="150", nome="Escritório Alfa")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("escritorio_alfa", resposta.get_data(as_text=True))
        usuario = auth.obter("escritorio_alfa")
        self.assertEqual(usuario["limite"], 150)
        self.assertEqual(usuario["papel"], "cliente")

    def test_cria_ilimitado(self):
        self._criar("parceiro_x", limite="ilimitado")
        self.assertIsNone(auth.obter("parceiro_x")["limite"])
        self.assertIsNone(auth.restante("parceiro_x"))

    def test_recusa_cota_fora_do_multiplo(self):
        resposta = self._criar("qualquer", limite="75")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("múltipla de 50", resposta.get_data(as_text=True))
        self.assertIsNone(auth.obter("qualquer"))

    def test_recusa_login_duplicado_espaco_e_senha_curta(self):
        self._criar("repetido")
        for dados, trecho in (
            ({"login": "repetido", "senha": "outra123", "limite": "50"}, "Já existe"),
            ({"login": "com espaco", "senha": "senha123", "limite": "50"}, "sem espaços"),
            ({"login": "curto", "senha": "a", "limite": "50"}, "ao menos"),
            ({"login": "admin", "senha": "senha123", "limite": "50"}, "Já existe"),
        ):
            resposta = self.admin.post("/usuarios/criar", data=dados)
            self.assertEqual(resposta.status_code, 400, dados["login"])
            self.assertIn(trecho, resposta.get_data(as_text=True))

    def test_usuario_criado_entra_e_respeita_a_cota(self):
        self._criar("cliente_novo", senha="novo2026", limite="50")
        cliente = cliente_logado("cliente_novo", "novo2026")
        self.assertEqual(cliente.get("/").status_code, 200)
        self.assertEqual(cliente.get("/usuarios").status_code, 403)  # nao e administrador

        self.assertEqual(cliente.get("/ncm/10064000").status_code, 200)
        self.assertEqual(auth.restante("cliente_novo"), 49)

        for _ in range(49):
            auth.registrar_consulta("cliente_novo")
        self.assertFalse(auth.pode_consultar("cliente_novo"))
        self.assertEqual(cliente.get("/ncm/10064000").status_code, 403)

    def test_persistencia_em_disco(self):
        self._criar("persistente", limite="200")
        # simula um reinicio: esquece o que esta em memoria e recarrega do arquivo
        auth.USUARIOS.pop("persistente")
        auth._USUARIOS_CARREGADOS = False
        self.assertEqual(auth.obter("persistente")["limite"], 200)

    def test_edicao_de_nome_cota_e_rotinas(self):
        self._criar("editavel", senha="edita2026", limite="100", rotinas=["ncm", "lote"])
        self.assertEqual(self.admin.get("/usuarios/editar/editavel").status_code, 200)

        resposta = self.admin.post(
            "/usuarios/editar/editavel",
            data={"nome": "Escritório Beta", "senha": "", "limite": "250",
                  "rotinas": ["ncm", "lote", "cesta"]},
            follow_redirects=True,
        )
        self.assertEqual(resposta.status_code, 200)
        usuario = auth.obter("editavel")
        self.assertEqual(usuario["nome"], "Escritório Beta")
        self.assertEqual(usuario["limite"], 250)
        self.assertEqual(usuario["rotinas"], ["ncm", "lote", "cesta"])
        # senha em branco mantem a atual
        self.assertIsNotNone(auth.autenticar("editavel", "edita2026"))

    def test_edicao_troca_a_senha(self):
        self._criar("troca_senha", senha="antiga123", limite="50", rotinas=["ncm"])
        self.admin.post(
            "/usuarios/editar/troca_senha",
            data={"nome": "", "senha": "nova12345", "limite": "50", "rotinas": ["ncm"]},
            follow_redirects=True,
        )
        self.assertIsNotNone(auth.autenticar("troca_senha", "nova12345"))
        self.assertIsNone(auth.autenticar("troca_senha", "antiga123"))

    def test_edicao_valida_cota_e_rotinas(self):
        self._criar("valida", senha="valida123", limite="50", rotinas=["ncm"])
        fora_do_multiplo = self.admin.post(
            "/usuarios/editar/valida", data={"limite": "75", "rotinas": ["ncm"]}
        )
        self.assertEqual(fora_do_multiplo.status_code, 400)
        self.assertIn("múltipla de 50", fora_do_multiplo.get_data(as_text=True))

        sem_rotina = self.admin.post("/usuarios/editar/valida", data={"limite": "50"})
        self.assertEqual(sem_rotina.status_code, 400)
        self.assertIn("ao menos uma rotina", sem_rotina.get_data(as_text=True))
        # nada mudou
        self.assertEqual(auth.obter("valida")["limite"], 50)

    def test_usuario_de_fabrica_nao_e_editavel(self):
        tela = self.admin.get("/usuarios/editar/Teste")
        self.assertEqual(tela.status_code, 200)
        self.assertIn("fixo do sistema", tela.get_data(as_text=True))

        salvar = self.admin.post(
            "/usuarios/editar/Teste", data={"limite": "50", "rotinas": ["ncm"]}
        )
        self.assertEqual(salvar.status_code, 400)
        self.assertEqual(auth.obter("Teste")["limite"], auth.LIMITE_TESTE)

    def test_edicao_persiste_em_disco(self):
        self._criar("persiste_edicao", senha="persiste1", limite="50", rotinas=["ncm"])
        self.admin.post(
            "/usuarios/editar/persiste_edicao",
            data={"nome": "Depois", "senha": "", "limite": "300", "rotinas": ["cesta"]},
            follow_redirects=True,
        )
        auth.USUARIOS.pop("persiste_edicao")
        auth._USUARIOS_CARREGADOS = False
        usuario = auth.obter("persiste_edicao")
        self.assertEqual(usuario["limite"], 300)
        self.assertEqual(usuario["rotinas"], ["cesta"])

    def test_somente_administrador_edita(self):
        self._criar("alvo_edicao", senha="alvo1234", limite="50", rotinas=["ncm"])
        for login, senha in (("Cliente", "Cliente"), ("Teste", "123")):
            cliente = cliente_logado(login, senha)
            self.assertEqual(cliente.get("/usuarios/editar/alvo_edicao").status_code, 403)
            self.assertEqual(
                cliente.post("/usuarios/editar/alvo_edicao",
                             data={"limite": "500", "rotinas": ["ncm"]}).status_code,
                403,
            )
        self.assertEqual(auth.obter("alvo_edicao")["limite"], 50)

    def test_remocao(self):
        self._criar("temporario")
        self.assertEqual(
            self.admin.post("/usuarios/remover/temporario", follow_redirects=True).status_code,
            200,
        )
        self.assertIsNone(auth.obter("temporario"))
        # os usuarios de fabrica nao podem ser removidos
        self.assertEqual(self.admin.post("/usuarios/remover/admin").status_code, 400)
        self.assertIsNotNone(auth.obter("admin"))

    def test_cria_com_rotinas_selecionadas(self):
        self._criar("parcial", senha="parcial2026", limite="100",
                    rotinas=["ncm", "lote"])
        self.assertEqual(auth.obter("parcial")["rotinas"], ["ncm", "lote"])
        # marcar todas equivale a acesso total (rotinas = None)
        self._criar("completo", senha="completo2026", limite="50",
                    rotinas=list(auth.ROTINAS))
        self.assertIsNone(auth.obter("completo")["rotinas"])

    def test_recusa_usuario_sem_nenhuma_rotina(self):
        resposta = self.admin.post(
            "/usuarios/criar",
            data={"login": "sem_rotina", "senha": "senha123", "limite": "50"},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("ao menos uma rotina", resposta.get_data(as_text=True))
        self.assertIsNone(auth.obter("sem_rotina"))

    def test_rotina_nao_liberada_e_bloqueada(self):
        self._criar("so_ncm", senha="ncm2026", limite="100", rotinas=["ncm", "lote"])
        cliente = cliente_logado("so_ncm", "ncm2026")

        for rota in ("/ncm", "/ncm/lote", "/ncm/10064000"):
            self.assertEqual(cliente.get(rota).status_code, 200, rota)

        for rota in ("/cesta", "/consulta", "/fontes", "/apresentacao", "/cnae/6201501"):
            resposta = cliente.get(rota)
            self.assertEqual(resposta.status_code, 403, rota)
            self.assertIn("Rotina não liberada", resposta.get_data(as_text=True))

        # a tela inicial nao liberada leva para a primeira rotina disponivel
        inicial = cliente.get("/")
        self.assertEqual(inicial.status_code, 302)
        self.assertTrue(inicial.headers["Location"].endswith("/ncm"))

    def test_menu_mostra_apenas_o_que_esta_liberado(self):
        self._criar("menu_curto", senha="menu2026", limite="50", rotinas=["ncm"])
        pagina = cliente_logado("menu_curto", "menu2026").get("/ncm").get_data(as_text=True)
        self.assertIn(">Consulta por NCM<", pagina)
        self.assertNotIn("Análise do cartão CNPJ", pagina)
        self.assertNotIn("link-cesta", pagina)

    def test_login_leva_a_primeira_rotina_liberada(self):
        self._criar("entra_no_lote", senha="lote2026", limite="50", rotinas=["lote", "cesta"])
        cliente = app.test_client()
        resposta = cliente.post(
            "/entrar", data={"login": "entra_no_lote", "senha": "lote2026"}
        )
        self.assertTrue(resposta.headers["Location"].endswith("/ncm/lote"))

    def test_usuarios_de_fabrica_acessam_tudo(self):
        for login, senha in (("admin", "2026"), ("Cliente", "Cliente"), ("Teste", "123")):
            cliente = cliente_logado(login, senha)
            for rota in ("/", "/ncm", "/ncm/lote", "/cesta", "/consulta", "/fontes"):
                self.assertEqual(cliente.get(rota).status_code, 200, f"{login} {rota}")

    def test_apenas_administrador_gerencia(self):
        for login, senha in (("Cliente", "Cliente"), ("Teste", "123")):
            cliente = cliente_logado(login, senha)
            self.assertEqual(cliente.get("/usuarios").status_code, 403)
            self.assertEqual(
                cliente.post("/usuarios/criar",
                             data={"login": "invasor", "senha": "123456", "limite": "50"}
                             ).status_code,
                403,
            )
        self.assertIsNone(auth.obter("invasor"))


def _planilha_de_ncms(linhas: list[list[str]]) -> io.BytesIO:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for linha in linhas:
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


class TestLoteNCM(unittest.TestCase):
    """Consulta em lote: lista digitada ou planilha importada."""

    def test_leitura_de_texto(self):
        itens = lote.de_texto(
            "1006.40.00 ARROZ TIPO 1\n04011010; LEITE\n8703.23.10 - SEDAN\nlinha sem codigo"
        )
        self.assertEqual([i["ncm"] for i in itens], ["10064000", "04011010", "87032310"])
        self.assertEqual(itens[0]["referencia"], "ARROZ TIPO 1")

    def test_leitura_de_planilha_com_cabecalho(self):
        arquivo = _planilha_de_ncms([
            ["Código interno", "Descrição do produto", "NCM"],
            ["P-001", "Arroz tipo 1 5kg", "1006.40.00"],
            ["P-002", "Leite integral", "04011010"],
        ])
        itens, avisos = lote.de_planilha("produtos.xlsx", arquivo.read())
        self.assertEqual([i["ncm"] for i in itens], ["10064000", "04011010"])
        # as colunas de texto viram a referencia do item
        self.assertEqual(itens[0]["referencia"], "P-001 · Arroz tipo 1 5kg")
        self.assertEqual(avisos, [])

    def test_planilha_sem_coluna_ncm_avisa_e_varre(self):
        arquivo = _planilha_de_ncms([
            ["produto", "codigo"],
            ["Arroz", "1006.40.00"],
        ])
        itens, avisos = lote.de_planilha("sem_cabecalho.xlsx", arquivo.read())
        self.assertEqual([i["ncm"] for i in itens], ["10064000"])
        self.assertTrue(any("célula a célula" in a for a in avisos))

    def test_formato_nao_suportado(self):
        with self.assertRaises(ValueError):
            lote.de_planilha("antigo.xls", b"qualquer")

    def test_processamento_e_resumo(self):
        resultado = lote.processar(lote.de_texto(
            "1006.40.00 ARROZ\n8703.23.10 SEDAN\n99999999 INEXISTENTE\n1006.40.00 REPETIDO"
        ))
        r = resultado["resumo"]
        self.assertEqual(r["total"], 3)  # o repetido e consultado uma vez so
        self.assertTrue(any("repetido" in a for a in resultado["avisos"]))
        self.assertEqual(r["nao_localizados"], 1)
        self.assertEqual(r["aliquota_zero"], 1)
        self.assertEqual(r["imposto_seletivo"], 1)

        arroz = next(x for x in resultado["resultados"] if x["ncm"] == "10064000")
        self.assertEqual(arroz["enquadramento"], "Regime diferenciado")
        self.assertIn("Anexo I item 1", arroz["anexos"])
        self.assertEqual(arroz["cclasstrib"][0]["cclasstrib"], "200003")

        # sem anexo, o candidato e a tributacao integral
        sedan = next(x for x in resultado["resultados"] if x["ncm"] == "87032310")
        self.assertEqual(sedan["enquadramento"], "Tributação integral")
        self.assertEqual(sedan["cclasstrib"][0]["cclasstrib"], "000001")
        self.assertTrue(sedan["imposto_seletivo"])

    def test_fluxo_web_e_downloads(self):
        cliente = cliente_logado()
        self.assertEqual(cliente.get("/ncm/lote").status_code, 200)

        arquivo = _planilha_de_ncms([["NCM", "Produto"], ["1006.40.00", "Arroz"]])
        resposta = cliente.post(
            "/ncm/lote",
            data={"planilha": (arquivo, "produtos.xlsx"), "ncms": "8703.23.10 SEDAN"},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.get_data(as_text=True)
        self.assertIn("200003", corpo)
        self.assertIn("SEDAN", corpo)

        token = corpo.split("/download-lote/")[1].split("/")[0]
        for formato, assinatura in (("xlsx", b"PK"), ("csv", b"NCM"), ("json", b"{")):
            arq = cliente.get(f"/download-lote/{token}/{formato}")
            self.assertEqual(arq.status_code, 200, formato)
            self.assertTrue(arq.data[:16].lstrip(b"\xef\xbb\xbf").startswith(assinatura))

        # o lote inteiro entra na cesta como um item
        cliente.post("/cesta/adicionar", data={"tipo": "lote", "token": token},
                     follow_redirects=True)
        payload = json.loads(cliente.get("/cesta/download/json").data)
        self.assertEqual(payload["cesta"]["consultas"][0]["tipo"], "lote")
        self.assertTrue(payload["resumo"]["linhas"])

    def test_lote_debita_uma_consulta_por_ncm(self):
        auth.zerar("Teste")
        cliente = cliente_logado("Teste", "123")
        resposta = cliente.post(
            "/ncm/lote", data={"ncms": "1006.40.00\n04011010\n84713012"}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(auth.consumo("Teste"), 3)
        self.assertEqual(auth.restante("Teste"), 7)
        auth.zerar("Teste")

    def test_lote_e_cortado_no_saldo_e_a_exportacao_acompanha(self):
        auth.zerar("Teste")
        for _ in range(8):  # sobram 2 das 10 consultas
            auth.registrar_consulta("Teste")
        cliente = cliente_logado("Teste", "123")

        codigos = ["1006.40.00", "04011010", "84713012", "87032310", "34011190"]
        resposta = cliente.post("/ncm/lote", data={"ncms": "\n".join(codigos)})
        self.assertEqual(resposta.status_code, 200)

        token = resposta.get_data(as_text=True).split("/download-lote/")[1].split("/")[0]
        payload = json.loads(cliente.get(f"/download-lote/{token}/json").data)
        # so os dois primeiros entraram - e a planilha exportada traz apenas eles
        self.assertEqual(payload["resumo"]["total"], 2)
        self.assertEqual(len(payload["ncms"]), 2)
        self.assertTrue(any("ficaram de fora" in a for a in payload["avisos"]))
        self.assertEqual(auth.restante("Teste"), 0)

        # esgotada a cota, um novo lote nem chega a ser processado
        self.assertEqual(
            cliente.post("/ncm/lote", data={"ncms": "1006.40.00"}).status_code, 403
        )
        auth.zerar("Teste")

    def test_lote_sem_limite_nao_e_cortado(self):
        cliente = cliente_logado("Cliente", "Cliente")
        codigos = ["1006.40.00", "04011010", "84713012", "87032310"]
        resposta = cliente.post("/ncm/lote", data={"ncms": "\n".join(codigos)})
        token = resposta.get_data(as_text=True).split("/download-lote/")[1].split("/")[0]
        payload = json.loads(cliente.get(f"/download-lote/{token}/json").data)
        self.assertEqual(payload["resumo"]["total"], 4)
        self.assertIsNone(auth.restante("Cliente"))

    def test_lote_vazio(self):
        cliente = cliente_logado()
        self.assertEqual(
            cliente.post("/ncm/lote", data={"ncms": "sem codigo aqui"}).status_code, 400
        )


class TestCesta(unittest.TestCase):
    """Rotina que acumula consultas e gera o relatorio consolidado."""

    def setUp(self) -> None:
        self.cliente = cliente_logado()

    def _token_cnae(self, cnaes: str) -> str:
        corpo = self.cliente.post("/analisar", data={"cnaes": cnaes}).get_data(as_text=True)
        return corpo.split("/download/")[1].split("/")[0]

    def _token_ncm(self, codigo: str) -> str:
        corpo = self.cliente.get(f"/ncm/{codigo}").get_data(as_text=True)
        return corpo.split("/download-ncm/")[1].split("/")[0]

    def _adicionar(self, tipo: str, token: str):
        return self.cliente.post(
            "/cesta/adicionar", data={"tipo": tipo, "token": token}, follow_redirects=True
        )

    def test_cesta_vazia(self):
        resposta = self.cliente.get("/cesta")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Ainda não há consultas", resposta.get_data(as_text=True))
        self.assertEqual(self.cliente.get("/cesta/download/xlsx").status_code, 404)

    def test_acumula_cnae_e_ncm_no_mesmo_relatorio(self):
        self.assertEqual(self._adicionar("cnae", self._token_cnae("8630-5/01")).status_code, 200)
        self.assertEqual(self._adicionar("ncm", self._token_ncm("10064000")).status_code, 200)

        payload = json.loads(self.cliente.get("/cesta/download/json").data)
        self.assertEqual(payload["resumo"]["consultas"], 2)
        self.assertEqual(payload["resumo"]["consultas_cnae"], 1)
        self.assertEqual(payload["resumo"]["consultas_ncm"], 1)
        self.assertGreater(payload["resumo"]["linhas"], 1)

        tipos = {linha["Tipo"] for linha in payload["linhas"]}
        self.assertIn("Serviço (CNAE)", tipos)
        self.assertIn("Bem (NCM)", tipos)
        # as duas origens compartilham o mesmo conjunto de colunas
        for linha in payload["linhas"]:
            self.assertEqual(list(linha.keys()), COLUNAS)

        # o arroz do Anexo I entra como aliquota zero no consolidado
        arroz = [l for l in payload["linhas"] if l["Código"] == "1006.40.00"]
        self.assertTrue(any(l["cClassTrib"] == "200003" for l in arroz))
        self.assertTrue(any(l["Redução IBS (%)"] == "100" for l in arroz))
        self.assertTrue(all(l["NBS"] == "Não aplicável" for l in arroz))

    def test_contador_no_menu_e_formatos(self):
        self._adicionar("ncm", self._token_ncm("10064000"))
        self.assertIn('class="contador"', self.cliente.get("/").get_data(as_text=True))
        for formato, assinatura in (("xlsx", b"PK"), ("csv", b"Consulta"), ("json", b"{")):
            resposta = self.cliente.get(f"/cesta/download/{formato}")
            self.assertEqual(resposta.status_code, 200, formato)
            inicio = resposta.data[:16].lstrip(b"\xef\xbb\xbf")
            self.assertTrue(inicio.startswith(assinatura), f"{formato}: {inicio!r}")

    def test_remover_e_limpar(self):
        self._adicionar("ncm", self._token_ncm("10064000"))
        self._adicionar("ncm", self._token_ncm("30049099"))
        pagina = self.cliente.get("/cesta").get_data(as_text=True)
        item = re.search(r"/cesta/remover/([\w-]+)", pagina).group(1)

        self.cliente.post(f"/cesta/remover/{item}", follow_redirects=True)
        payload = json.loads(self.cliente.get("/cesta/download/json").data)
        self.assertEqual(payload["resumo"]["consultas"], 1)

        self.cliente.post("/cesta/limpar", follow_redirects=True)
        self.assertEqual(self.cliente.get("/cesta/download/json").status_code, 404)

    def test_token_expirado_nao_entra_na_cesta(self):
        self.assertEqual(
            self.cliente.post("/cesta/adicionar", data={"tipo": "ncm", "token": "xxx"}).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
