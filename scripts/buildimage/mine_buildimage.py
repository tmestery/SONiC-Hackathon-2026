#!/usr/bin/env python3
"""
Mining script for sonic-buildimage:
Collects all closed issues that have linked pull requests.
Saves raw JSON payloads to data/buildimage/raw/issue-<number>.json.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

REPO_OWNER = "sonic-net"
REPO_NAME = "sonic-buildimage"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "data" / "buildimage" / "raw"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
PAGE_SIZE = 35

QUERY_TEMPLATE = """
query($cursor: String) {
  repository(owner: "%s", name: "%s") {
    issues(states: CLOSED, first: %d, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        state
        url
        createdAt
        closedAt
        author { login }
        labels(first: 20) { nodes { name } }
        assignees(first: 10) { nodes { login } }
        milestone { title }
        body
        comments(first: 30) {
          nodes {
            author { login }
            createdAt
            body
          }
        }
        closedByPullRequestsReferences(first: 10) {
          totalCount
          nodes {
            number
            title
            state
            merged
            mergedAt
            createdAt
            url
            repository { nameWithOwner }
            author { login }
            body
            files(first: 50) {
              nodes {
                path
                additions
                deletions
              }
            }
            comments(first: 20) {
              nodes {
                author { login }
                createdAt
                body
              }
            }
          }
        }
      }
    }
  }
}
""" % (REPO_OWNER, REPO_NAME, PAGE_SIZE)


def run_graphql_query(cursor=None, max_retries=3):
    cmd = ["gh", "api", "graphql", "-f", f"query={QUERY_TEMPLATE}"]
    if cursor:
        cmd += ["-F", f"cursor={cursor}"]

    for attempt in range(1, max_retries + 1):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                if "errors" in data:
                    print(f"GraphQL returned errors: {data['errors']}")
                    time.sleep(2 * attempt)
                    continue
                return data
            else:
                print(f"[Attempt {attempt}/{max_retries}] Error running gh: {res.stderr.strip()}")
                time.sleep(2 * attempt)
        except Exception as e:
            print(f"[Attempt {attempt}/{max_retries}] Exception: {e}")
            time.sleep(2 * attempt)

    print("Failed to run query after max retries.")
    return None


def format_issue(node):
    return {
        "number": node["number"],
        "title": node["title"],
        "state": node["state"],
        "url": node["url"],
        "createdAt": node["createdAt"],
        "closedAt": node["closedAt"],
        "author": node["author"]["login"] if node.get("author") else None,
        "labels": [l["name"] for l in node.get("labels", {}).get("nodes", [])],
        "assignees": [a["login"] for a in node.get("assignees", {}).get("nodes", [])],
        "milestone": node["milestone"]["title"] if node.get("milestone") else None,
        "body": node.get("body", ""),
        "comments": [
            {
                "author": c["author"]["login"] if c.get("author") else None,
                "createdAt": c.get("createdAt"),
                "body": c.get("body", "")
            }
            for c in node.get("comments", {}).get("nodes", [])
        ],
        "linkedPullRequests": [
            {
                "number": pr["number"],
                "repository": pr.get("repository", {}).get("nameWithOwner"),
                "url": pr.get("url"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "merged": pr.get("merged"),
                "mergedAt": pr.get("mergedAt"),
                "createdAt": pr.get("createdAt"),
                "author": pr["author"]["login"] if pr.get("author") else None,
                "body": pr.get("body", ""),
                "files": pr.get("files", {}).get("nodes", []),
                "comments": [
                    {
                        "author": c["author"]["login"] if c.get("author") else None,
                        "createdAt": c.get("createdAt"),
                        "body": c.get("body", "")
                    }
                    for c in pr.get("comments", {}).get("nodes", [])
                ]
            }
            for pr in node.get("closedByPullRequestsReferences", {}).get("nodes", [])
        ]
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cursor = None
    page = 0
    total_examined = 0
    total_saved = 0
    start_time = time.time()
    manifest_entries = []

    print(f"Starting mining for repo: {REPO_OWNER}/{REPO_NAME}")
    print(f"Destination directory: {OUTPUT_DIR.resolve()}")

    while True:
        page += 1
        data = run_graphql_query(cursor=cursor)
        if not data:
            print("Aborting due to query failure.")
            break

        issues_data = data.get("data", {}).get("repository", {}).get("issues", {})
        nodes = issues_data.get("nodes", [])
        total_examined += len(nodes)

        page_saved = 0
        for node in nodes:
            linked_prs = node.get("closedByPullRequestsReferences", {}).get("nodes", [])
            if not linked_prs:
                continue

            issue_num = node["number"]
            issue_file = OUTPUT_DIR / f"issue-{issue_num}.json"

            formatted = format_issue(node)
            with open(issue_file, "w") as f:
                json.dump(formatted, f, indent=2)

            page_saved += 1
            total_saved += 1

            manifest_entries.append({
                "issue_number": issue_num,
                "title": node["title"],
                "created_at": node["createdAt"],
                "closed_at": node["closedAt"],
                "linked_prs": [
                    {
                        "number": pr["number"],
                        "repository": pr.get("repository", {}).get("nameWithOwner"),
                        "merged": pr.get("merged")
                    }
                    for pr in linked_prs
                ]
            })

        elapsed = time.time() - start_time
        print(f"Page {page:02d} | Examined: {total_examined:4d} | Saved this page: {page_saved:2d} | Total saved: {total_saved:4d} | Elapsed: {elapsed:.1f}s")

        page_info = issues_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            print("Reached last page.")
            break

        cursor = page_info.get("endCursor")

    manifest = {
        "repository": f"{REPO_OWNER}/{REPO_NAME}",
        "mined_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total_issues_examined": total_examined,
        "total_issues_saved": total_saved,
        "issues": manifest_entries
    }

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    total_time = time.time() - start_time
    print(f"\nMining complete in {total_time:.1f}s!")
    print(f"Total closed issues examined: {total_examined}")
    print(f"Total issues with linked PRs saved: {total_saved}")
    print(f"Manifest written to: {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
