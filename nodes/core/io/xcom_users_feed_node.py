import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.api_key_vault import APIKeyVault
from core.types_registry import NodeCategory
from nodes.base.base_node import Base

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class XPost:
    """Represents a post from X.com"""

    id: str
    text: str
    author_id: str
    author_username: str
    author_name: str
    created_at: str
    metrics: dict[str, Any] = field(default_factory=dict)
    media: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "author_id": self.author_id,
            "author_username": self.author_username,
            "author_name": self.author_name,
            "created_at": self.created_at,
            "metrics": self.metrics,
            "media": self.media,
        }


class XcomUsersFeed(Base):
    """
    Fetches posts from a list of X.com (Twitter) usernames.

    Requires X API credentials:
    - XCOM_BEARER_TOKEN: OAuth 2.0 Bearer Token for authentication

    Input:
    - text: str - Comma-separated usernames from TextInput node (e.g., "elonmusk, naval, paulg")

    Output:
    - posts: list[dict] - List of posts sorted by recency
    - feed_text: str - Concatenated text of all posts for downstream processing
    - post_count: int - Total number of posts retrieved
    """

    inputs = {"text": str}
    outputs = {"posts": list, "feed_text": str, "post_count": int}
    required_keys = ["XCOM_BEARER_TOKEN"]

    default_params = {
        "tweets_per_user": 10,
        "include_retweets": False,
        "include_replies": False,
    }

    params_meta = [
        {
            "name": "tweets_per_user",
            "type": "integer",
            "default": 10,
            "label": "Posts Per User",
            "description": "Number of recent posts to fetch per user",
            "min": 1,
            "max": 100,
        },
        {
            "name": "include_retweets",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Include Retweets",
        },
        {
            "name": "include_replies",
            "type": "combo",
            "default": False,
            "options": [True, False],
            "label": "Include Replies",
        },
    ]

    CATEGORY = NodeCategory.IO
    ui_module = "XcomUsersFeedNodeUI"

    API_BASE = "https://api.x.com/2"
    RATE_LIMIT_DELAY = 1.0

    async def _execute_impl(self, inputs: dict[str, Any]) -> dict[str, Any]:
        bearer_token = APIKeyVault().get("XCOM_BEARER_TOKEN")
        if not bearer_token:
            raise ValueError("XCOM_BEARER_TOKEN is required but not set in vault")

        usernames = self._collect_usernames(inputs)

        if not usernames:
            logger.warning("XcomUsersFeed: No usernames provided")
            return {"posts": [], "feed_text": "", "post_count": 0}

        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            self.report_progress(10.0, f"Resolving {len(usernames)} usernames...")
            users = await self._resolve_usernames(client, headers, usernames)

            if not users:
                raise ValueError("Could not resolve any usernames. Check they exist.")

            all_posts: list[XPost] = []
            total_users = len(users)

            for idx, user in enumerate(users):
                progress = 15.0 + (idx / total_users) * 80.0
                self.report_progress(progress, f"Fetching posts from @{user['username']}...")

                posts = await self._get_user_tweets(client, headers, user)
                all_posts.extend(posts)

                await asyncio.sleep(self.RATE_LIMIT_DELAY)

            all_posts.sort(key=lambda p: p.created_at, reverse=True)

            posts_dicts = [p.to_dict() for p in all_posts]
            feed_text = self._build_feed_text(all_posts)

            self.report_progress(
                100.0, f"Completed: {len(all_posts)} posts from {total_users} users"
            )

            return {
                "posts": posts_dicts,
                "feed_text": feed_text,
                "post_count": len(all_posts),
            }

    def _collect_usernames(self, inputs: dict[str, Any]) -> list[str]:
        """Parse comma-separated usernames from input text."""
        usernames: list[str] = []

        input_text = inputs.get("text", "")
        if input_text and isinstance(input_text, str):
            parsed = [u.strip().lstrip("@") for u in input_text.split(",") if u.strip()]
            usernames.extend(parsed)

        seen: set[str] = set()
        deduped: list[str] = []
        for u in usernames:
            lower = u.lower()
            if lower not in seen:
                seen.add(lower)
                deduped.append(u)

        return deduped

    async def _resolve_usernames(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        usernames: list[str],
    ) -> list[dict[str, Any]]:
        """Batch resolve usernames to user objects with IDs."""
        users: list[dict[str, Any]] = []

        batch_size = 100
        for i in range(0, len(usernames), batch_size):
            batch = usernames[i : i + batch_size]
            params = {
                "usernames": ",".join(batch),
                "user.fields": "id,name,username,profile_image_url,description",
            }

            response = await client.get(
                f"{self.API_BASE}/users/by",
                headers=headers,
                params=params,
            )

            if response.status_code == 429:
                raise ValueError(
                    "X API rate limit exceeded (429). Wait 15 minutes before trying again, "
                    "or upgrade your API access tier."
                )
            elif response.status_code == 401:
                raise ValueError(
                    "X API authentication failed (401). Check your XCOM_BEARER_TOKEN is valid."
                )
            elif response.status_code == 403:
                raise ValueError(
                    "X API access forbidden (403). Your API tier may not have access to this endpoint."
                )
            elif response.status_code != 200:
                logger.warning(f"Failed to resolve usernames batch: {response.status_code}")
                continue

            data = response.json()
            results = data.get("data", [])
            users.extend(results)

            errors = data.get("errors", [])
            for err in errors:
                logger.warning(f"Username resolution error: {err.get('detail', err)}")

            if i + batch_size < len(usernames):
                await asyncio.sleep(self.RATE_LIMIT_DELAY)

        return users

    async def _get_user_tweets(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        user: dict[str, Any],
    ) -> list[XPost]:
        """Fetch recent tweets from a specific user."""
        user_id = user["id"]
        username = user.get("username", "unknown")
        name = user.get("name", username)

        tweets_per_user_raw = self.params.get("tweets_per_user", 10)
        if isinstance(tweets_per_user_raw, int):
            tweets_per_user = tweets_per_user_raw
        elif isinstance(tweets_per_user_raw, float):
            tweets_per_user = int(tweets_per_user_raw)
        elif isinstance(tweets_per_user_raw, str) and tweets_per_user_raw.isdigit():
            tweets_per_user = int(tweets_per_user_raw)
        else:
            tweets_per_user = 10
        include_retweets = bool(self.params.get("include_retweets", False))
        include_replies = bool(self.params.get("include_replies", False))

        exclude_types: list[str] = []
        if not include_retweets:
            exclude_types.append("retweets")
        if not include_replies:
            exclude_types.append("replies")

        request_params: dict[str, Any] = {
            "max_results": min(tweets_per_user, 100),
            "tweet.fields": "id,text,created_at,public_metrics,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "url,preview_image_url,type",
        }
        if exclude_types:
            request_params["exclude"] = ",".join(exclude_types)

        try:
            response = await client.get(
                f"{self.API_BASE}/users/{user_id}/tweets",
                headers=headers,
                params=request_params,
            )

            if response.status_code == 429:
                logger.warning(f"Rate limit hit for @{username}, skipping")
                return []
            elif response.status_code != 200:
                logger.warning(f"Failed to fetch tweets for @{username}: {response.status_code}")
                return []

            data = response.json()
            tweets_data = data.get("data", [])
            includes = data.get("includes", {})
            media_map = {m["media_key"]: m for m in includes.get("media", [])}

            posts: list[XPost] = []
            for tweet in tweets_data:
                media: list[dict[str, Any]] = []
                if "attachments" in tweet:
                    media_keys = tweet["attachments"].get("media_keys", [])
                    for key in media_keys:
                        if key in media_map:
                            media.append(media_map[key])

                post = XPost(
                    id=tweet["id"],
                    text=tweet["text"],
                    author_id=user_id,
                    author_username=username,
                    author_name=name,
                    created_at=tweet.get("created_at", ""),
                    metrics=tweet.get("public_metrics", {}),
                    media=media,
                )
                posts.append(post)

            return posts

        except Exception as e:
            logger.warning(f"Error fetching tweets for @{username}: {e}")
            return []

    def _build_feed_text(self, posts: list[XPost]) -> str:
        """Build a concatenated text representation of all posts."""
        lines: list[str] = []
        for post in posts:
            timestamp = post.created_at[:10] if post.created_at else "Unknown"
            lines.append(f"[@{post.author_username}] ({timestamp}): {post.text}")
            lines.append("")
        return "\n".join(lines)
