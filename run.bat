@echo off
echo Starting YouTube Video AI Summarizer...
echo Make sure you have installed the requirements: pip install -r requirements.txt
echo Also ensure FFmpeg is installed and available in your PATH
echo.
set PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%
streamlit run app.py
pause
