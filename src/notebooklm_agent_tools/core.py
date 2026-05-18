from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


class NotebookLMCommandError(RuntimeError):
    def __init__(self, command: list[str], message: str, returncode: int | None = None) -> None:
        super().__init__(message)
        self.command = command
        self.returncode = returncode


@dataclass
class SourceRecord:
    index: int
    source_id: str
    title: str
    source_type: str
    url: str | None
    created_at: str | None
    status: str | None

    @classmethod
    def from_manifest_entry(cls, source: dict[str, object]) -> "SourceRecord":
        return cls(
            index=int(source.get("index", 0)),
            source_id=str(source["id"]),
            title=str(source.get("title") or source["id"]),
            source_type=str(source.get("type") or "unknown"),
            url=str(source["url"]) if source.get("url") else None,
            created_at=str(source["created_at"]) if source.get("created_at") else None,
            status=str(source["status"]) if source.get("status") else None,
        )

    @property
    def normalized_type(self) -> str:
        raw = self.source_type.split(".")[-1]
        return raw.upper()

    def to_json(self) -> dict[str, object]:
        return {
            "index": self.index,
            "id": self.source_id,
            "title": self.title,
            "type": self.source_type,
            "normalized_type": self.normalized_type,
            "url": self.url,
            "created_at": self.created_at,
            "status": self.status,
        }


def slugify(text: str) -> str:
    value = SLUG_RE.sub("-", text.strip().replace("/", " ")).strip("-").lower()
    return value or "notebook"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_output_root() -> Path:
    return repo_root() / "notebooklm-output"


def default_artifact_output_root() -> Path:
    return default_output_root() / "artifacts"


def default_source_file_output_root() -> Path:
    return default_output_root() / "source-files"


