#!/usr/bin/env python3
"""
Test script to simulate file upload and identify issues
"""

import requests
import os

# Check if we have any sample log files to test with
def find_log_files():
    log_files = []
    
    # Check common locations for log files
    upload_dir = 'uploads'
    if os.path.exists(upload_dir):
        for file in os.listdir(upload_dir):
            if file.endswith('.log'):
                log_files.append(os.path.join(upload_dir, file))
    
    return log_files

def test_upload():
    url = 'http://localhost:5003/upload'
    
    # Find available log files
    log_files = find_log_files()
    
    if not log_files:
        print("No log files found for testing. Please place some .log files in the uploads directory.")
        return
    
    print(f"Found {len(log_files)} log files for testing:")
    for f in log_files:
        print(f"  - {f}")
    
    # Test with the first available log file as debrief.log
    test_file = log_files[0]
    print(f"\nTesting upload with: {test_file}")
    
    try:
        with open(test_file, 'rb') as f:
            files = {
                'debrief_log': ('debrief.log', f, 'text/plain')
            }
            
            print("Sending upload request...")
            response = requests.post(url, files=files, allow_redirects=False)
            
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 302:
                print(f"Redirect to: {response.headers.get('Location', 'Unknown')}")
            else:
                print(f"Response content: {response.text[:500]}...")
                
    except Exception as e:
        print(f"Error during upload test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_upload() 