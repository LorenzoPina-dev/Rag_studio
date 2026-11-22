"""Read dataset documents from the connector types offered by the UI.

Access is limited to fetching text/JSON records or extracting text from PDFs:
no user code is executed. Network/object-store clients stay optional; only
``pypdf`` is required for the PDF path (declared in pyproject.toml).
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import logging
import socket
import threading
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from app.components.corpus import normalize_documents
from app.core.config import settings

CONNECTORS = [
    "Local files",
    "S3",
    "Notion",
    "Google Drive",
    "Web crawl",
    "PostgreSQL",
    "REST API",
]

_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".jsonl", ".csv"}
_PDF_SUFFIXES = {".pdf"}
_SUPPORTED_TYPES = {suffix.lstrip(".") for suffix in _TEXT_SUFFIXES | _PDF_SUFFIXES}
_HTTP_CONNECTORS = {"REST API", "Notion", "Google Drive", "Web crawl"}
_MAX_DOCUMENTS = 200
_MAX_PDF_PAGES = 2000
_MAX_PDF_CHARS = 8_000_000
_MAX_REDIRECTS = 3
_FORBIDDEN_LOCAL_FILES = {"provider_settings.json"}


def _is_forbidden_local_file(path: Path) -> bool:
    name = path.name.lower()
    return name in _FORBIDDEN_LOCAL_FILES or name.startswith(".env")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep redirects in _fetch_http so every target can be revalidated."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def urlopen(request: urllib.request.Request, *, timeout: float):
    """Patchable urlopen wrapper that never follows redirects automatically."""
    opener = urllib.request.build_opener(_NoRedirectHandler)
    return opener.open(request, timeout=timeout)


def file_type_of(value: Any) -> str:
    """Normalized file type used by node filters and the dataset inventory."""
    text = str(value or "").split("?", 1)[0].split("#", 1)[0]
    return Path(text).suffix.lower().lstrip(".") or "text"


def _identifier(value: Any, index: int, origin: str) -> str:
    text = str(value).strip() if value not in (None, "") else ""
    if text:
        return text
    digest = hashlib.sha1(f"{origin}:{index}".encode("utf-8")).hexdigest()[:12]
    return f"doc_{digest}"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _pick(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return ""


def _records_to_documents(records: Any, origin: str) -> list[dict[str, str]]:
    if isinstance(records, dict):
        for key in ("documents", "items", "data", "results", "pages"):
            if isinstance(records.get(key), list):
                records = records[key]
                break
        else:
            records = [records]
    if not isinstance(records, list):
        raise ValueError(f"{origin}: expected a JSON list or an object with a documents list")

    documents: list[dict[str, str]] = []
    for index, item in enumerate(records[:_MAX_DOCUMENTS]):
        if not isinstance(item, dict):
            item = {"content": item}
        source = _as_text(_pick(item, ("source", "url", "uri", "path"))) or origin
        documents.append(
            {
                "id": _identifier(_pick(item, ("id", "doc_id", "uuid")), index, origin),
                "title": _as_text(_pick(item, ("title", "name", "heading"))) or f"Document {index + 1}",
                "source": source,
                "content": _as_text(_pick(item, ("content", "text", "body", "description", "value"))),
                "fileType": _as_text(_pick(item, ("fileType", "file_type", "type"))) or file_type_of(source),
            }
        )
    return normalize_documents(documents, origin)


def documents_from_text(filename: str, text: str) -> list[dict[str, str]]:
    """Parse pasted text or a text-based file into normalized documents."""
    origin = filename or "pasted.txt"
    suffix = Path(origin).suffix.lower()
    stripped = text.strip()
    if suffix == ".jsonl":
        records = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        return _records_to_documents(records, origin)
    if suffix == ".json" and stripped:
        try:
            records = json.loads(stripped)
        except json.JSONDecodeError:
            records = [{"content": text}]
        return _records_to_documents(records, origin)
    return _records_to_documents([{"content": text, "source": origin}], origin)


_PDF_LOGGER_NAMES = ("pypdf", "pdfminer")
_pdf_log_lock = threading.RLock()
_pdf_log_depth = 0
_pdf_log_levels: dict[str, int] = {}


@contextmanager
def _quiet_pdf_logging():
    """Silence font-encoding warnings from PDF parsers during extraction only.

    The depth counter keeps concurrent extractions from restoring a stale level.
    """
    global _pdf_log_depth
    with _pdf_log_lock:
        if _pdf_log_depth == 0:
            _pdf_log_levels.clear()
            for name in _PDF_LOGGER_NAMES:
                logger = logging.getLogger(name)
                _pdf_log_levels[name] = logger.level
                logger.setLevel(logging.ERROR)
        _pdf_log_depth += 1
    try:
        yield
    finally:
        with _pdf_log_lock:
            _pdf_log_depth -= 1
            if _pdf_log_depth == 0:
                for name, level in _pdf_log_levels.items():
                    logging.getLogger(name).setLevel(level)
                _pdf_log_levels.clear()


@_quiet_pdf_logging()
def _pdf_documents(data: bytes, name: str, source: str) -> list[dict[str, str]]:
    """Extract the text of one PDF into a single normalized document."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - guarded by pyproject dependency
        raise ValueError("Estrazione PDF non disponibile: installa pypdf (`pip install pypdf`)") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 - malformed PDF surfaces as a clear UI message
        raise ValueError(f"PDF non valido: {name} ({exc})") from exc
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError(f"PDF protetto da password: {name}")

    pages: list[str] = []
    total = 0
    for index, page in enumerate(reader.pages[:_MAX_PDF_PAGES]):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:  # noqa: BLE001 - one broken page must not disappear silently
            raise ValueError(f"Impossibile leggere la pagina {index + 1} di {name}: {exc}") from exc
        if not text:
            continue
        pages.append(text)
        total += len(text)
        if total >= _MAX_PDF_CHARS:
            break
    if not pages:
        raise ValueError(f"Nessun testo estraibile da {name}: PDF scansionato, serve OCR")

    return [
        {
            "id": f"pdf_{hashlib.sha1(source.encode('utf-8')).hexdigest()[:12]}",
            "title": Path(name).stem or name,
            "source": source,
            "content": "\n\n".join(pages),
            "fileType": "pdf",
        }
    ]


