# 🎥 YouTube Video AI Summarizer

A powerful Streamlit application that automatically downloads YouTube videos, transcribes them using AI, and generates concise summaries using advanced language models.

## ✨ Features

- **Easy to Use**: Simply paste any YouTube URL and get instant summaries
- **AI-Powered**: Uses Whisper for accurate transcription and Qwen for intelligent summarization
- **Modern Tech**: Built with the latest AI models and tools
- **Clean UI**: Beautiful, responsive interface with progress tracking
- **Automatic Cleanup**: Manages temporary files efficiently

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- FFmpeg (for audio processing)
- Qwen Code CLI installed and accessible in PATH
- At least 8GB RAM recommended for running AI models

### Installation

1. **Clone the repository** (if applicable) or navigate to the project folder

2. **Install Qwen Coder CLI**:
   - Install Qwen Coder and ensure the `qwen` command is available in your PATH
   - Make sure `qwen` is accessible from your command line

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg** (required for audio processing):
   - **Windows**: Download from [FFmpeg website](https://ffmpeg.org/download.html)
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

### Running the Application

```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## 📖 How to Use

1. **Paste URL**: Copy and paste any YouTube video URL into the input field
2. **Click Summarize**: Press the "🚀 Summarize Video" button
3. **Wait for Processing**: Watch the progress bar as the app:
   - Downloads the video audio
   - Transcribes it using Whisper
   - Generates a summary using Qwen
4. **View Results**: Read the AI-generated summary and optionally view the full transcript

## 🛠️ Technical Details

### Architecture

- **Frontend**: Streamlit for responsive web UI
- **Video Download**: pytubefix (enhanced pytube fork) and RapidAPI
- **Transcription**: OpenAI Whisper model
- **Summarization**: Qwen Coder CLI assistant with contextual prompts
- **Audio Processing**: FFmpeg for format conversion

### Tools Used

- **Whisper Base**: Fast and accurate speech recognition
- **Qwen Coder CLI**: Free coding assistant for text summarization

### File Structure

```
youtube-summarizer/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── context.md            # Project description
├── README.md             # This file
└── videos/               # Temporary video storage (auto-created)
```

## ⚠️ Important Notes

- **First Run**: The app will download Whisper model on first use (~1GB)
- **Memory Usage**: Only Whisper model requires significant RAM (~4GB)
- **Processing Time**: Depends on video length (typically 1-2x video duration)
- **Internet Required**: For downloading videos and Qwen Code API calls
- **Storage**: Temporary files are cleaned up automatically
- **Qwen Code**: Must be installed and accessible in system PATH

## 🎯 Supported Content

- Most YouTube videos (including age-restricted content if you have access)
- Various video qualities (automatically selects best audio)
- Multiple languages (Whisper supports 99+ languages)
- Videos up to 2 hours in length (longer videos may timeout)

## 🐛 Troubleshooting

### Common Issues

1. **"Qwen Coder is not installed"**
   - Install Qwen Coder and ensure the `qwen` command is available in your PATH
   - Ensure `qwen` command is accessible from your terminal

2. **"FFmpeg not found"**
   - Install FFmpeg and ensure it's in your system PATH

3. **"CUDA out of memory"**
   - The app will automatically fall back to CPU if GPU memory is insufficient
   - Consider using a smaller Whisper model by modifying the code

4. **"Model download failed"**
   - Check your internet connection
   - Ensure you have sufficient disk space (~1GB for Whisper model)

5. **"Qwen Code timeout"**
   - The text might be too long for processing
   - Try with shorter videos or break long transcripts into smaller chunks

6. **Slow processing**
   - Use shorter videos for faster results
   - Consider using GPU if available (modify code to use GPU)

### Getting Help

If you encounter issues:
1. Check the terminal output for detailed error messages
2. Ensure all dependencies are properly installed
3. Verify Qwen Coder CLI installation and PATH accessibility
4. Verify FFmpeg installation
5. Check available disk space and RAM

## 🔧 Customization

### Changing Whisper Models

To use different Whisper model sizes, modify the model loading in `app.py`:

```python
# For faster processing (less accurate)
self.whisper_model = whisper.load_model("tiny")

# For higher accuracy (slower, more memory)
self.whisper_model = whisper.load_model("large")
```

### Qwen Code Parameters

To customize Qwen Code behavior, modify the summarization function in `app.py`:

```python
# Adjust these parameters in the subprocess.run call
'--max-tokens', '512',     # Maximum length of summary
'--temperature', '0.7'     # Creativity level (0.0-1.0)
```

### Contextual Prompts

The app automatically includes the video title as context when generating summaries, which helps Qwen Code produce more relevant and accurate summaries. The prompt structure is:

```python
prompt = f"""You are analyzing a YouTube video titled: "{video_title}"

Please provide a concise summary of the following transcript from this video:

{transcript}

Create a clear, comprehensive summary that captures the main points, key information, and context from the video title."""
```

## 📄 License

This project is open source. Please check individual tool licenses:
- OpenAI Whisper: MIT License
- Qwen Coder: Free to use (check Qwen Coder license)
- pytubefix: MIT License
- Streamlit: Apache 2.0 License

## 🤝 Contributing

Feel free to open issues or submit pull requests to improve the application!

---

Built with ❤️ using cutting-edge AI technology
