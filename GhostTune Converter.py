import sys
import os
import re
import logging
import shutil
import threading
from urllib.parse import urlparse
from io import BytesIO

import yt_dlp
import requests
from PIL import Image
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    from moviepy import VideoFileClip

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, 
    QLineEdit, QComboBox, QPushButton, QMessageBox, QFileDialog, QHBoxLayout,
    QProgressBar, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSize, QTimer
from PyQt6.QtGui import QPixmap, QFont, QImage, QIcon

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
LOGO_URL = "https://raw.githubusercontent.com/Ghostshadowplays/Ghostyware-Logo/main/GhostywareLogo.png"
SUPPORTED_AUDIO_FORMATS = ["mp3", "wav", "aac", "ogg", "flac", "m4a", "opus", "aiff", "wma", "mka"]
SUPPORTED_VIDEO_FORMATS = ["mp4", "mkv", "mov", "avi", "webm", "flv"]
MAX_DOWNLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2GB limit
REQUEST_TIMEOUT = 10
FFMPEG_PATH = None
STOP_EVENT = threading.Event()

# --- Security: Input Validation ---
def validate_youtube_url(url):
    if not url or len(url) > 2048:
        return False
    youtube_regex = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    return re.match(youtube_regex, url) is not None

def validate_file_path(file_path, allowed_dir=None):
    if not file_path or len(file_path) > 4096:
        return False
    abs_path = os.path.abspath(file_path)
    if '..' in file_path or file_path.startswith('/'):
        return False
    if allowed_dir:
        allowed_abs = os.path.abspath(allowed_dir)
        if not abs_path.startswith(allowed_abs):
            return False
    return True

def validate_audio_format(audio_format):
    return audio_format.lower() in SUPPORTED_AUDIO_FORMATS

def find_ffmpeg():
    global FFMPEG_PATH
    FFMPEG_PATH = shutil.which("ffmpeg")
    if FFMPEG_PATH:
        logger.info(f"FFmpeg found at: {FFMPEG_PATH}")
        return FFMPEG_PATH
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
        if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
            logger.info(f"FFmpeg found via imageio_ffmpeg: {FFMPEG_PATH}")
            return FFMPEG_PATH
        else:
            FFMPEG_PATH = None
    except ImportError:
        logger.debug("imageio_ffmpeg not installed")
    except Exception as e:
        logger.error(f"Error checking imageio_ffmpeg: {e}")
        FFMPEG_PATH = None
    return FFMPEG_PATH

