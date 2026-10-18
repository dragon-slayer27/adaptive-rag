"""Command-line interface for document ingestion and inspection."""

import argparse
import json
from pathlib import Path
import sys
from typing import Optional
from app.core.config import get_settings
from app.ingestion.service import DocumentIngestionService
from app.ingestion.storage.repository import DocumentRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ingestion",
        description="Agentic RAG Document Ingestion CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Ingest subcommand
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a file or directory of documents")
    ingest_parser.add_argument("path", type=str, help="Path to file or directory to ingest")
    ingest_parser.add_argument(
        "--on-duplicate",
        choices=["skip", "replace"],
        default="skip",
        help="Duplicate resolution policy (default: skip)",
    )
    ingest_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Disable recursive directory scanning",
    )
    ingest_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Custom SQLite database path (default: from configuration)",
    )

    # List subcommand
    list_parser = subparsers.add_parser("list", help="List all ingested documents")
    list_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Custom SQLite database path",
    )

    # Inspect subcommand
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a specific document by ID")
    inspect_parser.add_argument("document_id", type=str, help="ID of document to inspect")
    inspect_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Custom SQLite database path",
    )

    # Delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete a document by ID")
    delete_parser.add_argument("document_id", type=str, help="ID of document to delete")
    delete_parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Custom SQLite database path",
    )

    return parser


def handle_ingest(args: argparse.Namespace, repo: DocumentRepository) -> int:
    target_path = Path(args.path)
    service = DocumentIngestionService(repository=repo)

    if not target_path.exists():
        print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
        return 1

    if target_path.is_file():
        item = service.ingest_file(target_path, on_duplicate=args.on_duplicate)
        if item.status == "failed":
            print(f"[-] FAILED: {item.file_path} -> {item.error}", file=sys.stderr)
            return 1
        elif item.status == "skipped":
            print(f"[*] SKIPPED (duplicate): {item.file_path} (ID: {item.document_id})")
        elif item.status == "replaced":
            print(f"[+] REPLACED: {item.file_path} (ID: {item.document_id})")
        else:
            print(f"[+] INGESTED: {item.file_path} (ID: {item.document_id})")
        return 0

    print(f"Scanning directory: {target_path}")
    batch_result = service.ingest_directory(
        target_path,
        on_duplicate=args.on_duplicate,
        recursive=not args.no_recursive,
    )

    print("\n--- Ingestion Summary ---")
    print(f"Total Discovered: {batch_result.total_discovered}")
    print(f"Ingested:         {batch_result.ingested}")
    print(f"Skipped:          {batch_result.skipped}")
    print(f"Replaced:         {batch_result.replaced}")
    print(f"Failed:           {batch_result.failed}")

    if batch_result.failed > 0:
        print("\nFailures:")
        for it in batch_result.items:
            if it.status == "failed":
                print(f"  [-] {it.file_path}: {it.error}")

    return 0 if batch_result.failed == 0 else 1


def handle_list(repo: DocumentRepository) -> int:
    docs = repo.list_documents()
    if not docs:
        print("Corpus is empty. No documents ingested yet.")
        return 0

    print(f"{'ID':<38} {'TYPE':<6} {'SECTIONS':<10} {'FILENAME':<24} {'TITLE'}")
    print("-" * 100)
    for d in docs:
        title = (d.title or "")[:35]
        print(f"{d.id:<38} {d.file_type:<6} {d.section_count:<10} {d.filename:<24} {title}")
    print(f"\nTotal: {len(docs)} document(s)")
    return 0


def handle_inspect(document_id: str, repo: DocumentRepository) -> int:
    doc = repo.get_document(document_id)
    if not doc:
        print(f"Error: Document not found: {document_id}", file=sys.stderr)
        return 1

    print(f"Document ID:   {doc.id}")
    print(f"Filename:      {doc.filename}")
    print(f"Title:         {doc.title}")
    print(f"File Type:     {doc.file_type}")
    print(f"Source Path:   {doc.source_path}")
    print(f"Content SHA256:{doc.content_hash}")
    print(f"Created At:    {doc.created_at}")
    print(f"Metadata:      {json.dumps(doc.metadata, indent=2)}")
    print(f"\nSections ({len(doc.sections)}):")
    print("=" * 70)

    for s in doc.sections:
        loc = []
        if s.page_number is not None:
            loc.append(f"Page {s.page_number}")
        if s.section_title:
            loc.append(f"Heading: {s.section_title}")
        loc_str = f" [{', '.join(loc)}]" if loc else ""
        print(f"\n[Section {s.section_index}{loc_str}]")
        sample_text = s.text[:300] + ("..." if len(s.text) > 300 else "")
        print(sample_text)
    return 0


def handle_delete(document_id: str, repo: DocumentRepository) -> int:
    deleted = repo.delete_document(document_id)
    if deleted:
        print(f"[+] Successfully deleted document: {document_id}")
        return 0
    else:
        print(f"Error: Document not found: {document_id}", file=sys.stderr)
        return 1


def main(args_list: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(args_list)

    if not args.command:
        parser.print_help()
        return 1

    settings = get_settings()
    db_path = getattr(args, "db", None) or settings.corpus_db_path
    repo = DocumentRepository(db_path=db_path)

    if args.command == "ingest":
        return handle_ingest(args, repo)
    elif args.command == "list":
        return handle_list(repo)
    elif args.command == "inspect":
        return handle_inspect(args.document_id, repo)
    elif args.command == "delete":
        return handle_delete(args.document_id, repo)

    return 0


if __name__ == "__main__":
    sys.exit(main())
