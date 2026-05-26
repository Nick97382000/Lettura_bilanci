import sys
import subprocess

def install_python_packages():
    packages = [
        "pdfplumber",
        "pdf2image",
        "pytesseract",
        "pandas",
        "pillow"
    ]
    for package in packages:
        try:
            __import__(package) # Try importing to check if installed
        except ImportError:
            print(f"Installing Python package: {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def install_apt_packages():
    apt_packages = [
        "tesseract-ocr",
        "tesseract-ocr-ita",
        "poppler-utils"
    ]
    print("Updating apt-get...")
    # Use a try-except block in case apt-get update fails or is not needed
    try:
        subprocess.check_call(["apt-get", "update", "-qq"])
    except subprocess.CalledProcessError as e:
        print(f"Warning: apt-get update failed: {e}. Continuing anyway...")
    
    print(f"Installing apt packages: {', '.join(apt_packages)}...")
    subprocess.check_call(["apt-get", "install", "-y"] + apt_packages)

# Run installations when the module is imported
install_python_packages()
install_apt_packages()
