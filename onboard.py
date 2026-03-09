#!/usr/bin/env python3
"""
PersonalAI Onboarding — main entry point.

Usage:
    python onboard.py                    Run full onboarding for a new user
    python onboard.py --resume <handle>  Resume from saved interview data
    python onboard.py --regen <handle>   Regenerate memory files from saved data

What this does:
  1. Conducts a 15-minute Claude-powered interview
  2. Generates personalized memory files from your answers
  3. Copies + patches the AI-Knowledge codebase with your identity
  4. Produces a ready-to-run ~/Desktop/AI-{handle}/ directory

Run this once per person you're setting up.
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path config
# ---------------------------------------------------------------------------

ONBOARD_DIR = Path(__file__).parent
AIKNOWLEDGE_SOURCE = Path.home() / "Desktop" / "AI-Knowledge"
OUTPUT_BASE = Path.home() / "Desktop"
SAVED_INTERVIEWS_DIR = ONBOARD_DIR / ".saved_interviews"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

sys.path.insert(0, str(ONBOARD_DIR))

try:
    from core.interviewer import run_interview
    from core.memory_gen import generate_all
    from core.patcher import copy_and_patch
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the AI-Onboard directory.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_interview(data: dict, handle: str):
    """Save interview data so onboarding can be resumed or memories regenerated."""
    SAVED_INTERVIEWS_DIR.mkdir(exist_ok=True)
    # Don't save API key to disk
    save_data = {k: v for k, v in data.items() if k != "api_key"}
    path = SAVED_INTERVIEWS_DIR / f"{handle}.json"
    path.write_text(json.dumps(save_data, indent=2))
    print(f"\n  Interview data saved to {path}")


def _load_interview(handle: str) -> dict:
    path = SAVED_INTERVIEWS_DIR / f"{handle}.json"
    if not path.exists():
        print(f"No saved interview found for @{handle}.")
        sys.exit(1)
    return json.loads(path.read_text())


def _check_source():
    if not AIKNOWLEDGE_SOURCE.exists():
        print(f"""
  Source AI-Knowledge directory not found at:
  {AIKNOWLEDGE_SOURCE}

  Either update AIKNOWLEDGE_SOURCE in onboard.py or clone it there first.
""")
        sys.exit(1)


def _print_done(handle: str, target_dir: Path):
    print(f"""
{'=' * 62}
  Done! Your personalized AI brain is ready.
{'=' * 62}

  Location:  {target_dir}

  Next steps:

  1. Go to your new directory:
     cd {target_dir}

  2. Install dependencies (once):
     pip install anthropic playwright rich
     playwright install chromium

  3. Sync your Twitter profile (reads your tweets, replies,
     likes, and bookmarks to sharpen the model):
     python run.py profile-sync --tweets 30 --replies 30 --likes 30 --bookmarks 30

  4. Build your psychological profile from memory files:
     python run.py soul-map

  5. Run a test session (dry-run, no actual posting):
     python run.py skill twitter_browser --dry-run

  6. Run a real session:
     python run.py skill twitter_browser --real

  After a few sessions:

  7. Deduplicate and merge near-duplicate memory entries:
     python run.py consolidate-memory

  8. Rebuild your soul map as memories grow:
     python run.py soul-map --rebuild

  Commands reference:
     python run.py profile-sync --tweets N --replies N --likes N --bookmarks N
     python run.py soul-map [--rebuild]
     python run.py consolidate-memory
     python run.py skill twitter_browser [--dry-run | --real]

  Tip: The system gets dramatically better after 2-3 sessions
  where you edit the replies. Your edits become rules.

{'=' * 62}
""")


# ---------------------------------------------------------------------------
# Core flow
# ---------------------------------------------------------------------------

def run_full_onboarding():
    _check_source()

    # Step 1: Interview
    print("\n  Starting interview...\n")
    data = run_interview()

    handle = data["foundation"]["handle"]
    api_key = data["api_key"]

    # Save interview data (sans API key)
    _save_interview(data, handle)

    # Step 2: Target directory
    target_dir = OUTPUT_BASE / f"AI-{handle}"
    if target_dir.exists():
        print(f"\n  Directory {target_dir} already exists.")
        overwrite = input("  Overwrite? (y/n): ").strip().lower()
        if overwrite != "y":
            print("  Aborted. Use --resume to add to existing setup.")
            sys.exit(0)

    # Step 3: Copy + patch codebase
    print(f"\n  Building your personalized AI-Knowledge instance at:")
    print(f"  {target_dir}\n")

    profile = {**data.get("foundation", {})}
    profile["keyword_bank"] = data.get("domain", {}).get("keyword_bank", {})
    profile["brand_pillars"] = data.get("domain", {}).get("brand_pillars", {})
    profile["current_work"] = data["foundation"].get("current_work", "")
    profile["background"] = data["foundation"].get("background", "")
    profile["_api_key"] = api_key  # written to .env, not saved to JSON

    print("  Copying and patching codebase...")
    result = copy_and_patch(AIKNOWLEDGE_SOURCE, target_dir, profile)

    # Step 4: Generate memory files
    print("\n  Generating memory files (this takes about 1 minute)...")
    generate_all(data, target_dir, api_key)

    # Step 5: Optional profile sync
    if data.get("do_profile_sync"):
        print("\n  Running profile sync to read your tweets...")
        try:
            sync_script = target_dir / "run.py"
            if sync_script.exists():
                os.system(f"python {sync_script} profile-sync --tweets 20 --replies 20 --likes 20")
        except Exception as e:
            print(f"  Profile sync failed (run it manually later): {e}")

    # Done
    _print_done(handle, target_dir)


def run_regen(handle: str):
    """Regenerate memory files from saved interview data (re-run Claude generation)."""
    data = _load_interview(handle)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        api_key = input("  Anthropic API key: ").strip()

    data["api_key"] = api_key
    target_dir = OUTPUT_BASE / f"AI-{handle}"

    print(f"\n  Regenerating memory files for @{handle}...")
    generate_all(data, target_dir, api_key)
    print("\n  Done.")


def run_resume(handle: str):
    """Resume from saved interview — skip interview, redo everything else."""
    _check_source()
    data = _load_interview(handle)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        api_key = input("  Anthropic API key: ").strip()
    data["api_key"] = api_key

    target_dir = OUTPUT_BASE / f"AI-{handle}"
    profile = {**data.get("foundation", {})}
    profile["keyword_bank"] = data.get("domain", {}).get("keyword_bank", {})
    profile["brand_pillars"] = data.get("domain", {}).get("brand_pillars", {})
    profile["current_work"] = data["foundation"].get("current_work", "")
    profile["background"] = data["foundation"].get("background", "")
    profile["_api_key"] = api_key

    print(f"\n  Patching codebase for @{handle}...")
    copy_and_patch(AIKNOWLEDGE_SOURCE, target_dir, profile)

    print(f"\n  Regenerating memory files...")
    generate_all(data, target_dir, api_key)

    _print_done(handle, target_dir)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    if not args:
        run_full_onboarding()
    elif args[0] == "--resume" and len(args) >= 2:
        run_resume(args[1].lstrip("@"))
    elif args[0] == "--regen" and len(args) >= 2:
        run_regen(args[1].lstrip("@"))
    else:
        print("""
PersonalAI Onboarding

Usage:
  python onboard.py                     Full onboarding for a new user
  python onboard.py --resume <handle>   Resume from saved interview data
  python onboard.py --regen <handle>    Regenerate memory files only
""")


if __name__ == "__main__":
    main()
