# GhostTune Converter

![GhostTune Logo](https://raw.githubusercontent.com/Ghostshadowplays/Ghostyware-Logo/main/GhostywareLogo.png)

GhostTune Converter is a professional, high-performance media conversion utility built with Python and PyQt6. It allows users to download and convert YouTube content or local media files into various audio and video formats with ease.

## Features

- **YouTube Integration**: Download and convert YouTube videos directly to your preferred format.
- **Local Conversion**: Convert existing media files on your machine.
- **Audio & Video Support**: Supports a wide range of formats (MP3, WAV, AAC, MP4, MKV, etc.).
- **Professional UI**: Modern "Midnight" dark theme with a clean, intuitive interface.
- **Real-time Feedback**: Progress bars and status updates for all operations.
- **Process Cancellation**: Safely stop ongoing conversions at any time.
- **HighDPI Support**: Scales correctly on high-resolution displays.

## Supported Formats

- **Audio**: mp3, wav, aac, ogg, flac, m4a, opus, aiff, wma, mka
- **Video**: mp4, mkv, mov, avi, webm, flv

## Prerequisites

- **Python 3.8+**
- **FFmpeg**: Required for media processing. The app will attempt to find a system installation or use `imageio-ffmpeg`.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Ghostshadowplays/GhostTune-Converter.git
   cd GhostTune-Converter
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the application using Python:

```bash
python "GhostTune Converter.py"
```

1. **Select Mode**: Choose between Audio or Video mode.
2. **Input**:
   - For **YouTube**: Paste the URL in the input field.
   - For **Local**: Click "Convert Local File" to browse.
3. **Format**: Select your desired output format from the dropdown.
4. **Convert**: Click the conversion button and select your output destination.

## Security & Disclaimer

This tool is designed for **personal use only**. Downloading or converting copyrighted content without permission may violate terms of service and copyright laws. The developer is not responsible for any misuse of this tool.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
