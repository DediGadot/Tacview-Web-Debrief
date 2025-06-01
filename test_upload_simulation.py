#!/usr/bin/env python3
"""
Test upload simulation with mission-based storage
"""

from app import extract_mission_metadata, MissionAnalyzer, get_past_analyses
import os
import json
import shutil
from datetime import datetime

def simulate_upload_process():
    """Simulate the complete upload process"""
    print("Simulating upload process with mission-based storage...")
    
    # Step 1: Extract mission metadata (like in upload route)
    metadata = extract_mission_metadata('debrief-3.log')
    mission_id = metadata['mission_id']
    
    print(f"Mission: {metadata['mission_name']}")
    print(f"ID: {mission_id}")
    
    # Step 2: Check if mission already exists
    existing_session_dir = os.path.join('results', mission_id)
    if os.path.exists(existing_session_dir):
        print(f"Mission already exists at: {existing_session_dir}")
        return mission_id
    
    # Step 3: Create analyzer and process files
    analyzer = MissionAnalyzer(mission_id, metadata)
    success, result = analyzer.process_files('dcs-3.log', 'debrief-3.log')
    
    if not success:
        print(f"Processing failed: {result}")
        return None
    
    # Step 4: Create visualizations (simplified)
    print("Creating visualizations...")
    visualizations = analyzer.create_visualizations(result)
    
    # Step 5: Store session data (like in upload route)
    session_data = {
        'mission_data': result,
        'visualizations': visualizations,
        'mission_metadata': metadata,
        'timestamp': datetime.now().isoformat()
    }
    
    session_file = os.path.join(analyzer.session_dir, 'session_data.json')
    with open(session_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"Session data saved to: {session_file}")
    return mission_id

def test_past_analyses():
    """Test the past analyses functionality"""
    print("\nTesting past analyses retrieval...")
    
    analyses = get_past_analyses()
    print(f"Found {len(analyses)} past analyses:")
    
    for analysis in analyses:
        print(f"  - Mission: {analysis['mission_name']}")
        print(f"    ID: {analysis['mission_id']}")
        print(f"    Timestamp: {analysis['timestamp']}")
        print(f"    Duration: {analysis['duration_minutes']} minutes")
        print(f"    Pilots: {analysis['active_pilots']}")
        print(f"    Kills: {analysis['total_kills']}")
        print()

def cleanup_test_data():
    """Clean up test data"""
    print("Cleaning up test data...")
    
    results_dir = 'results'
    if os.path.exists(results_dir):
        for item in os.listdir(results_dir):
            item_path = os.path.join(results_dir, item)
            if os.path.isdir(item_path) and 'test-unit-group-script' in item:
                print(f"Removing: {item_path}")
                shutil.rmtree(item_path)

def main():
    """Run the simulation"""
    print("=" * 60)
    print("UPLOAD SIMULATION TEST")
    print("=" * 60)
    
    try:
        # Clean up any existing test data
        cleanup_test_data()
        
        # Simulate upload
        mission_id = simulate_upload_process()
        
        if mission_id:
            print(f"\n✓ Upload simulation successful!")
            print(f"Mission ID: {mission_id}")
            
            # Test past analyses
            test_past_analyses()
            
            print("\n" + "=" * 60)
            print("UPLOAD SIMULATION TEST PASSED! ✓")
            print("=" * 60)
        else:
            print("\n❌ Upload simulation failed")
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    finally:
        # Clean up
        cleanup_test_data()

if __name__ == '__main__':
    main() 