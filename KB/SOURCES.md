# Fontes utilizadas (Knowledge Base)

Todos os arquivos desta pasta foram baixados das fontes oficiais listadas abaixo.
O catálogo legível por máquina está em [`fontes.json`](fontes.json) e é usado por
`scripts/atualizar_kb.py` (rebaixa e compara hash) e por `scripts/build_dataset.py`
(gera `data/manifesto.json` com SHA-256 de cada arquivo).

Data da coleta: **12/08/2026** (fontes de NCM em **13/08/2026**).

## 1. Correlação de serviços — Portal Nacional da NFS-e (RFB + Comitê Gestor do IBS)

| Arquivo | Documento | Versão | URL |
|---|---|---|---|
| `nfse-rtc/AnexoVIII-CorrelacaoItemNBSIndOpCClassTrib_IBSCBS_V1.01.00.xlsx` | **Anexo VIII — Correlação item da LC 116/03 × NBS × indOP × cClassTrib** | 1.01.00 (NT 009) | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/anexoviii-correlacaoitemnbsindopcclasstrib_ibscbs_v1-01-00.xlsx |
| `nfse-rtc/AnexoVII-IndOp_IBSCBS_V1.02.00.xlsx` | **Anexo VII — Tabela de Indicadores da Operação (cIndOp)** | 1.02.00 (NT 009) | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/anexovii-indop_ibscbs_v1-02-00.xlsx |
| `nfse-rtc/AnexoVI-LeiautesRN_RTC_IBSCBS-v1.04.00-NT009.xlsx` | Anexo VI — Leiautes e regras de negócio da NFS-e (RTC) | 1.04.00 (NT 009) | https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc/anexovi-leiautesrn_rtc_ibscbs-v1-04-00-2013-nt009.xlsx |

Página de origem: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc

> O próprio Anexo VIII declara ser "um trabalho inicial, ainda em desenvolvimento" —
> daí os alertas de validação exibidos pela ferramenta.

## 2. Classificação tributária IBS/CBS — Portal Nacional da NF-e

| Arquivo | Documento | Publicação | URL |
|---|---|---|---|
| `nfe-rtc/Tabela_Classificacao_Tributaria_IBS_CBS_2026-06-23.xlsx` | **Tabela de cClassTrib + CST do IBS/CBS** | 23/06/2026 (vigência 01/06/2026) | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=D5b4Ov84WDg= |
| `nfe-rtc/Tabela_Codigo_Credito_Presumido_IBS_CBS_2026-06-23.xlsx` | Tabela de Código de Crédito Presumido (cCredPres) | 23/06/2026 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=TpJZSmm9U1c= |
| `nfe-rtc/Tabela_Indicadores_CST_IBS_CBS_2025-05-19.xlsx` | Tabela de Indicadores de CST | 19/05/2025 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=AozMa50GUrE= |
| `nfe-rtc/Tabela_Codigos_Item_Lista_Servicos.xlsx` | **Tabela de Códigos de Item da Lista de Serviços (cListServ / LC 116/03)** | vigente | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=ZCj/PlYFSRQ= |
| `nfe-rtc/Tabela_Aliquotas_CBS_2026-05-12.xlsx` | Tabela de Alíquotas da CBS (0,9% em 2026) | 12/05/2026 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=LRksVAMl7nQ= |
| `nfe-rtc/NT_2025.002_v1.51_NFe.pdf` | Nota Técnica 2025.002 v.1.51 — RTC na NF-e/NFC-e | 04/08/2026 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=AKD/muSmiIY= |
| `nfe-rtc/NFe_Tabela_cClassTrib_IT2025-002.pdf` | Informe Técnico RT 2024.001 (histórico do cClassTrib) | 05/12/2024 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=XBgqrMtxPVY= |

Páginas de origem: [Documentos › Diversos](https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=/NJarYc9nus=)
e [Notas Técnicas](https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=04BIflQt1aY=).

## 3. NBS — MDIC / Secretaria de Comércio e Serviços

| Arquivo | Documento | URL |
|---|---|---|
| `nbs/NBS_2.0_tabela.csv` | **NBS 2.0 — tabela de códigos e descrições** | https://www.gov.br/mdic/pt-br/images/REPOSITORIO/scs/decos/NBS/NBSa_2-0.csv |
| `nbs/NBS_2.0_AnexoI_com_alteracoes_2018-12-06.pdf` | Anexo I — NBS 2.0 | https://www.gov.br/mdic/pt-br/images/REPOSITORIO/scs/decos/NBS/Anexoa_Ia_NBSa_2.0a_coma_alteraa_esa_6.12.18.pdf |
| `nbs/NEBS_2.0_AnexoII_notas_explicativas.pdf` | Anexo II — NEBS 2.0 (notas explicativas) | https://www.gov.br/mdic/pt-br/images/REPOSITORIO/scs/decos/NBS/Anexoa_IIa_NEBSa_2.0a_coma_alteraa_esa_6.12.18.pdf |
| `nbs/NBS_correlacao_1.1_para_2.0.xlsx` | De-para NBS 1.1 → 2.0 | https://www.gov.br/mdic/pt-br/images/REPOSITORIO/scs/decos/NBS/NBSa_DE-PARAa_COMPILADOa_FINALa_05a_deza_2018.xlsx |

