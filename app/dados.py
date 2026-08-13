"""Carga e indexacao dos datasets normalizados (pasta data/)."""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"

# Secoes CNAE (IBGE) predominantemente de operacoes com BENS.
SECOES_BENS = {"A", "B", "C", "G"}

STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "as", "os", "em", "para", "por",
    "com", "sem", "no", "na", "nos", "nas", "ou", "ao", "aos", "um", "uma", "que",
    "outros", "outras", "nao", "especificados", "anteriormente", "qualquer",
    "natureza", "congeneres", "atividades", "atividade", "servicos", "servico",
    "inclusive", "exceto", "quaisquer", "seus", "sua", "suas", "pelo", "pela",
}


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def tokens(texto: str) -> list[str]:
    limpo = "".join(c if c.isalnum() else " " for c in normaliza(texto))
    return [t for t in limpo.split() if len(t) > 2 and t not in STOPWORDS]


def _ler(nome: str):
    caminho = DATA / nome
    if not caminho.exists():
        raise FileNotFoundError(
            f"Dataset ausente: {caminho}. Rode: python scripts/build_dataset.py"
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


class Base:
    """Datasets carregados uma unica vez, com indices prontos para consulta."""

    def __init__(self) -> None:
        self.lc116: list[dict] = _ler("lc116.json")
        self.nbs: list[dict] = _ler("nbs.json")
        self.indop: list[dict] = _ler("indop.json")
        self.cclasstrib: list[dict] = _ler("cclasstrib.json")
        self.cst: list[dict] = _ler("cst.json")
        self.anexo_viii: list[dict] = _ler("anexo_viii.json")
        self.cnae: list[dict] = _ler("cnae.json")
        self.cnae_lc116: list[dict] = _ler("cnae_lc116.json")
        self.ncm: list[dict] = _ler("ncm.json")
        self.lc214_anexos: list[dict] = _ler("lc214_anexos.json")
        self.manifesto: dict = _ler("manifesto.json")

        self.por_cnae = {c["cnae"]: c for c in self.cnae}
        self.por_item = {i["item"]: i for i in self.lc116}
        self.por_indop = {i["indop"]: i for i in self.indop}
        self.por_cclasstrib = {c["cclasstrib"]: c for c in self.cclasstrib}
        self.por_nbs = {n["nbs"]: n for n in self.nbs}

        self.itens_por_cnae: dict[str, list[dict]] = {}
        for vinculo in self.cnae_lc116:
            self.itens_por_cnae.setdefault(vinculo["cnae"], []).append(vinculo)

        self.anexo_por_item: dict[str, list[dict]] = {}
        for registro in self.anexo_viii:
            self.anexo_por_item.setdefault(registro["item"], []).append(registro)

        self.por_ncm = {n["ncm"]: n for n in self.ncm}

        # cClassTrib citados por anexo da LC 214/2025 (ex.: "(Anexo IV)")
        self.cclasstrib_por_anexo: dict[str, list[dict]] = {}
        for classe in self.cclasstrib:
            for m in re.finditer(
                r"Anexo\s+([IVXL]+)", f"{classe['nome']} {classe['descricao']}"
            ):
                lista = self.cclasstrib_por_anexo.setdefault(m.group(1), [])
                if classe not in lista:
                    lista.append(classe)

        self._indice_tfidf()

    # ------------------------------------------------------------- similaridade
    def _indice_tfidf(self) -> None:
        """Indice TF-IDF simples sobre as descricoes dos itens da LC 116/2003."""
        import math

        self._docs: list[tuple[str, dict[str, float], float]] = []
        docs_tokens = [(i["item"], tokens(i["descricao"])) for i in self.lc116]
        n = len(docs_tokens) or 1
        freq_doc: dict[str, int] = {}
        for _, tks in docs_tokens:
            for t in set(tks):
                freq_doc[t] = freq_doc.get(t, 0) + 1
        self._idf = {t: math.log(n / (1 + df)) + 1.0 for t, df in freq_doc.items()}

        for item, tks in docs_tokens:
            pesos: dict[str, float] = {}
            for t in tks:
                pesos[t] = pesos.get(t, 0.0) + self._idf.get(t, 1.0)
            norma = math.sqrt(sum(v * v for v in pesos.values())) or 1.0
            self._docs.append((item, pesos, norma))

    def itens_semelhantes(self, texto: str, limite: int = 3) -> list[tuple[str, float]]:
        import math

        consulta: dict[str, float] = {}
        for t in tokens(texto):
            consulta[t] = consulta.get(t, 0.0) + self._idf.get(t, 1.0)
        if not consulta:
            return []
        norma_q = math.sqrt(sum(v * v for v in consulta.values())) or 1.0

        pontuacoes = []
        for item, pesos, norma in self._docs:
            produto = sum(peso * consulta[t] for t, peso in pesos.items() if t in consulta)
            if produto:
                pontuacoes.append((item, produto / (norma * norma_q)))
        pontuacoes.sort(key=lambda x: x[1], reverse=True)
        return pontuacoes[:limite]

    # ----------------------------------------------------------------------- NCM
    def hierarquia_ncm(self, digitos: str) -> list[dict]:
        """Capitulo, posicao, subposicao e item que contem o codigo informado."""
        niveis = [
            n for n in self.ncm
            if digitos.startswith(n["ncm"]) and len(n["ncm"]) <= len(digitos)
        ]
        return sorted(niveis, key=lambda n: len(n["ncm"]))

    def buscar_ncm(self, termo: str, limite: int = 60) -> list[dict]:
        digitos = re.sub(r"\D", "", termo)
        if digitos:
            achados = [n for n in self.ncm if n["ncm"].startswith(digitos)]
        else:
            chave = normaliza(termo)
            achados = [n for n in self.ncm if chave in normaliza(n["descricao"])]
        achados.sort(key=lambda n: (not n["vigente"], -n["nivel"] == 8, n["ncm"]))
        return achados[:limite]

    # ------------------------------------------------------------------ auxiliar
    def indops_para_bens(self) -> list[dict]:
        return [
            i
            for i in self.indop
            if i["usa_nfe"] and normaliza(i["tipo_operacao"]).startswith("bem movel")
        ]

    def descricao_nbs(self, codigo: str) -> str:
        registro = self.por_nbs.get(codigo)
        return registro["descricao"] if registro else ""

    def versao_fontes(self) -> list[dict]:
        return self.manifesto.get("fontes", [])


@lru_cache(maxsize=1)
def base() -> Base:
    return Base()
