#!/usr/bin/env python3
"""
Prunes outdated and preview Vercel deployments for the 'grocer' project,
retaining only the active production deployment.
"""

import json
import subprocess
import sys
import time

PROJECT_NAME = "grocer"
BATCH_SIZE = 15

def get_all_deployments():
    deployments = []
    next_ts = None
    page = 1
    print(f"Fetching deployments for project '{PROJECT_NAME}'...")
    while True:
        cmd = f"npx vercel ls {PROJECT_NAME} --json --limit 100"
        if next_ts:
            cmd += f" --next {next_ts}"
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Failed to fetch page {page}: {res.stderr}")
            break
        try:
            data = json.loads(res.stdout)
            deps = data.get("deployments", [])
            if not deps:
                break
            deployments.extend(deps)
            print(f"  Page {page}: fetched {len(deps)} deployments (total so far: {len(deployments)})")
            next_ts = data.get("pagination", {}).get("next")
            if not next_ts:
                break
            page += 1
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            break
    return deployments

def main():
    deployments = get_all_deployments()
    if not deployments:
        print("No deployments found.")
        return

    # Find the latest production deployment
    latest_prod = None
    for d in deployments:
        if d.get("target") == "production" and d.get("state") == "READY":
            latest_prod = d
            break

    if not latest_prod:
        print("ERROR: Could not identify latest active production deployment! Aborting for safety.")
        sys.exit(1)

    keep_url = latest_prod["url"]
    print(f"\nKEEPING ACTIVE PRODUCTION DEPLOYMENT:")
    print(f"  URL: https://{keep_url}")
    print(f"  Created: {latest_prod.get('createdAt')}")
    print(f"  Commit: {latest_prod.get('meta', {}).get('githubCommitSha', 'unknown')}")

    urls_to_remove = [d["url"] for d in deployments if d["url"] != keep_url]
    print(f"\nFound {len(urls_to_remove)} stale deployments to remove.")

    if not urls_to_remove:
        print("Everything is already clean!")
        return

    # Delete in batches
    deleted_count = 0
    for i in range(0, len(urls_to_remove), BATCH_SIZE):
        batch = urls_to_remove[i : i + BATCH_SIZE]
        batch_str = " ".join(batch)
        cmd = f"npx vercel rm -y {batch_str}"
        print(f"Deleting batch {i // BATCH_SIZE + 1} ({len(batch)} deployments)...")
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            deleted_count += len(batch)
            print(f"  Successfully deleted {deleted_count}/{len(urls_to_remove)}")
        else:
            print(f"  Warning on batch: {res.stderr.strip() or res.stdout.strip()}")
            # fallback one by one for this batch
            for u in batch:
                r = subprocess.run(f"npx vercel rm -y {u}", shell=True, capture_output=True, text=True)
                if r.returncode == 0:
                    deleted_count += 1
        time.sleep(0.5)

    print(f"\nDONE! Removed {deleted_count} stale deployments. Active production deployment preserved.")

if __name__ == "__main__":
    main()
