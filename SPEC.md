# Spec: Microservicio de extracción PDF → Markdown bajo carga

## Objetivo

Construir el microservicio pedido en el TP "Test de Carga, Estrés y Optimización
de Microservicio" (Desarrollo de Software, UTN FRSR) y superar el benchmark de
referencia de la cátedra con las mismas restricciones de hardware.

**Criterios de aceptación (tomados literalmente de la consigna):**

- `POST /extract` recibe un PDF por `multipart/form-data` **o** como binario
  directo en el body.
- Responde `200 OK`, `application/json`, con `{"content": "<markdown>", "page_count": <int>}`.
- Se empaqueta en una imagen Docker y se levanta con un único comando:
  `docker compose up --build`.
- Escala horizontalmente hasta **5 réplicas**, detrás de un reverse proxy con
  balanceo.
- Cada contenedor tiene **límites explícitos** de CPU y memoria
  (réplicas: 1.0 CPU y 1 GB de RAM como máximo).
- Script **k6** de spike: 0→100 VUs en 10 s, 20 s sostenidos, 100→0 en 10 s.
- Script **Vegeta** de carga fija: 50 req/s durante 30 s (1.500 pedidos),
  rotando los 4 PDFs de prueba, timeout de cliente de 30 s.
- Las pruebas usan la carpeta `tests/stress/pdfs`.
- Twelve-Factor: configuración por variables de entorno, port binding,
  procesos sin estado, logs a stdout.
- Backpressure: si la cola supera su tiempo útil se responde `503` de forma
  controlada (con `Retry-After`) en lugar de dejar que el cliente expire.
- Informe en Markdown con arquitectura, cuello de botella, métricas antes vs.
  después y el proceso de investigación.

**Benchmark a superar (consigna, sección "Benchmark de Referencia"):**

| Prueba | Métrica del profesor |
|---|---|
| k6 spike | 1.037 pedidos, 25,35 req/s, 0 % error, p50 1,88 s, p90 7,83 s, p95 8,80 s, máx 13,94 s |
| Vegeta 50 req/s | 16,65 req/s efectivos, 998/1.500 exitosos (66,53 %), 501 timeouts, p50 14,89 s |

## Supuestos

1. **Stack:** Python 3.13 + Starlette/Uvicorn + MuPDF (a través de los
   bindings que trae PyMuPDF). Se eligió por medición, no por gusto: ver
   `docs/adr/0001-motor-de-extraccion.md`.
2. **Proxy:** HAProxy (la consigna dice "tipo Traefik/Caddy"; se eligió
   HAProxy porque ofrece una cola central con timeout y prioridades).
   Ver `docs/adr/0002-balanceo-y-backpressure.md`.
3. **PDFs de prueba:** hasta tener la carpeta oficial de la cátedra se usan 4
   sustitutos generados por `scripts/generate_test_pdfs.py` con el mismo
   perfil (liviano → 292 páginas → ~9 MB con gráficos y capas).
4. **Markdown:** títulos (`#`), párrafos, listas y negritas cortas. No se
   reconstruyen tablas ni imágenes: el servicio extrae **texto**.
5. **Sin autenticación:** la consigna no la pide.

## Comandos

```
Levantar el sistema:     docker compose up --build
Prueba spike (k6):       docker compose --profile stress run --rm k6
Prueba fija (Vegeta):    docker compose --profile stress run --rm vegeta
Tests:                   python -m pytest
Lint:                    python -m ruff check . && python -m ruff format --check .
Servicio local (dev):    python -m pdf_extractor        (con PYTHONPATH=src)
Comparar con el profe:   python scripts/compare_results.py [--markdown]
Regenerar PDFs:          python scripts/generate_test_pdfs.py
Benchmark de motores:    python scripts/benchmark_extractors.py
Simulación de colas:     python scripts/simulate_queues.py
Gráficos del informe:    python scripts/make_charts.py
```

## Estructura

```
src/pdf_extractor/      Código del microservicio
  api/                  Capa HTTP: rutas, lectura del upload, errores
  extraction/           Dominio: PDF → líneas con estilo → Markdown
  concurrency/          Pool de procesos y control de admisión (backpressure)
  config.py, logs.py    Configuración por entorno y logs JSON a stdout
proxy/                  Configuración de HAProxy (balanceo + cola central)
tests/unit/             Tests rápidos de lógica pura
tests/integration/      Tests de la API con el pool de procesos real
tests/stress/           k6, Vegeta, PDFs de prueba y resultados
scripts/                PDFs de prueba, benchmarks, simulación, comparación y gráficos
docs/                   Informe, ADRs y datos de investigación
```

## Estilo de código

- Identificadores en inglés (coinciden con las librerías y el vocabulario HTTP);
  docstrings, comentarios y documentación en castellano.
- Los comentarios explican el **por qué**, no repiten el código.
- Funciones chicas, módulos con una sola responsabilidad, tipado estático.
- `ruff` para lint y formato.

```python
async def extract(request: Request) -> Response:
    """POST /extract: recibe un PDF y devuelve su contenido en Markdown."""
    pdf = await read_pdf_upload(request, max_bytes=settings.max_upload_bytes)
    async with admission.slot():
        body = await pool.extract(pdf)
    return Response(body, media_type="application/json")
```

## Estrategia de testing

- **Unitarios** (`tests/unit`): conversión a Markdown con datos armados a mano,
  parser de uploads, control de admisión, configuración.
- **Integración** (`tests/integration`): la API completa con `TestClient` y el
  pool de procesos real sobre los PDFs de prueba.
- **Carga** (`tests/stress`): k6 y Vegeta contra el sistema en Docker.

## Límites

- **Siempre:** correr tests y lint antes de dar algo por terminado; medir antes
  y después de cada optimización; registrar los intentos descartados.
- **Preguntar antes:** cambiar el contrato de `/extract`, sumar dependencias
  pesadas, cambiar los límites de hardware.
- **Nunca:** inventar métricas; subir secretos; desactivar tests para que pasen.

## Criterios de éxito

- [x] Tests y lint en verde (86 tests, `ruff` sin advertencias).
- [x] `docker compose up --build` levanta 5 réplicas + proxy con límites (verificado).
- [x] k6 y Vegeta corren con un solo comando y guardan sus resultados.
- [x] k6: más de 25,35 req/s con 0 % de error (medido con los PDFs oficiales:
      mediana de 25,45 req/s, en el límite del ruido; ver informe §6.3).
- [x] Vegeta: más de 66,53 % de éxito y p50 menor a 14,89 s (medido: 98,5–100 %
      y 0,6–1,4 s).
- [x] Informe con métricas medidas (ninguna inventada).

## Preguntas abiertas

- Los números del profesor se midieron en su hardware: para comparar en
  serio hay que correr ambas pruebas en la misma máquina.
- Si la cátedra cambia los PDFs, recalibrar el umbral de "PDF chico" (ADR-0002).
