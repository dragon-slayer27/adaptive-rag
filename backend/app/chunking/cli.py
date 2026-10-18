"""Command-line interface for document chunking and chunk inspection."""

import argparse
from pathlib import Path
import sys
from typing import Optional
from app.chunking.service import ChunkingService
from app.core.config import get_settings
from app.ingestion.storage.repository import DocumentRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.chunking",
        description="Agentic RAG Document Chunking CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Chunk single document
    chunk_parser = subparsers.add_parser("chunk", help="Chunk a single document by ID")
    chunk_parser.add_argument("document_id", type=str, help="ID of document to chunk")
    chunk_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild chunks even if document has already been chunked",
    )
    chunk_parser.add_argument("--chunk-size", type=int, default=None, help="Chunk size in tokens")
    chunk_parser.add_argument("--chunk-overlap", type=int, default=None, help="Chunk overlap in tokens")
    chunk_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database path")

    # Chunk all documents
    all_parser = subparsers.add_parser("chunk-all", help="Chunk all ingested documents in corpus")
    all_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild chunks for documents that were already chunked",
    )
    all_parser.add_argument("--chunk-size", type=int, default=None, help="Chunk size in tokens")
    all_parser.add_argument("--chunk-overlap", type=int, default=None, help="Chunk overlap in tokens")
    all_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database path")

    # List chunks
    list_parser = subparsers.add_parser("list", help="List chunk summaries across corpus")
    list_parser.add_argument("--document-id", type=str, default=None, help="Filter by document ID")
    list_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database path")

    # Inspect chunk
    inspect_parser = subparsers.add_parser("inspect", help="Inspect a specific chunk with provenance")
    inspect_parser.add_argument("chunk_id", type=str, help="ID of chunk to inspect")
    inspect_parser.add_argument("--db", type=str, default=None, help="Custom SQLite database path")

    return parser


def handle_chunk(args: argparse.Namespace, repo: DocumentRepository) -> int:
    service = ChunkingService(
        repository=repo,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    res = service.chunk_document(
        document_id=args.document_id,
        rebuild=args.rebuild,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    if res.status == "failed":
        print(f"[-] FAILED: {res.document_id} -> {res.error}", file=sys.stderr)
        return 1
    elif res.status == "skipped":
        print(f"[*] SKIPPED: {res.filename} ({res.document_id}) already chunked. Use --rebuild to replace.")
    elif res.status == "rebuilt":
        print(f"[+] REBUILT: {res.filename} ({res.document_id}) -> {res.chunks_created} chunk(s) created.")
    else:
        print(f"[+] CHUNKED: {res.filename} ({res.document_id}) -> {res.chunks_created} chunk(s) created.")
    return 0


def handle_chunk_all(args: argparse.Namespace, repo: DocumentRepository) -> int:
    service = ChunkingService(
        repository=repo,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print("Chunking all documents in corpus...")
    batch_result = service.chunk_all(
        rebuild=args.rebuild,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print("\n--- Chunking Summary ---")
    print(f"Total Documents:      {batch_result.total_documents}")
    print(f"Chunked:              {batch_result.chunked}")
    print(f"Skipped:              {batch_result.skipped}")
    print(f"Rebuilt:              {batch_result.rebuilt}")
    print(f"Failed:               {batch_result.failed}")
    print(f"Total Chunks Created: {batch_result.total_chunks_created}")

    if batch_result.failed > 0:
        print("\nFailures:")
        for r in batch_result.results:
            if r.status == "failed":
                print(f"  [-] {r.document_id} ({r.filename}): {r.error}")

    return 0 if batch_result.failed == 0 else 1


def handle_list(args: argparse.Namespace, repo: DocumentRepository) -> int:
    summaries = repo.list_chunk_summaries(document_id=args.document_id)
    if not summaries:
        print("No chunks found in corpus.")
        return 0

    print(f"{'DOCUMENT ID':<38} {'CHUNKS':<8} {'TOKENS':<8} {'AVG TOK':<10} {'FILENAME'}")
    print("-" * 95)
    total_chunks = 0
    total_tokens = 0
    for s in summaries:
        print(f"{s.document_id:<38} {s.total_chunks:<8} {s.total_tokens:<8} {s.avg_tokens:<10.1f} {s.filename}")
        total_chunks += s.total_chunks
        total_tokens += s.total_tokens
    print("-" * 95)
    print(f"Total: {len(summaries)} document(s), {total_chunks} chunk(s), {total_tokens} token(s)")
    return 0


def handle_inspect(chunk_id: str, repo: DocumentRepository) -> int:
    chunk = repo.get_chunk(chunk_id)
    if not chunk:
        print(f"Error: Chunk not found: {chunk_id}", file=sys.stderr)
        return 1

    print(f"Chunk ID:          {chunk.id}")
    print(f"Parent Document ID:{chunk.document_id}")
    print(f"Filename:          {chunk.filename}")
    print(f"File Type:         {chunk.file_type}")
    print(f"Source Path:       {chunk.source_path}")
    print(f"Document Title:    {chunk.document_title or '(None)'}")
    print(f"Section ID:        {chunk.section_id} (Section index: {chunk.section_index})")
    print(f"Section Title:     {chunk.section_title or '(None)'}")
    print(f"Page Number:       {chunk.page_number or '(None)'}")
    print(f"Chunk Index:       {chunk.chunk_index}")
    print(f"Token Count:       {chunk.token_count}")
    print(f"Character Offsets: [{chunk.start_char} : {chunk.end_char}] (Length: {chunk.end_char - chunk.start_char})")
    print(f"Created At:        {chunk.created_at}")
    print("\nChunk Text:")
    print("=" * 70)
    print(chunk.text)
    print("=" * 70)
    return 0


def main(args_list: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(args_list)

    if not args.command:
        parser.print_help()
        return 1

    settings = get_settings()
    db_path = getattr(args, "db", None) or settings.corpus_db_path
    repo = DocumentRepository(db_path=db_path)

    if args.command == "chunk":
        return handle_chunk(args, repo)
    elif args.command == "chunk-all":
        return handle_chunk_all(args, repo)
    elif args.command == "list":
        return handle_list(args, repo)
    elif args.command == "inspect":
        return handle_inspect(args.chunk_id, repo)

    return 0


if __name__ == "__main__":
    sys.exit(main())
