#!/usr/bin/env python
"""
Android Backup Assistant
Content Creator Edition
"""

import os
import hashlib
import time
import subprocess
from pathlib import Path
import logging
from typing import List, Set
import json
from collections import defaultdict
import sys
import platform
import winreg
import ctypes
import site
import webbrowser
import zipfile
import requests
import shutil
import traceback

# Global configurations
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, 'platform-tools', 'adb.exe')
RESOURCES_DIR = os.path.join(SCRIPT_DIR, 'RESOURCES')

successful_backups = []  # Global list to track successful backups

# Define the content for file_operations.py
file_ops_content = '''import os
import subprocess
from typing import List, Dict
import logging

class FileOperations:
    def __init__(self):
        self.successful_backups = []
        self.failed_backups = {}
        
    def backup_file(self, source_path: str, dest_path: str, file_name: str) -> bool:
        """Backup a single file and track its status"""
        try:
            result = subprocess.run(['adb', 'pull', source_path, dest_path], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                self.successful_backups.append(source_path)
                return True
            else:
                self.failed_backups[source_path] = result.stderr
                print(f"Error backing up {file_name}: {result.stderr}")
                return False
        except Exception as e:
            self.failed_backups[source_path] = str(e)
            print(f"Error backing up {file_name}: {str(e)}")
            return False

    def remove_backed_up_files(self) -> None:
        """Remove successfully backed up files from device"""
        print("\nRemoving successfully backed up files...")
        for file_path in self.successful_backups:
            try:
                result = subprocess.run(['adb', 'shell', f'rm "{file_path}"'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print(f"Removed: {os.path.basename(file_path)}")
                else:
                    print(f"Error removing {os.path.basename(file_path)}: {result.stderr}")
            except Exception as e:
                print(f"Error removing {os.path.basename(file_path)}: {str(e)}")
        print("\nFile removal completed.")

    def get_backup_stats(self) -> Dict:
        """Return backup statistics"""
        return {
            'successful': len(self.successful_backups),
            'failed': len(self.failed_backups),
            'total': len(self.successful_backups) + len(self.failed_backups)
        }
'''

