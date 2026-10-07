# Cómo trabajamos con git

El profesor evalúa también cómo usamos git, así que seguimos estas reglas.

## Ramas y Pull Requests

- **Nadie sube directo a `main`.** Cada cambio va en su rama y entra por Pull
  Request, revisado por otro integrante.
- Nombre de rama: `tipo/nombre-tema`, por ejemplo `feat/maxi-extractor`,
  `fix/rami-timeout-cola`, `docs/lucas-metricas`.
- Un PR hace **una sola cosa**. Si aparece otra mejora en el camino, va en otro PR.
- Antes de pedir revisión: `python -m pytest` y `python -m ruff check .` en verde.

## Commits

Mensajes cortos, en castellano, con el formato
[Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/):

```
feat(extraction): detectar títulos por tamaño relativo de letra
fix(api): responder 413 antes de leer un body demasiado grande
perf(markdown): limpiar caracteres invisibles con str.replace (103 → 24 ms)
docs(informe): agregar resultados de Vegeta
test(admission): cubrir el descarte por tiempo en cola
```

En los cambios de rendimiento, el mensaje lleva el número de antes y después.

## Configurar tu autor (una sola vez por PC)

Para que el historial muestre quién hizo cada cosa, configurá tu nombre y mail
**dentro del repo** (sin `--global` si la PC es compartida):

```bash
git config user.name "Tu Nombre"
```

```bash
git config user.email "tu-mail@ejemplo.com"
```

## Responsables por área

Cada área tiene un responsable que revisa los PRs que la tocan y la explica en
la defensa. Si necesitás cambiar algo de otra área, avisale a su responsable.

| Área | Archivos | Responsable |
|---|---|---|
| Base del proyecto, API, configuración e informe | Raíz (`README.md`, `SPEC.md`, `pyproject.toml`, `requirements*.txt`, `.gitignore`, `.gitattributes`), `src/pdf_extractor/` (`__init__`, `__main__`, `app`, `config`, `logs`), `src/pdf_extractor/api/`, `tests/conftest.py`, `tests/integration/`, `tests/unit/test_config.py`, `test_uploads.py`, `test_read_body.py`, `docs/INFORME.md`, ADR-0004 | Juani |
| Extracción y Markdown | `src/pdf_extractor/extraction/`, `tests/unit/test_markdown.py`, `test_reader.py`, `scripts/benchmark_extractors.py`, `scripts/generate_test_pdfs.py`, datos y gráfico del benchmark, ADR-0001 | Maxi |
| Concurrencia y backpressure | `src/pdf_extractor/concurrency/`, `src/pdf_extractor/worker_tasks.py`, `tests/unit/test_admission.py`, `test_worker_pool.py`, ADR-0003 | Rami |
| Docker, réplicas y HAProxy | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, `proxy/`, ADR-0002 | Facu |
| Pruebas de carga y métricas | `tests/stress/`, `scripts/compare_results.py`, `simulate_queues.py`, `make_charts.py`, sus tests, datos y gráfico de la simulación, `docs/resultados/` | Lucas |

## Fin de línea

`.gitattributes` fuerza LF en todos los archivos de texto. No lo cambies: los
`.sh` y `haproxy.cfg` se ejecutan en contenedores Linux y fallan con CRLF.
