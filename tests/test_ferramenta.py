"""Testes da leitura do cartao CNPJ e do motor de correlacao.

Execucao:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
        app.config["TESTING"] = True
        self.cliente = app.test_client()

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


if __name__ == "__main__":
    unittest.main()
