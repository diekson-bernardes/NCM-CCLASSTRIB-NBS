"""Ponto de entrada para servidores WSGI (Render, Railway, gunicorn, waitress).

    gunicorn wsgi:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT

IMPORTANTE: use apenas UM worker. As analises, as consultas de NCM e a cesta ficam
em memoria do processo; com varios workers o navegador cairia ora em um, ora em
outro, e os downloads passariam a falhar de forma intermitente. Para atender mais
gente ao mesmo tempo aumente as threads, nao os workers.
"""

from __future__ import annotations

from app.dados import base
from app.main import app

# carrega os datasets no start (evita que a primeira visita pague o custo)
base()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