Base legal da NBS: Portaria Conjunta RFB/SCS nº 2.000/2018.
Página: https://www.gov.br/mdic/pt-br/assuntos/sdic/comercio-e-servicos/nbs-nomenclatura-brasileira-de-servicos

## 4. NCM — bens

| Arquivo | Documento | Versão | URL |
|---|---|---|---|
| `ncm/siscomex_nomenclatura_ncm.json` | **Nomenclatura Comum do Mercosul (NCM/SH)** — 15.156 códigos com hierarquia e vigência | Vigente em 13/08/2026 — Resolução Gecex nº 926/2026 | https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json |
| `ncm/NFe_Tabela_NCM_uTrib_2026-02-01.xlsx` | Tabela de NCM e respectiva uTrib (comércio exterior) | Vigente a partir de 01/02/2026 | https://www.nfe.fazenda.gov.br/portal/exibirArquivo.aspx?conteudo=b951nG/pOmY= |

O vínculo **NCM → cClassTrib** não vem de uma tabela pronta: ele é derivado dos
**anexos da LC 214/2025** (que listam os NCM de cada regime) combinados com os
cClassTrib que citam esses anexos na tabela do Portal da NF-e. Ver
[`Docs/METODOLOGIA.md`](../Docs/METODOLOGIA.md), seção 6.

## 5. CNAE — IBGE / CONCLA

| Arquivo | Documento | URL |
|---|---|---|
| `cnae/ibge_cnae_subclasses.json` | Subclasses CNAE com seção, divisão, grupo, classe e notas explicativas (1.332 registros) | https://servicodados.ibge.gov.br/api/v2/cnae/subclasses |

## 6. De-para CNAE × item da LC 116/03 (não existe tabela nacional oficial)

| Arquivo | Documento | URL |
|---|---|---|
| `cnae-lc116/Anapolis_PORTARIA-463-25-ANEXO-UNICO-CNAE-x-Lista-Servicos.pdf` | **Portaria 463/2025 — Anexo Único (Anápolis/GO)**, base principal | https://www.anapolis.go.gov.br/wp-content/uploads/2025/06/PORTARIA-463-25-ANEXO-UNICO-Enquadramento-da-Lista-de-Servicos-com-os-CNAEs.pdf |
| `cnae-lc116/Salvador_Cnae_X_Item_Lista_Servicos.pdf` | Tabela CNAE × Lista de Serviços (SEFAZ Salvador/BA) | https://nfse.sefaz.salvador.ba.gov.br/OnLine/Documentos/Cnae_X_Item_Lista_Servicos.pdf |
| `cnae-lc116/BracoDoNorte_TABELA_CNAE_X_ISS.pdf` | Tabela CNAE × LC 116 (Braço do Norte/SC), conferência | https://bracodonorte.sc.gov.br/uploads/sites/297/2023/07/2199998_TABELA_CNAE_X_ISS_BN_pronta.pdf |

> Correlações municipais têm caráter indicativo. Se o município do contribuinte
> publicar tabela própria, ela prevalece — adicione o PDF nesta pasta, cadastre em
> `fontes.json` e crie o parser em `scripts/build_dataset.py`.

## 7. Legislação

| Arquivo | Documento | URL |
|---|---|---|
| `legislacao/LC_214_2025_camara.html` | **LC 214/2025** — institui IBS, CBS e IS (texto atualizado, 668 artigos) | https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-normaatualizada-pl.html |
| `legislacao/LC_116_2003_camara.html` | **LC 116/2003** — ISS e lista de serviços | https://www2.camara.leg.br/legin/fed/leicom/2003/leicomplementar-116-31-julho-2003-492028-normaatualizada-pl.html |

Espelhos do Legin (Câmara dos Deputados) porque `planalto.gov.br` não respondeu
na rede usada na coleta. Referências oficiais equivalentes:
https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm e
https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm
A EC 132/2023 não foi espelhada pelo mesmo motivo:
https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc132.htm

## Como atualizar

```bash
python scripts/atualizar_kb.py --checar
```

Baixa novamente cada fonte e compara o SHA-256; sem `--checar` grava os arquivos.
Depois de qualquer atualização, regenere os datasets:

```bash
python scripts/build_dataset.py
```
