#!/usr/bin/env python3
"""
GitHub → Gitea Crawler
Crawls GitHub repos and pushes everything to local Gitea
"""

import json
import os
import sys
import time
from github_crawler import GitHubCrawler
from gitea_pusher import GiteaPusher
from config import Config


def main():
    print("=" * 60)
    print("🕷️  GitHub → Gitea Smart Crawler")
    print("=" * 60)

    # Validate config
    if not Config.GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in .env")
        sys.exit(1)

    if not Config.GITEA_TOKEN:
        print("❌ GITEA_TOKEN not set in .env")
        sys.exit(1)

    if not Config.GITHUB_REPOS:
        print("❌ GITHUB_REPOS not set in .env")
        sys.exit(1)

    print(f"\n📋 Configuration:")
    print(f"   Gitea URL: {Config.GITEA_URL}")
    print(f"   Gitea Org: {Config.GITEA_ORG}")
    print(f"   Repos to crawl: {Config.GITHUB_REPOS}")
    print(f"   Max Issues: {Config.MAX_ISSUES}")
    print(f"   Max PRs: {Config.MAX_PRS}")

    # Initialize
    crawler = GitHubCrawler()
    pusher = GiteaPusher()

    # Ensure organization exists
    if not pusher.ensure_org():
        print("❌ Failed to create/find organization")
        sys.exit(1)

    # Process each repo
    results = {}
    for repo_full_name in Config.GITHUB_REPOS:
        parts = repo_full_name.split("/")
        if len(parts) != 2:
            print(f"⚠️ Invalid repo format: {repo_full_name} (expected owner/repo)")
            continue

        owner, repo = parts
        start_time = time.time()

        try:
            # Crawl from GitHub
            data = crawler.crawl_repo(owner, repo)
            if not data:
                print(f"❌ Failed to crawl {repo_full_name}")
                continue

            # Save local backup
            backup_dir = "crawled_data_backup"
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, f"{owner}_{repo}.json")
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Local backup saved: {backup_file}")

            # Push to Gitea
            pusher.push_crawled_data(repo, data)

            elapsed = time.time() - start_time
            results[repo_full_name] = {
                "status": "✅ Success",
                "time": f"{elapsed:.1f}s",
                "issues": len(data.get("issues", [])),
                "prs": len(data.get("pull_requests", [])),
                "files": len(data.get("source_files", [])),
                "commits": len(data.get("commits", [])),
            }

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Error processing {repo_full_name}: {e}")
            import traceback
            traceback.print_exc()
            results[repo_full_name] = {
                "status": f"❌ Error: {str(e)[:50]}",
                "time": f"{elapsed:.1f}s",
            }

    # Final summary
    print(f"\n\n{'='*60}")
    print(f"📊 FINAL SUMMARY")
    print(f"{'='*60}")

    for repo, info in results.items():
        print(f"\n📦 {repo}: {info['status']} ({info['time']})")
        if "issues" in info:
            print(f"   🐛 Issues: {info['issues']}")
            print(f"   🔀 PRs: {info['prs']}")
            print(f"   📁 Files: {info['files']}")
            print(f"   📝 Commits: {info['commits']}")

    print(f"\n🔗 Check your Gitea: {Config.GITEA_URL}/{Config.GITEA_ORG}")
    print(f"\n✅ All done!")


if __name__ == "__main__":
    main()