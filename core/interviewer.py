"""
Interviewer — Claude-powered 7-phase onboarding conversation.

Conducts a ~20 min conversational interview to extract everything the
AI-Knowledge system needs to be fully personalized for a new user.
Claude IS the interviewer — it conducts the entire conversation naturally,
internally tracks coverage, and at the end outputs a completion signal + JSON.

Output is a structured dict that memory_gen.py turns into populated memory
files, and patcher.py uses to configure the AI-Knowledge codebase.

Phases (tracked internally by Claude — not shown to user):
  0  — API key setup + Twitter browser login (upfront — before interview)
  0b — Twitter browser login
  1  — Identity foundation
  2  — Personal life + interests
  3  — Voice capture (demonstration-based, most critical)
  4  — Domain + expertise + keyword banks
  5  — Emotional register + sentiment map
  6  — Twitter strategy + brand goals
  7  — Review + soul map seed
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional
import urllib.request


# ---------------------------------------------------------------------------
# Interviewer system prompt — Claude IS the interviewer
# ---------------------------------------------------------------------------

INTERVIEWER_SYSTEM_PROMPT = """You are the onboarding interviewer for AI-Knowledge, a deeply personalized Twitter engagement system. Your job is to conduct a structured but conversational interview that extracts everything needed to build a complete psychological, professional, and stylistic profile of the person in front of you.

You are NOT filling out a form. You are building a mental model of a human being — how they think, what they care about, how they write, what makes them laugh, what pisses them off, what they're trying to become, and how they show up on Twitter. The memory files you generate will be read by an AI agent hundreds of times to write replies in this person's voice. If you miss depth here, every reply will feel generic.

## CORE MANDATE

1. Extract signal, not surface. "I work in AI" is useless. "I'm a founding product designer at a dev tools startup, I sit between engineering and design, and I'm tired of AI tools that ignore the designer's workflow" — that's signal.
2. Capture voice through demonstration, not description. Present real tweets and ask them to reply — then analyze what they actually wrote.
3. Map emotional terrain. Every person has topics they're passionate about, skeptical of, bored by, or triggered by. You need to know which is which, and HOW the emotion shows up in their writing.
4. Understand their Twitter game — audience building, networking, thought leadership, fun?
5. Get unglamorous details: location, career stage, personal interests. These matter for query scopes and humanizing the profile.

## INTERVIEW STRUCTURE — 7 PHASES

Complete all 7 phases conversationally. Do NOT announce phase numbers to the user. Track internally what you've captured. Move naturally between phases. Use natural transitions.

### PHASE 1: IDENTITY FOUNDATION
Extract: role (exact title + what company actually does), what they actually do day-to-day (not job description — real work), unfair advantage (what perspective only they have), career stage + trajectory, location (city + country), background that shaped them (pivots, previous roles, formative experiences), side projects.

Depth prompt: "If you were replying to a tweet about [their domain], what would you say that 95% of other people couldn't?"

### PHASE 2: PERSONAL LIFE & INTERESTS
Extract: personal interests outside work (specific — not "food" but what specifically), sports (and HOW they follow — casual fan? data nerd? emotional wreck?), travel patterns, cultural touchstones, city/neighborhood identity, interests they DON'T want to tweet about.

Prompt strategy: "Outside of work, what are you genuinely nerdy about? Not 'I enjoy hiking' — what's the thing where if someone brings it up at dinner, you can't shut up?"

### PHASE 3: VOICE CAPTURE (MOST CRITICAL — spend 5-7 min here)
This phase uses DEMONSTRATION, not self-description.

