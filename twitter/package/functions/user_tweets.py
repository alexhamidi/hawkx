"""
Fetch tweets for a given user by screen name.

Flow:
  1. get_user_id  — resolves screen name to numeric user ID via UserByScreenName
  2. get_user_tweets — paginates UserTweets with that ID until limit is reached
"""

import json

from ..utils.client import gql_get
from ..utils.constants import FEATURES, QUERY_IDS
from ..utils.types import TimelineEntry


def get_user_id(screen_name: str) -> str:
    """
    Resolve a screen name to a numeric user ID via UserByScreenName.

    Args:
        screen_name: Handle without the @ (e.g. "elonmusk")

    Returns:
        Numeric user ID as a string (e.g. "44196397").
        Sourced from data.user.result.rest_id in the response.
    """
    variables = {
        "screen_name": screen_name,
        "withSafetyModeUserFields": True,
    }
    field_toggles = {"withAuxiliaryUserLabels": False}
    path = f"{QUERY_IDS['UserByScreenName']}/UserByScreenName"
    data = gql_get(path, {
        "variables": json.dumps(variables),
        "features": json.dumps(FEATURES),
        "fieldToggles": json.dumps(field_toggles),
    })
    return data["data"]["user"]["result"]["rest_id"]


def get_user_tweets(screen_name: str, limit: int = 40, include_replies: bool = False) -> list[TimelineEntry]:
    """
    Fetch up to `limit` timeline entries from a user's tweet feed via UserTweets.
    Resolves the screen name to a user ID internally, then paginates using the
    bottom cursor until `limit` entries are collected or no further pages exist.

    Args:
        screen_name: Handle without the @ (e.g. "elonmusk")
        limit:       Max entries to return across all pages (default 40).
                     Each page fetches up to 20; cursor entries count toward the total
                     but can be filtered by the caller.
    include_replies: If True, include reply tweets in the timeline (default False).

    Returns:
        list[TimelineEntry] — raw entries from TimelineAddEntries instructions.
        Each entry is one of:
          TimelineTimelineItem  (entryId='tweet-{id}'):
            .content.itemContent.tweet_results.result: TweetResult
              .legacy.full_text: str
              .legacy.created_at: str
              .legacy.favorite_count / retweet_count / reply_count: int
              .legacy.entities.media: list[MediaEntity]
              .core.user_results.result.core.screen_name: str
              .views.count: str
          TimelineTimelineCursor (entryId='cursor-top' | 'cursor-bottom'):
            .content.cursorType: 'Top' | 'Bottom'
            .content.value: str   (pagination cursor, used internally)
    """
    user_id = get_user_id(screen_name)
    path = f"{QUERY_IDS['UserTweets']}/UserTweets"
    entries: list[TimelineEntry] = []
    cursor = None

    while len(entries) < limit:
        count = min(limit - len(entries), 20)
        variables = {
            "userId": user_id,
            "count": count,
            "includePromotedContent": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True,
            "withV2Timeline": True,
            "includeReplies": include_replies,
        }
        if cursor:
            variables["cursor"] = cursor

        data = gql_get(path, {
            "variables": json.dumps(variables),
            "features": json.dumps(FEATURES),
        })

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

        entries.extend(page_entries)

        next_cursor = None
        for entry in page_entries:
            content = entry.get("content", {})
            if content.get("entryType") == "TimelineTimelineCursor" and content.get("cursorType") == "Bottom":
                next_cursor = content.get("value")
                break

        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    return entries[:limit]
