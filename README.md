# Twitter API Integration Guide

This repository contains scripts for fetching recent tweets from Twitter/X accounts using different approaches.

## Overview

Due to recent changes in Twitter/X's API structure and access restrictions, different methods have been attempted:

1. **twitter-scraper library** - Failed due to changes in Twitter/X's structure
2. **Tweepy (Official Twitter API)** - Requires proper authentication setup
3. **Direct web scraping** - Not reliable due to anti-scraping measures
4. **python-twitter library** - Requires OAuth credentials

## Recommended Solution: Twitter API v2

The most reliable approach is using Twitter API v2 with proper authentication.

## Setup Instructions

### 1. Create Twitter Developer Account
1. Go to https://developer.twitter.com/
2. Sign in with your Twitter account
3. Apply for a developer account if you don't have one
4. Wait for approval (may take a few days)

### 2. Create a New App
1. Once approved, go to your developer dashboard
2. Click "Create Project + App"
3. Choose "Standalone App"
4. Fill in the required details
5. Give your app a name and description
6. Complete the form and submit

### 3. Get API Credentials
1. Go to your App settings → Keys and tokens
2. Generate a Bearer Token (for API v2)
3. Copy the Bearer Token (this is your API key)

### 4. Set Environment Variable
```bash
export TWITTER_BEARER_TOKEN="your_bearer_token_here"
```

### 5. Run the Script
```bash
python twitter_api_v2.py
```

## Files

- `twitter_api_v2.py` - Main script using Twitter API v2 (recommended)
- `twitter_old_api.py` - Alternative using legacy Twitter API (requires OAuth)
- `scrape_x.py` - Web scraping approach (not recommended)
- `fetch_tweets.py` - Various attempts with different libraries

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure your Bearer Token is correct
   - Check that your Twitter Developer account is approved
   - Verify your App has the correct permissions

2. **Rate Limiting**
   - Twitter API has rate limits
   - Wait if you hit rate limits
   - Consider using app-only authentication for higher limits

3. **User Not Found**
   - Verify the username is correct
   - Some accounts may be private or suspended

### Debug Mode
Add `debug=True` parameter to API calls to see detailed request/response information.

## Alternative Approaches

If you cannot set up Twitter API access:

1. **Use the web interface** directly at https://x.com/officialLoganK
2. **Use third-party Twitter clients** that may have API access
3. **Check if the account has other public profiles** (Instagram, LinkedIn, etc.)

## Security Notes

- Never share your API credentials publicly
- Use environment variables instead of hardcoding tokens
- Rotate credentials periodically
- Monitor your API usage and costs

## Support

For Twitter API specific issues:
- https://developer.twitter.com/en/support
- Twitter Developer Forums: https://twittercommunity.com/

For script issues:
- Check the Twitter API documentation
- Verify your credentials and permissions
- Ensure you have the required Python packages installed