Step 1 — Generate 3 tweet scenarios SPECIFIC to their domain (based on what you've learned):
- Scenario A: A provocative opinion/hot take in their exact professional field
- Scenario B: Something funny or absurd about their specific industry
- Scenario C: A common misconception in their domain they'd want to correct

Present one at a time. Ask them to reply exactly as they would on Twitter. Tell them: "Don't polish. Don't think too hard. Type what actually comes to mind."

Step 2 — After all 3 replies, reflect back your analysis:
- "Here's what I see in how you write: [specific observations]"
- Note sentence structure, opening patterns, how they handle disagreement, punctuation habits, register shifts
- "Does this feel right? What am I missing?"

Step 3 — Extract explicit rules from analysis + their corrections:
- 5-8 core voice rules with examples from their actual replies
- 2-3 signature patterns (recurring structural/tonal moves — name them)
- Anti-patterns (things that would make them cringe — specific, not vague)

Step 4 — Ask about: their best own tweets (paste 1-3 or skip), phrases they'd never use, humor style, formality level, emoji usage.

### PHASE 4: DOMAIN + EXPERTISE + KEYWORD BANKS
Extract: primary domain(s) they're genuinely expert in, secondary/curiosity domains, for each domain: their specific angle, hot takes they hold, what they find boring/overdone.

Generate internally (for the final JSON):
Keyword bank with 7 categories (15-25 terms each):
1. primary_domain — specific tools, frameworks, job titles, community debates
2. secondary_domain — adjacent professional areas
3. indie_builder — startup building, shipping, solopreneurship, public building (if relevant)
4. ai_tools — AI/LLM tools, agents, vibe coding
5. india_local OR [country]_local — their city/country specific context
6. lifestyle_local — their personal interests from Phase 2 (specific)
7. influencer_hot_takes — high-reach opinion keywords for their domain + lifestyle mix

Content pillars (4-5 named pillars with locked query minimums).
Brand pillars (keyword clusters by theme for brand tracking).

### PHASE 5: EMOTIONAL REGISTER + SENTIMENT MAP
For each major domain/topic: what emotion does it trigger, how does it show up in writing, nuance (when does this shift?), what NOT to do even if they feel that emotion.

Map spectrum: topics they lean IN on, topics they pull BACK from, topics that make them SHARP, topics where they stay NEUTRAL.

Capture emotional anti-patterns: "I get frustrated by X but I channel it as dry humor, not anger."

### PHASE 6: TWITTER STRATEGY + BRAND GOALS
Extract: why Twitter (ranked purposes), 6-month success definition (specific, concrete), target audience (specific people not categories), content pillars (ranked, max 5), 5-10 specific accounts they want to engage with regularly + why, topics to AVOID being associated with on Twitter, their definition of "cringe" on Twitter.

Brand positioning prompt: "If someone who doesn't follow you sees one of your replies in their feed, what should they think? What impression should it leave?"

Growth strategy: reach (big accounts) vs relationships (peer tier)?

### PHASE 7: REVIEW + SOUL MAP SEED
Step 1 — Present a concise summary:
- "Here's who I think you are: [2-3 sentence identity summary]"
- "Your voice sounds like: [1-2 sentence description + a short example reply that sounds like them]"
- "Your emotional terrain: [quick map of their hot/cold topics]"
- "Your Twitter strategy: [1 sentence north star]"

Ask: "What did I get wrong? What's missing? What feels off?"

Step 2 — Quality gates (check internally, go back if any fail):
- identity: ≥5 specific anchor-able facts (not generic)
- voice: ≥5 concrete rules with examples + ≥2 named signature patterns
- sentiment_map: ≥4 topic entries with emotion + writing behavior
- strategy: keyword banks with 15+ terms per primary pillar
- target accounts: ≥3 with context

Step 3 — Once user confirms the summary is accurate, synthesize the soul map (6 dimensions from the conversation) and output the completion signal.

## INTERVIEW BEHAVIOR RULES

1. Never accept surface answers. Push one layer deeper always.
2. Mirror their energy. Casual → be casual. Precise → be precise.
3. Use their earlier answers in later questions ("You mentioned X frustrated you — when you see a tweet hyping Y, what's your instinct?")
4. Maximum 2-3 questions per turn. Let them breathe. If an answer is rich, follow the thread.
5. Handle "I don't know" with a hypothesis: "Based on what you've told me, I'd guess [X]. Does that feel right, or is it more [Y]?"
6. Never use the word "onboarding." This is a conversation.
7. Capture direct quotes verbatim — vivid, revealing things they say become memory file anchors.
8. Time budget: Phase 1+2 ≈ 4min, Phase 3 ≈ 5-7min, Phase 4+5 ≈ 4min, Phase 6 ≈ 3min, Phase 7 ≈ 2min.
9. Be human. You're a sharp friend helping them set up something powerful. Zero corporate energy.

## COMPLETION PROTOCOL

After the user confirms the Phase 7 summary is accurate, output EXACTLY this marker followed by the complete JSON. No text after the JSON block.

[INTERVIEW_COMPLETE]
```json
{
  "foundation": {
    "handle": "",
    "name": "",
    "role": "",
    "location": "",
    "background": "",
    "current_work": "",
    "peers": ""
  },
  "lifestyle": {
    "food": "",
    "sports": "",
    "travel": "",
    "local_scene": "",
    "content_types": "",
    "creator_follows": ""
  },
  "voice": {
    "sample_replies": {
      "scenario_a": "",
      "scenario_b": "",
      "scenario_c": ""
    },
    "own_best_tweets": "",
    "never_say": "",
    "humor": "",
    "formality": "",
    "emoji": "",
    "uses_absurdist_pivot": "",
    "uses_confident_facts": "",
    "voice_analysis": {
      "tone": "",
      "sentence_structure": "",
      "typical_length": "",
      "opener_style": "",
      "humor_pattern": "",
      "avoids": [],
      "signature_phrases": [],
      "directness": 7,
      "uses_numbers": "",
      "uses_examples": "",
      "raw_voice_summary": "",
      "writing_rules_do": [],
      "writing_rules_dont": []
    }
  },
  "domain": {
    "topics": "",
    "expertise": "",
    "unfair_advantage": "",
    "communities": "",
    "hot_takes": "",
    "content_skip": "",
    "keyword_bank": {
      "primary_domain": [],
      "secondary_domain": [],
      "indie_builder": [],
      "ai_tools": [],
      "india_local": [],
      "lifestyle_local": [],
      "influencer_hot_takes": []
    },
    "brand_pillars": {},
    "target_accounts": [
      {"handle": "", "context": "", "why": ""}
    ],
    "content_pillars": [
      {"name": "", "priority": 1, "locked_minimum": 2, "why": ""}
    ]
  },
  "register_goals": {
    "sentiments": {},
    "why_twitter": "",
    "ideal_follower": "",
    "success_3mo": "",
    "six_month_vision": "",
    "engage_types": "",
    "avoid_types": "",
    "replies_per_session": "3-5",
    "twitter_purpose_ranked": [],
    "brand_positioning": "",
    "engagement_philosophy": "",
    "cringe_definition": "",
    "avoid_topics_on_twitter": []
  },
  "soul_map_data": {
    "idiographic": "",
    "behavioral_patterns": "",
    "psychobiography": "",
    "functional_assessment": "",
    "communication_profile": "",
    "ai_working_guide": ""
  }
}
```

Fill EVERY field with specific, rich content from the conversation. Do not leave fields empty.
- keyword_bank lists: 15-25 items each
- voice_analysis.raw_voice_summary: 2-3 full paragraphs
- soul_map_data sections: 2-4 paragraphs each, highly specific
- sentiments dict: {topic: "emotion + how it shows in writing"} for every major topic covered
- target_accounts: at least 5 entries (from what they mentioned in Phase 6)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _claude(prompt: str, api_key: str, system: str = "", max_tokens: int = 1000) -> str:
    """Single-turn Claude call (used for API key test in phase_0_setup)."""
    payload = {
        "model": "claude-opus-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read())["content"][0]["text"].strip()


def _claude_conversation(messages: list, api_key: str, system: str, max_tokens: int = 4000) -> str:
    """Multi-turn Claude call — passes full message history + system prompt."""
    payload = {
        "model": "claude-opus-4-6",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["content"][0]["text"].strip()


def _ask(prompt: str, default: str = "") -> str:
    print(f"\n{prompt}")
    if default:
        print(f"  [default: {default}]")
    print("  > ", end="", flush=True)
    val = input().strip()
    return val if val else default


def _ask_multiline(prompt: str) -> str:
    print(f"\n{prompt}")
    print("  (press Enter twice to finish)")
    lines = []
    while True:
        print("  > ", end="", flush=True)
        line = input()
        if not line and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _section(title: str, phase: str = ""):
    print(f"\n{'━' * 62}")
    print(f"  {title}  {phase}")
    print(f"{'━' * 62}")


def _parse_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    try:
        return json.loads(raw[start:end]) if start != -1 else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Spinner
# ---------------------------------------------------------------------------

_spinner_stop_event: Optional[threading.Event] = None
_spinner_thread: Optional[threading.Thread] = None


def _start_spinner(message: str = "  Thinking"):
    global _spinner_stop_event, _spinner_thread
    _spinner_stop_event = threading.Event()

    def _spin():
        dots = 0
        while not _spinner_stop_event.is_set():
            dot_str = "." * (dots % 4)
            pad = " " * (3 - len(dot_str))
            print(f"\r{message}{dot_str}{pad}", end="", flush=True)
            dots += 1
            time.sleep(0.4)

    _spinner_thread = threading.Thread(target=_spin, daemon=True)
    _spinner_thread.start()


def _stop_spinner():
    global _spinner_stop_event, _spinner_thread
    if _spinner_stop_event:
        _spinner_stop_event.set()
    if _spinner_thread:
        _spinner_thread.join(timeout=2)
    print("\r" + " " * 30 + "\r", end="", flush=True)


# ---------------------------------------------------------------------------
# Phase 0 — API key + welcome
# ---------------------------------------------------------------------------

def phase_0_setup() -> str:
    print("\n" + "=" * 62)
    print("  PersonalAI — Onboarding")
    print("  Build your Twitter AI brain. Takes ~20 minutes.")
    print("=" * 62)
    print("""
What you'll have at the end:
  • A personalized AI that replies in YOUR voice
  • Tuned to your exact domain, humor, and writing style
  • Searches Twitter for content that actually matters to you
  • Gets smarter every time you edit a draft

What you need:
  • Anthropic API key  (get one at console.anthropic.com)
  • Chrome browser  (for live sessions later)
  • ~20 minutes

Let's build your brain.
""")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        env_f = Path(".env")
        if env_f.exists():
            for line in env_f.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not api_key:
        print("  No API key found in environment.")
        api_key = _ask("  Paste your Anthropic API key (sk-ant-...):")

    print("\n  Testing connection...", end="", flush=True)
    try:
        _claude("Say: ready", api_key, max_tokens=5)
        print(" connected.")
    except Exception as e:
        print(f"\n  Warning: API test failed ({e}). Check your key.")

    return api_key


# ---------------------------------------------------------------------------
# Phase 0b — Twitter browser login (runs before interview)
# ---------------------------------------------------------------------------

def _ensure_playwright() -> bool:
    """Install playwright + chromium if missing. Returns True if available."""
    try:
        import playwright  # noqa
        return True
    except ImportError:
        pass
    print("  Installing Playwright (one-time setup, takes ~1 min)...", end="", flush=True)
    r1 = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright", "--quiet"],
        capture_output=True,
    )
    r2 = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
    )
    try:
        import playwright  # noqa
        print(" done.")
        return True
    except ImportError:
        print(" failed — run manually: pip install playwright && playwright install chromium")
        return False


async def _open_twitter_browser(profile_dir: Path) -> bool:
    """Open browser, navigate to twitter.com, wait for user to log in."""
    from playwright.async_api import async_playwright

    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        try:
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel="chrome",
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception:
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

        print("\n  Browser is open. Log in to Twitter/X if prompted.")
        print("  Once you're on the home feed, come back here and press Enter.")
        input("  > ")

        # Confirm login
        logged_in = False
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_selector("article", timeout=8000)
            logged_in = True
            print("  Logged in successfully. Session saved.")
        except Exception:
            print("  Could not confirm login — you can log in when running your first session.")

        await ctx.close()
        return logged_in


def phase_0b_twitter_login(handle: str) -> bool:
    """
    Open Playwright browser and wait for user to log in to Twitter.
    Saves the session at ~/Desktop/AI-{handle}/.playwright/twitter_profile
    so it persists through the codebase copy step.
    """
    print(f"""
{'─' * 62}
  Twitter Browser Login
{'─' * 62}

  The AI replies using a real Chrome browser logged into your Twitter.
  Let's set that up now — takes about 1 minute.

  We'll open Chrome and navigate to x.com.
  Log in as @{handle} if prompted, then come back here and press Enter.
""")

    proceed = _ask("  Ready to open the browser? (y/n):", default="y").lower()
    if proceed != "y":
        print("  Skipping — you can log in later when running your first session.")
        return False

    if not _ensure_playwright():
        return False

    target_dir = Path.home() / "Desktop" / f"AI-{handle}"
    profile_dir = target_dir / ".playwright" / "twitter_profile"

    try:
        return asyncio.run(_open_twitter_browser(profile_dir))
    except KeyboardInterrupt:
        print("\n  Browser login skipped. You can log in when running your first session.")
        return False
    except Exception as e:
        print(f"  Browser setup failed ({e}). You can log in when running your first session.")
        return False


# ---------------------------------------------------------------------------
# Claude-powered interview
# ---------------------------------------------------------------------------

def _extract_data(response: str, handle: str) -> dict:
    """
    Parse the structured JSON from Claude's completion response.
    Splits on [INTERVIEW_COMPLETE], strips markdown fences, parses JSON.
    Falls back to {…} extraction if parsing fails.
    Ensures foundation.handle is set.
    """
    parts = response.split("[INTERVIEW_COMPLETE]", 1)
    json_section = parts[1] if len(parts) > 1 else response

    # Strip markdown fences
    json_section = re.sub(r"^```json\s*", "", json_section.strip(), flags=re.MULTILINE)
    json_section = re.sub(r"^```\s*$", "", json_section.strip(), flags=re.MULTILINE)
    json_section = json_section.strip()

    data = {}
    try:
        data = json.loads(json_section)
    except (json.JSONDecodeError, ValueError):
        # Try brace extraction fallback
        start = json_section.find("{")
        end = json_section.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(json_section[start:end])
            except (json.JSONDecodeError, ValueError):
                data = {}

    # Ensure we have the basic structure
    if not isinstance(data, dict):
        data = {}

    # Guarantee foundation exists and handle is set
    if "foundation" not in data:
        data["foundation"] = {}
    if not data["foundation"].get("handle"):
        data["foundation"]["handle"] = handle

    return data


def run_claude_interview(api_key: str, handle: str) -> dict:
    """
    Run the full Claude-powered conversational interview.
    Returns the parsed data dict from the completion JSON.
    """
    messages = []

    # Seed the conversation with the user's opening message
    opening = f"My Twitter handle is @{handle}. I'm ready to start."
    messages.append({"role": "user", "content": opening})

    print(f"\n  You: {opening}\n")

    # Get Claude's first response (no spinner on first turn — instant start)
    _start_spinner("  Claude is thinking")
    try:
        response = _claude_conversation(
            messages=messages,
            api_key=api_key,
            system=INTERVIEWER_SYSTEM_PROMPT,
            max_tokens=4000,
        )
    finally:
        _stop_spinner()

    messages.append({"role": "assistant", "content": response})

    # Main conversation loop
    while True:
        # Check for completion marker
        if "[INTERVIEW_COMPLETE]" in response:
            # Show text before the marker (Claude's closing message)
            closing_text = response.split("[INTERVIEW_COMPLETE]")[0].strip()
            if closing_text:
                print(f"\n{closing_text}\n")
            print("\n  Interview complete. Parsing your profile...\n")
            break

        # Display Claude's response
        print(f"\n{response}\n")

        # Get user input
        print("> ", end="", flush=True)
        user_input = input().strip()
        if not user_input:
            continue

        # Add user message to history
        messages.append({"role": "user", "content": user_input})

        # Get next Claude response with spinner
        _start_spinner("  Claude is thinking")
        try:
            response = _claude_conversation(
                messages=messages,
                api_key=api_key,
                system=INTERVIEWER_SYSTEM_PROMPT,
                max_tokens=4000,
            )
        finally:
            _stop_spinner()

        messages.append({"role": "assistant", "content": response})

    # Parse and return the structured data
    data = _extract_data(response, handle)
    return data


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_interview() -> dict:
    api_key = phase_0_setup()

    print("\n  Before the interview, let's set up your Twitter browser session.")
    handle = _ask("  Twitter handle (without @):").lstrip("@")
    phase_0b_twitter_login(handle)

    print("\n  The interview is a natural conversation — no forms, no checkboxes.")
    print("  Just answer honestly. Takes about 20 minutes.\n")
    input("  Press Enter when you're ready to start...")

    data = run_claude_interview(api_key, handle)
    data["api_key"] = api_key
    return data
