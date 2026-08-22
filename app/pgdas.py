"""Rotina de importacao da declaracao PGDAS-D (Simples Nacional).

A ferramenta chegou pronta, como uma pagina HTML autonoma: ela le o PDF do
PGDAS-D no proprio navegador (pdf.js), separa os tributos por estabelecimento e
por atividade, calcula a carga efetiva e o enquadramento nos Anexos I e III, e
monta a versao para impressao. Nenhum byte do PDF sobe para o servidor.

Duas decisoes de integracao:

1. A pagina e servida como esta, sem passar pelo Jinja. Ela vem inteira do
   arquivo `recursos/pgdas_ferramenta.html`, entao atualizar a ferramenta e so
   trocar esse arquivo - nada aqui precisa mudar.

2. Ela aparece dentro do site num quadro (iframe). O CSS dela usa seletores
   globais (`body`, `header`, `table`, `td`) que reescreveriam o visual das
   demais telas; o quadro isola os dois estilos sem exigir a reescrita de uma
   ferramenta que ja funciona.

O unico acrescimo feito na hora de servir e o script de integracao abaixo: ele
avisa a altura ao quadro que a contem e debita uma consulta por declaracao lida.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / "recursos" / "pgdas_ferramenta.html"

# Marcador substituido pela URL real da rota que debita a cota.
_MARCA_URL = "__URL_REGISTRAR__"

INTEGRACAO = """
<script>
/* Integracao com o Classificador da Reforma Tributaria. Acrescentado ao servir a
   pagina - o arquivo original segue intacto. */
(function () {
  var URL_REGISTRAR = "__URL_REGISTRAR__";

  var dentroDoQuadro = window.parent !== window;

  /* A ferramenta usa `body { min-height: 100vh }`. Dentro do quadro, 100vh e a
     altura do proprio quadro: medir o corpo para redimensiona-lo faria o corpo
     crescer junto, sem parar. Aqui a regra e neutralizada e a altura passa a sair
     do conteudo de verdade - o que o corpo mede deixa de importar. */
  if (dentroDoQuadro) {
    var ajuste = document.createElement("style");
    ajuste.textContent = "html,body{min-height:0!important;height:auto!important}";
    document.head.appendChild(ajuste);
  }

  function alturaDoConteudo() {
    var maior = 0;
    var filhos = document.body.children;
    for (var i = 0; i < filhos.length; i++) {
      var caixa = filhos[i].getBoundingClientRect();
      if (caixa.height > 0) {
        maior = Math.max(maior, caixa.bottom + window.scrollY);
      }
    }
    return Math.ceil(maior);
  }

  /* O quadro que exibe esta pagina no site cresce junto com o conteudo. A folga
     de 2px evita ida e volta por arredondamento. */
  var ultimaAltura = 0;
  function avisaAltura() {
    if (!dentroDoQuadro) { return; }
    var altura = alturaDoConteudo();
    if (!altura || Math.abs(altura - ultimaAltura) <= 2) { return; }
    ultimaAltura = altura;
    parent.postMessage({ rtc: "altura-pgdas", altura: altura },
                       window.location.origin);
  }
  window.addEventListener("load", avisaAltura);
  if (window.ResizeObserver) { new ResizeObserver(avisaAltura).observe(document.body); }

  function aviso(texto) {
    if (typeof showStatus === "function") { showStatus(texto, false); }
    else { alert(texto); }
  }

  /* Cada declaracao importada debita uma consulta. A cobranca vem ANTES da
     leitura: com a cota esgotada o servidor responde 403 e o PDF nem chega a ser
     processado. Sem rede, a leitura (que e local) segue assim mesmo. */
  var lerOriginal = window.processPDF;
  if (typeof lerOriginal === "function") {
    window.processPDF = async function () {
      var resposta = null;
      try {
        resposta = await fetch(URL_REGISTRAR, { method: "POST" });
      } catch (erro) {
        resposta = null;
      }
      if (resposta && resposta.status === 403) {
        aviso("Cota de consultas esgotada — fale com o administrador.");
        avisaAltura();
        return;
      }
      var saida = await lerOriginal.apply(this, arguments);
      avisaAltura();
      return saida;
    };
  }
})();
</script>
"""


@lru_cache(maxsize=1)
def _original() -> str:
    return ARQUIVO.read_text(encoding="utf-8")


def pagina(url_registrar: str) -> str:
    """HTML da ferramenta com o script de integracao antes do </body>."""
    html = _original()
    script = INTEGRACAO.replace(_MARCA_URL, url_registrar)
    corte = html.rfind("</body>")
    if corte == -1:  # arquivo sem </body>: acrescenta ao final
        return html + script
    return html[:corte] + script + html[corte:]
