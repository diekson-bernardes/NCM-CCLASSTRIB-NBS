# Correlação CNAE → NBS → cClassTrib → indOP → item da LC 116/03

Ferramenta web local que lê o **cartão CNPJ em PDF** (Comprovante de Inscrição e de
Situação Cadastral da RFB) e devolve, para o CNAE principal e cada CNAE secundário,
a correlação fiscal da Reforma Tributária do Consumo (IBS/CBS — LC 214/2025):

| Saída | O que é | Fonte |
|---|---|---|
| **Item da LC 116/03** | subitem da lista de serviços | de-para CNAE × lista de serviços (tabelas municipais) |
| **NBS** | Nomenclatura Brasileira de Serviços | Anexo VIII da NFS-e nacional + NBS 2.0 (MDIC) |
| **indOP** | indicador da operação — define o local do fornecimento (art. 11 da LC 214/2025) | Anexo VII da NFS-e nacional |
| **cClassTrib** | código de classificação tributária do IBS/CBS, com o CST correspondente | Tabela de Classificação Tributária do Portal da NF-e (23/06/2026) |

Para CNAEs de comércio, indústria e agropecuária a NBS **não se aplica** (ela
classifica serviços e intangíveis): a ferramenta entrega a classificação por
**cClassTrib + indOP** e alerta que o enquadramento fino depende do NCM do produto.

## Consulta por NCM

Segunda via de pesquisa, independente do cartão CNPJ: informe o código NCM (ou
parte da descrição do produto) e a ferramenta devolve **CST**, **cClassTrib**,
percentuais de redução e **indOP** aplicáveis, indicando o anexo da LC 214/2025 que
fundamenta o regime — com o texto do item para conferência.

| Situação | Resultado |
|---|---|
| NCM citado em anexo de regime diferenciado | cClassTrib do anexo (ex.: `1006.40.00` arroz → Anexo I → `200003`, CST 200, redução de 100%) |
| NCM sem anexo | tributação integral: `000001`, CST 000 |
| NCM citado em cláusula de exceção | bloco "Exceções expressas", nunca descartado em silêncio |
| NCM do Anexo XVII | alerta de Imposto Seletivo (informado em grupo próprio do DF-e) |

Todas as fontes ficam versionadas em [`KB/`](KB/SOURCES.md).

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
python scripts/build_dataset.py
```

```bash
python -m app.main
```

Abra <http://127.0.0.1:5000>, envie o cartão CNPJ em PDF (ou digite CNAEs no campo
manual) e exporte o resultado em **XLSX**, **CSV** ou **JSON**.

Telas:

- **Análise do cartão CNPJ** — upload do PDF e correlação completa.
- **Consulta por NCM** — CST, cClassTrib, redução e indOP do produto (com export).
- **Consulta de NCM em lote** (`/ncm/lote`) — lista colada ou planilha `.xlsx`/`.csv` com os
  códigos: devolve o enquadramento de cada NCM (anexo, cClassTrib, CST, reduções), destaca os
  não localizados, os do Imposto Seletivo e os citados em exceção, e exporta em XLSX (abas
  *Resumo por NCM*, *Detalhado*, *Indicadores* e *Fontes*), CSV e JSON. A coluna de NCM é
  achada pelo cabeçalho; as demais colunas de texto viram a referência do item.
- **Consulta de tabelas** — busca por CNAE, item da LC 116, NBS, NCM, cClassTrib e indOP.
- **Cesta** (`/cesta`) — acumula os resultados das consultas (cartão CNPJ e NCM) e gera **um
  relatório consolidado**: as duas origens são convertidas para o mesmo conjunto de colunas,
  com resumo por CST e cClassTrib, contagem de linhas por faixa de redução e destaque das
  linhas que exigem conferência. Exporta XLSX (abas *Consolidado*, *Resumo*, *Consultas* e
  *Fontes*), CSV e JSON. A cesta fica em memória, ligada a um cookie — nada de contribuinte
  é gravado em disco.
- **Fontes (KB)** — documentos usados, versão, data e SHA-256.
- **Apresentação** (`/apresentacao`) — relatório para envio ao cliente: escopo, cobertura,
  exemplos reais, critérios de confiança e fontes. Os números vêm dos datasets
  (`Base.estatisticas()`), então a página nunca fica defasada; o botão *Imprimir / salvar PDF*
  usa uma folha de estilo de impressão própria. Versão avulsa em
  [`Docs/apresentacao.html`](Docs/apresentacao.html).

## Estrutura

```
app/                aplicação Flask
  dados.py          carga dos datasets + índice TF-IDF para similaridade
  parser_cnpj.py    leitura do cartão CNPJ em PDF
  correlacao.py     motor de correlação por CNAE
  ncm.py            motor de consulta por NCM (anexos da LC 214/2025)
  lote.py           leitura da lista/planilha de NCM e consulta em lote
  cesta.py          acúmulo das consultas e consolidação em colunas únicas
  relatorio.py      exportação XLSX / CSV / JSON
  main.py           rotas web
