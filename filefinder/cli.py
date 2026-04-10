"""Command-line interface for FileFinder agent."""

import argparse
import logging
import os
import sys

from .agent import FileFinderAgent


def main():
    parser = argparse.ArgumentParser(
        description="FileFinder - AI-powered file search agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Documents                      # Interactive mode
  %(prog)s ~/Documents "find my resume"     # Single query
  %(prog)s ~/Documents --stats              # Show index stats
  %(prog)s /data "budget report" --semantic # Use AI semantic search
        """,
    )
    parser.add_argument("directory", help="Directory to index and search")
    parser.add_argument("query", nargs="?", default=None, help="Search query")
    parser.add_argument("--semantic", action="store_true",
                       help="Use transformer-based semantic search (slower, smarter)")
    parser.add_argument("--type", metavar="EXT",
                       help="Find files by extension (e.g. --type pdf)")
    parser.add_argument("--limit", type=int, default=10,
                       help="Max results (default: 10)")
    parser.add_argument("--stats", action="store_true",
                       help="Show index statistics")
    parser.add_argument("--reindex", action="store_true",
                       help="Force full reindex")
    parser.add_argument("--no-content", action="store_true",
                       help="Skip content extraction (metadata only)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable debug logging")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    agent = FileFinderAgent(args.directory)

    try:
        # Tier 1: Fast metadata scan
        count = agent.initialize()
        print(f"\nIndexed {count} files.")

        # Tier 2: Background content extraction
        if not args.no_content:
            agent.index_content(background=True)
            print("Content extraction running in background...\n")
        else:
            print()

        if args.stats:
            _show_stats(agent)
        elif args.type:
            _search_by_type(agent, args.type, args.limit)
        elif args.query:
            if args.semantic:
                _search_semantic(agent, args.query, args.limit)
            else:
                _search(agent, args.query, args.limit)
        else:
            _interactive(agent, args.limit)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        agent.stop()


def _search(agent, query, limit):
    """Execute keyword search and display results."""
    results = agent.search(query, limit=limit)
    if not results:
        print(f'No results for "{query}"')
        print("Tip: Content is still being indexed in the background.")
        print("     Try again in a moment, or use --semantic for AI search.")
        return

    print(f'Results for "{query}":\n')
    _print_results(results)


def _search_semantic(agent, query, limit):
    """Execute semantic search and display results."""
    print("Loading semantic search model (first time may take a moment)...")
    results = agent.search_semantic(query, top_k=limit)
    if not results:
        print("No semantic results. Content may still be indexing.")
        return

    print(f'\nSemantic results for "{query}":\n')
    print(f"{'#':<4} {'Score':<8} {'File'}")
    print("-" * 60)
    for i, (path, score) in enumerate(results, 1):
        name = os.path.basename(path)
        print(f"{i:<4} {score:<8.3f} {name}")
        print(f"     {_dim(path)}")
    print()


def _search_by_type(agent, extension, limit):
    """Search by file extension."""
    results = agent.search_by_type(extension, limit=limit)
    if not results:
        print(f"No .{extension} files found.")
        return

    print(f".{extension} files:\n")
    for r in results:
        size = _format_size(r.get("size_bytes", 0))
        print(f"  {r['name']:<40} {size:>8}  {r.get('modified_time', '')[:10]}")
        print(f"  {_dim(r['path'])}")
    print(f"\n{len(results)} files found.")


def _show_stats(agent):
    """Display index statistics."""
    stats = agent.get_stats()
    total = stats.get("total_files", 0)
    indexed = stats.get("content_indexed", 0)
    pending = stats.get("content_pending", 0)
    size = _format_size(stats.get("total_size_bytes", 0))
    exts = stats.get("unique_extensions", 0)

    print("Index Statistics")
    print("-" * 35)
    print(f"  Total files:      {total}")
    print(f"  Content indexed:  {indexed}")
    print(f"  Content pending:  {pending}")
    print(f"  Total size:       {size}")
    print(f"  File types:       {exts}")

    if total > 0:
        pct = (indexed / total) * 100
        print(f"  Index progress:   {pct:.0f}%")
    print()


def _interactive(agent, limit):
    """Interactive search loop."""
    print("FileFinder Agent - Interactive Mode")
    print("=" * 40)
    print("Commands:")
    print("  <query>          Search for files")
    print("  open <number>    Open a file from last results")
    print("  reveal <number>  Show file in file manager")
    print("  stats            Show index statistics")
    print("  semantic <query> Use AI semantic search")
    print("  type <ext>       Find files by extension")
    print("  quit             Exit")
    print()

    last_results = []

    while True:
        try:
            raw = input("FileFinder> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split(None, 1)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        elif cmd == "stats":
            _show_stats(agent)

        elif cmd == "open" and len(parts) > 1:
            _handle_file_action(agent, last_results, parts[1], action="open")

        elif cmd == "reveal" and len(parts) > 1:
            _handle_file_action(agent, last_results, parts[1], action="reveal")

        elif cmd == "semantic" and len(parts) > 1:
            _search_semantic(agent, parts[1], limit)

        elif cmd == "type" and len(parts) > 1:
            _search_by_type(agent, parts[1].strip("."), limit)

        else:
            # Treat everything else as a search query
            results = agent.search(raw, limit=limit)
            if not results:
                print(f'No results for "{raw}". Try different terms or "semantic {raw}".')
                print()
                continue
            print(f'\nResults for "{raw}":\n')
            _print_results(results)
            last_results = results


def _print_results(results):
    """Print search results in a readable format."""
    for i, r in enumerate(results, 1):
        name = r.get("name", "?")
        ext = r.get("extension", "")
        size = _format_size(r.get("size_bytes", 0))
        match = r.get("match_type", "")
        status = r.get("content_status", "")

        tag = ""
        if status == "indexed":
            tag = " [content matched]"
        elif match == "filename":
            tag = " [name matched]"

        print(f"  [{i}] {name:<35} {size:>8}{tag}")
        print(f"      {_dim(r['path'])}")
    print(f"\n  {len(results)} results. Use 'open <number>' or 'reveal <number>'.\n")


def _handle_file_action(agent, results, number_str, action="open"):
    """Open or reveal a file from the results list."""
    try:
        idx = int(number_str) - 1
        if 0 <= idx < len(results):
            path = results[idx]["path"]
            if action == "open":
                if agent.open_file(path):
                    print(f"Opening: {path}")
                else:
                    print(f"Failed to open: {path}")
            else:
                if agent.reveal_file(path):
                    print(f"Revealing: {path}")
                else:
                    print(f"Failed to reveal: {path}")
        else:
            print(f"Invalid number. Use 1-{len(results)}.")
    except ValueError:
        print("Please provide a result number, e.g. 'open 1'.")


def _format_size(size_bytes):
    """Format file size for display."""
    if size_bytes is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}TB"


def _dim(text):
    """Return dimmed text (grey) for terminal display."""
    return f"\033[90m{text}\033[0m"


if __name__ == "__main__":
    main()
