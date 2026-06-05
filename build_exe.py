import subprocess  # nosec B404
import sys
import os

def build():
    """
    Builds the GhostTune Converter executable using PyInstaller.
    Includes necessary flags to handle metadata for moviepy and imageio.
    """
    print("Building GhostTune Converter executable...")
    
    # Ensure dependencies are installed
    print("Checking/Installing build dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])  # nosec B603

    # Ensure paths are absolute for PyInstaller
    project_root = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(project_root, "images", "icon.ico")
    images_dir = os.path.join(project_root, "images")

    # Base PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=GhostTune Converter",
        f"--icon={icon_path}",
        f"--add-data={images_dir};images",
        # Correctly collect metadata for packages that use importlib.metadata
        "--copy-metadata=imageio",
        "--copy-metadata=moviepy",
        # Ensure all hooks and submodules are collected
        "--collect-all=moviepy",
        "--collect-all=imageio",
        "GhostTune Converter.py"
    ]
    
    print(f"\nRunning command: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)  # nosec B603
        print("\n" + "="*50)
        print("Build successful!")
        print(f"Executable location: {os.path.join('dist', 'GhostTune Converter.exe')}")
        print("="*50)
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("\nError: PyInstaller not found. Please ensure it is installed.")
        sys.exit(1)

if __name__ == "__main__":
    # Change to the script's directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build()
