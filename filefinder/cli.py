"""Command-line interface for FileFinder."""

import argparse
import logging
import sys

from .searcher import FileSearcher, DEFAULT_MODEL


def main():
    parser = argparse.ArgumentParser(
        description="FileFinder - Search your files using natural language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/documents "find my assignment"
  %(prog)s ~/Documents "where is the invoice PDF" --top-k 10
  %(prog)s /data "machine learning report" --reindex
  %(prog)s /data --interactive
        """,
    )
    parser.add_argument(
        "directory",
        help="Directory to scan for files",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Natural language search query (omit for --interactive mode)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="Minimum similarity score 0.0-1.0 (default: 0.0)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Sentence-transformer model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=5,
        help="Max PDF pages to extract per file (default: 5)",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force reindexing, ignoring cache",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Enter interactive search mode (multiple queries)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    # Build index
    searcher = FileSearcher(
        directory=args.directory,
        model_name=args.model,
        pdf_page_limit=args.page_limit,
    )

    try:
        count = searcher.index(force_reindex=args.reindex)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print("No files could be indexed. Check the directory path and file contents.")
        sys.exit(1)

    print(f"\nIndexed {count} files.\n")

    if args.interactive:
        _interactive_loop(searcher, args)
    elif args.query:
        _run_query(searcher, args.query, args.top_k, args.threshold)
    else:
        print("Error: Provide a query or use --interactive mode.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


def _run_query(searcher, query, top_k, threshold):
    """Execute a single search query and print results."""
    results = searcher.search(query, top_k=top_k, threshold=threshold)

    if not results:
        print("No matching files found.")
        return

    print(f"Results for: \"{query}\"\n")
    print(f"{'Rank':<6} {'Score':<10} {'File'}")
    print("-" * 60)
    for rank, (file_path, score) in enumerate(results, 1):
        print(f"{rank:<6} {score:<10.4f} {file_path}")
    print()


def _interactive_loop(searcher, args):
    """Run an interactive search loop."""
    print("Interactive mode. Type 'quit' or 'exit' to stop.\n")
    while True:
        try:
            query = input("Search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        _run_query(searcher, query, args.top_k, args.threshold)


if __name__ == "__main__":
    main()
