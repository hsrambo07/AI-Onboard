"""
patcher.py — Copies the AI-Knowledge codebase and patches all hardcoded
user-specific strings with values from user_profile.json.

What gets patched:
  - "harsh_logs" / "@harsh_logs"                → user's handle
  - "Harsh Singhal"                              → user's name
  - "Founding Product Designer at Entelligence AI" → user's role
  - "Bangalore"                                  → user's location
  - "Entelligence competes with Greptile..."     → removed or replaced
  - "6 years across design/engineering..."        → user's background
  - KEYWORD_BANK in twitter_browser_skill.py     → user's keyword bank
  - BRAND_PILLARS in brand_tracker.py            → user's brand pillars
  - query generation prompt description          → user's role/location

Also:
  - Copies the full AI-Knowledge codebase to target_dir
  - Skips: memories/, logs/, .playwright/, __pycache__, .env, *.pyc
  - Writes .env with user's API key
"""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Files and patterns to patch
# ---------------------------------------------------------------------------

# Tuples of (pattern, replacement_template)
# replacement_template uses {key} placeholders from user_profile
STRING_PATCHES = [
    # Handle references
    (r"harsh_logs", "{handle}"),
    (r"@harsh_logs", "@{handle}"),
    (r'"harsh_logs"', '"{handle}"'),
    # Full name first, then standalone first name (order matters — full name before partial)
    (r"Harsh Singhal", "{name}"),
    (r'"Harsh"', '"{name}"'),
    (r"\bHarsh\b", "{name}"),
    # Role references (most specific first)
    (r"Founding Product Designer at Entelligence AI", "{role}"),
    (r"Founding Product Designer at Entelligence", "{role}"),
    (r"Founding Product Designer at AI startup", "{role}"),
    # Location
    (r"\bBangalore\b", "{location}"),
    (r"\bBLR\b", "{location_short}"),
    (r"\bBlr\b", "{location_short}"),
    # Background blurb in system prompt
    (
        r"6 years across design/engineering/product/GTM, based in Bangalore",
        "{background_blurb}",
    ),
    # Company name — full name before bare name to avoid double-replacement
    (r"Entelligence AI", "{company}"),
    (r"\bEntelligence\b", "{company}"),
    # Competitor context — remove or neutralize
    (
        r"Entelligence competes with Greptile, CodeRabbit, Cursor, GitHub Copilot, Codeium, Tabnine, Qodo\.",
        "{competitor_context}",
    ),
    (
        r"Entelligence AI \(AI tools for engineering teams: code review, bug detection, dev productivity\)",
        "{current_work_blurb}",
    ),
    (
        r"AI tools for engineering teams: code review, bug detection, dev productivity",
        "{current_work_blurb}",
    ),
]

# Files to skip entirely during copy (sensitive or machine-specific)
SKIP_PATHS = {
    ".env", ".playwright", "logs", "__pycache__",
    ".git", "node_modules", ".DS_Store",
}

# Extensions to skip (binary / generated)
SKIP_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif"}

# Files that need keyword bank injection
KEYWORD_BANK_FILE = "skills/twitter_browser_skill.py"
BRAND_PILLARS_FILE = "core/brand_tracker.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_replacements(profile: dict) -> dict:
    """Build the substitution dict from user_profile.json."""
    handle = profile.get("handle", "user")
    location = profile.get("location", "")
    location_short = location[:3].upper() if location else "LOC"
    role = profile.get("role", "")
    name = profile.get("name", "")
    background = profile.get("background", "")
    current_work = profile.get("current_work", "")

    # Extract company name from role ("Founding X at Acme Corp" -> "Acme Corp")
    company = ""
    if " at " in role:
        company = role.split(" at ", 1)[-1].strip()
    if not company:
        company = current_work.split()[0] if current_work else ""

    return {
        "handle": handle,
        "name": name,
        "role": role,
        "location": location,
        "location_short": location_short,
        "background_blurb": f"{background}, based in {location}" if background else f"based in {location}",
        "competitor_context": "",  # Remove competitor context for new users
        "current_work_blurb": current_work or role,
        "company": company,
    }


def _patch_content(content: str, replacements: dict) -> str:
    """Apply all string patches to file content."""
    for pattern, template in STRING_PATCHES:
        try:
            replacement = template.format(**replacements)
            content = re.sub(pattern, replacement, content)
        except Exception:
            pass
    return content


def _should_skip(path: Path) -> bool:
    if path.name in SKIP_PATHS:
        return True
    if path.suffix in SKIP_EXTENSIONS:
        return True
    for skip in SKIP_PATHS:
        if skip in path.parts:
            return True
    return False


# ---------------------------------------------------------------------------
# Keyword bank injection
# ---------------------------------------------------------------------------

def _gen_keyword_bank_code(keyword_bank: dict) -> str:
    """Generate Python KEYWORD_BANK dict code from user_profile keyword_bank."""
    if not keyword_bank:
        return None
    lines = ["    KEYWORD_BANK = {"]
    for category, keywords in keyword_bank.items():
        kw_list = json.dumps(keywords)
        lines.append(f'        "{category}": {kw_list},')
    lines.append("    }")
    return "\n".join(lines)


