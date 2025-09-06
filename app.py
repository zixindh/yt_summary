import streamlit as st
import yt_dlp
import whisper
import os
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
import time
import random
import json
import logging
import re
# Configure logging for debugging
logging.basicConfig(level=logging.INFO)

# Page configuration
st.set_page_config(
    page_title="YouTube Summarizer",
    page_icon="📝",
    layout="centered"
)

# Add session state for retry counter
if 'retry_count' not in st.session_state:
    st.session_state.retry_count = 0

# Custom CSS for minimalistic design
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 600;
        text-align: center;
        color: #333;
        margin-bottom: 0.5rem;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .sub-header {
        font-size: 1.1rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
        font-weight: 400;
    }
    .success-message {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        color: #495057;
        padding: 1.5rem;
        border-radius: 8px;
        margin: 1.5rem 0;
        line-height: 1.6;
        font-size: 1rem;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .error-message {
        background-color: #fff5f5;
        border: 1px solid #fed7d7;
        color: #c53030;
        padding: 1rem;
        border-radius: 6px;
        margin: 1rem 0;
        font-size: 0.95rem;
    }

    /* Clean up Streamlit default styles */
    .stProgress > div > div > div {
        background-color: #e9ecef;
    }
    .stProgress > div > div > div > div {
        background-color: #007bff;
    }

    /* Button styling */
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
        padding: 0.5rem 1.5rem;
    }

    /* Input styling */
    .stTextInput > div > div > input {
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

class YouTubeSummarizer:
    def __init__(self):
        self.videos_dir = Path("videos")
        self.videos_dir.mkdir(exist_ok=True)

        # Initialize models (lazy loading)
        self.whisper_model = None
        
        # List of public invidious instances (fallback option)
        self.invidious_instances = [
            "https://inv.tux.pizza",
            "https://invidious.nerdvpn.de", 
            "https://inv.in.projectsegfau.lt",
            "https://invidious.privacyredirect.com"
        ]

        # Cookie and proxy support via Streamlit Secrets
        self.setup_cookies_and_proxy()

        # Set FFmpeg path for Whisper
        self._set_ffmpeg_for_whisper()

    def setup_cookies_and_proxy(self):
        """Setup cookies and proxy from Streamlit secrets or environment"""
        self.cookies_file_path = None
        self.proxy_url = None
        
        # Try to get cookies
        try:
            # First try Streamlit secrets
            if hasattr(st, 'secrets'):
                cookies_content = st.secrets.get('YTDLP_COOKIES', '')
                if cookies_content:
                    temp_cookie_path = Path(tempfile.gettempdir()) / 'yt_cookies.txt'
                    with open(temp_cookie_path, 'w', encoding='utf-8') as f:
                        f.write(cookies_content)
                    self.cookies_file_path = str(temp_cookie_path)
                    logging.info("Loaded cookies from Streamlit secrets")
        except Exception as e:
            logging.warning(f"Could not load cookies: {e}")
            
        # Try to get proxy
        try:
            if hasattr(st, 'secrets'):
                proxy_val = st.secrets.get('YTDLP_PROXY', '')
                if proxy_val:
                    self.proxy_url = proxy_val
                    logging.info(f"Using proxy from secrets: {proxy_val}")
        except Exception as e:
            logging.warning(f"Could not load proxy: {e}")
    
    def load_whisper_model(self):
        """Load Whisper model for transcription"""
        if self.whisper_model is None:
            with st.spinner("Loading Whisper model..."):
                self.whisper_model = whisper.load_model("base")
        return self.whisper_model

    def _set_ffmpeg_for_whisper(self):
        """Set FFmpeg path for Whisper to use"""
        # Assume FFmpeg is available in PATH
        pass

    def sanitize_filename(self, filename):
        """Sanitize filename to remove problematic characters for Windows"""
        import re
        # Replace problematic characters with underscores (including Unicode)
        # Windows reserved characters: < > : " | ? * \ / and control chars
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '_', filename)
        # Also handle common Unicode punctuation that causes issues
        sanitized = re.sub(r'[：？]', '_', sanitized)  # Chinese colon and question mark
        sanitized = re.sub(r'[。·！@#￥%……&*（）——+【】、；]', '_', sanitized)  # Other Unicode punctuation
        # Replace backslashes and forward slashes
        sanitized = re.sub(r'[/\\]', '_', sanitized)
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' ._')
        return sanitized

    def extract_video_id(self, url: str):
        """Extract the YouTube video ID from a variety of URL formats."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            if hostname.endswith("youtu.be"):
                # Short URL like youtu.be/<id>
                video_id = parsed.path.lstrip("/")
                return video_id or None
            if hostname.endswith("youtube.com"):
                # Standard, shorts, or embed URLs
                if parsed.path.startswith("/watch"):
                    qs = parse_qs(parsed.query)
                    return (qs.get("v", [None])[0])
                if parsed.path.startswith("/shorts/"):
                    return parsed.path.split("/shorts/")[-1].split("/")[0]
                if parsed.path.startswith("/embed/"):
                    return parsed.path.split("/embed/")[-1].split("/")[0]
            # Fallback: try youtu.be pattern in path
            if "youtu.be/" in url:
                return url.split("youtu.be/")[-1].split("?")[0].split("&")[0].split("/")[0]
        except Exception:
            pass
        return None

    def fetch_title_via_oembed(self, url: str):
        """Fetch video title via YouTube oEmbed (no auth)."""
        try:
            resp = requests.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("title")
        except Exception:
            pass
        return None


    def get_video_info_via_api(self, video_id):
        """Get video info using YouTube's public API endpoints"""
        try:
            # Try noembed API first
            noembed_url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}"
            resp = requests.get(noembed_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'title': data.get('title', 'Unknown'),
                    'author': data.get('author_name', 'Unknown'),
                    'duration': data.get('duration', 0)
                }
        except:
            pass
        return None


    def get_subtitles_fallback(self, url):
        """Try to get subtitles without downloading the video"""
        try:
            opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US', 'en-GB'],
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Check for subtitles
                if 'subtitles' in info:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in info['subtitles']:
                            subs = info['subtitles'][lang]
                            if subs and isinstance(subs, list):
                                # Download subtitle content
                                for sub in subs:
                                    if 'url' in sub:
                                        resp = requests.get(sub['url'], timeout=10)
                                        if resp.status_code == 200:
                                            # Parse subtitle text
                                            text = self._parse_subtitle_content(resp.text, sub.get('ext', 'vtt'))
                                            if text:
                                                return text, info.get('title')
                
                # Try automatic captions
                if 'automatic_captions' in info:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in info['automatic_captions']:
                            subs = info['automatic_captions'][lang]
                            if subs and isinstance(subs, list):
                                for sub in subs:
                                    if 'url' in sub:
                                        resp = requests.get(sub['url'], timeout=10)
                                        if resp.status_code == 200:
                                            text = self._parse_subtitle_content(resp.text, sub.get('ext', 'vtt'))
                                            if text:
                                                return text, info.get('title')
                                                
        except Exception as e:
            logging.warning(f"Subtitle extraction failed: {e}")
            
        return None, None
    
    def _parse_subtitle_content(self, content, format='vtt'):
        """Parse subtitle content to plain text"""
        try:
            lines = content.strip().split('\n')
            text_lines = []
            
            if format == 'vtt':
                # Skip VTT header
                i = 0
                while i < len(lines) and not lines[i].strip().startswith('00:'):
                    i += 1
                    
                # Parse VTT content
                while i < len(lines):
                    line = lines[i].strip()
                    # Skip timestamp lines and empty lines
                    if '-->' not in line and line and not line.isdigit():
                        # Remove VTT tags
                        line = re.sub(r'<[^>]+>', '', line)
                        text_lines.append(line)
                    i += 1
                    
            return ' '.join(text_lines)
            
        except Exception as e:
            logging.warning(f"Subtitle parsing failed: {e}")
            return None
    
    def download_youtube_video(self, url):
        """Download YouTube video with enhanced anti-403 strategies"""
        try:
            # Clear cache before attempting download
            try:
                subprocess.run(['yt-dlp', '--rm-cache-dir'], capture_output=True, timeout=5)
            except:
                pass
            
            # Add random delay to avoid bot detection
            time.sleep(random.uniform(2, 5))
            
            # Base options with enhanced anti-detection measures
            base_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': str(self.videos_dir / 'audio_%(id)s.%(ext)s'),
                'quiet': False,  # Enable output for debugging
                'verbose': True,
                'no_warnings': False,
                'prefer_ffmpeg': True,
                'keepvideo': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                # Anti-detection options
                'nocheckcertificate': True,
                'no_check_certificate': True,
                'geo_bypass': True,
                'geo_bypass_country': 'US',
                'age_limit': None,
                # Network options
                'force_ipv4': True,
                'source_address': '0.0.0.0',
                'concurrent_fragment_downloads': 1,
                'retries': 10,
                'fragment_retries': 10,
                'retry_sleep_functions': {'http': lambda x: 2, 'fragment': lambda x: 2},
                # Disable cache to avoid stale data
                'cachedir': False,
                'rm_cachedir': True,
            }
            
            # List of user agents to try
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
            ]
            
            # Enhanced player client list with latest working clients
            player_clients = [
                ['android_testsuite', 'android_vr', 'android_music'],
                ['android_creator', 'android_testsuite'],
                ['android_vr'],
                ['android_music'], 
                ['ios', 'ios_music'],
                ['web_creator', 'web_embedded'],
                ['mweb', 'android'],
                ['tv_embedded', 'android_embedded'],
            ]
            
            # Add cookies if available
            if self.cookies_file_path and os.path.exists(self.cookies_file_path):
                base_opts['cookiefile'] = self.cookies_file_path
                logging.info("Using cookies file for authentication")
            
            # Add proxy if available
            if self.proxy_url:
                base_opts['proxy'] = self.proxy_url
                logging.info(f"Using proxy: {self.proxy_url}")
            
            last_error = None
            
            # Try different combinations
            for user_agent in user_agents:
                for clients in player_clients:
                    opts = base_opts.copy()
                    
                    # Set headers
                    opts['http_headers'] = {
                        'User-Agent': user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0',
                    }
                    
                    # Set extractor args
                    opts['extractor_args'] = {
                        'youtube': {
                            'player_client': clients,
                            'skip': ['dash', 'hls'],  # Skip adaptive formats
                        }
                    }
                    
                    try:
                        with st.spinner(f"Attempting download with {clients[0]} client..."):
                            with yt_dlp.YoutubeDL(opts) as ydl:
                                info = ydl.extract_info(url, download=True)
                                
                                # Get the downloaded file
                                filename = ydl.prepare_filename(info)
                                audio_file = Path(filename).with_suffix('.mp3')
                                
                                if audio_file.exists():
                                    logging.info(f"Successfully downloaded using {clients[0]} client")
                                    return str(audio_file), info.get('title', 'Unknown Title')
                                    
                    except Exception as e:
                        last_error = e
                        logging.warning(f"Failed with {clients[0]}: {str(e)}")
                        time.sleep(random.uniform(1, 3))  # Wait before retry
                        continue
            
            # If all attempts failed, raise the last error
            if last_error:
                raise last_error
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Provide detailed error handling
            if '403' in error_msg or 'forbidden' in error_msg:
                st.error("❌ **HTTP 403 Error**: YouTube is blocking access from this server.")
                st.info("""
                **This is a known issue on Streamlit Community Cloud.** 
                
                YouTube actively blocks cloud server IPs to prevent automated downloads.
                
                **Workarounds:**
                1. Deploy on a different platform (Heroku, Railway, etc.)
                2. Use a VPS with residential IP
                3. Set up a proxy server
                4. Use the app locally instead
                """)
            elif 'sign in' in error_msg or 'bot' in error_msg:
                st.error("🤖 **Bot Detection**: YouTube requires sign-in or has detected automated access.")
            elif 'private' in error_msg:
                st.error("🔒 **Private Video**: This video is private and cannot be accessed.")
            elif 'unavailable' in error_msg:
                st.error("❌ **Video Unavailable**: This video may be deleted, restricted, or region-locked.")
            else:
                st.error(f"⚠️ **Download Error**: {str(e)[:200]}...")
                
            # Log full error for debugging
            logging.error(f"Full error: {str(e)}")
            
            return None, None


    def transcribe_audio(self, audio_file):
        """Transcribe audio using Whisper"""
        try:
            # Convert to absolute path
            audio_path = Path(audio_file).resolve()

            # Check if audio file exists
            if not audio_path.exists():
                st.error("⚠️ Audio processing failed. Please try again.")
                return None

            # Check file size (empty files would be problematic)
            file_size = audio_path.stat().st_size

            if file_size == 0:
                st.error("⚠️ Audio processing failed. Please try again.")
                return None

            # Additional checks
            if not audio_path.is_file():
                st.error("⚠️ Audio processing failed. Please try again.")
                return None

            model = self.load_whisper_model()

            with st.spinner("Transcribing audio..."):
                result = model.transcribe(str(audio_path))
                return result["text"]

        except Exception as e:
            st.error("⚠️ Audio transcription failed. Please try again.")
            return None

    def summarize_text(self, text, video_title=None):
        """Summarize text using Qwen Coder CLI"""
        try:
            # Create a temporary file with the transcript
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(text)
                temp_file_path = temp_file.name

            # Prepare the prompt for Qwen Code with video title context
            if video_title:
                prompt = f"""You are analyzing a YouTube video titled: "{video_title}"

Please provide a very concise summary of the following transcript from this video:

{text}

Create a clear, comprehensive summary that captures the main points, key information, and context from the video title."""
            else:
                prompt = f"""Please provide a very concise summary of the following transcript:

{text}

Create a clear, very concise, comprehensive summary that captures the main points and key information."""

            with st.spinner("Generating summary with Qwen Coder..."):
                # Call Qwen Coder CLI with the prompt
                result = subprocess.run([
                    r'node',
                    r'C:\\Users\\tesla\\AppData\\Roaming\\npm\\node_modules\\@qwen-code\\qwen-code\\dist\\index.js',
                    '--prompt', prompt
                ], capture_output=True, text=True, encoding='utf-8', timeout=120)

                if result.returncode != 0:
                    st.error("⚠️ AI processing failed. Please try again.")
                    return None

                # Clean the output to remove system messages and keep only the actual summary
                raw_output = result.stdout.strip()

                # Remove common system messages from Qwen CLI output
                system_messages = [
                    "Loaded cached Qwen credentials.",
                    "Loading Qwen model...",
                    "Processing request...",
                    "Generating response...",
                    "Qwen Coder",
                    "qwen-code",
                    "Node.js",
                    "npm"
                ]

                # Split output into lines and filter out system messages
                lines = raw_output.split('\n')
                cleaned_lines = []

                for line in lines:
                    line = line.strip()
                    # Skip empty lines
                    if not line:
                        continue
                    # Skip system messages (case-insensitive)
                    if any(msg.lower() in line.lower() for msg in system_messages):
                        continue
                    # Skip lines that look like debug output (contain file paths, version info, etc.)
                    if any(char in line for char in ['[', ']', '{', '}', 'C:\\', '/usr/', 'node_modules']):
                        continue
                    # Keep the line if it looks like actual summary content
                    cleaned_lines.append(line)

                # Join the cleaned lines back together
                summary = '\n'.join(cleaned_lines).strip()

                # Clean up the temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

                return summary if summary else "Summary could not be generated."

        except subprocess.TimeoutExpired:
            st.error("⚠️ Processing took too long. Please try with a shorter video.")
            return None
        except Exception as e:
            st.error("⚠️ AI processing failed. Please try again.")
            return None

