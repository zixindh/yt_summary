# YouTube Video AI Summarization Tool

A Streamlit application that automatically summarizes YouTube videos using AI.

## Features

- **Easy Input**: Users can paste YouTube video links directly into the UI
- **Automated Processing**: Downloads videos using yt_dlp package
- **AI Transcription**: Uses Whisper model to convert speech to text
- **Smart Summarization**: Leverages Qwen Coder CLI assistant to generate concise summaries

## Workflow

1. User inputs YouTube video URL
2. Video is downloaded to the `videos/` folder
3. Whisper transcribes the audio content
4. Qwen Coder generates a summary of the transcript
5. Results are displayed to the user 

## Known Issues

1. youtube download is very slow, need a faster way
2. text summary has unrecognizable words, missing the video title as the subject
3. after typing in youtube link, there is an unnecessary step by hitting enter before you can summarize the video.