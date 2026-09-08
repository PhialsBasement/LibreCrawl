"""AI crawler readiness checks (llms.txt + robots.txt AI-bot policy)"""
from urllib.parse import urlparse


# User-agent tokens for AI crawlers/agents that read a site's robots.txt to
# decide whether they may fetch it. Not exhaustive, but covers the major
# training and retrieval crawlers as of 2026.
AI_CRAWLER_USER_AGENTS = [
    "GPTBot",
    "ChatGPT-User",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-User",
    "anthropic-ai",
    "PerplexityBot",
    "Google-Extended",
]


class AIReadinessChecker:
    """Checks whether a site publishes llms.txt and whether its robots.txt
    explicitly blocks any of the well-known AI crawler user-agents.

    Mirrors the session/base_domain/timeout convention used by
    SitemapParser elsewhere in this package.
    """

    def __init__(self, session, base_domain, timeout=10):
        self.session = session
        self.base_domain = base_domain
        self.timeout = timeout

    def check(self, base_url):
        """
        Returns:
            dict: {
                "llms_txt": bool,
                "robots_txt_found": bool,
                "blocked_ai_bots": [str, ...],
            }
        """
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

        result = {
            "llms_txt": False,
            "robots_txt_found": False,
            "blocked_ai_bots": [],
        }

        try:
            llms_response = self.session.get(
                f"{base_domain}/llms.txt", timeout=self.timeout
            )
            result["llms_txt"] = llms_response.status_code == 200
        except Exception as e:
            print(f"Could not fetch llms.txt: {e}")

        try:
            robots_response = self.session.get(
                f"{base_domain}/robots.txt", timeout=self.timeout
            )
            if robots_response.status_code == 200:
                result["robots_txt_found"] = True
                current_agents = []

                for line in robots_response.text.split("\n"):
                    line = line.split("#", 1)[0].strip()
                    if not line or ":" not in line:
                        continue

                    field, _, value = line.partition(":")
                    field = field.strip().lower()
                    value = value.strip()

                    if field == "user-agent":
                        current_agents = [value]
                    elif field == "disallow" and value == "/" and current_agents:
                        for agent in current_agents:
                            for bot in AI_CRAWLER_USER_AGENTS:
                                if (
                                    agent.lower() == bot.lower()
                                    and bot not in result["blocked_ai_bots"]
                                ):
                                    result["blocked_ai_bots"].append(bot)
        except Exception as e:
            print(f"Could not fetch robots.txt: {e}")

        return result
