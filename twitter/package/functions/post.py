"""
Fetch a single post (tweet) by ID.

Two endpoints are available:
  - TweetDetail (get_post)        — focal tweet + full reply threads, heavier
  - TweetResultByRestId (get_post_simple) — single tweet only, no replies, lighter
"""

import json

from ..utils.client import gql_get
from ..utils.constants import FEATURES, QUERY_IDS
from ..utils.types import TweetByIdResponse, TweetDetailResponse


def get_post(tweet_id: str) -> TweetDetailResponse:
    """
    Fetch a tweet and its reply threads via TweetDetail.

    Returns the focal tweet as a TimelineTimelineItem entry and each reply thread
    as a TimelineTimelineModule entry. The instructions list always begins with a
    TimelineClearCache entry followed by TimelineAddEntries.

    Args:
        tweet_id: Numeric tweet ID string (e.g. "2025486153969983826")

    Returns:
        TweetDetailResponse:
          data.threaded_conversation_with_injections_v2
            .instructions: list[TimelineInstruction]
                [0] type='TimelineClearCache'
                [1] type='TimelineAddEntries', entries=[
                      TimelineEntry(entryId='tweet-{id}',         # focal tweet
                                    content=TimelineItemContent(
                                      itemContent.tweet_results.result = TweetResult))
                      TimelineEntry(entryId='conversationthread-{id}',  # reply threads
                                    content=TimelineModuleContent(
                                      items=[{item: {itemContent: TweetItemContent}}]))
                      TimelineEntry(entryId='cursor-top' | 'cursor-bottom',
                                    content=CursorContent)
                    ]
                [2..] type='TimelineTerminateTimeline'
            .metadata.scribeConfig.page: str
    """
    variables = {
        "focalTweetId": tweet_id,
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True,
    }
    field_toggles = {
        "withArticleRichContentState": True,
        "withArticlePlainText": False,
        "withGrokAnalyze": False,
        "withDisallowedReplyControls": False,
    }
    path = f"{QUERY_IDS['TweetDetail']}/TweetDetail"
    return gql_get(path, {
        "variables": json.dumps(variables),
        "features": json.dumps(FEATURES),
        "fieldToggles": json.dumps(field_toggles),
    })


def get_post_simple(tweet_id: str) -> TweetByIdResponse:
    """
    Fetch a single tweet without replies via TweetResultByRestId.

    Args:
        tweet_id: Numeric tweet ID string (e.g. "2025486153969983826")

    Returns:
        TweetByIdResponse:
          data.tweetResult.result: TweetResult
            .rest_id: str                   numeric tweet ID
            .legacy: TweetLegacy
              .full_text: str               tweet text (may include trailing t.co media URL)
              .created_at: str              'Sun Feb 22 08:21:45 +0000 2026'
              .conversation_id_str: str
              .entities.urls: list[UrlEntity]
              .entities.media: list[MediaEntity]   (absent if no media)
              .extended_entities.media: list[MediaEntity]  (full media list incl. video_info)
              .favorite_count / retweet_count / reply_count / quote_count / bookmark_count: int
              .user_id_str: str
            .core.user_results.result: UserResult
              .core.screen_name / .core.name: str
              .legacy.followers_count / .legacy.description: str
              .is_blue_verified: bool
            .views.count: str               total view count as numeric string
            .source: str                    HTML anchor identifying the posting client
    """
    variables = {
        "tweetId": tweet_id,
        "includePromotedContent": True,
        "withBirdwatchNotes": True,
        "withVoice": True,
        "withCommunity": True,
    }
    field_toggles = {
        "withArticleRichContentState": True,
        "withArticlePlainText": False,
    }
    path = f"{QUERY_IDS['TweetResultByRestId']}/TweetResultByRestId"
    return gql_get(path, {
        "variables": json.dumps(variables),
        "features": json.dumps(FEATURES),
        "fieldToggles": json.dumps(field_toggles),
    })
