# Imagen del microservicio de extracción PDF → Markdown.
#
# Versión exacta de Python para que todas las réplicas (y todas las
# mediciones) corran sobre el mismo intérprete.
FROM python:3.13.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Primero solo las dependencias: Docker reutiliza esta capa mientras
# requirements.txt no cambie, así un cambio de código no reinstala todo.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/

# El servicio no necesita privilegios de root.
RUN useradd --system --uid 10001 --no-create-home app
USER app

# Port binding (Twelve-Factor, VII): el puerto se configura con PORT.
EXPOSE 8000
CMD ["python", "-m", "pdf_extractor"]
