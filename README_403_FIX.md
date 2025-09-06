# Fixing HTTP 403 Error on Streamlit Community Cloud

## The Problem
YouTube actively blocks cloud server IPs to prevent automated downloads. This is why you get HTTP 403 errors on Streamlit Community Cloud but not on your local machine.

## Solutions

### 1. Use Browser Cookies (Recommended)
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

### 3. Alternative Deployment Platforms
If the above doesn't work, consider deploying on:
- Heroku (with residential proxy addon)
- Railway.app
- Render.com
- Your own VPS with residential IP

## Technical Details

The app now implements multiple strategies to bypass 403 errors:

1. **Enhanced Player Clients**: Uses Android test suite, VR, and music clients which are less restricted
2. **User Agent Rotation**: Cycles through multiple browser user agents
3. **Cache Clearing**: Automatically clears yt-dlp cache before each download
4. **Request Headers**: Mimics real browser behavior with comprehensive headers
5. **Retry Logic**: Attempts multiple client combinations before failing

## Debugging

Check the app logs for detailed error messages. The app now logs which client is being used and what errors occur.

## Note

YouTube's anti-bot measures are constantly evolving. What works today might not work tomorrow. The cookie method is currently the most reliable approach for cloud deployments.