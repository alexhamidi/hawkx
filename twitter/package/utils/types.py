"""
TypedDicts mirroring X's GraphQL response shapes, derived from live API responses.
All fields marked NotRequired may be absent depending on tweet/user content.
"""

from typing import NotRequired, TypedDict


class MediaSize(TypedDict):
    h: int
    w: int
    resize: str  # 'fit' | 'crop'


class MediaSizes(TypedDict):
    large: MediaSize
    medium: MediaSize
    small: MediaSize
    thumb: MediaSize


class VideoVariant(TypedDict):
    content_type: str  # 'application/x-mpegURL' | 'video/mp4'
    url: str
    bitrate: NotRequired[int]  # absent for HLS master playlists


class VideoInfo(TypedDict):
    aspect_ratio: list[int]       # [width, height]
    duration_millis: int
    variants: list[VideoVariant]


class UrlEntity(TypedDict):
    display_url: str              # e.g. 'notion.com'
    expanded_url: str             # full destination URL
    indices: list[int]            # [start, end] char offsets in full_text
    url: str                      # t.co short URL


class UserMentionEntity(TypedDict):
    id_str: str
    name: str
    screen_name: str
    indices: list[int]


class MediaEntity(TypedDict):
    id_str: str
    media_key: str                # e.g. '13_2021411794015952896'
    media_url_https: str          # thumbnail/preview image
    type: str                     # 'photo' | 'video' | 'animated_gif'
    url: str                      # t.co short URL appearing in full_text
    display_url: str              # e.g. 'pic.x.com/...'
    expanded_url: str             # full permalink to the media
    sizes: MediaSizes
    original_info: dict           # {width: int, height: int, focus_rects: list}
    source_status_id_str: NotRequired[str]   # present when media is from a retweet source
    source_user_id_str: NotRequired[str]
    video_info: NotRequired[VideoInfo]       # present for video/animated_gif


class TweetEntities(TypedDict):
    hashtags: list[dict]
    media: NotRequired[list[MediaEntity]]
    symbols: list
    urls: list[UrlEntity]
    user_mentions: list[UserMentionEntity]
    timestamps: NotRequired[list]


class TweetLegacy(TypedDict):
    id_str: str
    full_text: str
    created_at: str               # e.g. 'Sun Feb 22 08:21:45 +0000 2026'
    conversation_id_str: str
    lang: str
    user_id_str: str
    display_text_range: list[int] # [start, end] char range of visible text
    entities: TweetEntities
    extended_entities: NotRequired[dict]     # same shape as entities; has full media list
    favorite_count: int
    retweet_count: int
    reply_count: int
    quote_count: int
    bookmark_count: int
    favorited: bool
    retweeted: bool
    bookmarked: bool
    is_quote_status: bool
    possibly_sensitive: NotRequired[bool]
    possibly_sensitive_editable: NotRequired[bool]
    in_reply_to_screen_name: NotRequired[str]
    in_reply_to_status_id_str: NotRequired[str]
    in_reply_to_user_id_str: NotRequired[str]
    quoted_status_id_str: NotRequired[str]
    retweeted_status_result: NotRequired[dict]  # {result: TweetResult} when this is a retweet


class UserCore(TypedDict):
    created_at: str
    name: str
    screen_name: str


class UserLegacy(TypedDict):
    name: str
    screen_name: str
    description: str
    created_at: str
    followers_count: int
    friends_count: int            # accounts this user follows
    favourites_count: int
    listed_count: int
    media_count: int
    statuses_count: int
    normal_followers_count: int
    fast_followers_count: int
    default_profile: bool
    default_profile_image: bool
    is_translator: bool
    has_custom_timelines: bool
    possibly_sensitive: bool
    profile_interstitial_type: str
    translator_type: str
    url: NotRequired[str]         # t.co link in bio
    profile_banner_url: NotRequired[str]
    pinned_tweet_ids_str: list[str]
    withheld_in_countries: list[str]
    want_retweets: NotRequired[bool]
    entities: dict                # {description: {urls: list}, url?: {urls: list}}


