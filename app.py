import streamlit as st
import yt_dlp
import whisper
import os
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    TooManyRequests,
    VideoUnavailable,
)
import time
import random
import json
try:
    from pytube import YouTube
    from pytube.exceptions import PytubeError
    PYTUBE_AVAILABLE = True
except ImportError:
    PYTUBE_AVAILABLE = False
    PytubeError = Exception

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

        # Optional: cookie/proxy support via Streamlit Secrets
        self.cookies_file_path = None
        try:
            cookies_content = st.secrets.get('YTDLP_COOKIES')
            if cookies_content:
                temp_cookie_path = Path(tempfile.gettempdir()) / 'yt_cookies.txt'
                with open(temp_cookie_path, 'w', encoding='utf-8') as f:
                    f.write(cookies_content)
                self.cookies_file_path = str(temp_cookie_path)
        except Exception:
            self.cookies_file_path = None

        self.proxy_url = None
        try:
            proxy_val = st.secrets.get('YTDLP_PROXY')
            if proxy_val:
                self.proxy_url = proxy_val
        except Exception:
            self.proxy_url = None

        # Set FFmpeg path for Whisper
        self._set_ffmpeg_for_whisper()

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

    def get_transcript_text(self, url: str):
        """Attempt to retrieve transcript without downloading media.

        Returns (transcript_text, video_title) or (None, video_title_if_available).
        """
        video_id = self.extract_video_id(url)
        title = self.fetch_title_via_oembed(url)
        if not video_id:
            return None, title

        try:
            # Prefer manually created English subtitles, then auto-generated, then any available language
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

            selected = None
            try:
                selected = transcripts.find_manually_created_transcript(["en", "en-US", "en-GB"])  # type: ignore[attr-defined]
            except Exception:
                selected = None
            if selected is None:
                try:
                    selected = transcripts.find_generated_transcript(["en", "en-US", "en-GB"])  # type: ignore[attr-defined]
                except Exception:
                    selected = None
            if selected is None:
                # Fallback to first available transcript of any language
                try:
                    selected = next(iter(transcripts))
                except StopIteration:
                    selected = None

            if selected is None:
                return None, title

            # Fetch and join lines
            chunks = selected.fetch()
            text = " ".join(chunk.get("text", "").replace("\n", " ") for chunk in chunks).strip()
            return (text if text else None), title
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, TooManyRequests):
            return None, title
        except Exception:
            return None, title

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

    def download_with_pytube(self, url):
        """Fallback download method using pytube"""
        if not PYTUBE_AVAILABLE:
            return None, None
            
        try:
            # Add delay and headers to avoid detection
            time.sleep(random.uniform(2, 5))
            
            # Try with custom client
            yt = YouTube(
                url,
                use_oauth=False,
                allow_oauth_cache=False
            )
            
            # Try to get audio stream
            audio_stream = yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                audio_stream = yt.streams.filter(progressive=True).order_by('abr').desc().first()
                
            if audio_stream:
                # Download the stream
                output_path = audio_stream.download(
                    output_path=str(self.videos_dir),
                    filename_prefix="audio_"
                )
                
                # Convert to mp3 if needed
                if not output_path.endswith('.mp3'):
                    mp3_path = Path(output_path).with_suffix('.mp3')
                    try:
                        subprocess.run([
                            'ffmpeg', '-i', output_path, '-acodec', 'mp3',
                            '-ab', '192k', str(mp3_path), '-y'
                        ], capture_output=True, check=True)
                        os.remove(output_path)
                        output_path = str(mp3_path)
                    except:
                        # If ffmpeg fails, just use the original file
                        pass
                        
                return output_path, yt.title
        except Exception as e:
            return None, None

    def download_youtube_video(self, url):
        
        try:
            # Add random delay to avoid bot detection
            time.sleep(random.uniform(1, 3))
            
            # Clean, robust base options; we will try a couple of player clients
            common_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'force_ipv4': True,
                'retries': 3,
                'fragment_retries': 3,
                'concurrent_fragment_downloads': 1,
                'http_chunk_size': 10 * 1024 * 1024,  # 10 MB
                'noplaylist': True,
                'geo_bypass': True,
                'geo_bypass_country': 'US',
                'outtmpl': str(self.videos_dir / 'video_%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'prefer_ffmpeg': True,
                'ffmpeg_location': 'ffmpeg',
                'cachedir': False,  # disable cache to avoid stale signatures
                'nocheckcertificate': True,
                'sleep_interval': 1,
                'max_sleep_interval': 3,
                'sleep_interval_requests': 1,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.youtube.com/'
                },
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }

            # Optional cookie/proxy injection when provided via secrets
            if self.cookies_file_path:
                common_opts['cookiefile'] = self.cookies_file_path
            if self.proxy_url:
                common_opts['proxy'] = self.proxy_url

            # Try a couple of different player clients with more options
            client_fallbacks = [
                ['web_creator'],  # Often works when web doesn't
                ['android_creator'],
                ['ios'],  # iOS client sometimes bypasses restrictions
                ['web_embedded'],  # Embedded player
                ['android_embedded'],
                ['mweb'],  # Mobile web
                ['web'],
                ['android'],
                ['tv_embedded'],
            ]
            
            # Add age gate bypass
            common_opts['age_limit'] = None

            last_err = None
            for clients in client_fallbacks:
                ydl_opts = dict(common_opts)
                ydl_opts['extractor_args'] = {
                    'youtube': {
                        'player_client': clients,
                    }
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        audio_file = Path(filename).with_suffix('.mp3')

                        original_title = info.get('title')
                        return str(audio_file), original_title
                except Exception as err:
                    # Save and try next client
                    last_err = err
                    continue

            # If all attempts failed, try pytube as fallback
            if last_err:
                st.info("Trying alternative download method...")
                audio_file, title = self.download_with_pytube(url)
                if audio_file and title:
                    return audio_file, title
                # If pytube also fails, try one more time with minimal yt-dlp options
                else:
                    minimal_opts = {
                        'format': 'best',
                        'outtmpl': str(self.videos_dir / 'video_%(id)s.%(ext)s'),
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'force_generic_extractor': False,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                    }
                    try:
                        with yt_dlp.YoutubeDL(minimal_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            filename = ydl.prepare_filename(info)
                            audio_file = Path(filename).with_suffix('.mp3')
                            return str(audio_file), info.get('title')
                    except:
                        raise last_err

        except Exception as e:
            # Final fallback to pytube if not already tried
            st.info("Primary download failed, trying alternative method...")
            audio_file, title = self.download_with_pytube(url)
            if audio_file and title:
                return audio_file, title
            
            # Check if it's a bot detection error
            error_msg = str(e).lower()
            if 'sign in' in error_msg or 'bot' in error_msg or '403' in error_msg:
                st.error("🤖 **Bot Detection**: YouTube is blocking automated access from this server.")
                st.warning("💡 **Alternatives**:\n\n"
                          "1. Try a video that has captions/subtitles (no download needed)\n"
                          "2. Use videos from educational channels (often less restricted)\n"
                          "3. Try shorter videos (under 10 minutes)\n"
                          "4. Wait a few minutes and try again\n"
                          "5. Use the transcript-only option when available")
                
                # Provide some example videos that usually work
                with st.expander("🎬 Suggested videos that typically work"):
                    st.write("""
                    - TED Talks: https://www.youtube.com/user/TEDtalksDirector
                    - Khan Academy: https://www.youtube.com/user/khanacademy
                    - MIT OpenCourseWare: https://www.youtube.com/user/MIT
                    - Crash Course: https://www.youtube.com/user/crashcourse
                    - Computerphile: https://www.youtube.com/user/Computerphile
                    - 3Blue1Brown: https://www.youtube.com/channel/UCYO_jab_esuFRV4b17AJtAw
                    """)
                    
                # Increment retry counter
                st.session_state.retry_count += 1
            else:
                st.error(f"⚠️ Unable to download video: {str(e)[:200]}...")
                
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
        use_whisper_fallback = st.checkbox(
            "Use Whisper fallback if transcript unavailable (slower)",
            value=False,
            help="If no captions are available, download audio and transcribe locally. Note: May not work for all videos due to YouTube restrictions."
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
            # Step 1: Try to fetch transcript without download
            status_text.text("Fetching transcript...")
            progress_bar.progress(20)
            transcript, video_title = summarizer.get_transcript_text(url)
            
            # If no transcript and whisper not enabled, provide helpful message
            if not transcript and not use_whisper_fallback:
                st.warning("📝 No transcript found for this video. Enable 'Use Whisper fallback' to transcribe the audio (this will be slower but works for most videos).")
                
                # Try to get video info to show to user
                video_id = summarizer.extract_video_id(url)
                if video_id:
                    video_info = summarizer.get_video_info_via_api(video_id)
                    if video_info:
                        st.info(f"🎬 **Video**: {video_info['title']} by {video_info['author']}")

            audio_file = None

            if not transcript and use_whisper_fallback:
                # Optional fallback: download audio and transcribe
                status_text.text("Downloading audio (fallback)...")
                progress_bar.progress(30)
                audio_file, video_title_dl = summarizer.download_youtube_video(url)
                if not audio_file:
                    return

                progress_bar.progress(40)
                status_text.text("Transcribing audio (fallback)...")
                transcript = summarizer.transcribe_audio(audio_file)
                if not transcript:
                    return
                # Prefer any title we got from oEmbed; otherwise use dl title
                if not video_title:
                    video_title = video_title_dl

            if not transcript:
                st.error("⚠️ No transcript could be obtained for this video. Please try:\n\n1. Enable the 'Whisper fallback' option\n2. Try a different video\n3. Use a video that has captions/subtitles enabled")
                
                # Provide some suggestions
                st.info("💡 **Tips for best results**:\n\n"
                       "- Videos with auto-generated captions work best (look for 'CC' button)\n"
                       "- Educational content is often less restricted\n"
                       "- Shorter videos (under 15 min) have better success rates\n"
                       "- Recent videos may have more restrictions")
                
                # Check if it might be a restricted video
                if 'music' in url.lower() or 'vevo' in url.lower():
                    st.warning("🎵 Music videos often have additional restrictions. Try educational or tutorial content instead.")
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
