# Publicação da ferramenta (Render)

O GitHub Pages não serve esta aplicação: ele publica só arquivos estáticos e aqui há
Python no servidor (leitura do PDF do cartão CNPJ, geração das planilhas, cesta em
memória). A publicação é feita em um host que executa Python — abaixo, o Render, com
deploy automático a cada `git push`.

## O que já está no repositório

| Arquivo | Papel |
|---|---|
| [`wsgi.py`](../wsgi.py) | ponto de entrada WSGI; carrega os datasets no start |
| [`render.yaml`](../render.yaml) | descreve o serviço (plano, build, start, versão do Python) |
| [`Procfile`](../Procfile) | mesmo comando de start, para hosts que leem Procfile (Railway, Heroku) |
| [`requirements.txt`](../requirements.txt) | Flask, openpyxl, pdfplumber e gunicorn |

Os datasets (`data/*.json`) estão versionados, então o build **não** precisa reprocessar
a pasta `KB` — sobe direto.

## Passo a passo (uma vez)

1. Crie a conta em <https://render.com> e escolha **Get started with GitHub**.
2. No painel: **New → Blueprint**.
3. Autorize o Render a ver o repositório `diekson-bernardes/NCM-CCLASSTRIB-NBS`
   (é privado — na tela de permissões do GitHub marque **Only select repositories** e
   selecione esse).
4. O Render lê o `render.yaml` e propõe o serviço `correlacao-rtc`. Confirme com **Apply**.
5. O primeiro build leva alguns minutos. Ao final, a URL aparece no topo do serviço, no
   formato `https://correlacao-rtc.onrender.com`.

A partir daí, todo `git push` no branch `master` dispara um novo deploy.

## O que esperar do plano gratuito

- **Hibernação:** sem acesso por ~15 minutos o serviço dorme; a visita seguinte demora
  cerca de 1 minuto para responder. Depois disso fica normal.
- **Memória:** 512 MB. Os datasets carregados ocupam algo em torno de 150 MB — cabe, mas
  é o principal limite a observar.
- **Estado em memória:** análises, consultas de NCM e a **cesta** vivem no processo. Cada
  deploy ou hibernação zera a cesta. Se isso incomodar na rotina de trabalho, o caminho é
  persistir em SQLite (ver "Próximos passos" no README).
- **Um worker só:** o `startCommand` usa `--workers 1 --threads 4` justamente por causa
  do estado em memória. Aumentar workers quebraria os downloads de forma intermitente
  (o token cairia em outro processo). Para mais acessos simultâneos, aumente as threads.

## Acesso

O site exige login em todas as telas. Os usuários são `admin` (administrador),
`Cliente` (uso normal) e `Teste` (demonstração, 10 consultas) — detalhes no README.

No painel do Render → **Environment**, defina:

```
RTC_SECRET_KEY   = <string aleatória longa>
RTC_SENHA_ADMIN  = <senha forte>
RTC_SENHA_CLIENTE = <senha forte>
RTC_SENHA_TESTE  = <senha da demonstração>
```

`RTC_SECRET_KEY` faz as sessões sobreviverem a um reinício — sem ela, cada deploy
desconecta quem estava logado. As três senhas substituem as de desenvolvimento sem
alterar o repositório; as senhas nunca ficam no código em texto puro, só como hash.

**Atenção ao plano gratuito:** a contagem de consultas (`var/uso.json`) e os usuários
criados pelo administrador (`var/usuarios.json`) ficam em disco, e o disco do Render free
é efêmero — a cada deploy ou hibernação, a contagem zera e os usuários criados pelo painel
desaparecem (os três de fábrica continuam, pois estão no código). Para que persistam, o
caminho é um banco (Postgres do próprio Render) ou um disco persistente no plano pago.

## Atualizações

- **Código:** `git push` no `master` → deploy automático.
- **Fontes oficiais:** rode localmente `python scripts/atualizar_kb.py --checar`; se algo
  mudou, baixe (sem `--checar`), rode `python scripts/build_dataset.py`, confira os testes
  e faça commit dos arquivos de `KB/` e `data/` alterados. O deploy leva as tabelas novas.

## Se o plano gratuito não servir

- **Render Starter** (pago, mensal): sem hibernação e com mais memória — mesma configuração,
  basta trocar `plan: free` por `plan: starter` no `render.yaml`.
- **Railway / Fly.io:** usam o `Procfile` como está.
- **VPS próprio:** `pip install -r requirements.txt` e
  `gunicorn wsgi:app --workers 1 --threads 4 --bind 0.0.0.0:8000` atrás de um Nginx.
- **Uso interno apenas:** uma rede privada (Tailscale) entre os dispositivos da equipe
  dispensa hospedagem e mantém a ferramenta fora da internet.
