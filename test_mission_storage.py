#!/usr/bin/env python3
"""
Test script for mission-based storage system
"""

import os
import tempfile
import shutil
from app import extract_mission_metadata, MissionAnalyzer

def test_mission_metadata_extraction():
    """Test mission metadata extraction from debrief-3.log"""
    print("Testing mission metadata extraction...")
    
    metadata = extract_mission_metadata('debrief-3.log')
    
    print(f"Mission Name: {metadata['mission_name']}")
    print(f"Mission File Mark: {metadata['mission_file_mark']}")
    print(f"Mission Time: {metadata['mission_time']} seconds")
    print(f"Mission ID: {metadata['mission_id']}")
    
    # Verify the mission ID is filesystem-safe
    assert '/' not in metadata['mission_id']
    assert '\\' not in metadata['mission_id']
    assert '"' not in metadata['mission_id']
    
    print("✓ Mission metadata extraction successful")
    return metadata

def test_mission_analyzer_creation():
    """Test MissionAnalyzer creation with mission metadata"""
    print("\nTesting MissionAnalyzer creation...")
    
    metadata = extract_mission_metadata('debrief-3.log')
    analyzer = MissionAnalyzer(metadata['mission_id'], metadata)
    
    print(f"Session directory: {analyzer.session_dir}")
    print(f"Mission metadata: {analyzer.mission_metadata}")
    
    # Verify directory was created
    assert os.path.exists(analyzer.session_dir)
    
    print("✓ MissionAnalyzer creation successful")
    return analyzer

def test_duplicate_mission_detection():
    """Test that duplicate missions are detected"""
    print("\nTesting duplicate mission detection...")
    
    metadata = extract_mission_metadata('debrief-3.log')
    mission_id = metadata['mission_id']
    
    # Create first analyzer
    analyzer1 = MissionAnalyzer(mission_id, metadata)
    
    # Create second analyzer with same mission ID
    analyzer2 = MissionAnalyzer(mission_id, metadata)
    
    # Both should point to the same directory
    assert analyzer1.session_dir == analyzer2.session_dir
    
    print("✓ Duplicate mission detection works")

def test_mission_id_uniqueness():
    """Test that different missions get different IDs"""
    print("\nTesting mission ID uniqueness...")
    
    # Create a modified version of debrief-3.log
    with open('debrief-3.log', 'r') as f:
        content = f.read()
    
    # Modify the mission time slightly
    modified_content = content.replace('mission_time	=	1429.994', 'mission_time	=	1430.000')
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as temp_file:
        temp_file.write(modified_content)
        temp_file_path = temp_file.name
    
    try:
        # Extract metadata from both files
        original_metadata = extract_mission_metadata('debrief-3.log')
        modified_metadata = extract_mission_metadata(temp_file_path)
        
        print(f"Original ID: {original_metadata['mission_id']}")
        print(f"Modified ID: {modified_metadata['mission_id']}")
        
        # IDs should be different
        assert original_metadata['mission_id'] != modified_metadata['mission_id']
        
        print("✓ Mission ID uniqueness verified")
        
    finally:
        os.unlink(temp_file_path)

def cleanup_test_directories():
    """Clean up any test directories"""
    print("\nCleaning up test directories...")
    
    results_dir = 'results'
    if os.path.exists(results_dir):
        for item in os.listdir(results_dir):
            item_path = os.path.join(results_dir, item)
            if os.path.isdir(item_path) and 'test-unit-group-script' in item:
                print(f"Removing test directory: {item_path}")
                shutil.rmtree(item_path)
    
    print("✓ Cleanup complete")

def main():
    """Run all tests"""
    print("=" * 60)
    print("MISSION-BASED STORAGE SYSTEM TESTS")
    print("=" * 60)
    
    try:
        # Run tests
        metadata = test_mission_metadata_extraction()
        analyzer = test_mission_analyzer_creation()
        test_duplicate_mission_detection()
        test_mission_id_uniqueness()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        print(f"\nMission-based storage is working correctly.")
        print(f"Mission: {metadata['mission_name']}")
        print(f"ID: {metadata['mission_id']}")
        print(f"Storage directory: {analyzer.session_dir}")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    finally:
        cleanup_test_directories()

if __name__ == '__main__':
    main() 