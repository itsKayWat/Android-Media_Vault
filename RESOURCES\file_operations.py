import os
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