def _parse_http_body(body: str, origin: str) -> list[dict[str, str]]:
    try:
        records = json.loads(body)
    except json.JSONDecodeError:
        return _records_to_documents([{"content": body, "source": origin}], origin)
    return _records_to_documents(records, origin)


def _validate_http_target(url: str) -> tuple[str, int]:
    """Return (port-effective host, port) after SSRF checks on every redirect hop."""
    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Inserisci un URL http:// o https:// per questo connettore")
    if parsed.username or parsed.password:
        raise ValueError("URL con credenziali inline non consentite per questo connettore")
    host = parsed.hostname
    if not host:
        raise ValueError("URL senza host valido per questo connettore")
    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("Porta non valida nell'URL del connettore") from exc

    if not settings.allow_private_connectors:
        try:
            resolutions = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ValueError(f"Impossibile risolvere l'host del connettore: {host}") from exc
        for info in resolutions:
            address = info[4][0].split("%", 1)[0]
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                continue
            if (
                not ip.is_global
                or ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise ValueError(f"Host non consentito per il connettore HTTP: {host}")
    return host.lower(), port


def _fetch_http(path: str, connection: dict[str, Any]) -> list[dict[str, str]]:
    url = str(path or connection.get("url") or "").strip()
    _validate_http_target(url)

    headers = connection.get("headers") or {}
    if isinstance(headers, str):
        headers = json.loads(headers or "{}")
    outgoing = {str(key): str(value) for key, value in headers.items()}
    original_target: tuple[str, int] | None = None

    for _ in range(_MAX_REDIRECTS + 1):
        target = _validate_http_target(url)
        if original_target is None:
            original_target = target
        # Credentials follow the original host/port only: never leak them cross-host.
        request_headers = dict(outgoing) if target == original_target else {}
        request = urllib.request.Request(url, headers=request_headers)
        with urlopen(request, timeout=15) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Redirect HTTP senza header Location")
                url = urljoin(url, location)
                continue
            if status is None or not 200 <= status < 300:
                raise ValueError(f"Richiesta HTTP non riuscita (status {status})")
            body = response.read(5_000_000).decode("utf-8", errors="replace")
        return _parse_http_body(body, url)
    raise ValueError(f"Troppi redirect HTTP (massimo {_MAX_REDIRECTS})")


def _resolve_local_path(path: str) -> Path:
    """Resolve a local connector path and refuse anything outside allowed roots."""
    source = Path(path).expanduser().resolve()
    allowed = [Path(root).expanduser().resolve() for root in settings.dataset_allowed_roots]
    if not any(source.is_relative_to(root) for root in allowed):
        raise ValueError(f"Percorso locale non consentito: {path}")
    return source


def _fetch_local(path: str) -> list[dict[str, str]]:
    source = _resolve_local_path(path)
    if not source.exists():
        raise ValueError(f"Percorso locale non trovato: {path}")
    if source.is_file() and _is_forbidden_local_file(source):
        raise ValueError(f"File di configurazione non consentito per il connettore locale: {source.name}")
    files = (
        [source]
        if source.is_file()
        else sorted(p for p in source.iterdir() if p.is_file() and not _is_forbidden_local_file(p))
    )
    documents: list[dict[str, str]] = []
    for file in files[:_MAX_DOCUMENTS]:
        suffix = file.suffix.lower()
        if suffix in _PDF_SUFFIXES:
            documents.extend(_pdf_documents(file.read_bytes(), file.name, str(file)))
        elif suffix in _TEXT_SUFFIXES:
            documents.extend(documents_from_text(file.name, file.read_text(encoding="utf-8", errors="replace")))
    if not documents:
        raise ValueError(f"Nessun documento di testo o PDF trovato in {path}")
    return documents


def _fetch_s3(path: str, connection: dict[str, Any]) -> list[dict[str, str]]:
    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise ValueError("Il connettore S3 richiede il pacchetto minio") from exc

    bucket, _, prefix = str(path or "").removeprefix("s3://").partition("/")
    bucket = str(connection.get("bucket") or bucket)
    prefix = str(connection.get("prefix") or prefix)
    endpoint = str(connection.get("endpoint") or "").strip()
    if not (bucket and endpoint and connection.get("accessKey") and connection.get("secretKey")):
        raise ValueError("Per S3 servono bucket, endpoint, accessKey e secretKey")

    client = Minio(
        endpoint,
        access_key=str(connection["accessKey"]),
        secret_key=str(connection["secretKey"]),
        secure=bool(connection.get("secure", False)),
    )
    documents: list[dict[str, str]] = []
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        if len(documents) >= _MAX_DOCUMENTS:
            break
        name = obj.object_name or ""
        is_pdf = name.lower().endswith(".pdf")
        limit = 50_000_000 if is_pdf else 2_000_000
        if not name or (obj.size or 0) > limit:
            continue
        response = client.get_object(bucket, name)
        try:
            payload = response.read()
        finally:
            response.close()
            response.release_conn()
        uri = f"s3://{bucket}/{name}"
        if is_pdf:
            documents.extend(_pdf_documents(payload, name, uri))
        else:
            for document in documents_from_text(name, payload.decode("utf-8", errors="replace")):
                document["source"] = uri
                documents.append(document)
    if not documents:
        raise ValueError(f"Nessun documento trovato in s3://{bucket}/{prefix}")
    return documents


def _fetch_postgres(path: str, connection: dict[str, Any]) -> list[dict[str, str]]:
    try:
        from sqlalchemy import create_engine, text as sql_text
    except ImportError as exc:  # pragma: no cover - declared dependency
        raise ValueError("Il connettore PostgreSQL richiede SQLAlchemy") from exc

    dsn = str(connection.get("dsn") or path or "").strip()
    if not dsn.startswith(("postgresql://", "postgres+psycopg://", "postgresql+psycopg://")):
        raise ValueError("Inserisci una connection string PostgreSQL valida")
    query = str(connection.get("query") or "SELECT id, title, source, content FROM documents LIMIT 200")
    engine = create_engine(dsn)
    try:
        with engine.connect() as sql_connection:
            rows = sql_connection.execute(sql_text(query)).mappings().all()
    finally:
        engine.dispose()
    return _records_to_documents([dict(row) for row in rows], dsn)


def files_from_documents(documents: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Build the inventory shown in the UI before any node filtering."""
    return [
        {
            "id": item["id"],
            "name": item["title"],
            "path": item["source"],
            "fileType": item.get("fileType") or file_type_of(item["source"]),
            "size": len(item.get("content", "")),
            "indexed": True,
        }
        for item in documents[:_MAX_DOCUMENTS]
    ]


def inspect_local_files(path: str) -> list[dict[str, Any]]:
    """List every file in a local folder, including types we cannot parse."""
    source = _resolve_local_path(path)
    if not source.exists():
        raise ValueError(f"Percorso locale non trovato: {path}")
    if source.is_file() and _is_forbidden_local_file(source):
        raise ValueError(f"File di configurazione non consentito per il connettore locale: {source.name}")
    files = (
        [source]
        if source.is_file()
        else sorted(p for p in source.iterdir() if p.is_file() and not _is_forbidden_local_file(p))
    )
    inventory: list[dict[str, Any]] = []
    for file in files[:_MAX_DOCUMENTS]:
        file_type = file_type_of(file.name)
        inventory.append(
            {
                "id": hashlib.sha1(str(file).encode("utf-8")).hexdigest()[:12],
                "name": file.name,
                "path": str(file),
                "fileType": file_type,
                "size": file.stat().st_size,
                "indexed": file_type in _SUPPORTED_TYPES,
            }
        )
    return inventory


def inspect_s3_files(path: str, connection: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List S3 objects from metadata only, without downloading their content."""
    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover - depends on optional runtime install
        raise ValueError("Il connettore S3 richiede il pacchetto minio") from exc

    connection = connection or {}
    bucket, _, prefix = str(path or "").removeprefix("s3://").partition("/")
    bucket = str(connection.get("bucket") or bucket)
    prefix = str(connection.get("prefix") or prefix)
    endpoint = str(connection.get("endpoint") or "").strip()
    if not (bucket and endpoint and connection.get("accessKey") and connection.get("secretKey")):
        raise ValueError("Per S3 servono bucket, endpoint, accessKey e secretKey")

    client = Minio(
        endpoint,
        access_key=str(connection["accessKey"]),
        secret_key=str(connection["secretKey"]),
        secure=bool(connection.get("secure", False)),
    )
    inventory: list[dict[str, Any]] = []
    for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
        name = obj.object_name or ""
        if not name or name.endswith("/"):
            continue  # directory markers are not files
        uri = f"s3://{bucket}/{name}"
        file_type = file_type_of(name)
        inventory.append(
            {
                "id": hashlib.sha1(uri.encode("utf-8")).hexdigest()[:12],
                "name": Path(name).name,
                "path": uri,
                "fileType": file_type,
                "size": int(obj.size or 0),
                "indexed": file_type in _SUPPORTED_TYPES,
            }
        )
        if len(inventory) >= _MAX_DOCUMENTS:
            break
    return inventory


def scan_files(
    source_type: str,
    path: str,
    connection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a connector inventory without extracting document text.

    Local files and S3 are listed from metadata alone, so sync stays fast even
    for huge PDF corpora. Record-based connectors have no file listing API: they
    still fetch their (small) JSON payload to derive an inventory, but the text
    is never cached on the dataset.
    """
    if source_type == "Local files":
        return inspect_local_files(path)
    if source_type == "S3":
        return inspect_s3_files(path, connection)
    return files_from_documents(fetch_documents(source_type, path, connection))


def fetch_documents(source_type: str, path: str, connection: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Fetch documents for a connector. Inline documents bypass this function."""
    connection = connection or {}
    if source_type in _HTTP_CONNECTORS:
        return _fetch_http(path, connection)
    if source_type == "Local files":
        return _fetch_local(path)
    if source_type == "S3":
        return _fetch_s3(path, connection)
    if source_type == "PostgreSQL":
        return _fetch_postgres(path, connection)
    raise ValueError(f"Connettore non supportato: {source_type}")
