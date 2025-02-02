#!/usr/bin/env python
"""
AndroidMediaVault Requirements Installer
"""

import subprocess
import sys
import os

def install_requirements():
    print("Installing AndroidMediaVault Requirements...")
    
    # List of required packages
    requirements = [
        'requests',
        'pathlib',
        'typing',
    ]
    
    # Install each requirement
    for package in requirements:
        print(f"\nInstalling {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"Error installing {package}: {str(e)}")
            return False
        except Exception as e:
            print(f"Unexpected error installing {package}: {str(e)}")
            return False
    
    print("\nAll requirements installed successfully!")
    input("\nPress Enter to exit...")
    return True

if __name__ == "__main__":
    install_requirements()