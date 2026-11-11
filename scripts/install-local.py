#!/usr/bin/env python3
"""Install only Graft, preserving any previous copy; do not edit Hermes config."""
import argparse
import os
from pathlib import Path
import shutil
import time

parser = argparse.ArgumentParser(description="Install Graft into a local Hermes home.")
parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")))
args = parser.parse_args()
source = Path(__file__).resolve().parents[1]
home = args.hermes_home.expanduser().resolve()
if not (home / "config.yaml").exists() and not (home / "hermes-agent").exists():
    raise SystemExit("Finish installing Hermes first, or pass its actual home with --hermes-home.")
target = home / "plugins" / "graft"
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists() or target.is_symlink():
    if target.resolve() == source:
        print("This checkout is already linked into Hermes."); raise SystemExit(0)
    backup = home / "plugins-backup" / ("graft-" + time.strftime("%Y%m%d-%H%M%S"))
    backup.parent.mkdir(parents=True, exist_ok=True)
    target.rename(backup)
    print("Saved previous Graft copy:", backup)
shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules", "tests", "deploy", "test-results"))
print("Graft files installed at:", target)
print("Next: enable Graft's agent and Desktop components in Hermes → Capabilities → Plugins.")
print("If it is not listed, restart Hermes or use Rescan. No settings or secrets were changed.")
