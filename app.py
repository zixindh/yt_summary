import streamlit as st
import yt_dlp
import openai
try:
    import whisper
    WHISPER_AVAILABLE = True
except Exception:
    whisper = None
    WHISPER_AVAILABLE = False
import os
import tempfile
import subprocess
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="YouTube Summarizer",
    page_icon="📝",
    layout="centered"
)

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

        # Set FFmpeg path for Whisper
        self._set_ffmpeg_for_whisper()

    def load_whisper_model(self):
        """Load local Whisper model if available. Returns model or None."""
        if not WHISPER_AVAILABLE:
            return None

        if self.whisper_model is None:
            with st.spinner("Loading local Whisper model..."):
                # Default to smaller 'tiny' model for Streamlit Cloud to reduce memory
                # and download size. Change to 'base' or 'small' locally if you have more resources.
                try:
                    self.whisper_model = whisper.load_model("tiny")
                except Exception as e:
                    # Provide a helpful message in the UI and return None so the app can fall back
                    st.error(f"⚠️ Failed to load Whisper model: {e}")
                    return None
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

    def download_youtube_video(self, url):
        """Download YouTube video as audio"""
        try:
            # Configure yt-dlp options with optimized settings for speed
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': str(self.videos_dir / 'video_%(id)s.%(ext)s'),  # Use video ID instead of title
                'quiet': True,
                'no_warnings': True,

                # Speed optimizations
                'concurrent_fragments': 4,  # Download multiple fragments simultaneously
                'fragment_retries': 3,     # Retry failed fragments
                'retries': 3,              # Retry download on failure
                'throttled_rate': None,    # Disable throttling
                'extract_flat': False,     # Extract full metadata
                'dump_single_json': False, # Don't dump JSON to speed up

                # Network optimizations
                'socket_timeout': 30,      # Connection timeout
                'extractor_retries': 3,    # Retry metadata extraction

                # Performance settings
                'buffersize': 1024 * 1024, # 1MB buffer size
                'http_chunk_size': 10 * 1024 * 1024, # 10MB chunks
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Replace extension with mp3
                audio_file = Path(filename).with_suffix('.mp3')

                # Get original title for AI prompt (preserve special characters for context)
                original_title = info['title']
                # Sanitize title only for display if needed
                sanitized_title = self.sanitize_filename(original_title)

                return str(audio_file), original_title

        except Exception as e:
            st.error("⚠️ Unable to download video. Please check the URL and try again.")
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

            # Prefer local Whisper if available and user is running in a local environment
            model = self.load_whisper_model()
            if model is not None:
                with st.spinner("Transcribing audio with local Whisper model..."):
                    try:
                        result = model.transcribe(str(audio_path))
                        return result.get("text")
                    except Exception as e:
                        st.error("⚠️ Local Whisper transcription failed. Falling back to OpenAI if available.")

            # Fallback: Use OpenAI's speech-to-text if OPENAI_API_KEY is provided
            openai_key = os.environ.get('OPENAI_API_KEY')
            if openai_key:
                openai.api_key = openai_key
                with st.spinner("Transcribing audio via OpenAI..."):
                    try:
                        with open(audio_path, "rb") as af:
                            # Use the Whisper transcription endpoint (may vary by SDK version)
                            response = openai.Audio.transcriptions.create(file=af, model="gpt-4o-transcribe")

                        # Extract text from response
                        text = None
                        if isinstance(response, dict):
                            text = response.get("text") or response.get("transcript")
                        else:
                            text = getattr(response, 'text', None)

                        if not text:
                            st.error("⚠️ Transcription failed. No text returned from OpenAI.")
                            return None

                        return text
                    except openai.error.OpenAIError as oe:
                        st.error(f"⚠️ OpenAI transcription failed: {str(oe)}")
                        return None
                    except Exception:
                        st.error("⚠️ Audio transcription failed. Please try again.")
                        return None

            st.error("⚠️ No transcription backend available. Install 'openai-whisper' locally or set OPENAI_API_KEY for cloud transcription.")
            return None

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
                # Call Qwen Coder CLI with the prompt. Try 'qwen' first, then fallback to a common
                # global node_modules path. Streamlit Cloud commonly has 'node' available.
                result = None
                try:
                    result = subprocess.run(['qwen', '--prompt', prompt], capture_output=True, text=True, encoding='utf-8', timeout=120)
                except FileNotFoundError:
                    # Fallback to node + global module path. Allow override via QWEN_NODE_PATH env var.
                    node_module_path = os.environ.get('QWEN_NODE_PATH', '/usr/local/lib/node_modules/@qwen-code/qwen-code/dist/index.js')
                    try:
                        result = subprocess.run(['node', node_module_path, '--prompt', prompt], capture_output=True, text=True, encoding='utf-8', timeout=120)
                    except FileNotFoundError:
                        st.error("⚠️ Qwen CLI not found. Install the `qwen` CLI or set QWEN_NODE_PATH to the qwen-code JS file.")
                        return None

                if result is None or result.returncode != 0:
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

    # Initialize the summarizer
    summarizer = YouTubeSummarizer()

    # Input section with two options: URL or upload audio (helps with restricted videos)
    st.markdown("### Input")

    input_method = st.radio("Choose input method:", ("YouTube URL", "Upload audio file"), index=0, horizontal=True)

    audio_file = None
    video_title = None

    if input_method == "YouTube URL":
        # Create a form to handle Enter key and button clicks
        with st.form("url_form"):
            url = st.text_input(
                "YouTube URL",
                placeholder="Paste your YouTube video link here...",
                label_visibility="hidden"
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
                # Step 1: Download video
                status_text.text("Processing video...")
                progress_bar.progress(10)

                audio_file, video_title = summarizer.download_youtube_video(url)
                if not audio_file:
                    return

                progress_bar.progress(30)

                # Step 2: Transcribe audio
                status_text.text("Converting to text...")
                transcript = summarizer.transcribe_audio(audio_file)

                if not transcript:
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

                # Cleanup
                try:
                    os.remove(audio_file)
                except:
                    pass

            except Exception as e:
                st.markdown(f'<div class="error-message">❌ Error: {str(e)}</div>', unsafe_allow_html=True)

            finally:
                progress_bar.empty()
                status_text.empty()

    # Minimal footer
    elif input_method == "Upload audio file":
        uploaded = st.file_uploader("Upload an audio file (mp3, wav, m4a)", type=["mp3", "wav", "m4a"], accept_multiple_files=False)
        if uploaded is not None:
            # Save uploaded file to videos/ and proceed
            saved_path = summarizer.videos_dir / summarizer.sanitize_filename(uploaded.name)
            with open(saved_path, "wb") as f:
                f.write(uploaded.getbuffer())

            st.success(f"Saved uploaded file to {saved_path}")

            # Transcribe
            with st.spinner("Transcribing uploaded audio..."):
                transcript = summarizer.transcribe_audio(str(saved_path))

            if not transcript:
                st.error("⚠️ Transcription failed for uploaded file.")
            else:
                with st.expander("View full transcript"):
                    st.text_area("Full transcript", transcript, height=200, disabled=True, label_visibility="hidden")

                summary = summarizer.summarize_text(transcript, video_title=None)
                if summary:
                    st.markdown("### Summary")
                    st.markdown(f'<div class="success-message">{summary}</div>', unsafe_allow_html=True)
                try:
                    os.remove(saved_path)
                except:
                    pass
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #999; font-size: 0.9rem;'>"
        "Powered by AI"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