# --- Worker Classes for Threading ---
class ConversionWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # success, message
    blocked_ui = pyqtSignal(str)
    unblocked_ui = pyqtSignal()

    def __init__(self, mode, **kwargs):
        super().__init__()
        self.mode = mode  # 'youtube' or 'local'
        self.kwargs = kwargs

    def run(self):
        STOP_EVENT.clear()
        if self.mode == 'youtube':
            self.convert_youtube()
        else:
            self.convert_local()

    def convert_youtube(self):
        url = self.kwargs.get('url')
        format_ext = self.kwargs.get('format_ext')
        output_dir = self.kwargs.get('output_dir')
        media_type = self.kwargs.get('media_type')
        
        def progress_hook(d):
            if STOP_EVENT.is_set():
                raise Exception("Interrupted by user")
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total_bytes and total_bytes > 0:
                    if total_bytes > MAX_DOWNLOAD_SIZE:
                        raise Exception("File size exceeds maximum allowed limit")
                    percent = (d['downloaded_bytes'] / total_bytes) * 100
                    self.progress.emit(f"Progress: {percent:.2f}%|{int(percent)}")
                else:
                    mb = d['downloaded_bytes'] / (1024 * 1024)
                    self.progress.emit(f"Progress: {mb:.2f} MB|0")
            elif d['status'] == 'finished':
                self.progress.emit("Progress: 100%|100")

        try:
            self.blocked_ui.emit(f"Downloading & Converting to {format_ext.upper()}...")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, mode=0o755)

            if media_type == 'audio':
                options = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
                    'noplaylist': True,
                    'progress_hooks': [progress_hook],
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': format_ext,
                    }],
                    'ffmpeg_location': FFMPEG_PATH,
                    'max_filesize': MAX_DOWNLOAD_SIZE,
                    'socket_timeout': REQUEST_TIMEOUT,
                    'quiet': True,
                    'no_warnings': True,
                }
            else:
                options = {
                    'format': f'bestvideo+bestaudio/best',
                    'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
                    'merge_output_format': format_ext,
                    'noplaylist': True,
                    'progress_hooks': [progress_hook],
                    'ffmpeg_location': FFMPEG_PATH,
                    'max_filesize': MAX_DOWNLOAD_SIZE,
                    'socket_timeout': REQUEST_TIMEOUT,
                    'quiet': True,
                    'no_warnings': True,
                }

            with yt_dlp.YoutubeDL(options) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                file_name = ydl.prepare_filename(info_dict)
                base, _ = os.path.splitext(file_name)
                final_file_path = f"{base}.{format_ext}"
            
            self.progress.emit("Progress: 100%|100")
            self.finished.emit(True, f"YouTube video converted and saved to:\n{output_dir}\n\nFile: {os.path.basename(final_file_path)}")
        except Exception as e:
            if "Interrupted by user" in str(e):
                self.finished.emit(False, "Process was cancelled by user.")
            else:
                logger.error(f"YouTube conversion error: {e}")
                self.finished.emit(False, f"Failed to convert YouTube video: {e}")
        finally:
            self.unblocked_ui.emit()

    def convert_local(self):
        file_path = self.kwargs.get('file_path')
        save_path = self.kwargs.get('save_path')
        format_ext = self.kwargs.get('format_ext')
        media_type = self.kwargs.get('media_type')

        self.blocked_ui.emit(f"Converting to {format_ext.upper()}...")
        self.progress.emit("Progress: Converting...|0")

        original_ffmpeg = os.environ.get("FFMPEG_BINARY")
        if FFMPEG_PATH:
            os.environ["FFMPEG_BINARY"] = FFMPEG_PATH

        video = None
        try:
            video = VideoFileClip(file_path)
            if STOP_EVENT.is_set():
                raise Exception("Interrupted by user")
            
            from proglog import TqdmProgressBarLogger
            class CancelableLogger(TqdmProgressBarLogger):
                def __init__(self, worker_progress):
                    super().__init__()
                    self.worker_progress = worker_progress

                def callback(self, **kw):
                    if STOP_EVENT.is_set():
                        raise Exception("Interrupted by user")

                def bars_callback(self, bar, attr, value, old_value=None):
                    if attr == 'index':
                        total = self.bars[bar]['total']
                        if total and total > 0:
                            percent = int((value / total) * 100)
                            self.worker_progress.emit(f"Progress: {percent}%|{percent}")

            logger_instance = CancelableLogger(self.progress)

            if media_type == 'audio':
                codec_map = {
                    "mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac",
                    "ogg": "libvorbis", "flac": "flac", "m4a": "aac",
                    "opus": "libopus", "aiff": "pcm_s16be", "wma": "wmav2", "mka": "libmp3lame"
                }
                selected_codec = codec_map.get(format_ext.lower())
                video.audio.write_audiofile(save_path, codec=selected_codec, verbose=False, logger=logger_instance)
            else:
                # Video conversion
                video.write_videofile(save_path, verbose=False, logger=logger_instance)
            
            if STOP_EVENT.is_set():
                 raise Exception("Interrupted by user")

            self.progress.emit("Progress: 100%|100")
            self.finished.emit(True, f"Local file converted to {format_ext.upper()}.")
        except Exception as e:
            if "Interrupted by user" in str(e):
                self.finished.emit(False, "Process was cancelled by user.")
            else:
                logger.error(f"Local conversion error: {e}")
                self.finished.emit(False, f"Failed to convert local file: {e}")
        finally:
            if video:
                try:
                    video.close()
                except Exception as e:
                    logger.debug(f"Error closing video clip: {e}")
            if original_ffmpeg is None:
                os.environ.pop("FFMPEG_BINARY", None)
            else:
                os.environ["FFMPEG_BINARY"] = original_ffmpeg
            self.unblocked_ui.emit()

