#!/usr/bin/env python3
"""
Twitter/X scraper CLI. Uses Chrome cookies — be logged into X in Chrome.
"""

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from hawkx.settings import get_profile, set_profile
from twitter.package import (
    get_bookmarks,
    get_post,
    get_post_simple,
    get_user_tweets,
    set_chrome_profile,
)


def _tweet_from_entry(entry):
    content = entry.get("content", {})
    if content.get("entryType") == "TimelineTimelineCursor":
        return None
    tweet = (
        content.get("itemContent", {})
        .get("tweet_results", {})
        .get("result", {})
    )
    if not tweet or "legacy" not in tweet:
        return None
    return tweet


def _tweets_from_entries(entries):
    tweets = []
    for entry in entries:
        entry_id = entry.get("entryId", "")
        if entry_id.startswith("cursor-"):
            continue
        tweet = _tweet_from_entry(entry)
        if tweet:
            tweets.append(tweet)
        elif content := entry.get("content", {}):
            for item in content.get("items", []):
                ic = item.get("item", {}).get("itemContent", {})
                tweet = ic.get("tweet_results", {}).get("result", {})
                if tweet and "legacy" in tweet:
                    tweets.append(tweet)
    return tweets


def _extract_images(tweet):
    legacy = tweet.get("legacy", {})
    seen = set()
    images = []
    for src in [
        legacy.get("extended_entities", {}).get("media") or [],
        legacy.get("entities", {}).get("media") or [],
    ]:
        for m in src:
            url = m.get("media_url_https") or m.get("media_url", "")
            if url and url not in seen:
                images.append(url)
                seen.add(url)
    return images


def _tweet_to_record(tweet, include_images=False, include_reply_meta=False):
    legacy = tweet.get("legacy", {})
    r = {
        "id": tweet.get("rest_id") or legacy.get("id_str"),
        "text": legacy.get("full_text", ""),
        "created_at": legacy.get("created_at", ""),
        "user": tweet.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {}).get("screen_name", ""),
        "favorites": legacy.get("favorite_count", 0),
        "retweets": legacy.get("retweet_count", 0),
        "replies": legacy.get("reply_count", 0),
    }
    if include_images:
        r["images"] = _extract_images(tweet)
    if include_reply_meta and legacy.get("in_reply_to_status_id_str"):
        r["in_reply_to"] = {
            "status_id": legacy.get("in_reply_to_status_id_str"),
            "screen_name": legacy.get("in_reply_to_screen_name"),
        }
    return r


def _parse_screen_name(value: str) -> str:
    value = value.strip().rstrip("/")
    if "/" in value:
        value = value.split("/")[-1] or value.split("/")[-2]
    return value.lstrip("@") if value else value


def _parse_tweet_id(value: str) -> str:
    value = value.strip().rstrip("/")
    if "/status/" in value:
        value = value.split("/status/")[-1].split("/")[0].split("?")[0]
    return value


def cmd_user(args):
    screen_name = _parse_screen_name(args.user)
    entries = get_user_tweets(screen_name, limit=args.limit, include_replies=args.replies)
    tweets = _tweets_from_entries(entries)
    records = [_tweet_to_record(t, include_images=args.images, include_reply_meta=args.replies) for t in tweets]
    if args.text:
        for r in records:
            print(r["text"])
    else:
        print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_bookmarks(args):
    entries = get_bookmarks(limit=args.limit)
    tweets = _tweets_from_entries(entries)
    records = [_tweet_to_record(t, include_images=args.images, include_reply_meta=args.replies) for t in tweets]
    if args.text:
        for r in records:
            print(r["text"])
    else:
        print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_post(args):
    tweet_id = _parse_tweet_id(args.tweet_id)
    if not args.replies:
        data = get_post_simple(tweet_id)
        result = data.get("data", {}).get("tweetResult", {}).get("result", {})
        if not result:
            print(json.dumps({"error": "Tweet not found"}), file=sys.stderr)
            sys.exit(1)
        tweets = [result]
    else:
        data = get_post(tweet_id)
        instructions = (
            data.get("data", {})
            .get("threaded_conversation_with_injections_v2", {})
            .get("instructions", [])
        )
        entries = []
        for instr in instructions:
            if instr.get("type") == "TimelineAddEntries":
                entries.extend(instr.get("entries", []))
                break
        tweets = _tweets_from_entries(entries)

    records = [_tweet_to_record(t, include_images=args.images, include_reply_meta=args.replies) for t in tweets]
    if args.text:
        for r in records:
            print(r["text"])
    else:
        print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_setprofile(args):
    set_profile(args.profile)
    print(f"Profile set to {args.profile}")


