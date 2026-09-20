#!/usr/bin/env python3
"""
Inspects and prunes stale GitHub deployment records for kwakhare5/Grocer.
"""

import json
import subprocess
import urllib.error
import urllib.request
import sys

def get_github_token():
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        capture_output=True,
        text=True
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return None

def main():
    token = get_github_token()
    if not token:
        print("ERROR: Could not retrieve GitHub token from git credential manager.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Grocer-Deployment-Cleaner"
    }

    # Fetch all deployments
    all_deployments = []
    page = 1
    print("Fetching GitHub deployments for kwakhare5/Grocer...")
    while True:
        url = f"https://api.github.com/repos/kwakhare5/Grocer/deployments?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                if not data:
                    break
                all_deployments.extend(data)
                print(f"  Page {page}: {len(data)} deployments (Total: {len(all_deployments)})")
                if len(data) < 100:
                    break
                page += 1
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    print(f"\nTotal GitHub deployments found: {len(all_deployments)}")
    if not all_deployments:
        print("No deployments found on GitHub.")
        return

    # Inspect the most recent deployment
    latest = all_deployments[0]
    print(f"Most recent deployment: ID={latest['id']}, SHA={latest.get('sha')[:7]}, Env={latest.get('environment')}, Created={latest.get('created_at')}")

    # Keep the latest deployment matching our latest commit if possible
    # We want to delete all older deployments
    to_delete = all_deployments[1:]
    print(f"Preparing to delete {len(to_delete)} stale deployment records on GitHub...")

    deleted_count = 0
    for d in to_delete:
        d_id = d["id"]
        # Step 1: Mark deployment as inactive
        status_url = f"https://api.github.com/repos/kwakhare5/Grocer/deployments/{d_id}/statuses"
        status_data = json.dumps({"state": "inactive"}).encode()
        status_req = urllib.request.Request(status_url, data=status_data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(status_req):
                pass
        except Exception:
            pass

        # Step 2: Delete deployment
        del_url = f"https://api.github.com/repos/kwakhare5/Grocer/deployments/{d_id}"
        del_req = urllib.request.Request(del_url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(del_req) as del_resp:
                if del_resp.status in (204, 200):
                    deleted_count += 1
                    if deleted_count % 20 == 0 or deleted_count == len(to_delete):
                        print(f"  Deleted {deleted_count}/{len(to_delete)} GitHub deployments...")
        except urllib.error.HTTPError as e:
            print(f"  Failed to delete {d_id}: HTTP {e.code}")
        except Exception as e:
            print(f"  Error deleting {d_id}: {e}")

    print(f"\nDONE! Deleted {deleted_count} stale deployment records from GitHub. Latest deployment preserved.")

if __name__ == "__main__":
    main()
