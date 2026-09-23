#!/usr/bin/env python3
"""Probe the live IDKMesh discovery surface with representative crawler UAs.

This is an external availability check. It does not claim indexing, ranking,
citation, or vendor endorsement.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

ROOT_ROBOTS = "https://mskazemi.com/robots.txt"
HOME = "https://mskazemi.com/idkmesh/"
TOPICS = "https://mskazemi.com/idkmesh/topics/"
SITEMAP = "https://mskazemi.com/idkmesh/sitemap.xml"

USER_AGENTS = {
    "browser": "Mozilla/5.0 (compatible; IDKMesh-Discovery-Monitor/1.0)",
    "google": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "bing": "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "openai": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "claude-search": "Claude-SearchBot",
    "claude-user": "Claude-User",
    "perplexity": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "perplexity-user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
}


def fetch(url: str, user_agent: str, timeout: float = 20.0) -> tuple[int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(256_000).decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as error:
        return error.code, error.read(64_000).decode("utf-8", errors="replace")


def main() -> int:
    failures: list[str] = []

    robots_status, robots = fetch(ROOT_ROBOTS, USER_AGENTS["browser"])
    if robots_status != 200:
        failures.append(f"robots.txt returned HTTP {robots_status}")
    else:
        lower = robots.lower()
        if "sitemap:" not in lower or "mskazemi.com/idkmesh/sitemap.xml" not in lower:
            failures.append("domain-root robots.txt does not advertise the IDKMesh sitemap")

    sitemap_status, sitemap = fetch(SITEMAP, USER_AGENTS["browser"])
    if sitemap_status != 200:
        failures.append(f"sitemap returned HTTP {sitemap_status}")
    else:
        for expected in (HOME, TOPICS):
            if expected not in sitemap:
                failures.append(f"sitemap does not contain {expected}")

    topic_status, topic_body = fetch(TOPICS, USER_AGENTS["browser"])
    if topic_status != 200:
        failures.append(f"topic hub returned HTTP {topic_status}")
    elif "AI agent verification" not in topic_body or "multi-agent orchestration" not in topic_body:
        failures.append("topic hub returned 200 but expected topic content is absent")

    browser_status, browser_body = fetch(HOME, USER_AGENTS["browser"])
    if browser_status != 200 or "IDKMesh" not in browser_body:
        failures.append(f"browser baseline invalid: HTTP {browser_status}")

    baseline_len = len(browser_body)
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

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print("Discovery surface healthy for all representative crawler probes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
