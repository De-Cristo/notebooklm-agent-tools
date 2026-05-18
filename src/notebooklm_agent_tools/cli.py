from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    NotebookLMCommandError,
    default_artifact_output_root,
    download_source_bundle,
    doctor_lines,
    download_artifacts,
    export_sources,
    fetch_source_files,
    run_notebooklm,
    source_list,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nlm-agent",
        description="Portable helper CLI for notebooklm-py workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Show local environment and NotebookLM CLI status.")

    run_parser = subparsers.add_parser("run", help="Pass arguments directly to the upstream notebooklm CLI.")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments forwarded to notebooklm.")

    export_parser = subparsers.add_parser(
        "export-sources",
        help="Export NotebookLM source fulltext into a local directory.",
    )
    export_parser.add_argument("--notebook", help="Notebook ID. Uses current notebook if omitted.")
    export_parser.add_argument("--output", type=Path, help="Output directory.")
    export_parser.add_argument("--limit", type=int, help="Only export the first N sources.")
    export_parser.add_argument("--no-resume", action="store_true", help="Re-export even if files already exist.")

    download_sources_parser = subparsers.add_parser(
        "download-sources",
        help="Download or export all notebook sources with source-type-aware strategies.",
    )
    download_sources_parser.add_argument("--notebook", help="Notebook ID. Uses current notebook if omitted.")
    download_sources_parser.add_argument("--output", type=Path, help="Output directory.")
    download_sources_parser.add_argument("--limit", type=int, help="Only process the first N sources.")
    download_sources_parser.add_argument("--type", dest="type_filter", help="Only process one normalized source type, for example PDF or MARKDOWN.")
    download_sources_parser.add_argument("--resume", dest="resume", action="store_true", help="Skip existing files. This is the default behavior.")
    download_sources_parser.add_argument("--no-resume", dest="resume", action="store_false", help="Re-download even if files already exist.")
    download_sources_parser.set_defaults(resume=True)

    fetch_parser = subparsers.add_parser(
        "fetch-source-files",
        help="Best-effort download of original source URLs into a local directory.",
    )
    fetch_parser.add_argument("--notebook", help="Notebook ID. Uses current notebook if omitted.")
    fetch_parser.add_argument("--output", type=Path, help="Output directory.")
    fetch_parser.add_argument("--limit", type=int, help="Only fetch the first N URL-backed sources.")
    fetch_parser.add_argument("--no-resume", action="store_true", help="Re-fetch even if metadata files already exist.")

    download_parser = subparsers.add_parser(
        "download-artifacts",
        help="Stable wrapper for upstream NotebookLM artifact downloads.",
    )
    download_parser.add_argument(
        "artifact_type",
        choices=[
            "audio",
            "cinematic-video",
            "data-table",
            "flashcards",
            "infographic",
            "mind-map",
            "quiz",
            "report",
            "slide-deck",
            "video",
        ],
        help="Artifact type to download.",
    )
    download_parser.add_argument("--notebook", help="Notebook ID. Uses current notebook if omitted.")
    download_parser.add_argument("--output", type=Path, help="Output file or directory.")
    download_parser.add_argument(
        "--selector",
        choices=["latest", "earliest", "all"],
        default="latest",
        help="Which artifacts to target.",
    )
    download_parser.add_argument("--name", help="Fuzzy-match artifact title.")
    download_parser.add_argument("--artifact-id", help="Artifact ID or partial ID.")
    download_parser.add_argument("--json", action="store_true", help="Return upstream JSON output.")
    download_parser.add_argument("--dry-run", action="store_true", help="Preview only.")
    download_parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    download_parser.add_argument("--no-clobber", action="store_true", help="Skip existing files.")
    download_parser.add_argument("--format", dest="format_name", help="Optional upstream format argument.")

    source_list_parser = subparsers.add_parser(
        "list-sources",
        help="List sources from NotebookLM with optional wrapper-level type filtering.",
    )
    source_list_parser.add_argument("--notebook", help="Notebook ID. Uses current notebook if omitted.")
    source_list_parser.add_argument("--type", dest="type_filter", help="Only include one normalized type, for example PDF or MARKDOWN.")
    source_list_parser.add_argument("--limit", type=int, help="Only show the first N sources.")
    source_list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table-like text list.")

    return parser


def cmd_doctor() -> int:
    for line in doctor_lines():
        print(line)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    forwarded = list(args.args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]
    result = run_notebooklm(forwarded, check=False)
    return result.returncode


def cmd_export_sources(args: argparse.Namespace) -> int:
    target_dir = export_sources(
        notebook_id=args.notebook,
        output_dir=args.output,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(f"Wrote export to {target_dir}")
    return 0


def cmd_download_sources(args: argparse.Namespace) -> int:
    target_dir = download_source_bundle(
        notebook_id=args.notebook,
        output_dir=args.output,
        limit=args.limit,
        type_filter=args.type_filter,
        resume=args.resume,
    )
    print(f"Wrote source bundle to {target_dir}")
    return 0


def cmd_fetch_source_files(args: argparse.Namespace) -> int:
    target_dir = fetch_source_files(
        notebook_id=args.notebook,
        output_dir=args.output,
        limit=args.limit,
        resume=not args.no_resume,
    )
    print(f"Wrote source-file fetch to {target_dir}")
    return 0


def cmd_download_artifacts(args: argparse.Namespace) -> int:
    output = args.output
    if output is None:
        output = default_artifact_output_root() / args.artifact_type
    result = download_artifacts(
        artifact_type=args.artifact_type,
        notebook_id=args.notebook,
        output_path=output,
        selector=args.selector,
        name=args.name,
        artifact_id=args.artifact_id,
        dry_run=args.dry_run,
        force=args.force,
        no_clobber=args.no_clobber,
        json_output=args.json,
        format_name=args.format_name,
    )
    if args.json and result.stdout:
        sys.stdout.write(result.stdout)
    else:
        print(f"Artifact command completed for {args.artifact_type}. Output target: {output}")
    return 0


def cmd_list_sources(args: argparse.Namespace) -> int:
    records = source_list(
        notebook_id=args.notebook,
        type_filter=args.type_filter,
        limit=args.limit,
    )
    if args.json:
        payload = [record.to_json() for record in records]
        sys.stdout.write(f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n")
        return 0

    for record in records:
        print(f"{record.index:03d}  {record.normalized_type:<10}  {record.source_id}  {record.title}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "doctor":
            return cmd_doctor()
        if args.command == "run":
            return cmd_run(args)
        if args.command == "export-sources":
            return cmd_export_sources(args)
        if args.command == "download-sources":
            return cmd_download_sources(args)
        if args.command == "fetch-source-files":
            return cmd_fetch_source_files(args)
        if args.command == "download-artifacts":
            return cmd_download_artifacts(args)
        if args.command == "list-sources":
            return cmd_list_sources(args)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except NotebookLMCommandError as exc:
        print(str(exc), file=sys.stderr)
        return exc.returncode or 1

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
