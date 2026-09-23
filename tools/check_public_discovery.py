#!/usr/bin/env python3
"""Probe the live IDKMesh discovery surface with representative crawler UAs.

This is an external availability check. It does not claim indexing, ranking,
citation, or vendor endorsement.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
import urllib.robotparser

ROOT_ROBOTS = "https://mskazemi.com/robots.txt"
HOME = "https://mskazemi.com/idkmesh/"
TOPICS = "https://mskazemi.com/idkmesh/topics/"
SITEMAP = "https://mskazemi.com/idkmesh/sitemap.xml"
LLMS = "https://mskazemi.com/idkmesh/llms.txt"
INDEXNOW_KEY = "7c1f6d4a9b2e3c8f5a0d1e7b4c6f8a2d"
INDEXNOW_KEY_URL = f"https://mskazemi.com/idkmesh/{INDEXNOW_KEY}.txt"

DIRECTORY_HUBS = {
    name: f"https://mskazemi.com/idkmesh/{name}/"
    for name in (
        "architecture",
        "audits",
        "community",
        "conversations",
        "decisions",
        "findings",
        "foundations",
        "planning",
        "research",
        "specifications",
    )
}

TOPIC_PAGES = {
    "agent-governance": (
        "https://mskazemi.com/idkmesh/topics/agent-governance.html",
        "AI agent governance",
    ),
    "ai-agent-verification": (
        "https://mskazemi.com/idkmesh/topics/ai-agent-verification.html",
        "AI agent verification",
    ),
    "ai-code-review": (
        "https://mskazemi.com/idkmesh/topics/ai-code-review.html",
        "AI code review",
    ),
    "llm-judge-reliability": (
        "https://mskazemi.com/idkmesh/topics/llm-judge-reliability.html",
        "LLM-as-a-judge",
    ),
    "mcp-a2a-interoperability": (
        "https://mskazemi.com/idkmesh/topics/mcp-a2a-interoperability.html",
        "MCP",
    ),
    "multi-agent-orchestration": (
        "https://mskazemi.com/idkmesh/topics/multi-agent-orchestration.html",
        "Multi-agent orchestration",
    ),
    "provenance-evidence": (
        "https://mskazemi.com/idkmesh/topics/provenance-evidence.html",
        "AI provenance",
    ),
    "verification-scaling": (
        "https://mskazemi.com/idkmesh/topics/verification-scaling.html",
        "Verification debt",
    ),
    "verified-swarm-engineering": (
        "https://mskazemi.com/idkmesh/topics/verified-swarm-engineering.html",
        "Verified swarm",
    ),
    "verifier-panels": (
        "https://mskazemi.com/idkmesh/topics/verifier-panels.html",
        "Verifier panels",
    ),
}

USER_AGENTS = {
    "browser": "Mozilla/5.0 (compatible; IDKMesh-Discovery-Monitor/1.0)",
    "google": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "bing": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "yahoo": "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
    "openai": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "claude-search": "Claude-SearchBot",
    "claude-user": "Claude-User",
    "perplexity": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "perplexity-user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
}

ROBOTS_USER_AGENTS = {
    "google": "Googlebot",
    "bing": "bingbot",
    "yahoo": "Slurp",
    "openai": "OAI-SearchBot",
    "claude-search": "Claude-SearchBot",
    "claude-user": "Claude-User",
    "perplexity": "PerplexityBot",
    "perplexity-user": "Perplexity-User",
}


def fetch(url: str, user_agent: str, timeout: float = 10.0) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(512_000).decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as error:
        return error.code, error.read(64_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def _robots_parser(text: str) -> urllib.robotparser.RobotFileParser:
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def probe() -> list[str]:
    failures: list[str] = []
    browser = USER_AGENTS["browser"]

    robots_status, robots = fetch(ROOT_ROBOTS, browser)
    if robots_status != 200:
        failures.append(f"robots.txt returned HTTP {robots_status}")
    else:
        lower = robots.lower()
        if "sitemap:" not in lower or "mskazemi.com/idkmesh/sitemap.xml" not in lower:
            failures.append("domain-root robots.txt does not advertise the IDKMesh sitemap")
        parser = _robots_parser(robots)
        for name, token in ROBOTS_USER_AGENTS.items():
            for url in (HOME, TOPICS):
                if not parser.can_fetch(token, url):
                    failures.append(f"robots.txt blocks {name} from {url}")

    sitemap_status, sitemap = fetch(SITEMAP, browser)
    if sitemap_status != 200:
        failures.append(f"sitemap returned HTTP {sitemap_status}")
    else:
        expected_urls = [
            HOME,
            TOPICS,
            *DIRECTORY_HUBS.values(),
            *(url for url, _ in TOPIC_PAGES.values()),
        ]
        for expected in expected_urls:
            if expected not in sitemap:
                failures.append(f"sitemap does not contain {expected}")

    home_status, home_body = fetch(HOME, browser)
    if home_status != 200 or "IDKMesh" not in home_body:
        failures.append(f"browser homepage baseline invalid: HTTP {home_status}")

    topic_status, topic_body = fetch(TOPICS, browser)
    if topic_status != 200:
        failures.append(f"topic hub returned HTTP {topic_status}")
    elif "AI agent verification" not in topic_body or "multi-agent orchestration" not in topic_body.lower():
        failures.append("topic hub returned 200 but expected topic content is absent")

    for hub_id, url in DIRECTORY_HUBS.items():
        status, body = fetch(url, browser)
        if status != 200:
            failures.append(f"{hub_id} directory hub returned HTTP {status}")
        elif not body.strip():
            failures.append(f"{hub_id} directory hub returned an empty body")

    for topic_id, (url, marker) in TOPIC_PAGES.items():
        status, body = fetch(url, browser)
        if status != 200:
            failures.append(f"{topic_id}: HTTP {status}")
            continue
        if marker.lower() not in body.lower():
            failures.append(f"{topic_id}: expected content marker {marker!r} is absent")
        if 'rel="canonical"' not in body.lower():
            failures.append(f"{topic_id}: rendered page has no canonical link")
        if 'name="description"' not in body.lower():
            failures.append(f"{topic_id}: rendered page has no meta description")

    llms_status, llms = fetch(LLMS, browser)
    if llms_status != 200:
        failures.append(f"llms.txt returned HTTP {llms_status}")
    else:
        for expected in ("AI agent verification", "Multi-agent orchestration", TOPICS):
            if expected not in llms:
                failures.append(f"llms.txt is missing {expected!r}")

    key_status, key_body = fetch(INDEXNOW_KEY_URL, browser)
    if key_status != 200:
        failures.append(f"IndexNow key returned HTTP {key_status}")
    elif key_body.strip() != INDEXNOW_KEY:
        failures.append("IndexNow key body does not match the committed public key")

    if home_status == 200 and "IDKMesh" in home_body:
        baseline_len = len(home_body)
        for name, user_agent in USER_AGENTS.items():
            if name == "browser":
                continue
            status, body = fetch(HOME, user_agent)
            if status != 200:
                failures.append(f"{name}: homepage HTTP {status}")
                continue
            if "IDKMesh" not in body or "Verified" not in body:
                failures.append(f"{name}: homepage content missing IDKMesh markers")
            if baseline_len and len(body) < baseline_len * 0.70:
                failures.append(
                    f"{name}: crawler body is unexpectedly small "
                    f"({len(body)} vs browser {baseline_len})"
                )
            print(f"{name}: HTTP {status}, {len(body)} bytes")

    return failures


def main() -> int:
    failures = probe()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "Discovery surface healthy: robots, sitemap, directory hubs, topic hub, "
        "ten topic pages, llms.txt, IndexNow key, and representative crawler "
        "probes all passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