def resolve_notebooklm_binary() -> str:
    env_binary = os.environ.get("NLM_NOTEBOOKLM_BIN")
    if env_binary:
        return env_binary

    candidates = [
        repo_root() / ".venv" / "bin" / "notebooklm",
        repo_root() / "venv" / "bin" / "notebooklm",
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    found = shutil.which("notebooklm")
    if found:
        return found

    raise FileNotFoundError(
        "Could not find the upstream 'notebooklm' CLI. "
        "Run ./scripts/bootstrap.sh or set NLM_NOTEBOOKLM_BIN."
    )


def run_notebooklm(
    args: list[str],
    *,
    capture_output: bool = False,
    text: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [resolve_notebooklm_binary(), *args]
    try:
        return subprocess.run(command, capture_output=capture_output, text=text, check=check)
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip() or f"Command failed with exit code {exc.returncode}."
        raise NotebookLMCommandError(command, details, returncode=exc.returncode) from exc


@dataclass
class SourceExportError:
    index: int
    source_id: str
    title: str
    returncode: int
    stderr: str

    def to_json(self) -> dict[str, object]:
        return {
            "index": self.index,
            "id": self.source_id,
            "title": self.title,
            "returncode": self.returncode,
            "stderr": self.stderr,
        }


def normalize_source_type(value: str) -> str:
    return value.strip().upper().replace("-", "_")


def load_source_manifest(notebook_id: str | None = None) -> dict[str, object]:
    args = ["source", "list", "--json"]
    if notebook_id:
        args.extend(["--notebook", notebook_id])
    result = run_notebooklm(args, capture_output=True)
    return json.loads(result.stdout)


def source_records_from_manifest(
    manifest: dict[str, object],
    *,
    type_filter: str | None = None,
    limit: int | None = None,
) -> list[SourceRecord]:
    records = [SourceRecord.from_manifest_entry(source) for source in manifest.get("sources", [])]
    if type_filter:
        normalized_filter = normalize_source_type(type_filter)
        records = [record for record in records if record.normalized_type == normalized_filter]
    if limit is not None:
        records = records[:limit]
    return records


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def select_output_dir(manifest: dict[str, object], explicit_output: Path | None) -> Path:
    if explicit_output is not None:
        return explicit_output

    notebook_title = str(manifest.get("notebook_title") or manifest.get("notebook_id") or "notebook")
    return default_output_root() / slugify(notebook_title)


def infer_extension_from_url_and_content_type(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix:
        return suffix

    if content_type:
        mime = content_type.split(";", 1)[0].strip().lower()
        guessed = mimetypes.guess_extension(mime)
        if guessed:
            return guessed

    return ".bin"


def arxiv_pdf_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc not in {"arxiv.org", "www.arxiv.org"}:
        return url

    path = parsed.path
    if path.startswith("/pdf/"):
        return url if path.endswith(".pdf") else f"https://arxiv.org{path}.pdf"
    if path.startswith("/abs/"):
        identifier = path[len("/abs/") :]
        return f"https://arxiv.org/pdf/{identifier}.pdf"
    if path.startswith("/html/"):
        identifier = path[len("/html/") :]
        return f"https://arxiv.org/pdf/{identifier}.pdf"
    return url


def select_source_download_url(record: SourceRecord) -> str | None:
    if not record.url:
        return None
    if "arxiv.org" in record.url and (
        "/abs/" in record.url or "/html/" in record.url or "/pdf/" in record.url
    ):
        return arxiv_pdf_url(record.url)
    return record.url


def fetch_url_to_file(url: str, destination: Path) -> tuple[int | None, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "notebooklm-agent-tools/0.1",
            "Accept": "*/*",
        },
    )
    with urlopen(request) as response:
        status = getattr(response, "status", None)
        content_type = response.headers.get("Content-Type")
        data = response.read()
        destination.write_bytes(data)
        return status, content_type


def export_sources(
    *,
    notebook_id: str | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    stream: bool = True,
) -> Path:
    manifest = load_source_manifest(notebook_id=notebook_id)
    records = source_records_from_manifest(manifest, limit=limit)

    target_dir = select_output_dir(manifest, output_dir)
    ensure_dir(target_dir)

    write_text(target_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    errors: list[SourceExportError] = []
    total = len(records)

    for index, record in enumerate(records, start=1):
        source_id = record.source_id
        title = record.title
        source_slug = slugify(title)[:90]
        source_file = target_dir / f"{index:03d}-{source_slug}-{source_id}.txt"

        if resume and source_file.exists() and source_file.stat().st_size > 0:
            if stream and (index % 10 == 0 or index == total):
                print(f"Skipped existing {index}/{total}")
            continue

        cmd = ["source", "fulltext", source_id, "--output", str(source_file)]
        if notebook_id:
            cmd.extend(["--notebook", notebook_id])

        try:
            run_notebooklm(cmd, capture_output=True)
        except NotebookLMCommandError as exc:
            stderr = str(exc)[-4000:]
            errors.append(
                SourceExportError(
                    index=index,
                    source_id=source_id,
                    title=title,
                    returncode=exc.returncode or 1,
                    stderr=stderr,
                )
            )
            write_text(
                source_file,
                (
                    f"ERROR exporting source fulltext\n\n"
                    f"source_id: {source_id}\n"
                    f"title: {title}\n\n"
                    f"{stderr}\n"
                ),
            )

        if stream and (index % 10 == 0 or index == total):
            print(f"Exported {index}/{total}")
            sys.stdout.flush()

    readme = (
        f"# NotebookLM Source Export\n\n"
        f"Notebook title: {manifest.get('notebook_title', 'unknown')}\n\n"
        f"This directory contains a bulk export of NotebookLM full indexed text.\n\n"
        f"- `manifest.json`: notebook and source metadata\n"
        f"- `errors.json`: export failures, if any\n"
        f"- `*.txt`: one fulltext export per source\n\n"
        f"These `.txt` files represent NotebookLM-indexed content, not guaranteed original binaries.\n"
    )
    write_text(target_dir / "README.md", readme)
    write_text(
        target_dir / "errors.json",
        json.dumps([error.to_json() for error in errors], indent=2, ensure_ascii=False),
    )

    return target_dir


def download_artifacts(
    *,
    artifact_type: str,
    notebook_id: str | None = None,
    output_path: Path | None = None,
    selector: str = "latest",
    name: str | None = None,
    artifact_id: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_clobber: bool = False,
    json_output: bool = False,
    format_name: str | None = None,
) -> subprocess.CompletedProcess[str]:
    args = ["download", artifact_type]
    if notebook_id:
        args.extend(["--notebook", notebook_id])

    if selector == "all":
        args.append("--all")
    elif selector == "earliest":
        args.append("--earliest")
    else:
        args.append("--latest")

    if name:
        args.extend(["--name", name])
    if artifact_id:
        args.extend(["--artifact", artifact_id])
    if json_output:
        args.append("--json")
    if dry_run:
        args.append("--dry-run")
    if force:
        args.append("--force")
    if no_clobber:
        args.append("--no-clobber")
    if format_name:
        args.extend(["--format", format_name])

    if output_path is None:
        output_path = default_artifact_output_root() / artifact_type
    if selector == "all":
        ensure_dir(output_path)
    else:
        ensure_dir(output_path.parent)
    args.append(str(output_path))

    return run_notebooklm(args, capture_output=json_output)


def fetch_source_files(
    *,
    notebook_id: str | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    stream: bool = True,
) -> Path:
    manifest = load_source_manifest(notebook_id=notebook_id)
    url_sources = [record for record in source_records_from_manifest(manifest) if record.url]
    if limit is not None:
        url_sources = url_sources[:limit]

    notebook_title = str(manifest.get("notebook_title") or manifest.get("notebook_id") or "notebook")
    target_dir = output_dir or (default_source_file_output_root() / slugify(notebook_title))
    ensure_dir(target_dir)

    write_text(target_dir / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    errors: list[dict[str, object]] = []
    downloaded: list[dict[str, object]] = []
    total = len(url_sources)

    for index, record in enumerate(url_sources, start=1):
        source_id = record.source_id
        title = record.title
        url = select_source_download_url(record) or ""
        source_slug = slugify(title)[:90]
        meta_path = target_dir / f"{index:03d}-{source_slug}-{source_id}.json"

        if resume and meta_path.exists():
            if stream and (index % 10 == 0 or index == total):
                print(f"Skipped existing {index}/{total}")
                sys.stdout.flush()
            continue

        try:
            temp_path = target_dir / f"{index:03d}-{source_slug}-{source_id}.download"
            status, content_type = fetch_url_to_file(url, temp_path)
            extension = infer_extension_from_url_and_content_type(url, content_type)
            data_path = target_dir / f"{index:03d}-{source_slug}-{source_id}{extension}"
            if data_path.exists():
                data_path.unlink()
            temp_path.rename(data_path)

            meta = {
                "index": index,
                "id": source_id,
                "title": title,
                "url": url,
                "type": record.source_type,
                "http_status": status,
                "content_type": content_type,
                "path": data_path.name,
            }
            write_text(meta_path, json.dumps(meta, indent=2, ensure_ascii=False))
            downloaded.append(meta)
        except Exception as exc:
            error = {
                "index": index,
                "id": source_id,
                "title": title,
                "url": url,
                "error": str(exc),
            }
            errors.append(error)
            write_text(meta_path, json.dumps(error, indent=2, ensure_ascii=False))

        if stream and (index % 10 == 0 or index == total):
            print(f"Fetched {index}/{total}")
            sys.stdout.flush()

    readme = (
        f"# NotebookLM Source File Fetch\n\n"
        f"Notebook title: {notebook_title}\n\n"
        f"This directory contains best-effort downloads of original source URLs.\n\n"
        f"- `manifest.json`: notebook and source metadata from NotebookLM\n"
        f"- `downloads.json`: successfully fetched source file records\n"
        f"- `errors.json`: failed URL fetches\n"
        f"- `*.json`: per-source fetch metadata\n\n"
        f"Only sources with a URL can be fetched this way. Uploaded local NotebookLM sources without a public URL cannot be reconstructed here.\n"
    )
    write_text(target_dir / "README.md", readme)
    write_text(target_dir / "downloads.json", json.dumps(downloaded, indent=2, ensure_ascii=False))
    write_text(target_dir / "errors.json", json.dumps(errors, indent=2, ensure_ascii=False))
    return target_dir


def source_list(
    *,
    notebook_id: str | None = None,
    type_filter: str | None = None,
    limit: int | None = None,
) -> list[SourceRecord]:
    manifest = load_source_manifest(notebook_id=notebook_id)
    return source_records_from_manifest(manifest, type_filter=type_filter, limit=limit)


def source_fulltext(
    source_id: str,
    *,
    notebook_id: str | None = None,
    output_path: Path,
) -> None:
    cmd = ["source", "fulltext", source_id, "--output", str(output_path)]
    if notebook_id:
        cmd.extend(["--notebook", notebook_id])
    run_notebooklm(cmd, capture_output=True)


def download_source_bundle(
    *,
    notebook_id: str | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    type_filter: str | None = None,
    stream: bool = True,
) -> Path:
    manifest = load_source_manifest(notebook_id=notebook_id)
    records = source_records_from_manifest(manifest, type_filter=type_filter, limit=limit)
    target_dir = select_output_dir(manifest, output_dir)
    ensure_dir(target_dir)

    run_manifest: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    total = len(records)

    for index, record in enumerate(records, start=1):
        source_slug = slugify(record.title)[:90]
        strategy = "fulltext"
        local_name = None
        status = "ok"
        effective_url = select_source_download_url(record)

        if record.normalized_type == "MARKDOWN":
            extension = ".md"
            strategy = "fulltext-markdown"
        elif record.normalized_type == "PDF" and effective_url:
            extension = ".pdf"
            strategy = "download-pdf"
        elif record.normalized_type == "WEB_PAGE" and effective_url:
            extension = ".html"
            strategy = "download-webpage"
        elif effective_url:
            extension = infer_extension_from_url_and_content_type(effective_url, None)
            strategy = "download-url"
        else:
            extension = ".txt"
            strategy = "fulltext-text"

        target_file = target_dir / f"{index:03d}-{source_slug}-{record.source_id}{extension}"
        local_name = target_file.name

        if resume and target_file.exists() and target_file.stat().st_size > 0:
            run_manifest.append(
                {
                    **record.to_json(),
                    "strategy": strategy,
                    "local_filename": local_name,
                    "status": "skipped-existing",
                    "effective_url": effective_url,
                }
            )
            if stream and (index % 10 == 0 or index == total):
                print(f"Skipped existing {index}/{total}")
                sys.stdout.flush()
            continue

        try:
            if strategy.startswith("fulltext"):
                source_fulltext(record.source_id, notebook_id=notebook_id, output_path=target_file)
            else:
                temp_file = target_file.with_suffix(target_file.suffix + ".download")
                http_status, content_type = fetch_url_to_file(effective_url or "", temp_file)
                if strategy == "download-url":
                    inferred_extension = infer_extension_from_url_and_content_type(effective_url or "", content_type)
                    final_file = target_file.with_suffix(inferred_extension)
                    if final_file != target_file:
                        target_file = final_file
                        local_name = target_file.name
                if target_file.exists():
                    target_file.unlink()
                temp_file.rename(target_file)

            run_manifest.append(
                {
                    **record.to_json(),
                    "strategy": strategy,
                    "local_filename": local_name,
                    "status": status,
                    "effective_url": effective_url,
                }
            )
        except Exception as exc:
            status = "error"
            error = {
                **record.to_json(),
                "strategy": strategy,
                "local_filename": local_name,
                "status": status,
                "effective_url": effective_url,
                "error": str(exc),
            }
            run_manifest.append(error)
            errors.append(error)

        if stream and (index % 10 == 0 or index == total):
            print(f"Downloaded {index}/{total}")
            sys.stdout.flush()

    bundle_manifest = {
        "notebook_id": manifest.get("notebook_id"),
        "notebook_title": manifest.get("notebook_title"),
        "count": len(records),
        "sources": run_manifest,
    }
    write_text(target_dir / "manifest.json", json.dumps(bundle_manifest, indent=2, ensure_ascii=False))
    write_text(target_dir / "errors.json", json.dumps(errors, indent=2, ensure_ascii=False))
    write_text(
        target_dir / "README.md",
        (
            "# NotebookLM Source Download Bundle\n\n"
            "This directory contains a bulk source download/export run.\n\n"
            "- `manifest.json`: per-source metadata, local filename, strategy, and status\n"
            "- `errors.json`: failed sources\n"
            "- downloaded files or fulltext exports\n\n"
            "Strategies are selected automatically per source type.\n"
        ),
    )
    return target_dir


def detect_notebooklm_auth_paths() -> list[Path]:
    notebooklm_home = Path(os.environ.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm"))
    candidates = [
        notebooklm_home / "storage_state.json",
        notebooklm_home / "profiles" / "default" / "storage_state.json",
    ]
    return candidates


def doctor_lines() -> Iterable[str]:
    yield f"repo_root: {repo_root()}"
    try:
        binary = resolve_notebooklm_binary()
        yield f"notebooklm_binary: {binary}"
    except FileNotFoundError as exc:
        yield f"notebooklm_binary: MISSING ({exc})"
        return

    notebooklm_home = Path(os.environ.get("NOTEBOOKLM_HOME", Path.home() / ".notebooklm"))
    yield f"notebooklm_home: {notebooklm_home}"
    auth_paths = detect_notebooklm_auth_paths()
    yield f"storage_state_exists: {any(path.exists() for path in auth_paths)}"
    for index, path in enumerate(auth_paths, start=1):
        yield f"auth_path[{index}]: {path} exists={path.exists()}"
