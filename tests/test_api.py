from fastapi.testclient import TestClient

from archdiag.api import app

client = TestClient(app)

NOTES = """External users connect through a firewall to a load balancer using HTTPS on port 443.
The load balancer distributes traffic to two application servers.
"""


def test_health() -> None:
    assert client.get("/health").status_code == 200


def test_example_endpoint() -> None:
    res = client.get("/example")
    assert res.status_code == 200
    assert "firewall" in res.json()["notes"].lower()


def test_generate() -> None:
    res = client.post("/generate", json={"notes": NOTES})
    assert res.status_code == 200
    body = res.json()
    assert body["components"]
    assert body["svg"].startswith("<svg")
    assert "invent" in body["disclaimer"].lower() or "invented" in body["disclaimer"].lower() or "inventing" not in body["disclaimer"].lower()
    names = [c["name"].lower() for c in body["components"]]
    assert any("firewall" in n for n in names)


def test_svg_download() -> None:
    res = client.post("/generate.svg", json={"notes": NOTES})
    assert res.status_code == 200
    assert "svg" in res.headers["content-type"]
    assert res.content.decode().startswith("<svg")
