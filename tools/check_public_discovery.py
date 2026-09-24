#!/usr/bin/env python3
"""Probe the live IDKMesh discovery surface with representative crawler UAs.

This is an external availability check. It does not claim indexing, ranking,
citation, or vendor endorsement.
"""

from __future__ import annotations

import sys
from html.parser import HTMLParser
import urllib.error
import urllib.request
import urllib.robotparser

ROOT_ROBOTS = "https://mskazemi.com/robots.txt"
HOME = "https://mskazemi.com/idkmesh/"
TOPICS = "https://mskazemi.com/idkmesh/topics/"
QUESTIONS = "https://mskazemi.com/idkmesh/questions.html"
SITEMAP = "https://mskazemi.com/idkmesh/sitemap.xml"
LLMS = "https://mskazemi.com/idkmesh/llms.txt"
INDEXNOW_KEY = "7c1f6d4a9b2e3c8f5a0d1e7b4c6f8a2d"
INDEXNOW_KEY_URL = f"https://mskazemi.com/idkmesh/{INDEXNOW_KEY}.txt"
SOCIAL_IMAGE = "https://mskazemi.com/idkmesh/assets/idkmesh-social.png"
BAD_SOCIAL_IMAGE = "https://mskazemi.com/idkmesh/idkmesh/assets/idkmesh-social.png"
JEKYLL_SENTINEL = "https://mskazemi.com/idkmesh/WHAT_IS_IDKMESH.html"

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
    "duckduckgo": "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",
    "apple": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)",
    "openai": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "claude-search": "Claude-SearchBot",
    "claude-user": "Claude-User",
    "perplexity": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "perplexity-user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
    "mistral-index": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-Index/1.0; +https://docs.mistral.ai/robots)",
    "mistral-user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots)",
    "amazon-search": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-SearchBot/0.1) Chrome/120.0.0.0 Safari/537.36",
    "amazon-user": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-User/0.1) Chrome/120.0.0.0 Safari/537.36",
}

ROBOTS_PRODUCT_TOKENS = {
    # Google documents Google-Extended as a robots.txt product token rather
    # than a distinct HTTP request user-agent. It controls whether Google-crawled
    # content may be used for Gemini Apps / Vertex AI Gemini grounding.
    "gemini": "Google-Extended",
}

