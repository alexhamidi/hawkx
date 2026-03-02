"""
Fetch the authenticated user's bookmarks via the Bookmarks endpoint.
Paginates automatically until `limit` entries are collected or no more pages exist.
"""

import json

from ..utils.client import gql_get
from ..utils.constants import FEATURES, QUERY_IDS
from ..utils.types import TimelineEntry


def get_bookmarks(limit: int = 40) -> list[TimelineEntry]:
    """
    Fetch up to `limit` bookmark entries for the authenticated user via Bookmarks.
    Uses the auth_token + ct0 cookies from Chrome — no user ID parameter needed.
    Paginates using the bottom cursor until `limit` entries are collected or
    no further pages exist.

    Args:
        limit: Max entries to return across all pages (default 40).
               Cursor entries count toward the total but can be filtered by the caller.

    Returns:
        list[TimelineEntry] — raw entries from TimelineAddEntries instructions.
        Each entry is one of:
          TimelineTimelineItem  (entryId='tweet-{id}'):
            .content.itemContent.tweet_results.result: TweetResult
              .legacy.full_text: str
              .legacy.created_at: str
              .legacy.favorite_count / retweet_count / reply_count / bookmark_count: int
              .legacy.entities.media: list[MediaEntity]   (absent if no media)
              .legacy.extended_entities.media: list[MediaEntity]  (with video_info)
              .core.user_results.result.core.screen_name: str
              .views.count: str
          TimelineTimelineCursor (entryId='cursor-top' | 'cursor-bottom'):
            .content.cursorType: 'Top' | 'Bottom'
            .content.value: str   (pagination cursor, used internally)
    """
    path = f"{QUERY_IDS['Bookmarks']}/Bookmarks"
    entries: list[TimelineEntry] = []
    cursor = None

    while len(entries) < limit:
        count = min(limit - len(entries), 20)
        variables = {
            "count": count,
            "includePromotedContent": False,
        }
        if cursor:
            variables["cursor"] = cursor

        field_toggles = {"withArticleRichContentState": True}

        data = gql_get(path, {
            "variables": json.dumps(variables),
            "features": json.dumps(FEATURES),
            "fieldToggles": json.dumps(field_toggles),
        })

        instructions = (
            data.get("data", {})
                .get("bookmark_timeline_v2", {})
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