scripts/
  atualizar_kb.py   rebaixa as fontes catalogadas em KB/fontes.json
  build_dataset.py  normaliza KB/ → data/*.json
data/               datasets gerados (não editar à mão)
KB/                 fontes oficiais + SOURCES.md + fontes.json
tests/              testes (python -m unittest discover -s tests)
Docs/               metodologia e decisões
```

## Confiança das correlações

| Marca | Significado |
|---|---|
| `alta` | vínculo CNAE → item da LC 116 vindo de tabela municipal oficial |
| `média` / `baixa` | sugestão por similaridade textual entre a descrição do CNAE e a do item — **exige validação** |
| operação com bens | CNAE das seções A, B, C ou G sem vínculo de serviço |

Não existe tabela nacional oficial de CNAE × item da LC 116/03; o de-para usa a
Portaria 463/2025 de Anápolis/GO e a tabela da SEFAZ Salvador/BA (1.237 vínculos,
570 CNAEs). Veja [`Docs/METODOLOGIA.md`](Docs/METODOLOGIA.md).

## Acesso

Todas as telas exigem login ([`app/auth.py`](app/auth.py)):

| Usuário | Perfil | Limite |
|---|---|---|
| `admin` | administrador — vê o painel de usuários em `/usuarios` | sem limitação |
| `Cliente` | uso normal | sem limitação |
| `Teste` | demonstração | 10 consultas |

Consomem cota as ações que produzem enquadramento — análise de cartão CNPJ, consulta de
NCM, consulta em lote (**uma consulta por NCM processado**) e detalhe de CNAE. Um lote maior
que o saldo é processado até onde a cota alcança, e a planilha exportada traz exatamente os
códigos processados, com aviso de quantos ficaram de fora. Navegar, buscar nas tabelas e baixar um relatório
já gerado não consomem; uma consulta que falha também não. Esgotada a cota, o usuário
`Teste` continua navegando, mas não faz novas consultas até o administrador zerar a
contagem em `/usuarios`.

O administrador cria novos usuários em `/usuarios`, informando login, senha, a cota —
**múltiplos de 50** consultas ou **ilimitado** — e **quais rotinas** ficam liberadas:
análise do cartão CNPJ, consulta por NCM, NCM em lote, cesta, consulta de tabelas, fontes
e apresentação. O menu se ajusta ao que o usuário pode acessar, uma rotina bloqueada
responde com a tela “Rotina não liberada”, e o login leva à primeira rotina disponível.
Só o administrador libera rotinas — e ele mesmo acessa todas. Os usuários criados têm perfil de cliente,
ficam em `var/usuarios.json` (senha em hash, fora do versionamento) e podem ser removidos
pelo painel; os três usuários de fábrica não.

As senhas ficam no repositório apenas como hash (pbkdf2-sha256) e podem ser trocadas por
variável de ambiente. A contagem de uso é gravada em `var/uso.json` (fora do versionamento).

## Publicação

A ferramenta precisa de um host que execute Python — GitHub Pages não serve (só arquivos
estáticos). O repositório já traz `wsgi.py`, `render.yaml` e `Procfile`; o passo a passo
para publicar no Render, com deploy automático a cada push, está em
[`Docs/DEPLOY.md`](Docs/DEPLOY.md).

Em servidor, use sempre **um worker**:

```bash
gunicorn wsgi:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT
```

As análises, as consultas de NCM e a cesta ficam na memória do processo; com vários
workers os downloads falhariam de forma intermitente.

Defina `RTC_SECRET_KEY` no host para que as sessões de login sobrevivam a um reinício, e
`RTC_SENHA_ADMIN` / `RTC_SENHA_CLIENTE` / `RTC_SENHA_TESTE` para publicar com senhas
diferentes das de desenvolvimento.

## Manutenção

As tabelas da reforma mudam com frequência:

```bash
python scripts/atualizar_kb.py --checar
```

Se algo mudou, rode sem `--checar` e regenere os datasets com
`python scripts/build_dataset.py`.

## Aviso

Ferramenta de apoio. O Anexo VIII da NFS-e é declaradamente uma versão em evolução
e as correlações municipais são indicativas — o enquadramento fiscal definitivo é
responsabilidade do contribuinte.