class UserResult(TypedDict):
    __typename: str               # 'User'
    id: str                       # base64-encoded global ID
    rest_id: str                  # numeric user ID string
    avatar: dict                  # {image_url: str}
    core: UserCore
    legacy: UserLegacy
    is_blue_verified: bool
    verification: dict            # {verified: bool}
    location: dict                # {location: str}
    profile_image_shape: str      # 'Circle' | 'Square'
    profile_bio: dict             # {description: str}
    privacy: dict                 # {protected: bool}
    dm_permissions: dict          # {can_dm: bool}
    has_graduated_access: bool
    super_follow_eligible: bool
    super_followed_by: bool
    super_following: bool
    follow_request_sent: bool
    relationship_perspectives: dict  # {following, followed_by, blocking, blocked_by, muting}
    affiliates_highlighted_label: NotRequired[dict]
    professional: NotRequired[dict]  # {professional_type: str, rest_id: str, category: list}


class TweetViews(TypedDict):
    count: str                    # numeric string
    state: str                    # 'EnabledWithCount' | 'Enabled'


class TweetResult(TypedDict):
    __typename: str               # 'Tweet'
    rest_id: str                  # numeric tweet ID string
    core: dict                    # {user_results: {result: UserResult}}
    legacy: TweetLegacy
    source: str                   # HTML anchor: '<a href="...">Client Name</a>'
    views: TweetViews
    is_translatable: bool
    edit_control: dict            # {edit_tweet_ids, editable_until_msecs, edits_remaining, is_edit_eligible}
    unmention_data: dict
    has_birdwatch_notes: NotRequired[bool]
    grok_analysis_button: NotRequired[bool]
    grok_annotations: NotRequired[dict]
    quoted_status_result: NotRequired[dict]  # {result: TweetResult} when quoting another tweet


# ── Timeline entry types ────────────────────────────────────────────────────

class TweetItemContent(TypedDict):
    __typename: str               # 'TimelineTweet'
    itemType: str                 # 'TimelineTweet'
    tweetDisplayType: str         # 'Tweet' | 'SelfThread' | 'MediaGrid'
    tweet_results: dict           # {result: TweetResult}


class TimelineItemContent(TypedDict):
    __typename: str               # 'TimelineTimelineItem'
    entryType: str                # 'TimelineTimelineItem'
    itemContent: TweetItemContent
    clientEventInfo: NotRequired[dict]


class TimelineModuleContent(TypedDict):
    __typename: str               # 'TimelineTimelineModule'
    entryType: str                # 'TimelineTimelineModule'
    items: list[dict]             # list of {item: {itemContent: TweetItemContent}}
    clientEventInfo: NotRequired[dict]


class CursorContent(TypedDict):
    __typename: str               # 'TimelineTimelineCursor'
    entryType: str                # 'TimelineTimelineCursor'
    cursorType: str               # 'Top' | 'Bottom'
    value: str                    # opaque pagination cursor


class TimelineEntry(TypedDict):
    entryId: str                  # e.g. 'tweet-1234' | 'conversationthread-1234' | 'cursor-bottom'
    sortIndex: str                # numeric string; descending = newest first
    content: TimelineItemContent | TimelineModuleContent | CursorContent


# ── Top-level response shapes ───────────────────────────────────────────────

class TimelineInstruction(TypedDict):
    type: str                     # 'TimelineClearCache' | 'TimelineAddEntries' | 'TimelineTerminateTimeline'
    entries: NotRequired[list[TimelineEntry]]  # present when type == 'TimelineAddEntries'
    direction: NotRequired[str]   # present when type == 'TimelineTerminateTimeline': 'Top' | 'Bottom'


class TweetDetailResponse(TypedDict):
    """
    Response from TweetDetail (YCNdW_ZytXfV9YR3cJK9kw).
    Contains the focal tweet plus reply threads as timeline entries.

    data
      threaded_conversation_with_injections_v2
        instructions: list[TimelineInstruction]
          — TimelineClearCache  (no extra fields)
          — TimelineAddEntries  (.entries = list[TimelineEntry])
              entry types:
                'tweet-{id}'                → TimelineTimelineItem  (focal tweet)
                'conversationthread-{id}'   → TimelineTimelineModule (reply thread)
                'cursor-top' / 'cursor-bottom' → TimelineTimelineCursor
          — TimelineTerminateTimeline  (.direction = 'Top' | 'Bottom')
        metadata
          scribeConfig: {page: str}
    """
    data: dict


class TweetByIdResponse(TypedDict):
    """
    Response from TweetResultByRestId (4PdbzTmQ5PTjz9RiureISQ).
    Lighter than TweetDetail — single tweet only, no replies.

    data
      tweetResult
        result: TweetResult
    """
    data: dict  # {tweetResult: {result: TweetResult}}
