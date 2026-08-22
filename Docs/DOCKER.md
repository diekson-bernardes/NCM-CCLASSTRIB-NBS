# Deploy com Docker Compose

Dois contêineres: o site (Flask + gunicorn) e o PostgreSQL onde ficam os usuários
criados no painel e a contagem de consultas. É a forma de publicar em qualquer máquina —
VPS, servidor do escritório ou a própria estação — sem depender do plano gratuito de
nenhum host.

| Arquivo | Papel |
|---|---|
| [`Dockerfile`](../Dockerfile) | imagem do site: Python 3.12, dependências, `app/`, `data/`, gunicorn |
| [`docker-compose.yml`](../docker-compose.yml) | os dois serviços, o volume do banco e as variáveis |
| [`.env.example`](../.env.example) | modelo da configuração; copie para `.env` e preencha |
| [`.dockerignore`](../.dockerignore) | mantém `KB/` (19 MB), testes e docs fora da imagem |

## Subir

```bash
cp .env.example .env      # Windows: copy .env.example .env
# preencha POSTGRES_PASSWORD e RTC_SECRET_KEY; para gerar valores:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up -d --build
```

O site responde em <http://localhost:8000> (mude a porta com `PORTA=` no `.env`). A
primeira subida leva alguns minutos: instala as dependências e carrega os datasets.

`POSTGRES_PASSWORD` e `RTC_SECRET_KEY` são obrigatórias — sem elas o compose para com a
mensagem correspondente, em vez de subir um site com senha em branco.

## Comandos do dia a dia

```bash
docker compose ps                  # estado dos dois serviços (o banco mostra "healthy")
docker compose logs -f site        # log de acesso e erros da aplicação
docker compose restart site        # reiniciar só o site
docker compose down                # parar (o banco e o cadastro permanecem)
docker compose up -d --build       # aplicar uma nova versão do código
```

## O que persiste, e o que não

O cadastro de usuários e a contagem de consultas ficam no volume `dados-banco`, fora dos
contêineres: sobrevivem a `restart`, a `down` e à troca da imagem. Para conferir, abra
**Usuários e uso** no painel do administrador — a etiqueta deve estar em *permanente*,
apontando `banco:5432/correlacao_rtc`.

Já as análises em andamento, as consultas de NCM e a **cesta** vivem na memória do
processo: reiniciar o site as descarta. É a mesma limitação do deploy no Render, e o
motivo do **único worker** no `Dockerfile` — com mais de um, o navegador cairia ora em um
processo, ora em outro, e os downloads falhariam de forma intermitente. Para atender mais
gente ao mesmo tempo aumente `--threads`, não `--workers`, e **não** use
`docker compose up --scale site=N`.

### Backup do cadastro

```bash
docker compose exec banco pg_dump -U rtc correlacao_rtc > backup.sql
```

Restaurar:

```bash
docker compose exec -T banco psql -U rtc correlacao_rtc < backup.sql
```

### Trazer o cadastro que estava em arquivo

Se a ferramenta já rodava fora do Docker, com os usuários em `var/usuarios.json`, monte a
pasta na primeira subida — a aplicação copia o conteúdo para o banco sozinha e depois a
montagem pode sair:

```yaml
    volumes:
      - ./var:/app/var:ro
```

## Rodar sem banco

Não é o recomendado, mas serve para uma demonstração rápida: comente as linhas
`DATABASE_URL` e `depends_on` do serviço `site`. O cadastro volta para
`var/usuarios.json` dentro do contêiner e desaparece quando ele é recriado. O painel passa
a mostrar a etiqueta *temporário*.

## Publicar na internet

O compose expõe HTTP simples na porta 8000. Para um endereço público, coloque um proxy com
TLS na frente (Nginx, Traefik ou Caddy) e então:

1. no `.env`, defina `RTC_ATRAS_DE_PROXY=1` — sem isso a aplicação monta as URLs como
   `http` e marca o cookie da cesta como inseguro;
2. troque `ports:` por `expose: ["8000"]` no serviço `site`, para que só o proxy alcance a
   aplicação;
3. preencha `RTC_SENHA_ADMIN`, `RTC_SENHA_CLIENTE` e `RTC_SENHA_TESTE` — as senhas de
   desenvolvimento (`admin/2026`, `Cliente/Cliente`, `Teste/123`) estão no README e no
   histórico do repositório.

`RTC_ATRAS_DE_PROXY` fica em `0` por padrão de propósito: com `1` e sem proxy, qualquer
cliente poderia forjar os cabeçalhos `X-Forwarded-*`.

## Atualizar as tabelas oficiais

A imagem não carrega a pasta `KB`. O ciclo continua na máquina de desenvolvimento:
`python scripts/atualizar_kb.py --checar`, depois `python scripts/build_dataset.py`, commit
dos arquivos de `data/` e, no servidor, `docker compose up -d --build`.
