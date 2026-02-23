#!/usr/bin/env python3
"""
LightRAG Code Assistant
REST API + Interactive CLI
"""

import sys
import uvicorn
from config import Config


def run_api():
    """اجرای REST API"""
    print("=" * 60)
    print("🚀 LightRAG Code Assistant API")
    print(f"   Model: {Config.OLLAMA_MODEL}")
    print(f"   ChromaDB: {Config.CHROMA_PERSIST_DIR}")
    print(f"   API: http://{Config.API_HOST}:{Config.API_PORT}")
    print(f"   Docs: http://localhost:{Config.API_PORT}/docs")
    print("=" * 60)

    uvicorn.run(
        "api:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=False,
        log_level="info",
    )


def run_cli():
    """اجرای CLI تعاملی"""
    from rag_engine import RAGEngine

    rag = RAGEngine()

    print("\n" + "=" * 60)
    print("💬 LightRAG CLI - Ask anything about the repository!")
    print("=" * 60)
    print()
    print("Commands:")
    print("  /code <query>     Search only in code")
    print("  /issue <query>    Search only in issues")
    print("  /pr <query>       Search only in PRs")
    print("  /search <query>   Search without LLM")
    print("  /stats            Show statistics")
    print("  /quit             Exit")
    print()
    print("Or just type your question to use full RAG!")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n💬 You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Bye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("👋 Bye!")
            break

        if user_input == "/stats":
            stats = rag.get_stats()
            print(f"\n📊 Stats:")
            print(f"   LLM: {stats['llm_model']}")
            print(f"   Documents: {stats['total_documents']}")
            for name, count in stats["collections"].items():
                print(f"   {name}: {count}")
            continue

        # Search only (no LLM)
        if user_input.startswith("/search "):
            query = user_input[8:]
            results = rag.retrieve(query)
            if results:
                print(f"\n📋 Found {len(results)} results:")
                for i, r in enumerate(results, 1):
                    print(f"\n━━━ {i}. [{r['collection']}] score: {r['score']} ━━━")
                    meta = r["metadata"]
                    if r["collection"] == "code":
                        print(f"📄 {meta.get('file_path', '')}")
                    elif r["collection"] == "issue":
                        print(f"🐛 Issue #{meta.get('issue_number', '')}: {meta.get('title', '')}")
                    elif r["collection"] == "pull_request":
                        print(f"🔀 PR #{meta.get('pr_number', '')}: {meta.get('title', '')}")
                    print(f"\n{r['content'][:300]}...")
            else:
                print("❌ No results found")
            continue

        # RAG with collection filter
        collections = None
        question = user_input

        if user_input.startswith("/code "):
            collections = ["code"]
            question = user_input[6:]
        elif user_input.startswith("/issue "):
            collections = ["issue"]
            question = user_input[7:]
        elif user_input.startswith("/pr "):
            collections = ["pull_request"]
            question = user_input[4:]

        # Full RAG query
        print("\n🔍 Searching relevant context...")
        result = rag.query(question, collections=collections)

        print(f"\n🤖 Assistant:\n")
        print(result["answer"])

        if result["sources"]:
            print(f"\n📚 Sources ({result['sources_count']}):")
            for s in result["sources"]:
                if s["type"] == "code":
                    print(f"   📄 {s.get('file', '')} (score: {s['score']})")
                elif s["type"] == "issue":
                    print(f"   🐛 Issue #{s.get('issue_number', '')}: {s.get('title', '')} (score: {s['score']})")
                elif s["type"] == "pull_request":
                    print(f"   🔀 PR #{s.get('pr_number', '')}: {s.get('title', '')} (score: {s['score']})")
                elif s["type"] == "commit":
                    print(f"   📝 {s.get('sha', '')}: {s.get('message', '')} (score: {s['score']})")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py api     Start REST API server")
        print("  python main.py cli     Interactive CLI mode")
        sys.exit(0)

    command = sys.argv[1]

    if command == "api":
        run_api()
    elif command == "cli":
        run_cli()
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()