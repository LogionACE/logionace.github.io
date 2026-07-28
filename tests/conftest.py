"""
Shared fixtures for the LogionACE site tests.

Everything here is offline. The site talks to exactly one external service --
the LogionOS API named in `ace-config.js` -- and these tests never let a request
reach it. Two mechanisms enforce that:

  * `ace-config.js` is served with its API base rewritten to the local test
    server, so the pages under test are same-origin with their API. That is not
    only about blocking egress: a cross-origin fulfilled response would need a
    CORS preflight, and preflights are issued below the level `page.route` can
    intercept.
  * Every request whose host is not loopback is aborted and recorded. A test can
    assert the recording is empty, which is a stronger statement than "no test
    happened to hit the network today".

Chrome is the system Chrome, per the project's testing rules, and the browser
fixture skips rather than fails if that binary cannot be launched -- an
environment without it should report a skip, not a false negative.
"""
from __future__ import annotations

import functools
import http.server
import json
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import pytest

SITE_ROOT = Path(__file__).resolve().parent.parent

# `tools` is a package in the site root, which is not a package itself.
if str(SITE_ROOT) not in sys.path:
    sys.path.insert(0, str(SITE_ROOT))

#: The API base as it ships. Rewritten to the loopback server for browser tests.
API_PLACEHOLDER = "https://logionos-api.onrender.com"

ORDERS_PATH = "/v1/ace/orders"

#: Shapes that `ace-session.js` accepts, restated so a test cannot accidentally
#: prove the flow works using a token the real code would reject.
SAMPLE_ORDER_ID = "aceord_4f1c9b2ad7e35081"
SAMPLE_TOKEN = "Ky7sT2pQ4mVx9bLd0nRf8wZa1cJhE6uY"

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: Pre-existing site chrome: every page links a Google-hosted web font. Blocked
#: like everything else off-machine, but recorded separately, so a test asserting
#: "nothing left the machine" is asserting something about this work rather than
#: re-failing on a font link that predates it. The report carries it as a concern.
FONT_HOSTS = frozenset({"fonts.googleapis.com", "fonts.gstatic.com"})


# -- the static site server -------------------------------------------------

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """`SimpleHTTPRequestHandler` without the per-request logging."""

    def log_message(self, *args: Any) -> None:  # pragma: no cover - noise only
        pass


