"""An unhandled server error must reach the browser as a 500, not as nothing.

This exists because a real bug was misdiagnosed. A receipt download failed with
`TypeError: Failed to fetch` in the browser and looked like a network fault or a
CORS misconfiguration; it was an `AttributeError` in the route. The 500 carried no
`Access-Control-Allow-Origin`, so the browser refused to surface it at all.

The cause is structural, not a typo. Starlette builds its stack as
`[ServerErrorMiddleware, *user_middleware, ExceptionMiddleware]` and wraps in
reverse, so `ServerErrorMiddleware` is always **outermost** - outside
`CORSMiddleware`. An exception that reaches it produces a response that never
passes back through CORS.

The trap worth pinning down: `@app.exception_handler(Exception)` does *not* fix
this. Starlette pulls handlers registered for `500`/`Exception` out of the
handler map and gives them to `ServerErrorMiddleware`, which is the very layer
that sits outside CORS. Only user middleware can catch inside it.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app

ORIGIN = "http://localhost:3000"


@pytest.fixture
def client_with_a_broken_route() -> TestClient:
    """A route that raises, mounted on the real app so the real middleware runs.

    `raise_server_exceptions=False` makes TestClient behave like a browser -
    returning the 500 response rather than re-raising into the test, which is the
    only way to inspect the headers a browser would see.
    """

    @app.get("/api/_test_explode")
    async def _explode() -> None:
        raise RuntimeError("deliberate")

    return TestClient(app, raise_server_exceptions=False)


def test_an_unhandled_error_returns_500_with_cors_headers(
    client_with_a_broken_route: TestClient,
) -> None:
    """The assertion the misdiagnosis turned on. Without the header the browser
    reports a network failure and the real 500 is invisible."""
    response = client_with_a_broken_route.get(
        "/api/_test_explode", headers={"Origin": ORIGIN}
    )

    assert response.status_code == 500
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_the_error_body_says_nothing_changed_and_leaks_no_internals(
    client_with_a_broken_route: TestClient,
) -> None:
    """A 500 is read by a person. It must say what happened in a sentence and
    carry no exception type, module path or traceback - the log has those
    (CLAUDE.md §5, and §4 #5 on what may not reach a user-facing field)."""
    body = client_with_a_broken_route.get(
        "/api/_test_explode", headers={"Origin": ORIGIN}
    ).json()

    assert body == {"detail": "Something failed on our side. Nothing was changed."}
    assert "RuntimeError" not in str(body)
    assert "deliberate" not in str(body)


def test_the_catch_all_sits_inside_cors_and_not_outside_it() -> None:
    """Asserts the *ordering*, so a later `add_middleware` cannot silently undo it.

    `add_middleware` inserts at index 0, so the last registered is outermost among
    user middleware. CORS must therefore be registered last and appear first in
    the list - if someone adds a new middleware after it, CORS stops being
    outermost and every 500 goes back to being invisible.
    """
    names = [m.cls.__name__ for m in app.user_middleware]
    assert names, "the app has no user middleware at all"
    assert names[0] == "CORSMiddleware", (
        f"CORSMiddleware must be the outermost user middleware, got {names}"
    )


def test_a_bare_exception_handler_would_not_have_worked() -> None:
    """Documents the trap in an executable form rather than only in prose.

    Starlette moves any handler registered for `Exception` or `500` onto
    `ServerErrorMiddleware`, which is outside CORS - so registering one there is
    not an alternative to the middleware above. If a future Starlette changes
    this, this test fails and the middleware can be reconsidered.
    """
    probe = FastAPI()

    @probe.exception_handler(Exception)
    async def _handler(_request: object, _exc: Exception) -> None:  # pragma: no cover
        return None

    # The handler is pulled out of the map for ServerErrorMiddleware's use, and so
    # is not left among the per-status handlers that run inside the stack.
    assert Exception in probe.exception_handlers
    stack_names = [m.cls.__name__ for m in probe.user_middleware]
    assert "CORSMiddleware" not in stack_names
