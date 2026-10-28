"""Import the FastAPI app in its own process and print facts about it as ONE JSON line.

Run with the API folder as the working directory (tests/helpers.py run_probe does this):
    python tests/api_probe.py routes
    python tests/api_probe.py get /ping /departments
The app's startup event is NOT run, so nothing is written to MySQL.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())

import main  # noqa: E402  (certificate_manager_api/main.py)


def _walk_routes(routes, found: list) -> None:
    from fastapi.routing import APIRoute
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            # FastAPI >= 0.137 keeps include_router() lazy: one entry that holds the router's routes
            _walk_routes(route.effective_candidates(), found)
        elif isinstance(route, APIRoute) or type(route).__name__ == "_EffectiveRouteContext":
            for method in sorted(route.methods):
                found.append([method, route.path])


def list_routes() -> list:
    found = []
    _walk_routes(main.app.routes, found)
    return found


def get_paths(paths: list) -> dict:
    from fastapi.testclient import TestClient
    client = TestClient(main.app)  # no "with": the startup event (init_db) must not run
    result = {}
    for path in paths:
        response = client.get(path)
        try:
            body = response.json()
        except ValueError:
            body = response.text
        result[path] = {"status": response.status_code, "json": body}
    return result


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "routes":
        output = list_routes()
    elif command == "get":
        output = get_paths(sys.argv[2:])
    else:
        raise SystemExit(f"unknown command {command}")
    print(json.dumps(output, ensure_ascii=True, default=str))
