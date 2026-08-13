# Prompts de manutenção

## 1. Atualizar as tabelas da reforma

> Rode `python scripts/atualizar_kb.py --checar`. Para cada fonte marcada como
> MUDOU, baixe a nova versão, confira se o layout das colunas continua o mesmo
> (principalmente o Anexo VIII, que usa células mescladas), regenere os datasets com
> `python scripts/build_dataset.py`, rode os testes e atualize a versão indicada em
> `KB/fontes.json` e `KB/SOURCES.md`.

Verificar também se saiu versão nova em:

- Anexo VIII / Anexo VII — https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc
- Tabela de cClassTrib — https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=/NJarYc9nus=
- Notas Técnicas da NF-e — https://www.nfe.fazenda.gov.br/portal/listaConteudo.aspx?tipoConteudo=04BIflQt1aY=

## 2. Incluir a tabela CNAE × LC 116 de um município

> Baixe o PDF/planilha da tabela CNAE × lista de serviços do município X para
> `KB/cnae-lc116/`, cadastre a fonte em `KB/fontes.json` (arquivo, título, órgão,
> versão, url, uso), escreva o parser correspondente em `scripts/build_dataset.py`
> (padrão das funções `parse_anapolis` / `parse_salvador`, devolvendo pares
> `(cnae 7 dígitos, item "NN.NN")`), registre-o na lista `fontes` de
> `build_cnae_lc116` e regenere os datasets. Informe quantos vínculos novos entraram
> e quantos CNAEs passaram a ter correlação oficial.

## 3. Revisar os anexos de NCM da LC 214/2025

> Depois de qualquer alteração da LC 214/2025 (ex.: a LC 227/2026 revogou o Anexo
> XIV), rebaixe `KB/legislacao/LC_214_2025_camara.html`, rode
> `python scripts/build_dataset.py` e confira em `data/lc214_anexos.json` a
> contagem de itens por anexo e as referências de NCM extraídas. Verifique em
> especial anexos com layout de três colunas (IV, V, XI, XII, XIII) e o Anexo XVII
> (coluna única). Se surgir um anexo novo, confirme se há cClassTrib citando-o na
> tabela do Portal da NF-e — é isso que liga o anexo ao código.

## 4. Revisar as sugestões por similaridade

> Liste os CNAEs classificados como `servico_sugerido` na análise de um cartão CNPJ,
> compare a descrição do CNAE (e as notas explicativas em `data/cnae.json`) com a
> descrição do item da LC 116 sugerido e diga quais devem virar vínculo fixo. Os
> vínculos confirmados devem ser adicionados como fonte própria de de-para, não
> alterados manualmente em `data/` (que é regenerado).

## 5. Validar um enquadramento específico

> Para o CNAE X: mostre o item da LC 116, os códigos NBS, o indOP e o cClassTrib
> propostos pela ferramenta; confronte com o texto da LC 214/2025 em
> `KB/legislacao/LC_214_2025_camara.html` (artigos citados na coluna LC 214/25 da
> tabela de cClassTrib) e com as notas explicativas da NBS em
> `KB/nbs/NEBS_2.0_AnexoII_notas_explicativas.pdf`. Aponte divergências.