ROBOTS_USER_AGENTS = {
    "google": "Googlebot",
    "bing": "bingbot",
    "yahoo": "Slurp",
    "duckduckgo": "DuckDuckBot",
    "apple": "Applebot",
    "openai": "OAI-SearchBot",
    "claude-search": "Claude-SearchBot",
    "claude-user": "Claude-User",
    "perplexity": "PerplexityBot",
    "perplexity-user": "Perplexity-User",
    "mistral-index": "MistralAI-Index",
    "mistral-user": "MistralAI-User",
    "amazon-search": "Amzn-SearchBot",
    "amazon-user": "Amzn-User",
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


class _IndexabilityParser(HTMLParser):
    """Extract the small metadata subset that controls public indexability."""

    def __init__(self) -> None:
        super().__init__()
        self.canonicals: list[str] = []
        self.robots: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "link" and "canonical" in {
            token.strip().lower()
            for token in values.get("rel", "").split()
            if token.strip()
        }:
            href = values.get("href", "").strip()
            if href:
                self.canonicals.append(href)

        if tag.lower() == "meta" and values.get("name", "").lower() in {
            "robots",
            "googlebot",
            "bingbot",
        }:
            content = values.get("content", "").strip()
            if content:
                self.robots.append(content)


def _check_indexable_html(
    label: str,
    expected_url: str,
    body: str,
    failures: list[str],
) -> None:
    parser = _IndexabilityParser()
    parser.feed(body)

    if parser.canonicals != [expected_url]:
        failures.append(
            f"{label}: canonical URLs {parser.canonicals!r} do not equal "
            f"the expected {expected_url!r}"
        )

    blocking = sorted(
        directive
        for directive in parser.robots
        if "noindex" in directive.lower()
    )
    if blocking:
        failures.append(
            f"{label}: rendered page contains a noindex directive: {blocking!r}"
        )


def _check_social_image(label: str, body: str, failures: list[str]) -> None:
    if SOCIAL_IMAGE not in body:
        failures.append(f"{label}: rendered page is missing the canonical social image")
    if BAD_SOCIAL_IMAGE in body:
        failures.append(f"{label}: rendered page duplicates the /idkmesh base path in its social image")


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
            for url in (HOME, TOPICS, QUESTIONS):
                if not parser.can_fetch(token, url):
                    failures.append(f"robots.txt blocks {name} from {url}")
        for name, token in ROBOTS_PRODUCT_TOKENS.items():
            for url in (HOME, TOPICS, QUESTIONS):
                if not parser.can_fetch(token, url):
                    failures.append(
                        f"robots.txt blocks {name} product token {token} from {url}"
                    )

    sitemap_status, sitemap = fetch(SITEMAP, browser)
    if sitemap_status != 200:
        failures.append(f"sitemap returned HTTP {sitemap_status}")
    else:
        expected_urls = [
            HOME,
            TOPICS,
            QUESTIONS,
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
    else:
        if "AI agent verification" not in topic_body or "multi-agent orchestration" not in topic_body.lower():
            failures.append("topic hub returned 200 but expected topic content is absent")
        _check_social_image("topic hub", topic_body, failures)
        _check_indexable_html("topic hub", TOPICS, topic_body, failures)

    question_status, question_body = fetch(QUESTIONS, browser)
    if question_status != 200:
        failures.append(f"question-map returned HTTP {question_status}")
    else:
        lowered_questions = question_body.lower()
        if (
            "100 questions about ai agent verification" not in lowered_questions
            or "what is verified swarm engineering?" not in lowered_questions
        ):
            failures.append(
                "question-map returned 200 but expected 100-question content is absent"
            )
        _check_social_image("question map", question_body, failures)
        _check_indexable_html("question map", QUESTIONS, question_body, failures)

    sentinel_status, sentinel_body = fetch(JEKYLL_SENTINEL, browser)
    if sentinel_status != 200:
        failures.append(f"Jekyll sentinel returned HTTP {sentinel_status}")
    else:
        _check_social_image("Jekyll sentinel", sentinel_body, failures)
        _check_indexable_html(
            "Jekyll sentinel",
            JEKYLL_SENTINEL,
            sentinel_body,
            failures,
        )

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
        if 'name="description"' not in body.lower():
            failures.append(f"{topic_id}: rendered page has no meta description")
        _check_social_image(topic_id, body, failures)
        _check_indexable_html(topic_id, url, body, failures)

    llms_status, llms = fetch(LLMS, browser)
    if llms_status != 200:
        failures.append(f"llms.txt returned HTTP {llms_status}")
    else:
        for expected in (
            "AI agent verification",
            "Multi-agent orchestration",
            TOPICS,
            QUESTIONS,
        ):
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

            question_crawler_status, question_crawler_body = fetch(QUESTIONS, user_agent)
            if question_crawler_status != 200:
                failures.append(
                    f"{name}: question map HTTP {question_crawler_status}"
                )
                continue
            if (
                "100 questions about ai agent verification"
                not in question_crawler_body.lower()
            ):
                failures.append(
                    f"{name}: question map content missing 100-question marker"
                )
            _check_indexable_html(
                f"{name}: question map",
                QUESTIONS,
                question_crawler_body,
                failures,
            )
            if question_status == 200 and len(question_body):
                if len(question_crawler_body) < len(question_body) * 0.70:
                    failures.append(
                        f"{name}: question-map crawler body is unexpectedly small "
                        f"({len(question_crawler_body)} vs browser {len(question_body)})"
                    )
            print(
                f"{name}: question map HTTP {question_crawler_status}, "
                f"{len(question_crawler_body)} bytes"
            )

    return failures


def main() -> int:
    failures = probe()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "Discovery surface healthy: robots, sitemap, directory hubs, topic hub, "
        "100-question map, ten topic pages, exact canonicals, indexability, "
        "llms.txt, IndexNow key, Gemini robots control, and representative crawler "
        "probes all passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
