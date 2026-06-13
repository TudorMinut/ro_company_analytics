import json
import time
import urllib.error
import urllib.parse
import urllib.request


CKAN_API = "https://data.gov.ro/api/3/action"


def call_ckan(action: str, params: dict, max_retries: int = 5) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"{CKAN_API}/{action}?{query}"

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "ro-company-analytics/1.0"}
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if not payload.get("success"):
                raise RuntimeError(f"CKAN error: {payload}")

            return payload["result"]

        except urllib.error.HTTPError as exc:
            last_error = exc

            if exc.code in [502, 503, 504]:
                print(f"CKAN temporary error {exc.code}, retry {attempt}/{max_retries}")
                time.sleep(5 * attempt)
                continue

            raise

        except urllib.error.URLError as exc:
            last_error = exc
            print(f"CKAN URL error, retry {attempt}/{max_retries}: {exc}")
            time.sleep(5 * attempt)

    raise RuntimeError(f"CKAN failed after {max_retries} retries: {url}") from last_error


def search_packages(query: str, rows: int = 10) -> list[dict]:
    result = call_ckan(
        "package_search",
        {
            "q": query,
            "rows": rows
        }
    )

    return result.get("results", [])


def get_package(package_id: str) -> dict:
    return call_ckan("package_show", {"id": package_id})


def deduplicate_packages(packages: list[dict]) -> list[dict]:
    seen = set()
    result = []

    for package in packages:
        key = package.get("id") or package.get("name")

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(package)

    return result