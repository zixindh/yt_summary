# Streamlit Community Cloud Deployment Guide

## Quick Setup

1. **Fork this repository** to your GitHub account

2. **Deploy on Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Select your forked repository
   - Set main file path as `app.py`

3. **Configure Secrets**:
   - In your Streamlit app dashboard, go to Settings → Secrets
   - Add the following configuration:

```toml
# REQUIRED: Get your free API key from https://rapidapi.com/ytjar/api/youtube-mp36/
rapidapi_key = "your-rapidapi-key-here"

# OPTIONAL: If you have a proxy server
proxy_url = "http://your-proxy-server:port"
```

## Getting Your RapidAPI Key

1. Visit [RapidAPI YouTube MP3 API](https://rapidapi.com/ytjar/api/youtube-mp36/)
2. Click "Subscribe to Test" (free tier available)
3. Create a RapidAPI account if you don't have one
4. Copy your API key from the dashboard
5. Add it to your Streamlit secrets as shown above

## How It Works

The app uses two methods to download YouTube videos:

1. **pytubefix** (Primary): Direct download when possible
2. **RapidAPI** (Fallback): Cloud-friendly API service

When deployed on Streamlit Community Cloud, YouTube often blocks direct downloads. The RapidAPI fallback ensures your app continues working reliably.

## Troubleshooting

### Error: "Neither pytubefix nor RapidAPI key is available"
- Make sure you've added the `rapidapi_key` in your Streamlit secrets
- Check that the key is valid and has remaining quota

### Error: "HTTP 403 Forbidden"
- This is expected on cloud platforms
- The app should automatically fall back to RapidAPI
- If not, check your RapidAPI key configuration

### Slow Performance
- Transcription with Whisper can take time, especially for longer videos
- Consider using the "tiny" Whisper model for faster processing

## Cost Considerations

- **RapidAPI Free Tier**: Usually includes 100-500 requests per month
- **Streamlit Community Cloud**: Free hosting with resource limits
- For heavy usage, consider upgrading to paid tiers or self-hosting

## Alternative Deployment Options

If you need unlimited downloads or better performance:
- Deploy on Heroku with a residential proxy addon
- Use Railway.app or Render.com
- Self-host on a VPS with residential IP
- Run locally on your own machine