# --- Main Window ---
class GhostTuneApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GhostTune Converter")
        self.setMinimumSize(550, 650)
        self.apply_styles()
        
        self.init_ui()
        find_ffmpeg()
        QTimer.singleShot(100, self.show_disclaimer)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f12;
            }
            QWidget {
                background-color: #0f0f12;
                color: #e0e0e0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #b0b0b0;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit {
                background-color: #1a1a1e;
                border: 1px solid #333339;
                border-radius: 6px;
                padding: 10px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #993cda;
                background-color: #212126;
            }
            QComboBox {
                background-color: #1a1a1e;
                border: 1px solid #333339;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                min-height: 20px;
            }
            QComboBox:hover {
                border-color: #44444c;
            }
            QComboBox::drop-down {
                border: 0;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a1e;
                border: 1px solid #333339;
                selection-background-color: #993cda;
                outline: none;
            }
            QRadioButton {
                spacing: 8px;
                font-size: 14px;
                color: #e0e0e0;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #555;
                border-radius: 9px;
                background: none;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #993cda;
                border-radius: 9px;
                background-color: #993cda;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                text-align: center;
                background-color: #1a1a1e;
                height: 8px;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0.5, x2:1, y2:0.5, stop:0 #993cda, stop:1 #4158D0);
                border-radius: 4px;
            }
        """)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(20)

        # Header Section
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 10)
        header_layout.setSpacing(15)
        
        self.logo_label = QLabel()
        self.load_logo()
        header_layout.addWidget(self.logo_label)
        
        title_container = QVBoxLayout()
        title_label = QLabel("GhostTune")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff; margin-bottom: -5px;")
        
        subtitle_label = QLabel("Advanced Media Converter")
        subtitle_label.setStyleSheet("color: #993cda; font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;")
        
        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)
        header_layout.addLayout(title_container)
        header_layout.addStretch()
        main_layout.addWidget(header_container)

        # Media Type Toggle (Segmented-like feel)
        toggle_container = QWidget()
        toggle_container.setStyleSheet("background-color: #1a1a1e; border-radius: 10px; padding: 5px;")
        type_layout = QHBoxLayout(toggle_container)
        type_layout.setContentsMargins(10, 5, 10, 5)
        
        self.audio_radio = QRadioButton("Audio Mode")
        self.video_radio = QRadioButton("Video Mode")
        self.audio_radio.setChecked(True)
        self.audio_radio.toggled.connect(self.update_format_list)
        self.video_radio.toggled.connect(self.update_format_list)
        
        self.radio_group = QButtonGroup()
        self.radio_group.addButton(self.audio_radio)
        self.radio_group.addButton(self.video_radio)
        
        type_layout.addStretch()
        type_layout.addWidget(self.audio_radio)
        type_layout.addSpacing(20)
        type_layout.addWidget(self.video_radio)
        type_layout.addStretch()
        main_layout.addWidget(toggle_container)

        # Input Section
        input_group = QVBoxLayout()
        input_group.setSpacing(8)
        
        url_label = QLabel("YOUTUBE URL")
        url_label.setStyleSheet("font-size: 11px; color: #777; font-weight: bold;")
        input_group.addWidget(url_label)
        
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("Paste link here...")
        input_group.addWidget(self.url_entry)
        
        main_layout.addLayout(input_group)

        # Format Section
        format_group = QVBoxLayout()
        format_group.setSpacing(8)
        
        format_label = QLabel("TARGET FORMAT")
        format_label.setStyleSheet("font-size: 11px; color: #777; font-weight: bold;")
        format_group.addWidget(format_label)
        
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(SUPPORTED_AUDIO_FORMATS)
        format_group.addWidget(self.format_dropdown)
        
        main_layout.addLayout(format_group)

        # Progress Section
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 10, 0, 10)
        progress_layout.setSpacing(8)

        status_header = QHBoxLayout()
        self.loading_label = QLabel("")
        self.loading_label.setStyleSheet("color: #993cda; font-weight: bold;")
        
        self.percentage_label = QLabel("Ready")
        self.percentage_label.setStyleSheet("color: #e0e0e0;")
        
        status_header.addWidget(self.loading_label)
        status_header.addStretch()
        status_header.addWidget(self.percentage_label)
        progress_layout.addLayout(status_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(progress_container)

        # Buttons Section
        button_layout = QVBoxLayout()
        button_layout.setSpacing(12)
        
        self.youtube_button = self.create_styled_button("Convert YouTube", self.start_youtube_conversion, is_primary=True)
        self.local_button = self.create_styled_button("Convert Local File", self.start_local_conversion)
        
        self.cancel_button = self.create_styled_button("Cancel Operation", self.stop_process, color="#cf352e")
        self.cancel_button.hide()
        
        button_layout.addWidget(self.youtube_button)
        button_layout.addWidget(self.local_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()

    def update_format_list(self):
        self.format_dropdown.clear()
        if self.audio_radio.isChecked():
            self.format_dropdown.addItems(SUPPORTED_AUDIO_FORMATS)
            self.youtube_button.setText("Convert YouTube to Audio")
            self.local_button.setText("Convert Local File to Audio")
        else:
            self.format_dropdown.addItems(SUPPORTED_VIDEO_FORMATS)
            self.youtube_button.setText("Convert YouTube to Video")
            self.local_button.setText("Convert Local File to Video")

    def create_styled_button(self, text, callback, color="#333339", is_primary=False):
        btn = QPushButton(text)
        if is_primary:
            style = """
                QPushButton {
                    background-color: #993cda;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #ac5ce4;
                }
                QPushButton:pressed {
                    background-color: #822eb9;
                }
                QPushButton:disabled {
                    background-color: #2a2a2e;
                    color: #555;
                }
            """
        else:
            style = f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: 1px solid #44444c;
                    border-radius: 8px;
                    padding: 12px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: #44444c;
                    border-color: #55555c;
                }}
                QPushButton:pressed {{
                    background-color: #2a2a2e;
                }}
                QPushButton:disabled {{
                    background-color: #1a1a1e;
                    color: #444;
                    border-color: #2a2a2e;
                }}
            """
        btn.setStyleSheet(style)
        btn.clicked.connect(callback)
        return btn

    def load_logo(self):
        try:
            response = requests.get(LOGO_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            image_data = response.content
            image = QImage.fromData(image_data)
            pixmap = QPixmap.fromImage(image)
            scaled_pixmap = pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
        except Exception as e:
            logger.error(f"Failed to load logo: {e}")

    def show_disclaimer(self):
        message = (
            "Code of Conduct & Disclaimer:\n\n"
            "This application is designed for converting videos to audio formats for personal use only.\n\n"
            "Downloading or converting copyrighted content from YouTube or other sources "
            "without permission is prohibited by law. By using this app, you agree that "
            "the developer will not be held responsible for any misuse of this tool.\n\n"
            "Please ensure you have the right to download and convert any content.\n"
        )
        reply = QMessageBox.question(self, "Code of Conduct", message, QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Cancel:
            sys.exit()

    def block_ui(self, message):
        self.youtube_button.setEnabled(False)
        self.local_button.setEnabled(False)
        self.url_entry.setEnabled(False)
        self.format_dropdown.setEnabled(False)
        self.audio_radio.setEnabled(False)
        self.video_radio.setEnabled(False)
        self.cancel_button.show()
        self.loading_label.setText(message)
        self.percentage_label.setText("Starting...")
        self.progress_bar.setRange(0, 0)

    def unblock_ui(self):
        self.youtube_button.setEnabled(True)
        self.local_button.setEnabled(True)
        self.url_entry.setEnabled(True)
        self.format_dropdown.setEnabled(True)
        self.audio_radio.setEnabled(True)
        self.video_radio.setEnabled(True)
        self.cancel_button.hide()
        self.loading_label.setText("")
        self.percentage_label.setText("Ready")
        self.progress_bar.setRange(0, 100)

    def stop_process(self):
        STOP_EVENT.set()
        self.loading_label.setText("Stopping... please wait.")
        self.progress_bar.setRange(0, 0)

    def start_youtube_conversion(self):
        url = self.url_entry.text().strip()
        format_ext = self.format_dropdown.currentText()
        media_type = 'audio' if self.audio_radio.isChecked() else 'video'
        if not validate_youtube_url(url):
            QMessageBox.critical(self, "Input Error", "Invalid YouTube URL.")
            return
        
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory", os.path.join(os.path.expanduser('~'), 'Downloads'))
        if not output_dir:
            return

        self.run_worker(mode='youtube', url=url, format_ext=format_ext, output_dir=output_dir, media_type=media_type)

    def start_local_conversion(self):
        format_ext = self.format_dropdown.currentText()
        media_type = 'audio' if self.audio_radio.isChecked() else 'video'
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Media File", "",
            "Media Files (*.mp4 *.mov *.avi *.mkv *.webm *.flv *.wmv *.mpeg *.mpg *.ts *.vob *.mp3 *.wav *.aac *.ogg *.flac *.m4a);;All Files (*)"
        )
        if not file_path: return

        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = f"{base}.{format_ext}"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Media As", suggested,
            f"{format_ext.upper()} Files (*.{format_ext});;All Files (*)"
        )
        if not save_path: return

        self.run_worker(mode='local', file_path=file_path, save_path=save_path, format_ext=format_ext, media_type=media_type)

    def run_worker(self, **kwargs):
        self.thread = QThread()
        self.worker = ConversionWorker(**kwargs)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.blocked_ui.connect(self.block_ui)
        self.worker.unblocked_ui.connect(self.unblock_ui)
        
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def update_progress(self, text):
        if "|" in text:
            display_text, progress_val = text.split("|")
            self.percentage_label.setText(display_text)
            try:
                val = int(progress_val)
                if val > 0:
                    self.progress_bar.setRange(0, 100)
                    self.progress_bar.setValue(val)
            except ValueError:
                pass
            except Exception as e:
                logger.error(f"Error updating progress bar: {e}")
        else:
            self.percentage_label.setText(text)

    def on_finished(self, success, message):
        if success:
            QMessageBox.information(self, "Success", message)
            self.url_entry.clear()
        else:
            if "cancelled" in message.lower():
                QMessageBox.information(self, "Cancelled", message)
            else:
                QMessageBox.critical(self, "Error", message)
        
        # Reset progress elements after a delay
        QTimer.singleShot(2000, self.reset_progress)

    def reset_progress(self):
        self.percentage_label.setText("Ready")
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GhostTuneApp()
    window.show()
    sys.exit(app.exec())
