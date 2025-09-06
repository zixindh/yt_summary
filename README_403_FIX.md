# YouTube Download Configuration Guide

## The Problem
YouTube actively blocks cloud server IPs to prevent automated downloads. This is why you may get HTTP 403 errors on Streamlit Community Cloud but not on your local machine.

## Solutions (in order of effectiveness)

### 1. Use RapidAPI YouTube Downloader (Recommended)
This bypasses direct YouTube access by using a third-party API service.

1. Sign up for a free account at [RapidAPI](https://rapidapi.com/ytjar/api/youtube-mp36)
2. Get your API key
3. Add to Streamlit secrets:

```toml
rapidapi_key = "your-api-key-here"
```

Note: Free tier has limited requests per month, but it's a reliable solution for cloud deployments.

### 2. Use a Proxy Server
If pytubefix is getting blocked, you can route requests through a proxy:

```toml
proxy_url = "http://proxy-server:port"
# or with authentication
proxy_url = "http://username:password@proxy-server:port"
```

### 3. Alternative Deployment Platforms
If you need unlimited downloads, consider deploying on:
- Heroku (with residential proxy addon)
- Railway.app
- Render.com
- Your own VPS with residential IP
- Local deployment

## Technical Details

The app now uses a simplified approach focused on reliability:

1. **Primary Method**: pytubefix - An enhanced fork of pytube with:
   - Better error handling
   - Proxy support
   - More robust against YouTube changes
   - Anti-bot detection measures

2. **Fallback Method**: RapidAPI YouTube MP3 service
   - Bypasses direct YouTube access
   - Works reliably on cloud platforms
   - Requires API key but offers stable service

## Configuration in Streamlit Secrets

Add these secrets in your Streamlit app settings:

```toml
# Required for RapidAPI fallback
rapidapi_key = "your-rapidapi-key"

# Optional: If you have a proxy server
proxy_url = "http://your-proxy-server:port"
```

## Debugging

Check the app logs for detailed error messages. The app now logs:
- Which download method is being used
- Specific error messages from each attempt
- Proxy configuration if used

## Note

YouTube's anti-bot measures are constantly evolving. By using RapidAPI as a fallback, the app ensures reliable operation even when direct downloads fail.