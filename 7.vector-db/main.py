#!/usr/bin/env python3
"""
Vector Database Manager
ایندکس و جستجوی معنایی داده‌های ریپازیتوری
"""

import sys
from config import Config
from indexer import Indexer
from search_engine import SearchEngine
from chroma_manager import ChromaManager


def cmd_index(clear=False):
    """ایندکس کردن ریپازیتوری"""
    indexer = Indexer()
    indexer.index_all(clear=clear)


def cmd_stats():
    """نمایش آمار"""
    chroma = ChromaManager()
    stats = chroma.get_stats()

    print("\n📊 ChromaDB Statistics")
    print("=" * 40)
    for name, count in stats["collections"].items():
        bar = "█" * min(count // 10, 30)
        print(f"   {name:20s}: {count:5d}  {bar}")
    print(f"   {'─'*20}  {'─'*5}")
    print(f"   {'TOTAL':20s}: {stats['total']:5d}")


def cmd_search():
    """جستجوی تعاملی"""
    engine = SearchEngine()

    print("\n" + "=" * 60)
    print("🔍 INTERACTIVE SEARCH")
    print("=" * 60)
    print()
    print("Commands:")
    print("  /code <query>      Search source code")
    print("  /issue <query>     Search issues")
    print("  /pr <query>        Search pull requests")
    print("  /commit <query>    Search commits")
    print("  /all <query>       Search everything (default)")
    print("  /context <query>   Get RAG context")
    print("  /stats             Show statistics")
    print("  /quit              Exit")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n🔍 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Bye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("👋 Bye!")
            break

        if user_input == "/stats":
            cmd_stats()
            continue

        # Parse command
        if user_input.startswith("/code "):
            results = engine.search_code(user_input[6:])
        elif user_input.startswith("/issue "):
            results = engine.search_issues(user_input[7:])
        elif user_input.startswith("/pr "):
            results = engine.search_prs(user_input[4:])
        elif user_input.startswith("/commit "):
            results = engine.search_commits(user_input[8:])
        elif user_input.startswith("/context "):
            context = engine.get_context_for_rag(user_input[9:])
            print(f"\n📋 RAG Context:\n\n{context}")
            continue
        elif user_input.startswith("/all "):
            results = engine.search(user_input[5:])
        else:
            results = engine.search(user_input)

        # Display
        if results:
            print(f"\n📋 Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(engine.format_result(result, i))
        else:
            print("❌ No results found")


def main():
    print("=" * 60)
    print("🗄️  VECTOR DATABASE MANAGER")
    print(f"   Repo: {Config.GITEA_ORG}/{Config.REPO_NAME}")
    print(f"   DB: {Config.CHROMA_PERSIST_DIR}")
    print("=" * 60)

    if not Config.GITEA_TOKEN:
        print("❌ GITEA_TOKEN not set in .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python main.py index          Index repository")
        print("  python main.py index --clear  Clear & re-index")
        print("  python main.py search         Interactive search")
        print("  python main.py stats          Show statistics")
        sys.exit(0)

    command = sys.argv[1]

    if command == "index":
        clear = "--clear" in sys.argv
        cmd_index(clear)
    elif command == "search":
        cmd_search()
    elif command == "stats":
        cmd_stats()
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()