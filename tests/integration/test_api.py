"""Tests de la API completa: HTTP + control de admisión + pool de procesos real."""

import asyncio
import logging

import httpx
import pytest
from starlette.testclient import TestClient

from pdf_extractor.app import create_app
from pdf_extractor.config import Settings

REPORT = (("Informe de carga", 22), ("Resultados de la prueba con texto de cuerpo suficiente.", 11))


@pytest.fixture(scope="module")
def client():
    # Un solo servicio (con sus procesos worker) para todo el módulo: levantar
    # workers lleva alrededor de un segundo y no hace falta repetirlo.
    with TestClient(create_app(Settings(max_upload_mb=1))) as test_client:
        yield test_client


def test_binary_upload_returns_markdown_and_page_count(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT, pages=3), headers={"Content-Type": "application/pdf"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "content": "# Informe de carga\n\nResultados de la prueba con texto de cuerpo suficiente.",
        "page_count": 3,
    }


def test_multipart_upload_gives_the_same_result_as_binary(client, build_pdf):
    pdf = build_pdf(*REPORT)

    binary = client.post("/extract", content=pdf, headers={"Content-Type": "application/pdf"})
    multipart = client.post("/extract", files={"file": ("informe.pdf", pdf, "application/pdf")})

    assert multipart.status_code == 200
    assert multipart.json() == binary.json()


def test_upload_without_content_type_is_treated_as_binary(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT))

    assert response.status_code == 200


def test_any_non_multipart_content_type_is_treated_as_binary(client, build_pdf):
    # Es lo que manda "curl --data-binary @archivo.pdf" si no se agrega -H.
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = client.post("/extract", content=build_pdf(*REPORT), headers=headers)

    assert response.status_code == 200


def test_response_reports_queue_and_extraction_time(client, build_pdf):
    response = client.post("/extract", content=build_pdf(*REPORT))

    assert response.headers["server-timing"].startswith("queue;dur=")


@pytest.mark.parametrize(
    ("body", "content_type", "status", "code"),
    [
        pytest.param(b"", "application/pdf", 400, "EMPTY_BODY", id="vacio"),
        pytest.param(b'{"pdf": "no"}', "application/json", 422, "INVALID_PDF", id="json"),
        pytest.param(b"esto no es un PDF", "application/pdf", 422, "INVALID_PDF", id="sin-firma"),
        pytest.param(b"%PDF-1.7 contenido roto", "application/pdf", 422, "INVALID_PDF", id="pdf-roto"),
        pytest.param(b"%PDF-" + b"0" * (2 * 1024 * 1024), "application/pdf", 413, "PAYLOAD_TOO_LARGE", id="2MB"),
    ],
)
def test_invalid_requests_get_a_json_error(client, body, content_type, status, code):
    response = client.post("/extract", content=body, headers={"Content-Type": content_type})

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_wrong_method_also_gets_a_json_error(client):
    response = client.get("/extract")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.headers["allow"] == "POST"


def test_health_reports_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "running": 0, "waiting": 0}


def test_each_request_is_logged_with_its_extraction_data(client, build_pdf, caplog):
    with caplog.at_level(logging.INFO, logger="pdf_extractor.access"):
        client.post("/extract", content=build_pdf(*REPORT, pages=2))

    (record,) = [r for r in caplog.records if r.name == "pdf_extractor.access"]
    assert record.fields["status"] == 200
    assert record.fields["page_count"] == 2
    assert {"queue_ms", "extract_ms", "duration_ms"} <= record.fields.keys()


def test_overloaded_service_answers_503_instead_of_queueing(long_pdf):
    """Con 1 worker y cola 0, de dos pedidos simultáneos uno se procesa y
    el otro se rechaza en el momento con 503 + Retry-After."""
    app = create_app(Settings(extraction_workers=1, max_queue_size=0))

    async def two_simultaneous_requests():
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=60) as http:
                return await asyncio.gather(
                    http.post("/extract", content=long_pdf),
                    http.post("/extract", content=long_pdf),
                )

    responses = asyncio.run(two_simultaneous_requests())

    assert sorted(response.status_code for response in responses) == [200, 503]
    rejected = next(response for response in responses if response.status_code == 503)
    assert rejected.headers["retry-after"] == "2"
    assert rejected.json()["error"]["code"] == "SERVICE_OVERLOADED"
