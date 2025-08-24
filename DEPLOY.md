Streamlit Community Cloud deployment notes
========================================

This repository is prepared to install Whisper locally on Streamlit Community Cloud.

What is included
- `.streamlit/apt.txt` and `.streamlit/packages.txt` request FFmpeg and libsndfile.
- `requirements.txt` includes `openai-whisper`, `torch`, and audio packages required for local transcription.

Important notes
- Installing Whisper and PyTorch on first deploy can be slow and will increase the app build time. Expect the first deploy to take several minutes.
- If you run into memory issues, consider switching to a smaller Whisper model (e.g. `tiny`) in `app.py`.
- The app will attempt to use local Whisper. If you later want to use OpenAI cloud transcription/summarization, set `OPENAI_API_KEY` in Streamlit Secrets.

Streamlit Community Cloud setup
1. Create a new app from this repository and branch.
2. In the app settings, ensure the build runs with the default Python environment (the `requirements.txt` will be installed).
3. (Optional) Add `OPENAI_API_KEY` to Secrets if you prefer cloud fallback.

Troubleshooting
- If the build fails due to missing system packages, check the app logs on Streamlit Cloud; you may need to add additional apt packages to `.streamlit/apt.txt`.
- If PyTorch wheel isn't available for the platform, Streamlit Cloud may try to compile from source — adding a specific torch wheel or switching to CPU-only lighter versions can help.

If you want me to also change `app.py` to prefer a smaller Whisper model by default and to gracefully handle memory/CPU constraints on SCC, tell me and I'll implement it.