def is_admin():
    """Check if the script has admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def handle_error(e, show_traceback=False):
    """Handle errors and prevent immediate closing"""
    print("\nError occurred:")
    print(str(e))
    if show_traceback:
        print("\nDetailed error information:")
        traceback.print_exc()
    input("\nPress Enter to exit...")
    sys.exit(1)

def setup_windows_registry():
    """Setup Windows Registry for double-click functionality"""
    if platform.system() != "Windows":
        return
        
    if not is_admin():
        try:
            # Re-run the script with admin privileges
            script_path = os.path.abspath(__file__)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, f'"{script_path}"', None, 1
            )
        except Exception as e:
            handle_error(f"Failed to get admin privileges: {e}")
        return

    try:
        python_path = sys.executable
        script_path = os.path.abspath(__file__)
        script_command = f'"{python_path}" "{script_path}" %*'
        
        # Set up Python.File association
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Python.File\shell\open\command") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, script_command)
            
        # Associate .py extension
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, ".py") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Python.File")
            
        print("Successfully configured double-click support!")
        
    except Exception as e:
        handle_error(f"Error setting up registry: {e}")

def ensure_first_run_setup():
    """Perform first-run setup tasks"""
    try:
        config_file = Path.home() / "AndroidBackup" / ".config"
        
        if not config_file.exists():
            print("\nFirst time setup detected!")
            print("Configuring system for optimal usage...\n")
            
            # Create config file
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Setup Windows Registry for double-click if needed
            if platform.system() == "Windows":
                print("Setting up double-click support...")
                setup_windows_registry()
            
            # Save config to prevent future setup runs
            with open(config_file, 'w') as f:
                json.dump({
                    'setup_complete': True,
                    'setup_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'python_version': platform.python_version(),
                    'system_platform': platform.system()
                }, f, indent=4)
            
            print("\nSetup complete! You can now double-click the script to run it.")
            print("The script will continue with the backup process...")
            time.sleep(2)
    except Exception as e:
        handle_error(f"Error during first-run setup: {e}", show_traceback=True)

def download_platform_tools():
    """Download and install Android Platform Tools"""
    script_dir = Path(__file__).parent
    platform_tools_dir = script_dir / "platform-tools"
    zip_path = script_dir / "platform-tools-latest-windows.zip"
    
    # If already downloaded, just extract
    if zip_path.exists():
        print("\nFound existing platform-tools zip file.")
        try:
            if platform_tools_dir.exists():
                shutil.rmtree(platform_tools_dir)
            
            print("Extracting files...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(script_dir)
            
            adb_exe = platform_tools_dir / "adb.exe"
            if adb_exe.exists():
                os.chmod(str(adb_exe), 0o755)
                print("Installation complete!")
                return str(adb_exe)
        except Exception as e:
            print(f"Error extracting existing zip: {e}")
    
    # Download if not found locally
    try:
        print("\nDownloading Android Platform Tools...")
        url = "https://dl.google.com/android/repository/platform-tools_r34.0.5-windows.zip"
        
        # Download with progress
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(zip_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for data in response.iter_content(chunk_size=4096):
                    downloaded += len(data)
                    f.write(data)
                    done = int(50 * downloaded / total_size)
                    sys.stdout.write(f'\rDownload Progress: [{"="*done}{" "*(50-done)}] {downloaded}/{total_size} bytes')
                    sys.stdout.flush()
        print("\nDownload complete!")
        
        # Extract the zip file
        print("Extracting files...")
        if platform_tools_dir.exists():
            shutil.rmtree(platform_tools_dir)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(script_dir)
        
        # Set proper permissions
        adb_exe = platform_tools_dir / "adb.exe"
        if adb_exe.exists():
            os.chmod(str(adb_exe), 0o755)
        
        print("Installation complete!")
        return str(adb_exe)
        
    except Exception as e:
        print(f"\nError downloading/extracting platform tools: {e}")
        return None

def add_to_path(path):
    """Add platform-tools to system PATH"""
    try:
        if platform.system() == "Windows":
            # Get the current PATH
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               "Environment", 
                               0, 
                               winreg.KEY_READ | winreg.KEY_WRITE)
            current_path = winreg.QueryValueEx(key, "Path")[0]
            
            # Add new path if it's not already there
            if path not in current_path:
                new_path = current_path + ";" + path
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                
            winreg.CloseKey(key)
            # Notify Windows of environment change
            subprocess.run(['setx', 'Path', new_path], capture_output=True)
            print("Added platform-tools to PATH")
            return True
    except Exception as e:
        print(f"Error adding to PATH: {e}")
        return False

def setup_manual_adb():
    """Help user setup manually downloaded platform-tools"""
    print("\nSetting up manually downloaded platform-tools...")
    
    # Ask user for the platform-tools location
    print("\nPlease enter the path to the extracted platform-tools folder")
    print("(Usually ends with 'platform-tools' and contains adb.exe)")
    print("Example: C:\\Users\\username\\Downloads\\platform-tools")
    
    while True:
        path = input("\nPath: ").strip('"')  # Remove quotes if user copied from explorer
        adb_path = Path(path) / "adb.exe"
        
        if not adb_path.exists():
            print("\nCouldn't find adb.exe in that location.")
            print("Please make sure you've extracted the zip file and entered the correct path.")
            if input("\nTry again? (yes/no): ").lower() != 'yes':
                return None
            continue
        
        # Found ADB, now add to PATH
        try:
            if add_to_path(str(adb_path.parent)):
                print("\nSuccessfully added platform-tools to PATH!")
                print("Please restart your computer to complete the setup.")
                input("\nPress Enter to exit...")
                return str(adb_path)
            else:
                print("\nFailed to add to PATH. Please run the script as administrator.")
                return None
        except Exception as e:
            print(f"\nError setting up ADB: {e}")
            return None

def print_header():
    """Print the program header"""
    print("\nStarting Android Backup Assistant...")
    print("Initializing setup...")
    
    # Create RESOURCES directory if it doesn't exist
    resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RESOURCES')
    os.makedirs(resources_dir, exist_ok=True)
    print(f"RESOURCES directory created/verified at: {resources_dir}")
    
    print("Importing required modules...")
    print("Modules imported successfully!")
    
    print("\n╔════════════════════════════════════════════╗")
    print("║         Android Backup Assistant            ║")
    print("║            Content Creator Edition          ║")
    print("╚════════════════════════════════════════════╝\n")
    
    print("First time? Just follow the prompts!")
    print('Need help? Type "python android-backup.py --help"\n')

def ensure_adb_available():
    """Ensure ADB is available and return its path"""
    global ADB_PATH
    
    if not os.path.exists(ADB_PATH):
        print("\nADB not found. Downloading platform-tools...")
        download_platform_tools()
    
    if not os.path.exists(ADB_PATH):
        raise Exception("Failed to setup ADB. Please install Android Platform Tools manually.")
    
    # Test ADB functionality
    try:
        subprocess.run([ADB_PATH, 'version'], capture_output=True, check=True)
    except subprocess.CalledProcessError:
        raise Exception("ADB installation appears corrupted. Please reinstall Android Platform Tools.")
    except Exception as e:
        raise Exception(f"Error testing ADB: {str(e)}")
    
    return ADB_PATH

def wait_for_device():
    """Wait for device connection"""
    while True:
        try:
            result = subprocess.run([ADB_PATH, 'devices'], capture_output=True, text=True)
            devices = [line.split('\t')[0] for line in result.stdout.split('\n')[1:] if line.strip()]
            
            if devices:
                return True
                
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(1)
            
        except Exception as e:
            print(f"\nError checking device connection: {str(e)}")
            time.sleep(1)

def get_backup_preferences():
    """Get user preferences for backup process"""
    print("\nBackup Preferences")
    print("=================")
    print("Would you like successfully backed up files to be removed from the device?")
    print("(Failed transfers will be kept on device)")
    print("1. Yes - Remove files after successful backup")
    print("2. No - Keep all files on device")
    
    while True:
        choice = input("\nEnter choice (1-2): ")
        if choice == "1":
            return True
        elif choice == "2":
            return False
        else:
            print("Invalid choice. Please enter 1 or 2.")

def remove_backed_up_files(successful_files):
    """Remove successfully backed up files from device"""
    print("\nRemoving successfully backed up files from device...")
    for file_path in successful_files:
        try:
            result = subprocess.run([ADB_PATH, 'shell', f'rm "{file_path}"'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Removed: {os.path.basename(file_path)}")
            else:
                print(f"Failed to remove: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error removing {os.path.basename(file_path)}: {str(e)}")
    print("\nFile removal completed.")

def organize_backup_folder(backup_dir):
    """Organize backed up files by type and date"""
    print("\nOrganizing backed up files...")
    
    for root, _, files in os.walk(backup_dir):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                # Get file creation/modification time
                file_time = os.path.getmtime(file_path)
                file_date = time.strftime('%Y-%m-%d', time.localtime(file_time))
                
                # Determine file type
                _, ext = os.path.splitext(file.lower())
                if ext in ['.mp4', '.mov', '.avi']:
                    type_folder = 'Videos'
                elif ext in ['.jpg', '.jpeg', '.png']:
                    type_folder = 'Photos'
                else:
                    type_folder = 'Other'
                
                # Create type and date folders
                type_path = os.path.join(root, type_folder)
                date_path = os.path.join(type_path, file_date)
                os.makedirs(date_path, exist_ok=True)
                
                # Move file to new location
                new_path = os.path.join(date_path, file)
                if os.path.exists(new_path):
                    # If file exists, append timestamp to filename
                    base, ext = os.path.splitext(file)
                    new_path = os.path.join(date_path, f"{base}_{int(time.time())}{ext}")
                
                os.rename(file_path, new_path)
                print(f"Organized: {file} -> {type_folder}/{file_date}/")
                
            except Exception as e:
                print(f"Error organizing {file}: {str(e)}")
                continue

def backup_folder(source_folder, dest_folder, total_files, processed_files, 
                 successful_files, failed_files, delete_after_backup=False):
    """Backup a single folder"""
    print(f"\nProcessing {source_folder}...")
    print("=" * 50)
    print(f"Backing up to: {dest_folder}")
    
    # Create log file for failed transfers
    log_file = os.path.join(SCRIPT_DIR, 'failed_transfers.log')
    
    try:
        # Get list of files in the folder
        result = subprocess.run([ADB_PATH, 'shell', f'find "{source_folder}" -type f'],
                              capture_output=True, text=True)
        files = result.stdout.strip().split('\n')
        files = [f for f in files if f and  # Remove empty entries
                any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi'])]
        
        # Create destination folder if it doesn't exist
        os.makedirs(dest_folder, exist_ok=True)
        
        # Process each file
        for file_count, source_path in enumerate(files, 1):
            file_name = os.path.basename(source_path)
            dest_path = os.path.join(dest_folder, file_name)
            
            # Show progress
            print_progress(source_folder, file_count, len(files), total_files, processed_files, file_name, dest_path)
            
            # Attempt backup with retries
            if backup_file(source_path, dest_path):
                successful_files.append(source_path)
                # Only delete if this folder was selected for backup and deletion was enabled
                if delete_after_backup and REMOVE_AFTER_BACKUP:
                    try:
                        subprocess.run([ADB_PATH, 'shell', f'rm "{source_path}"'])
                    except Exception as e:
                        print(f"Warning: Could not delete {source_path}: {str(e)}")
            else:
                failed_files.append(source_path)
                # Log failed transfer
                with open(log_file, 'a') as f:
                    f.write(f"Failed to backup: {source_path}\n")
                    f.write(f"Destination: {dest_path}\n")
                    f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("-" * 50 + "\n")
                print(f"\nFailed to backup {file_name} - logged to failed_transfers.log")
            
            processed_files += 1
            
        # After successful backup, organize the files
        organize_backup_folder(dest_folder)
        return True
        
    except Exception as e:
        # Log folder-level error
        with open(log_file, 'a') as f:
            f.write(f"Error processing folder {source_folder}: {str(e)}\n")
            f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 50 + "\n")
        print(f"\nError processing folder {source_folder}: {str(e)}")
        print("Error logged to failed_transfers.log")
        return False

def print_progress(folder, current, total_folder, total_files, processed_files, current_file, dest_path):
    """Print progress information"""
    folder_progress = (current / total_folder) * 100 if total_folder > 0 else 0
    total_progress = ((processed_files + current) / total_files) * 100 if total_files > 0 else 0
    
    print(f"\nCurrent folder: {folder}")
    print(f"Progress: {folder_progress:.1f}% ({current}/{total_folder})")
    print(f"Total progress: {total_progress:.1f}% ({processed_files + current}/{total_files})")
    print(f"Current file: {current_file}")
    print(f"Destination: {dest_path}")

def backup_file(source_path, dest_path, retries=3):
    """Attempt to backup a file with retries"""
    for attempt in range(retries):
        try:
            print(f"\nBacking up: {os.path.basename(source_path)}")
            result = subprocess.run([ADB_PATH, 'pull', source_path, dest_path], 
                                  capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"Successfully backed up: {os.path.basename(source_path)}")
                return True
                
            if "error: device offline" in result.stderr or "error: no devices/emulators found" in result.stderr:
                print("\nDevice disconnected. Waiting for reconnection...")
                wait_for_device()
                continue
                
        except subprocess.TimeoutExpired:
            print(f"\nTimeout occurred. Retrying... (Attempt {attempt + 1}/{retries})")
            continue
            
        except Exception as e:
            print(f"\nError occurred: {str(e)}")
            
        print(f"\nRetrying file transfer... (Attempt {attempt + 1}/{retries})")
    
    return False

def prompt_continue():
    """Prompt user whether to continue after error"""
    while True:
        response = input("\nContinue with remaining files? (y/n): ").lower()
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print("Please enter 'y' or 'n'")

def parse_args():
    """Parse command line arguments"""
    import argparse
    parser = argparse.ArgumentParser(description='Android Backup Assistant', add_help=False)
    parser.add_argument('-h', '--help', action='store_true', help='Show detailed help')
    parser.add_argument('--auto', action='store_true', help='Enable automatic backup')
    parser.add_argument('--clean', action='store_true', help='Delete files after backup')
    parser.add_argument('--report', action='store_true', help='Generate backup report')
    parser.add_argument('--verify', action='store_true', help='Verify existing backups')
    parser.add_argument('--setup', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--install-adb', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--first-run', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args()

def setup_resources():
    """Setup RESOURCES folder and required files"""
    try:
        # Get the directory where the script is located
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        resources_dir = script_dir / "RESOURCES"
        
        # Create RESOURCES directory if it doesn't exist
        resources_dir.mkdir(exist_ok=True)
        print(f"RESOURCES directory created/verified at: {resources_dir}")
        
        # Create file_operations.py if it doesn't exist
        file_ops_path = resources_dir / "file_operations.py"
        if not file_ops_path.exists():
            print("Creating file_operations.py...")
            with open(file_ops_path, 'w') as f:
                f.write(file_ops_content)
            print("Created file_operations.py successfully!")
            
        # Create __init__.py to make RESOURCES a package
        init_path = resources_dir / "__init__.py"
        if not init_path.exists():
            init_path.touch()
            print("Created __init__.py successfully!")
            
        return True
    except Exception as e:
        handle_error(f"Error setting up resources: {e}", show_traceback=True)
        return False

def main():
    """Main program execution"""
    print_header()
    
    # Get user preferences for file removal
    remove_files = get_backup_preferences()
    
    # Ensure ADB is available
    try:
        ensure_adb_available()
    except Exception as e:
        handle_error(f"ADB setup failed: {str(e)}", show_traceback=True)
        return
    
    # Setup backup location
    backup_dir = setup_backup_location()
    
    # Check for Samsung devices
    print("\nChecking for Samsung devices...")
    
    # Wait for device connection
    print("\nWaiting for device connection...")
    print(f"Using ADB from: {ADB_PATH}")
    wait_for_device()
    print("\nDevice connected successfully!")
    
    print("Starting backup process...")
    print(f"\nBackup Location: {backup_dir}")
    print(f"Absolute path: {os.path.abspath(backup_dir)}")
    
    # Get user selection for backup
    folders_to_backup = select_backup_folders()
    
    # Track successful and failed backups
    successful_files = []
    failed_files = []
    
    # Start the backup process
    if start_backup(backup_dir, folders_to_backup, successful_files, failed_files):
        if remove_files and successful_files:
            remove_backed_up_files(successful_files)
        
        # Organize all backed up files
        print("\nOrganizing backed up files by type and date...")
        organize_backup_folder(backup_dir)
    
    # Print final summary
    print("\n" + "=" * 50)
    print("Backup Process Complete!")
    print("=" * 50)
    print(f"Successfully backed up: {len(successful_files)} files")
    print(f"Failed transfers: {len(failed_files)} files")
    
    if os.path.exists('failed_transfers.log'):
        print("\nDetailed error log available in: failed_transfers.log")
    
    if failed_files:
        print("\nFailed files:")
        for file in failed_files[:5]:  # Show first 5 failed files
            print(f"- {os.path.basename(file)}")
        if len(failed_files) > 5:
            print(f"... and {len(failed_files) - 5} more")
    
    input("\nPress Enter to exit...")

def start_backup(backup_dir, folders_to_backup, successful_files, failed_files):
    """Start the backup process with the selected folders"""
    if not backup_dir:
        print("Error: Backup location not set!")
        return False
        
    # Scan selected folders
    print("\nScanning folders...")
    total_files = 0
    total_size = 0
    folder_info = []  # Store info about each folder
    
    for i, folder in enumerate(folders_to_backup, 1):
        files, size = scan_folder(folder)
        if files > 0:
            print(f"{i}. Found {files} files in {folder} ({size:.1f} MB)")
            folder_info.append((folder, files, size))
            total_files += files
            total_size += size
    
    print(f"\nTotal files to backup: {total_files}")
    print(f"Total size: {total_size:.1f} MB")
    
    print("\nOptions:")
    print("Press Enter or '0' to backup everything")
    print("Or enter folder numbers (comma-separated) to backup specific folders")
    print("Example: 1,3,5 to backup only those folders")
    
    choice = input("\nYour choice: ").strip()
    
    if choice and choice != '0':  # If user entered numbers
        try:
            # Split by comma and handle potential empty strings
            selected_indices = [int(x.strip()) - 1 for x in choice.split(',') if x.strip()]
            
            # Validate all indices before proceeding
            if not all(0 <= i < len(folder_info) for i in selected_indices):
                print("Invalid folder number(s). Please try again.")
                return start_backup(backup_dir, folders_to_backup, successful_files, failed_files)
            
            folders_to_backup = [folder_info[i][0] for i in selected_indices]
            
            # Recalculate totals for selected folders
            total_files = sum(folder_info[i][1] for i in selected_indices)
            total_size = sum(folder_info[i][2] for i in selected_indices)
            
            print(f"\nSelected {len(folders_to_backup)} folders")
            print(f"Files to backup: {total_files}")
            print(f"Total size: {total_size:.1f} MB")
            
            if not input("\nPress Enter to continue or 'q' to quit: ").lower().startswith('q'):
                return process_backup(backup_dir, folders_to_backup, total_files, successful_files, failed_files)
            return False
            
        except (ValueError, IndexError) as e:
            print(f"Invalid selection format. Please try again.")
            return start_backup(backup_dir, folders_to_backup, successful_files, failed_files)
    
    # If user pressed Enter or entered '0', proceed with all folders
    if not input("\nPress Enter to continue or 'q' to quit: ").lower().startswith('q'):
        return process_backup(backup_dir, folders_to_backup, total_files, successful_files, failed_files)
    return False

def process_backup(backup_dir, folders_to_backup, total_files, successful_files, failed_files):
    """Process the actual backup of selected folders"""
    processed_files = 0
    
    # Create a set of selected folder paths for easy lookup
    selected_folder_paths = {os.path.normpath(folder) for folder in folders_to_backup}
    
    for folder in folders_to_backup:
        dest_folder = os.path.join(backup_dir, os.path.basename(folder))
        
        # Only process deletion for folders that were explicitly selected
        delete_after_backup = folder in selected_folder_paths
        
        if not backup_folder(folder, dest_folder, total_files, processed_files, 
                           successful_files, failed_files, delete_after_backup):
            print("\nBackup process interrupted.")
            return False
            
    return True

def setup_backup_location():
    """Setup and create backup directory structure"""
    print("\nBackup Location Setup")
    print("====================")
    
    # Default location is in script directory
    default_location = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Backup')
    print(f"Default backup location: {default_location}")
    
    print("\nWould you like to:")
    print("1. Use default location")
    print("2. Choose custom location")
    
    while True:
        choice = input("\nEnter choice (1-2): ")
        if choice == "1":
            backup_dir = default_location
            break
        elif choice == "2":
            backup_dir = input("\nEnter backup location: ").strip('"')
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Create main backup directory
    print(f"\nCreating backup directory at: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Create folder structure
    print("Creating folder structure...")
    folders = [
        'Camera',
        'Screenshots',
        'Downloads',
        'WhatsApp Media',
        'Telegram',
        'Instagram',
        'TikTok',
        'SnapChat',
        'Screen Recordings',
        'Video Captures',
        'Video Editor',
        'Facebook',
        'Movies',
        'Other'  # For miscellaneous files
    ]
    
    for folder in folders:
        folder_path = os.path.join(backup_dir, folder)
        os.makedirs(folder_path, exist_ok=True)
        print(f"Created: {folder}")
    
    return backup_dir

def get_device_folders():
    """Get list of folders and files to scan on device"""
    base_paths = [
        # DCIM directory and its subdirectories
        '/storage/emulated/0/DCIM',
        '/storage/emulated/0/DCIM/Camera',
        '/storage/emulated/0/DCIM/Videocaptures',
        '/storage/emulated/0/DCIM/Video Editor',
        '/storage/emulated/0/DCIM/Snapchat',
        '/storage/emulated/0/DCIM/Screen recordings',
        '/storage/emulated/0/DCIM/RedTiger',
        '/storage/emulated/0/DCIM/Facebook',
        '/storage/emulated/0/DCIM/Dicks Refund',
        # Movies directory and its subdirectories
        '/storage/emulated/0/Movies',
        '/storage/emulated/0/Movies/TikTok',
        '/storage/emulated/0/Movies/Facetune'
    ]
    
    return base_paths

def scan_folder(folder_path):
    """Scan a folder for media files"""
    try:
        # First, check if the folder exists
        check_result = subprocess.run([ADB_PATH, 'shell', f'[ -d "{folder_path}" ] && echo "exists"'],
                                    capture_output=True, text=True)
        
        files = []
        total_size = 0
        
        # If it's a directory, scan recursively
        if "exists" in check_result.stdout:
            result = subprocess.run([ADB_PATH, 'shell', f'find "{folder_path}" -type f -name "*.*"'],
                                  capture_output=True, text=True)
            files.extend([f for f in result.stdout.strip().split('\n') if f and 
                       any(f.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.avi', '.mp3'])])
        
        # Also check if it's a direct file path
        else:
            result = subprocess.run([ADB_PATH, 'shell', f'[ -f "{folder_path}" ] && echo "{folder_path}"'],
                                  capture_output=True, text=True)
            if result.stdout.strip():
                files.append(folder_path)
        
        # Calculate total size
        for file in files:
            size_result = subprocess.run([ADB_PATH, 'shell', f'stat -c%s "{file}"'],
                                       capture_output=True, text=True)
            try:
                total_size += int(size_result.stdout.strip())
            except ValueError:
                continue
                
        return len(files), total_size / (1024 * 1024)  # Convert to MB
    except Exception as e:
        print(f"Error scanning {folder_path}: {str(e)}")
        return 0, 0

def select_backup_folders():
    """Let user select which folders to backup"""
    folders = get_device_folders()
    
    print("\nWhat would you like to backup?")
    print("1. Everything")
    print("2. Select specific folders")
    
    while True:
        choice = input("\nEnter choice (1-2): ")
        if choice == "1":
            return folders
        elif choice == "2":
            print("\nSelect folders to backup:")
            selected_folders = []
            for i, folder in enumerate(folders, 1):
                print(f"{i}. {folder}")
            
            selections = input("\nEnter folder numbers (comma-separated): ")
            try:
                indices = [int(x.strip()) - 1 for x in selections.split(',')]
                return [folders[i] for i in indices if 0 <= i < len(folders)]
            except:
                print("Invalid selection. Please try again.")
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        input("\nPress Enter to exit...")
        sys.exit(0)
    except Exception as e:
        handle_error(f"Fatal error: {e}", show_traceback=True)
        input("\nPress Enter to exit...")
