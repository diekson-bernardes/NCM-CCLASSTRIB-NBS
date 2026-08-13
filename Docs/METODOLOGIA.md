# Metodologia da correlação

Documento de referência das decisões técnicas e das limitações conhecidas.
Coleta das fontes: 12/08/2026.

## 1. Cadeia de correlação

```
Cartão CNPJ (PDF)
   └── CNAE (subclasse, 7 dígitos)
         ├── serviço  → item da LC 116/03 → Anexo VIII → { NBS*, indOP, cClassTrib, local de incidência }
         └── bens     → NBS não aplicável → { indOP de bem móvel, cClassTrib } + verificação por NCM
```

`*` um item da LC 116 costuma corresponder a vários códigos NBS, e o mesmo item pode
ter mais de um cClassTrib (tributação integral × regimes com redução) e mais de um
indOP (presencial, não presencial, à distância).

## 2. Leitura do cartão CNPJ

`app/parser_cnpj.py` localiza as âncoras do comprovante da RFB
(`CÓDIGO E DESCRIÇÃO DA ATIVIDADE ECONÔMICA PRINCIPAL`, `... SECUNDÁRIAS`,
`... DA NATUREZA JURÍDICA`) e extrai os CNAEs de cada bloco, aceitando as máscaras
`62.01-5-01`, `6201-5/01` e `6201501`. A regex exige separadores típicos de CNAE,
evitando que o CNPJ do cabeçalho seja lido como atividade.

PDFs digitalizados (imagem) não têm texto extraível: nesse caso a ferramenta avisa
e o usuário informa os CNAEs manualmente.

## 3. CNAE → item da LC 116/03

Não há tabela nacional oficial. Duas camadas:

1. **De-para municipal** (`data/cnae_lc116.json`, 1.237 vínculos, 570 CNAEs):
   Portaria 463/2025 de Anápolis/GO (base principal, extraída das tabelas do PDF) e
   tabela da SEFAZ Salvador/BA (complementar). Confiança **alta**; a origem de cada
   vínculo é registrada e exibida.
2. **Similaridade textual** para CNAEs de serviço sem vínculo: TF-IDF sobre as
   descrições dos 200 subitens da lista, com remoção de acentos e stopwords do
   domínio. Score ≥ 0,35 → **média**; ≥ 0,18 → **baixa**; abaixo disso nada é
   sugerido e a trilha de bens é oferecida como alternativa. Máximo de 3 sugestões.

Cobertura atual: dos 1.332 CNAEs, 570 têm vínculo oficial; os 762 restantes são
majoritariamente indústria (325), comércio (197) e agropecuária (116) — ou seja,
operações com bens, em que o item da LC 116 realmente não se aplica.

**Como melhorar:** adicione a tabela do município do contribuinte em
`KB/cnae-lc116/`, cadastre-a em `KB/fontes.json` e escreva o parser correspondente
em `scripts/build_dataset.py` (função `build_cnae_lc116`). Tabela municipal própria
prevalece sobre as demais.

## 4. Item da LC 116 → NBS, indOP e cClassTrib (Anexo VIII)

A aba `tabela geral` do Anexo VIII usa **células mescladas**: item, NBS, cClassTrib,
local de incidência e as colunas de onerosidade valem para todas as linhas da
mescla. O parser (`scripts/build_dataset.py`) propaga os valores mesclados e só
então monta a tupla completa `(item, NBS, indOP, local, onerosidade, cClassTrib)`.

Sem essa propagação o resultado fica errado de duas formas: itens aparecem sem
cClassTrib (ex.: 04.03 Hospitais) e um mesmo tratamento é quebrado em vários
registros artificiais.

Em seguida as NBS que compartilham item, cClassTrib e o mesmo conjunto de indOP são
agrupadas — resultando em 296 registros para 207 itens. Exemplos:

- `04.01 Medicina` → cClassTrib 200029 (redução de 60%), indOP 030101/030102/100301,
  NBS 1.2301.22.00.
- `05.01 Medicina veterinária` → 200052 para as NBS de atendimento e 200038 para a
  NBS de insumos agropecuários, ambos com indOP 050101/050102.
- `01.01 Análise e desenvolvimento de sistemas` → 000001 com 11 NBS, além das
  classificações alternativas 200043 e 200044.

## 5. Trilha de operações com bens

Aplicada quando o CNAE é das seções A (agropecuária), B (extrativa), C (indústria)
ou G (comércio) e não tem vínculo de serviço:

- **NBS:** não aplicável — a NBS classifica serviços e intangíveis; bens usam NCM.
- **Item da LC 116:** não aplicável.
- **indOP:** indicadores de bem móvel material válidos em NF-e — `010101`
  (presencial, retirada no estabelecimento) e `010103` (não presencial, entrega no
  endereço do destinatário).
