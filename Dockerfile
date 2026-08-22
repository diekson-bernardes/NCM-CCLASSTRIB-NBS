# Imagem do Classificador da Reforma Tributaria.
#
# Sobe apenas o necessario para servir: app/, data/ e wsgi.py. A pasta KB (19 MB
# de PDFs e planilhas oficiais) fica fora - ela alimenta o build_dataset.py, que
# roda na maquina do desenvolvedor; o que o site le em producao sao os JSON de
# data/, ja versionados.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# camada separada: so muda quando o requirements muda, o resto do build reaproveita
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY wsgi.py ./
COPY app ./app
COPY data ./data

# usuario sem privilegios; var/ existe para o caso de rodar sem banco (DATABASE_URL
# vazia), quando o cadastro cai nos arquivos JSON
RUN useradd --system --create-home rtc \
    && mkdir -p /app/var \
    && chown -R rtc:rtc /app/var
USER rtc

EXPOSE 8000

# /entrar e a unica tela publica: serve de sinal de vida sem precisar de sessao
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/entrar', timeout=4)"

# UM worker, sempre: analises, consultas de NCM e cesta vivem na memoria do
# processo. Para atender mais gente ao mesmo tempo, aumente as threads.
CMD ["gunicorn", "wsgi:app", "--workers", "1", "--threads", "4", \
     "--timeout", "120", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
