#!/usr/bin/env python3
"""Debug script to test configuration loading."""

import os
from pathlib import Path
from dotenv import load_dotenv
from prometh_cortex.config import load_config

print("=== DEBUG CONFIG LOADING ===")
print(f"Current working directory: {Path.cwd()}")

# Test dotenv loading
print("\n1. Testing dotenv loading:")
load_dotenv(".env")
datalake_repos_raw = os.getenv("DATALAKE_REPOS")
print(f"Raw DATALAKE_REPOS from env: {repr(datalake_repos_raw)}")

# Test path existence
if datalake_repos_raw:
    path = Path(datalake_repos_raw).expanduser().resolve()
    print(f"Resolved path: {path}")
    print(f"Path exists: {path.exists()}")
    print(f"Path is dir: {path.is_dir()}")

# Test our config loading
print("\n2. Testing prometh-cortex config loading:")
try:
    config = load_config()
    print(f"Config loaded successfully!")
    print(f"Datalake repos: {config.datalake_repos}")
    for i, repo in enumerate(config.datalake_repos):
        print(f"  Repo {i}: {repo} (exists: {repo.exists()})")
except Exception as e:
    print(f"Config loading failed: {e}")
    import traceback
    traceback.print_exc()