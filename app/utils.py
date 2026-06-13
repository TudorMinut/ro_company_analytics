import re
import unicodedata
import urllib.parse
from pathlib import PurePosixPath


ALLOWED_FORMATS = {"CSV", "TXT", "ZIP", "XLS", "XLSX"}


def safe_name(value: str) -> str:
    value = value or "unknown"
    value = value.lower().strip()
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    return value.strip("_") or "unknown"


def safe_metadata_value(value) -> str:
    if value is None:
        return ""

    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text[:2000]


def format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "unknown"

    size = float(num_bytes)

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} PB"


def get_filename(resource: dict) -> str:
    url = resource.get("url", "")
    parsed_path = urllib.parse.urlparse(url).path
    filename = PurePosixPath(parsed_path).name

    if not filename or "." not in filename:
        name = resource.get("name") or resource.get("id") or "resource"
        fmt = (resource.get("format") or "dat").lower().lstrip(".")
        filename = f"{name}.{fmt}"

    return safe_name(filename)


def get_resource_format(resource: dict, filename: str) -> str:
    resource_format = (resource.get("format") or "").upper().strip().lstrip(".")

    if resource_format:
        return resource_format

    suffix = PurePosixPath(filename).suffix.upper().strip().lstrip(".")
    return suffix


def resource_matches(filename: str, patterns: list[str]) -> bool:
    if not patterns:
        return True

    return any(re.search(pattern, filename, re.IGNORECASE) for pattern in patterns)


def is_allowed_resource(resource: dict, filename: str) -> bool:
    resource_format = get_resource_format(resource, filename)

    if not resource_format:
        return True

    return resource_format in ALLOWED_FORMATS


def extract_web_uu_year(filename: str) -> str | None:
    patterns = [
        r"web_uu_an(\d{4})\.(txt|csv)$",
        r"webuuan(\d{4})\.(txt|csv)$",
        r"webuu(\d{4})\.(txt|csv)$",
        r"web_uu_(\d{4})\.(txt|csv)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1)

    return None