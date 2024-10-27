import yt_dlp
import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import threading
from moviepy.editor import VideoFileClip
import requests
from PIL import Image, ImageTk
from io import BytesIO


def load_image_from_url(image_url, size=(85, 85)):
    """Load an image from a URL."""
    try:
        response = requests.get(image_url)
        response.raise_for_status()  # Raise an error for bad responses
        image = Image.open(BytesIO(response.content))
        image = image.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(image)
    except Exception as e:
        print(f"Error loading image from URL {image_url}: {e}")
        return None

def create_label_with_image(master, text, image_url, text_color="#993cda"):
    """Create a label with an image."""
    loaded_image = load_image_from_url(image_url, size=(85, 85))
    if loaded_image:
        label = ctk.CTkLabel(master, text=text, font=("Helvetica", 25, "bold"),
                             image=loaded_image, text_color=text_color, compound="left")
        label.image = loaded_image  
        label.pack(pady=(30, 0))  
        return label  
    else:
        print("Failed to load image.")

# Initialize main application window
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
app = ctk.CTk()
app.title("GhostTune Converter")
app.geometry("500x540")
app.resizable(False,False)

logo_url = "https://raw.githubusercontent.com/Ghostshadowplays/Ghostyware-Logo/main/GhostywareLogo.png"
create_label_with_image(app, "GhostTune Converter", logo_url)  

# Display Code of Conduct Disclaimer
def show_code_of_conduct():
    message = (
        "Code of Conduct & Disclaimer:\n\n"
        "This application is designed for converting videos to audio formats for personal use only.\n\n"
        "Downloading or converting copyrighted content from YouTube or other sources "
        "without permission is prohibited by law. By using this app, you agree that "
        "the developer will not be held responsible for any misuse of this tool.\n\n"
        "Please ensure you have the right to download and convert any content.\n"
    )
    if not messagebox.askokcancel("Code of Conduct", message):
        app.destroy()  # Close the app if the user does not accept the disclaimer

# Call the disclaimer function
show_code_of_conduct()

# Create a label to display download percentage
percentage_label = ctk.CTkLabel(app, text="Download Progress: 0%", font=("Arial", 16))
percentage_label.pack(pady=(20, 10))

# Create a label for loading indication
loading_label = ctk.CTkLabel(app, text="", font=("Arial", 14))
loading_label.pack(pady=(20, 10))

def update_percentage(value):
    """Update percentage label in the main thread."""
    percentage_label.configure(text=f"Download Progress: {value:.2f}%")

def block_ui():
    """Disable all interactive elements in the app."""
    youtube_button.configure(state="disabled")
    local_button.configure(state="disabled")
    url_entry.configure(state="disabled")
    audio_format_dropdown.configure(state="disabled")
    loading_label.configure(text="Downloading... Please wait.")  # Show loading message
    app.update()  # Force update the UI

def unblock_ui():
    """Enable all interactive elements in the app."""
    youtube_button.configure(state="normal")
    local_button.configure(state="normal")
    url_entry.configure(state="normal")
    audio_format_dropdown.configure(state="normal")
    loading_label.configure(text="")  # Hide loading message

def convert_youtube_to_audio(url, audio_format):
    """Convert YouTube video to selected audio format."""
    try:
        block_ui()  # Block UI during download

        # Set options for downloading
        options = {
            'format': 'bestaudio/best',
            'extractaudio': True,  # Extract audio
            'audioformat': audio_format,  # Save as selected audio format
            'outtmpl': os.path.join(os.path.expanduser('~'), 'Downloads', '%(title)s.%(ext)s'),  # Output file template
            'noplaylist': True,  # Download only the single video, not the playlist
            'progress_hooks': [progress_hook],  # Add progress hook
        }

        # Download using yt_dlp
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        # Show success message
        messagebox.showinfo("Success", f"YouTube video has been converted to {audio_format.upper()}.")
        update_percentage(0)  # Reset to 0 immediately after success message

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during YouTube conversion: {e}")
        update_percentage(0)  # Reset percentage label on error

    finally:
        unblock_ui()  # Unblock UI after download

def progress_hook(d):
    """Track download progress and update the percentage label."""
    if d['status'] == 'downloading':
        # Calculate progress and update the percentage label
        if d.get('total_bytes', 0) > 0:
            progress = (d['downloaded_bytes'] / d['total_bytes']) * 100
            app.after(0, update_percentage, progress)

    elif d['status'] == 'finished':
        print("Download finished")  # Debug output
        app.after(0, update_percentage, 100)  # Set percentage to 100% when finished

        # Reset progress after a short delay
        app.after(2000, update_percentage, 0)  # Reset after 2 seconds

def convert_local_video_to_audio(audio_format):
    """Convert a local video file to selected audio format."""
    file_path = filedialog.askopenfilename(title="Select Video File", filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
    if file_path:
        save_path = filedialog.asksaveasfilename(defaultextension=f".{audio_format}", filetypes=[(f"{audio_format.upper()} Files", f"*.{audio_format}")])
        if save_path:
            try:
                block_ui()  # Block UI during conversion
                # Reset percentage label before starting conversion
                update_percentage(0)

                # Run conversion in a separate thread
                threading.Thread(target=run_moviepy_conversion, args=(file_path, save_path)).start()

            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {e}")

def run_moviepy_conversion(file_path, save_path):
    """Run MoviePy to convert video to audio with progress."""
    try:
        # Load the video file
        video = VideoFileClip(file_path)

        # Write the audio to the specified file
        video.audio.write_audiofile(save_path, codec='libmp3lame')  # Change codec based on selected format if necessary

        messagebox.showinfo("Success", "Video file has been converted to audio.")
        update_percentage(100)  # Complete progress

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred during local video conversion: {e}")

    finally:
        unblock_ui()  # Unblock UI after conversion
        update_percentage(0)  # Reset percentage label

# Create YouTube URL entry
url_label = ctk.CTkLabel(app, text="Enter YouTube URL:", font=("Arial", 16))
url_label.pack(pady=(20, 5))
url_entry = ctk.CTkEntry(app, width=300)
url_entry.pack(pady=(0, 20))

audio_format_var = ctk.StringVar(value="mp3")  # Default format
audio_formats = ["mp3", "wav", "aac", "ogg", "flac", "m4a", "wma", "aiff"]  # List of supported audio formats
format_label = ctk.CTkLabel(app, text="Select Audio Format:", font=("Arial", 16))
format_label.pack(pady=(20, 5))

audio_format_dropdown = ctk.CTkOptionMenu(
    app, 
    variable=audio_format_var, 
    values=audio_formats,
    fg_color="#4158D0",
    button_color="#4158D0",
    dropdown_hover_color="#993cda",
    dropdown_fg_color="#4158D0",
    width=100
)
audio_format_dropdown.pack(pady=(0, 20))

youtube_button = ctk.CTkButton(
    app, 
    text="Convert YouTube to Audio", 
    command=lambda: threading.Thread(target=convert_youtube_to_audio, args=(url_entry.get(), audio_format_var.get())).start(),
    fg_color="#4158D0", 
    hover_color="#993cda", 
    border_color="#e7e7e7", 
    border_width=2, 
    width=200
)
youtube_button.pack(pady=(0, 20))

local_button = ctk.CTkButton(
    app, 
    text="Convert Local Video to Audio", 
    command=lambda: convert_local_video_to_audio(audio_format_var.get()),
    fg_color="#4158D0", 
    hover_color="#993cda", 
    border_color="#e7e7e7", 
    border_width=2, 
    width=200
)
local_button.pack(pady=(0, 20))

# Run the application
app.mainloop()
