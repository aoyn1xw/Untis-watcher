"""
build_exe.py – Script to build the Untis Watcher executable.

This script uses PyInstaller to create a Windows executable that runs
in the system tray without showing a console window.
"""

import subprocess
import sys
import os


def check_pyinstaller():
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller
        print("✓ PyInstaller is already installed.")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installed successfully.")


def build_exe():
    """Build the executable using PyInstaller."""
    print("\n" + "="*60)
    print("Building Untis Watcher executable...")
    print("="*60 + "\n")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=UntisWatcher",
        "--onefile",                    # Single executable file
        "--windowed",                   # No console window (runs in background)
        "--icon=NONE",                  # No custom icon (uses default)
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageDraw",
        "--hidden-import=pystray",
        "--hidden-import=requests",
        "--hidden-import=openai",
        "--hidden-import=telegram",
        "--clean",                      # Clean PyInstaller cache
        "main.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        
        # Copy .env file to dist folder if it exists
        if os.path.exists('.env'):
            import shutil
            shutil.copy2('.env', 'dist/.env')
            print("\n✓ Copied .env file to dist folder")
        
        print("\n" + "="*60)
        print("✓ Build completed successfully!")
        print("="*60)
        print(f"\nYour executable is located at:")
        print(f"  {os.path.abspath('dist/UntisWatcher.exe')}")
        print("\nTo run it:")
        print("  1. Double-click UntisWatcher.exe")
        print("  2. Look for the icon in your system tray")
        print("  3. Right-click the icon to quit")
        print("\n⚠ IMPORTANT: Make sure .env file is in the same folder as the .exe")
        print("\nTip: Add UntisWatcher.exe to your Windows startup folder to run on boot.")
        startup_folder = os.path.join(os.environ['APPDATA'], 
                                     r"Microsoft\Windows\Start Menu\Programs\Startup")
        print(f"  Startup folder: {startup_folder}")
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    check_pyinstaller()
    build_exe()
