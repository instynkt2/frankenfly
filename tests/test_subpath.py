"""Resolve the real page's URLs as a browser would behind a prefix proxy."""
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse

from fastapi.testclient import TestClient
import pytest

from frankenfly.server import Runtime, create_app


class PageURLs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in {"src", "href"} and value and not value.startswith("https://"):
                self.references.append(value)


@pytest.mark.parametrize("prefix", ["/", "/frankenfly/"])
def test_page_assets_and_api_stay_within_the_mount(prefix, tmp_path):
    # No simulation starts: test the actual static files and API routing only.
    client = TestClient(create_app(Runtime(tmp_path, tmp_path)))
    page = client.get("/")
    assert page.status_code == 200
    parser = PageURLs()
    parser.feed(page.text)
    script = client.get("/assets/app.js").text
    references = parser.references + re.findall(r"fetch\('([^']+)'", script)
    references += re.findall(r"mascot.src = '([^']+)'", script)
    page_url = "https://example.test" + prefix
    assert len(references) >= 10
    for reference in references:
        resolved = urlparse(urljoin(page_url, reference))
        assert resolved.netloc == "example.test"
        assert resolved.path.startswith(prefix), (prefix, reference, resolved.path)
        # This is the path produced by proxy_pass with the trailing URI slash.
        backend_path = "/" + resolved.path[len(prefix):]
        if backend_path == "/api/control":
            assert client.post(backend_path, json={"action": "clear"}).status_code == 401
        elif backend_path == "/api/operator":
            assert client.get(backend_path).status_code == 401
        elif backend_path == "/api/geometry":
            assert client.get(backend_path).status_code == 503
        else:
            assert client.get(backend_path).status_code == 200, reference