- **cClassTrib:** referência `000001` (tributação integral) e a lista completa das
  classificações admitidas em NF-e com CST diferente de 000, para os regimes
  específicos por NCM (reduções, alíquota zero, monofasia, exportação, diferimento).

## 6. Consulta por NCM (bens)

Segunda entrada da ferramenta, independente do cartão CNPJ. A cadeia é:

```
NCM (8 dígitos)
  └── anexo da LC 214/2025 que cita o código
        └── cClassTrib que remete a esse anexo  →  CST + % de redução
  └── indOP de bem móvel material (independe do produto)
```

Não existe tabela oficial "NCM × cClassTrib". A ligação é construída em duas
pontas, ambas oficiais:

1. **Anexos da LC 214/2025** (`data/lc214_anexos.json`, 351 itens com 542
   referências de NCM): extraídos do texto da lei. Os anexos usam três layouts —
   `ITEM | DESCRIÇÃO` (I, VII, VIII, IX, X, XV), `ITEM | DESCRIÇÃO | NCM/SH`
   (IV, V, XI, XII, XIII) e coluna única com rótulo + lista (XVII). No layout de
   três colunas as inclusões vêm da coluna de códigos e a descrição contribui só
   com as exceções; nos demais, um código é tratado como exceção quando aparece
   depois de "exceto/ressalvado/salvo" dentro do mesmo período.
2. **cClassTrib que citam o anexo** na tabela do Portal da NF-e — por exemplo
   `200003 Vendas de produtos destinados à alimentação humana (Anexo I)`,
   `200034 ... (Anexo VII)`, `200038 ... insumos agropecuários (Anexo IX)`.

Regras de apresentação:

- O casamento é por **prefixo**: `1006.40.00` casa com a referência `1006.40.00`
  e também com `1006.4` ou `10.06` quando o anexo cita o nível superior.
- Quando o mesmo NCM aparece como **exceção** de um item, ele é mostrado em bloco
  separado ("Exceções expressas") — nunca silenciosamente removido. Ex.:
  `9018.11.00` entra pelo item 1.1 do Anexo XII e é expressamente excluído do
  item 1.3.
- O **cClassTrib 000001** (tributação integral) é sempre exibido como referência:
  é a regra geral e também o que se aplica quando os requisitos do anexo não são
  atendidos.
- O **Anexo XVII** (Imposto Seletivo) não tem cClassTrib próprio: aparece como
  bloco e alerta separados.
- A coluna "Tipo de Alíquota" da tabela oficial é sempre `Padrão`; o que
  identifica o benefício é `pRedIBS`/`pRedCBS` (100 = alíquota zero, 60 = redução
  de 60%). A tela e os relatórios mostram esses percentuais.

Limites: a lei condiciona vários regimes a requisitos não expressos no código
(destinação, registro sanitário, tipo de adquirente). A ferramenta entrega o
enquadramento **candidato** com o texto integral do item do anexo para conferência.

## 7. Datasets gerados

| Arquivo | Registros | Origem |
|---|---|---|
| `data/anexo_viii.json` | 296 | Anexo VIII 1.01.00 |
| `data/indop.json` | 39 | Anexo VII 1.02.00 |
| `data/cclasstrib.json` | 164 | Tabela cClassTrib 23/06/2026 |
| `data/cst.json` | 18 | idem |
| `data/lc116.json` | 200 | Tabela cListServ (Portal NF-e) |
| `data/nbs.json` | 1.237 | NBS 2.0 (MDIC) |
| `data/cnae.json` | 1.332 | API do IBGE |
| `data/cnae_lc116.json` | 1.237 | tabelas municipais |
| `data/ncm.json` | 15.156 | NCM/SH do Portal Único Siscomex |
| `data/lc214_anexos.json` | 351 | anexos da LC 214/2025 (542 refs de NCM) |
| `data/manifesto.json` | — | catálogo + SHA-256 das fontes |

## 8. Limitações conhecidas

- O Anexo VIII declara ser versão inicial "ainda em desenvolvimento"; alguns itens
  da LC 116 ainda não têm NBS correlacionada.
- O de-para CNAE × LC 116 é municipal e indicativo; um mesmo CNAE pode admitir
  vários itens conforme o serviço efetivamente prestado.
- A ferramenta correlaciona **atividades cadastradas**, não operações concretas: a
  escolha final do indOP depende de como o fornecimento ocorre (presencial, à
  distância, com entrega) e o cClassTrib pode variar por regime específico.
- Na consulta por NCM, o regime depende também de requisitos não codificados no
  NCM (destinação, legislação sanitária, tipo de adquirente) — o texto do anexo é
  sempre exibido para conferência.
- Alíquotas não são calculadas — a tabela de alíquotas da CBS (0,9% em 2026) está
  na KB apenas como referência do período de transição.
