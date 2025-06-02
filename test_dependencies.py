#!/usr/bin/env python3
"""
Test script to check all dependencies for DCS Mission Debrief
"""

def test_dependencies():
    print("Testing DCS Mission Debrief Dependencies...")
    print("=" * 50)
    
    # Test basic Python modules
    required_modules = [
        'os', 'json', 'subprocess', 'tempfile', 'shutil', 'uuid', 
        'hashlib', 're', 'datetime', 'math', 'random'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module} - {e}")
    
    # Test Flask and extensions
    flask_modules = ['flask', 'werkzeug.utils']
    for module in flask_modules:
        try:
            __import__(module)
            print(f"✓ {module}")
        except ImportError as e:
            print(f"✗ {module} - {e}")
    
    # Test Plotly
    try:
        import plotly.graph_objects as go
        import plotly.utils
        from plotly.subplots import make_subplots
        print("✓ plotly (graph_objects, utils, subplots)")
    except ImportError as e:
        print(f"✗ plotly - {e}")
    
    # Test pandas (if used)
    try:
        import pandas as pd
        print("✓ pandas")
    except ImportError as e:
        print(f"✗ pandas - {e}")
    
    print("\n" + "=" * 50)
    
    # Test file access
    print("Testing File System Access...")
    
    # Test directories
    import os
    required_dirs = ['uploads', 'results', 'templates']
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"✓ {dir_name}/ directory exists")
            if os.access(dir_name, os.W_OK):
                print(f"✓ {dir_name}/ is writable")
            else:
                print(f"✗ {dir_name}/ is not writable")
        else:
            print(f"✗ {dir_name}/ directory missing")
    
    # Test core analysis scripts
    analysis_scripts = ['dcs_xml_extractor.py', 'dcs_mission_analyzer.py']
    for script in analysis_scripts:
        if os.path.exists(script):
            print(f"✓ {script} exists")
        else:
            print(f"✗ {script} missing")
    
    print("\n" + "=" * 50)
    
    # Test basic Flask app startup
    print("Testing Flask App Initialization...")
    try:
        from app import app
        print("✓ Flask app imported successfully")
        
        # Test if app is configured
        if app.secret_key:
            print("✓ Flask app has secret key")
        else:
            print("✗ Flask app missing secret key")
            
        # Test route registration
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        required_routes = ['/', '/upload', '/dashboard/<session_id>']
        for route in required_routes:
            if route in routes:
                print(f"✓ Route {route} registered")
            else:
                print(f"✗ Route {route} missing")
                
    except Exception as e:
        print(f"✗ Flask app initialization failed: {e}")
    
    print("\n" + "=" * 50)
    print("Dependency check complete!")

if __name__ == '__main__':
    test_dependencies() 