def _print_usage():
    print("""Command expected.

Commands:

  getuser <name> [number]
    Fetch [number] recent tweets from a user.
    Flags: -R (replies)  -I (images)  -t (text only)
    Example: hawkx getuser elonmusk 20 -I

  getbookmarks [number]
    Fetch your bookmarks.
    Flags: -R (replies)  -I (images)  -t (text only)
    Example: hawkx getbookmarks 50 -t

  getpost <id>
    Fetch a tweet.
    Flags: -R (replies)  -I (images)  -t (text only)
    Example: hawkx getpost 1234567890 -R

  setprofile <profile>
    Set Chrome profile in ~/.hawkx/settings.json
    Example: hawkx setprofile 'Profile 1'

Use hawkx <command> -h for full options.""")


def main():
    if len(sys.argv) <= 1 or sys.argv[1].lower() == "help":
        _print_usage()
        sys.exit(1 if len(sys.argv) <= 1 else 0)

    parser = argparse.ArgumentParser(
        prog="hawkx",
        description="Fetch tweets from X using Chrome session. Be logged into x.com in Chrome.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_user = sub.add_parser("getuser", help="Fetch tweets from a user timeline")
    p_user.add_argument("user", help="Screen name or URL (e.g. elonmusk or https://x.com/elonmusk)")
    p_user.add_argument("limit", type=int, nargs="?", default=40, help="Number of posts (default 40)")
    p_user.add_argument("-R", "--replies", action="store_true", help="Include replies")
    p_user.add_argument("-I", "--images", action="store_true", help="Include image URLs")
    p_user.add_argument("-t", "--text", action="store_true", help="Print only tweet text")
    p_user.set_defaults(func=cmd_user)

    p_bm = sub.add_parser("getbookmarks", help="Fetch your bookmarks")
    p_bm.add_argument("limit", type=int, nargs="?", default=40, help="Number of bookmarks (default 40)")
    p_bm.add_argument("-R", "--replies", action="store_true", help="Include reply metadata")
    p_bm.add_argument("-I", "--images", action="store_true", help="Include image URLs")
    p_bm.add_argument("-t", "--text", action="store_true", help="Print only tweet text")
    p_bm.set_defaults(func=cmd_bookmarks)

    p_post = sub.add_parser("getpost", help="Fetch a tweet")
    p_post.add_argument("tweet_id", help="Tweet ID or URL")
    p_post.add_argument("-R", "--replies", action="store_true", help="Include replies")
    p_post.add_argument("-I", "--images", action="store_true", help="Include image URLs")
    p_post.add_argument("-t", "--text", action="store_true", help="Print only tweet text")
    p_post.set_defaults(func=cmd_post)

    p_setprofile = sub.add_parser("setprofile", help="Set Chrome profile in ~/.hawkx/settings.json")
    p_setprofile.add_argument("profile", help="Profile name (e.g. 1, Profile 1, Default)")
    p_setprofile.set_defaults(func=cmd_setprofile)

    args = parser.parse_args()
    if args.cmd != "setprofile":
        set_chrome_profile(get_profile())
    args.func(args)


if __name__ == "__main__":
    main()