def main():
    st.markdown('<div class="main-header">YouTube Video Summarizer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Get quick summaries from YouTube videos</div>', unsafe_allow_html=True)
    
    # Show warning if multiple retries
    if st.session_state.retry_count > 2:
        st.info("🔄 If you're experiencing repeated failures, YouTube may be temporarily blocking this server. Try again in a few minutes.")

    # Initialize the summarizer
    summarizer = YouTubeSummarizer()

    # Input section with form for better UX
    st.markdown("### Enter YouTube URL")

    # Create a form to handle Enter key and button clicks
    with st.form("url_form"):
        url = st.text_input(
            "YouTube URL",
            placeholder="Paste your YouTube video link here...",
            label_visibility="hidden"
        )
        # Options
        col1, col2 = st.columns(2)
        with col1:
            try_subtitles_first = st.checkbox(
                "Try subtitles first (faster)",
                value=True,
                help="Attempt to use YouTube's existing subtitles before downloading audio"
            )
        with col2:
            whisper_model = st.selectbox(
                "Whisper model",
                ["tiny", "base", "small"],
                index=1,
                help="Larger models are more accurate but slower"
            )

        # Submit button - always enabled when form is submitted
        submitted = st.form_submit_button("Summarize", type="primary")

    # Process when form is submitted (either by button click or Enter key)
    if submitted and url:
        # Validate URL
        if "youtube.com" not in url and "youtu.be" not in url:
            st.error("⚠️ Please enter a valid YouTube URL")
            return

        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Step 1: Get video title first
            status_text.text("Getting video information...")
            progress_bar.progress(10)
            video_title = summarizer.fetch_title_via_oembed(url)
            
            transcript = None
            audio_file = None
            
            # Step 2: Try subtitles first if enabled
            if try_subtitles_first:
                status_text.text("Checking for subtitles...")
                progress_bar.progress(20)
                subtitle_text, subtitle_title = summarizer.get_subtitles_fallback(url)
                
                if subtitle_text:
                    transcript = subtitle_text
                    if not video_title and subtitle_title:
                        video_title = subtitle_title
                    st.success("✅ Using YouTube subtitles (faster method)")
                    progress_bar.progress(50)
            
            # Step 3: If no subtitles, download and transcribe
            if not transcript:
                # Download audio
                status_text.text("Downloading audio...")
                progress_bar.progress(30)
                audio_file, video_title_dl = summarizer.download_youtube_video(url)
                
                if not audio_file:
                    # If download failed, error is already shown by download_youtube_video
                    return
                
                # Use download title if we didn't get one from oEmbed
                if not video_title and video_title_dl:
                    video_title = video_title_dl
                
                # Update Whisper model if different from default
                if whisper_model != "base":
                    summarizer.whisper_model = None  # Force reload
                    summarizer.whisper_model = whisper.load_model(whisper_model)
                    
                # Transcribe with Whisper
                progress_bar.progress(50)
                status_text.text(f"Transcribing audio with Whisper ({whisper_model} model)...")
                transcript = summarizer.transcribe_audio(audio_file)
                
                if not transcript:
                    st.error("⚠️ Transcription failed. Please try a different video.")
                    return

            progress_bar.progress(60)

            # Display transcript (secondary)
            with st.expander("View full transcript"):
                st.text_area("Full transcript", transcript, height=200, disabled=True, label_visibility="hidden")

            # Step 3: Generate summary
            status_text.text("Creating summary...")
            summary = summarizer.summarize_text(transcript, video_title)

            if not summary:
                return

            progress_bar.progress(100)
            status_text.text("Complete!")

            # Display results - focus on summary
            st.markdown("### Summary")
            st.markdown(f'<div class="success-message">{summary}</div>', unsafe_allow_html=True)
            
            # Reset retry counter on success
            st.session_state.retry_count = 0

            # Cleanup downloaded audio if any
            if audio_file:
                try:
                    os.remove(audio_file)
                except Exception:
                    pass

        except Exception as e:
            st.markdown(f'<div class="error-message">❌ Error: {str(e)}</div>', unsafe_allow_html=True)

        finally:
            progress_bar.empty()
            status_text.empty()

    # Minimal footer with status
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #999; font-size: 0.9rem;'>"
        "Powered by AI | "
        "<span style='color: #666;'>Note: Some videos may be restricted by YouTube</span>"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
