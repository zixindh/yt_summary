# Fixing HTTP 403 Error on Streamlit Community Cloud

## The Problem
YouTube actively blocks cloud server IPs to prevent automated downloads. This is why you get HTTP 403 errors on Streamlit Community Cloud but not on your local machine.

## Solutions (in order of effectiveness)

### 1. Use Browser Cookies (Most Effective)
This is the most effective method to bypass 403 errors.

#### Step 1: Export Cookies from Your Browser
1. Install a cookie export extension:
   - Chrome: "Get cookies.txt LOCALLY" 
   - Firefox: "cookies.txt"

2. Log in to YouTube in your browser

3. Export cookies for youtube.com domain to a file

#### Step 2: Add Cookies to Streamlit Secrets
1. Go to your Streamlit app settings
2. Add a new secret named `YTDLP_COOKIES`
3. Paste the entire content of your cookies.txt file

Example format in secrets.toml:
```toml
YTDLP_COOKIES = """
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	COOKIE_NAME	cookie_value
.youtube.com	TRUE	/	TRUE	1234567890	ANOTHER_COOKIE	another_value
"""
```

### 2. Use a Proxy (Alternative)
Add a proxy URL to your Streamlit secrets:

```toml
YTDLP_PROXY = "http://proxy-server:port"
# or with authentication
YTDLP_PROXY = "http://username:password@proxy-server:port"
```

### 3. Use RapidAPI YouTube Downloader (New!)
This bypasses direct YouTube access by using a third-party API service.

1. Sign up for a free account at [RapidAPI](https://rapidapi.com/ytjar/api/youtube-mp36)
2. Get your API key
3. Add to Streamlit secrets:

```toml
RAPIDAPI_KEY = "your-api-key-here"
```

Note: Free tier has limited requests per month, but it's a reliable fallback.

### 4. Alternative Deployment Platforms
If the above doesn't work, consider deploying on:
- Heroku (with residential proxy addon)
- Railway.app
- Render.com
- Your own VPS with residential IP

## Technical Details

The app now implements multiple strategies to bypass 403 errors:

1. **Force IPv4**: YouTube sometimes blocks IPv6; the app forces IPv4 connections
2. **Enhanced Player Clients**: Uses Android test suite, VR, and music clients which are less restricted
3. **User Agent Rotation**: Cycles through multiple browser user agents
4. **Cache Clearing**: Automatically clears yt-dlp cache before each download
5. **Request Headers**: Mimics real browser behavior with comprehensive headers
6. **Multiple Fallbacks**: 
   - Primary: yt-dlp with various client strategies
   - Secondary: pytubefix (enhanced pytube fork)
   - Tertiary: RapidAPI online service
   - Quaternary: YouTube subtitles extraction (no download needed)

## New Features

### Subtitle Extraction (Default)
The app now tries to extract YouTube's existing subtitles first, which:
- Avoids download entirely (no 403 errors)
- Much faster than audio transcription
- Works on most videos with captions

### pytubefix Integration
An enhanced fork of pytube that:
- Better error handling
- Proxy support
- More robust against YouTube changes

## Debugging

Check the app logs for detailed error messages. The app now logs:
- Which download method is being used
- Specific error messages from each attempt
- Network configuration (IPv4/IPv6, proxy, etc.)

## Note

YouTube's anti-bot measures are constantly evolving. The app now has multiple fallback strategies to ensure it keeps working even when one method fails.