@pytest.fixture(scope="session")
def site_server() -> str:
    """Serve the worktree over loopback and return its base URL.

    The site is served as files, from this working tree, exactly as GitHub Pages
    would serve them. No build step exists to diverge from.
    """
    handler = functools.partial(_QuietHandler, directory=str(SITE_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# -- the browser ------------------------------------------------------------

@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip(
        "playwright.sync_api", reason="playwright is not installed"
    )
    with sync_api.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch(channel="chrome")
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"system Chrome could not be launched: {exc}")
        try:
            yield instance
        finally:
            instance.close()


class Harness:
    """One page, one loopback origin, and no way out to the internet."""

    def __init__(self, page, base: str) -> None:
        self.page = page
        self.base = base
        #: Requests aborted because they were leaving the machine, excluding the
        #: font hosts every page has linked since before this work.
        self.external_attempts: list[str] = []
        #: Blocked font requests, kept apart so they can be asserted about.
        self.font_attempts: list[str] = []
        #: Every API call the page made, in order, with its body.
        self.api_calls: list[dict] = []
        self.console_errors: list[str] = []
        #: Uncaught exceptions. A blocked font is noise; a thrown error is not.
        self.page_errors: list[str] = []

    # -- navigation --
    def open(self, path: str, fragment: str = "") -> None:
        url = f"{self.base}/{path}"
        if fragment:
            url += "#" + fragment.lstrip("#")
        self.page.goto(url, wait_until="domcontentloaded")

    def status_fragment(
        self, order_id: str = SAMPLE_ORDER_ID, token: str = SAMPLE_TOKEN
    ) -> str:
        return f"order={order_id}&token={token}"

    # -- API stubbing --
    def api(
        self,
        pattern: str,
        *,
        status: int = 200,
        payload: Optional[dict] = None,
        body: Optional[str] = None,
        content_type: str = "application/json",
    ) -> None:
        """Answer `pattern` with a canned response, recording the request."""

        def handler(route) -> None:
            request = route.request
            self.api_calls.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "headers": dict(request.headers),
                    "body": request.post_data,
                }
            )
            route.fulfill(
                status=status,
                content_type=content_type,
                headers={"Cache-Control": "no-store"},
                body=body if body is not None else json.dumps(payload or {}),
            )

        self.page.route(pattern, handler)

    def api_handler(self, pattern: str, handler: Callable[[Any], None]) -> None:
        """Answer `pattern` with a handler of the test's own, still recorded."""

        def wrapped(route) -> None:
            self.api_calls.append(
                {
                    "method": route.request.method,
                    "url": route.request.url,
                    "headers": dict(route.request.headers),
                    "body": route.request.post_data,
                }
            )
            handler(route)

        self.page.route(pattern, wrapped)

    def orders_url(self, suffix: str = "") -> str:
        return f"**{ORDERS_PATH}{suffix}"

    def calls_to(self, path_fragment: str) -> list[dict]:
        return [call for call in self.api_calls if path_fragment in call["url"]]

    def wait_until(
        self, predicate: Callable[[], bool], description: str, timeout_ms: int = 5000
    ) -> None:
        """Wait on something only the test can see, such as a request arriving."""
        waited = 0
        while waited < timeout_ms:
            if predicate():
                return
            self.page.wait_for_timeout(50)
            waited += 50
        raise AssertionError(f"timed out waiting for {description}")

    # -- browser state --
    def session_storage(self) -> dict:
        return self.page.evaluate("() => ({...window.sessionStorage})")

    def local_storage(self) -> dict:
        return self.page.evaluate("() => ({...window.localStorage})")

    def text(self, selector: str) -> str:
        return (self.page.text_content(selector) or "").strip()

    def visible(self, selector: str) -> bool:
        return self.page.is_visible(selector)


@pytest.fixture
def site(browser, site_server):
    """A page whose API base points at the loopback server."""
    context = browser.new_context(viewport={"width": 1280, "height": 960})
    page = context.new_page()
    harness = Harness(page, site_server)

    config_source = (SITE_ROOT / "ace-config.js").read_text("utf-8")
    assert API_PLACEHOLDER in config_source, (
        "ace-config.js no longer names the API base this harness rewrites"
    )
    rewritten = config_source.replace(API_PLACEHOLDER, site_server)

    def guard(route) -> None:
        host = urlparse(route.request.url).hostname
        if host in LOOPBACK_HOSTS:
            route.continue_()
            return
        if host in FONT_HOSTS:
            harness.font_attempts.append(route.request.url)
        else:
            harness.external_attempts.append(route.request.url)
        route.abort()

    # Registered first, so a route a test adds later wins; anything a test did
    # not stub and that is not loopback dies here.
    page.route("**/*", guard)

    def serve_config(route) -> None:
        route.fulfill(
            status=200,
            content_type="application/javascript",
            headers={"Cache-Control": "no-store"},
            body=rewritten,
        )

    page.route("**/ace-config.js", serve_config)

    page.on(
        "console",
        lambda message: harness.console_errors.append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda error: harness.page_errors.append(str(error)))

    try:
        yield harness
    finally:
        context.close()


# -- small helpers used by more than one module -----------------------------

@pytest.fixture(scope="session")
def site_root() -> Path:
    return SITE_ROOT


def read(name: str) -> str:
    return (SITE_ROOT / name).read_text("utf-8")


def html_pages() -> list[Path]:
    return sorted(SITE_ROOT.glob("*.html"))


def site_scripts() -> list[Path]:
    return sorted(SITE_ROOT.glob("*.js"))
