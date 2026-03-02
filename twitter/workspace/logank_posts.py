#!/usr/bin/env python3
"""
Fetch all posts from @officialLoganK.
Twitter's UserTweets API caps at ~3,200 most-recent tweets; we request up to that.
Each record: { id, content, timestamp, type: "post"|"repost", images }
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from twitter.package.utils.client import gql_get
from twitter.package.utils.constants import FEATURES, QUERY_IDS
from twitter.package import get_user_id


def fetch_all_tweets(screen_name: str, limit: int = 3200) -> list[dict]:
    user_id = get_user_id(screen_name)
    path = f"{QUERY_IDS['UserTweets']}/UserTweets"
    posts = []
    cursor = None
    page = 0
    empty_streak = 0

    while len(posts) < limit:
        variables = {
            "userId": user_id,
            "count": 100,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": True,
            "withV2Timeline": True,
        }
        if cursor:
            variables["cursor"] = cursor

        # retry loop for rate-limit / transient errors
        for attempt in range(4):
            try:
                data = gql_get(path, {
                    "variables": json.dumps(variables),
                    "features": json.dumps(FEATURES),
                })
                break
            except Exception as e:
                if "429" in str(e) and attempt < 3:
                    wait = 120 * (2 ** attempt)  # 120, 240, 480s
                    print(f"  rate limited — waiting {wait}s…", flush=True)
                    time.sleep(wait)
                else:
                    raise
        else:
            break

        instructions = (
            data.get("data", {})
                .get("user", {})
                .get("result", {})
                .get("timeline_v2", {})
                .get("timeline", {})
                .get("instructions", [])
        )

        page_entries = next(
            (i["entries"] for i in instructions if "entries" in i), []
        )
        if not page_entries:
            break

        page += 1
        tweet_count_this_page = 0
        new_cursor = None

        for entry in page_entries:
            entry_id = entry.get("entryId", "")
            content = entry.get("content", {})

            if content.get("cursorType") == "Bottom":
                new_cursor = content.get("value")
                continue
            if entry_id.startswith("cursor-"):
                continue

            tweet = (
                content.get("itemContent", {})
                       .get("tweet_results", {})
                       .get("result", {})
            )
            if not tweet or "legacy" not in tweet:
                continue

            legacy = tweet["legacy"]
            tweet_id = legacy.get("id_str") or tweet.get("rest_id", "")
            full_text = legacy.get("full_text", "")
            created_at = legacy.get("created_at", "")

            is_repost = bool(
                tweet.get("retweeted_status_result") or
                full_text.startswith("RT @")
            )

            images = []
            seen: set = set()
            for src in [
                legacy.get("extended_entities", {}).get("media") or [],
                legacy.get("entities", {}).get("media") or [],
            ]:
                for media in src:
                    if media.get("type") == "photo":
                        url = media.get("media_url_https") or media.get("media_url", "")
                        if url and url not in seen:
                            images.append(url)
                            seen.add(url)

            posts.append({
                "id": tweet_id,
                "content": full_text,
                "timestamp": created_at,
                "type": "repost" if is_repost else "post",
                "images": images,
            })
            tweet_count_this_page += 1

        print(f"  page {page}: +{tweet_count_this_page} tweets (total {len(posts)})", flush=True)

        # checkpoint save
        with open(out_path, "w") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)

        if tweet_count_this_page == 0:
            empty_streak += 1
            if empty_streak >= 3:
                print("  3 consecutive empty pages — API limit reached", flush=True)
                break
        else:
            empty_streak = 0

        if not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor

        time.sleep(1.5)  # be polite between pages

    return posts[:limit]


out_path = os.path.join(os.path.dirname(__file__), "logank_posts.json")

print("Fetching @officialLoganK tweets…")
posts = fetch_all_tweets("officialLoganK", limit=3200)
with open(out_path, "w") as f:
    json.dump(posts, f, indent=2, ensure_ascii=False)

reposts = sum(1 for p in posts if p["type"] == "repost")
originals = len(posts) - reposts
with_images = sum(1 for p in posts if p["images"])

print(f"\nSaved {len(posts)} posts → {out_path}")
print(f"  {originals} original posts, {reposts} reposts")
print(f"  {with_images} have images")
if posts:
    print(f"\nSample:")
    print(json.dumps(posts[0], indent=2))