def _patch_keyword_bank(content: str, keyword_bank: dict) -> str:
    """Replace the KEYWORD_BANK definition in twitter_browser_skill.py."""
    if not keyword_bank:
        return content

    new_bank = _gen_keyword_bank_code(keyword_bank)
    if not new_bank:
        return content

    # Match the existing KEYWORD_BANK = { ... } block (multiline)
    pattern = r"    KEYWORD_BANK\s*=\s*\{[^}]*(?:\{[^}]*\}[^}]*)?\}"
    # More robust: find the block by looking for KEYWORD_BANK = { then matching braces
    start_match = re.search(r"    KEYWORD_BANK\s*=\s*\{", content)
    if not start_match:
        return content

    start = start_match.start()
    # Find the matching closing brace
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    return content[:start] + new_bank + content[end:]


# ---------------------------------------------------------------------------
# Brand pillars injection
# ---------------------------------------------------------------------------

def _gen_brand_pillars_code(brand_pillars: dict) -> str:
    if not brand_pillars:
        return None
    lines = ["BRAND_PILLARS = {"]
    for pillar, keywords in brand_pillars.items():
        kw_list = json.dumps(keywords)
        lines.append(f'    "{pillar}": {kw_list},')
    lines.append("}")
    return "\n".join(lines)


def _patch_brand_pillars(content: str, brand_pillars: dict) -> str:
    """Replace the BRAND_PILLARS definition in brand_tracker.py."""
    if not brand_pillars:
        return content

    new_pillars = _gen_brand_pillars_code(brand_pillars)
    if not new_pillars:
        return content

    start_match = re.search(r"^BRAND_PILLARS\s*=\s*\{", content, re.MULTILINE)
    if not start_match:
        return content

    start = start_match.start()
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    return content[:start] + new_pillars + content[end:]


# ---------------------------------------------------------------------------
# For-You feed include list injection (twitter_browser_skill.py)
# ---------------------------------------------------------------------------

def _patch_for_you_base(content: str, keyword_bank: dict) -> str:
    """Replace _FOR_YOU_MUST_INCLUDE_BASE with user's domain keywords."""
    if not keyword_bank:
        return content

    # Pull top keywords from primary + secondary domains + ai_tools
    include_kws = []
    seen = set()
    for cat in ["primary_domain", "secondary_domain", "ai_tools", "influencer_hot_takes"]:
        for kw in keyword_bank.get(cat, [])[:10]:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                include_kws.append(kw_lower)

    if not include_kws:
        return content

    # Format as a multi-line list (max 6 per line for readability)
    lines = ["    _FOR_YOU_MUST_INCLUDE_BASE = ["]
    row = []
    for kw in include_kws:
        row.append(f'"{kw}"')
        if len(row) == 6:
            lines.append("        " + ", ".join(row) + ",")
            row = []
    if row:
        lines.append("        " + ", ".join(row) + ",")
    lines.append("    ]")
    new_block = "\n".join(lines)

    start_match = re.search(r"    _FOR_YOU_MUST_INCLUDE_BASE\s*=\s*\[", content)
    if not start_match:
        return content

    start = start_match.start()
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    return content[:start] + new_block + content[end:]


# ---------------------------------------------------------------------------
# handle filter in brand_tracker
# ---------------------------------------------------------------------------

def _patch_handle_filter(content: str, handle: str) -> str:
    """Replace 'harsh_logs' in the brand tracker's handle filter."""
    content = content.replace('"harsh_logs"', f'"{handle}"')
    content = content.replace("'harsh_logs'", f"'{handle}'")
    content = re.sub(r'"harsh"', f'"{handle[:5]}"', content)
    return content


# ---------------------------------------------------------------------------
# Main copy + patch
# ---------------------------------------------------------------------------

def copy_and_patch(
    source_dir: Path,
    target_dir: Path,
    profile: dict,
    verbose: bool = True,
):
    """
    Copy AI-Knowledge from source_dir to target_dir, patching all
    hardcoded user-specific strings with values from profile.
    """
    replacements = _build_replacements(profile)
    handle = profile.get("handle", "user")
    keyword_bank = profile.get("keyword_bank", {})
    brand_pillars = profile.get("brand_pillars", {})

    target_dir.mkdir(parents=True, exist_ok=True)

    patched = 0
    copied = 0
    skipped = 0

    for src_path in sorted(source_dir.rglob("*")):
        if _should_skip(src_path):
            skipped += 1
            continue

        rel = src_path.relative_to(source_dir)

        # Skip memories/ — they'll be written by memory_gen
        if rel.parts and rel.parts[0] == "memories":
            continue

        dst_path = target_dir / rel

        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue

        try:
            content = src_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            shutil.copy2(src_path, dst_path)
            copied += 1
            continue

        # Apply string patches
        original = content
        content = _patch_content(content, replacements)

        # File-specific patches
        if rel.name == "twitter_browser_skill.py" and keyword_bank:
            content = _patch_keyword_bank(content, keyword_bank)
            content = _patch_for_you_base(content, keyword_bank)

        if rel.name == "brand_tracker.py":
            content = _patch_brand_pillars(content, brand_pillars)
            content = _patch_handle_filter(content, handle)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_text(content, encoding="utf-8")

        if content != original:
            patched += 1
        else:
            copied += 1

    if verbose:
        print(f"    {copied + patched} files copied ({patched} patched with your profile)")

    # Write .env with API key
    api_key = profile.get("_api_key", "")
    if api_key:
        env_path = target_dir / ".env"
        env_path.write_text(f"ANTHROPIC_API_KEY={api_key}\n")

    # Create empty logs/ dir
    (target_dir / "logs").mkdir(exist_ok=True)

    return {"patched": patched, "copied": copied}
