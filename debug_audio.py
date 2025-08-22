#!/usr/bin/env python3
"""
Debug script to check audio file properties
"""
from pathlib import Path
import os

def debug_audio_file():
    """Debug the audio file to see what's wrong"""
    videos_dir = Path("videos")
    if not videos_dir.exists():
        print(f"Videos directory doesn't exist: {videos_dir}")
        return

    print(f"Contents of {videos_dir.absolute()}:")
    for file in videos_dir.iterdir():
        if file.is_file():
            size = file.stat().st_size
            print(f"  {file.name}: {size} bytes")

            # Check if it's an mp3 file
            if file.suffix.lower() == '.mp3':
                print(f"    - MP3 file found")
                print(f"    - Absolute path: {file.absolute()}")
                print(f"    - Exists: {file.exists()}")
                print(f"    - Is file: {file.is_file()}")

                # Try to read first few bytes
                try:
                    with open(file, 'rb') as f:
                        header = f.read(10)
                        print(f"    - First 10 bytes: {header.hex()}")
                        if header.startswith(b'ID3') or header.startswith(b'\xFF\xFB') or header.startswith(b'\xFF\xF3') or header.startswith(b'\xFF\xF2'):
                            print(f"    - Looks like a valid MP3 file")
                        else:
                            print(f"    - May not be a valid MP3 file")
                except Exception as e:
                    print(f"    - Error reading file: {e}")

    print("\nCurrent working directory:", Path.cwd())
    print("Python path:", os.sys.path[:3])

if __name__ == "__main__":
    debug_audio_file()
