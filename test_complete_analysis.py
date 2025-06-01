#!/usr/bin/env python3
"""
Test complete analysis pipeline with mission-based storage
"""

from app import extract_mission_metadata, MissionAnalyzer
import os
import json

def test_complete_analysis():
    """Test the complete analysis pipeline"""
    print("Testing complete analysis pipeline with mission-based storage...")
    
    # Extract mission metadata
    metadata = extract_mission_metadata('debrief-3.log')
    print(f"Mission: {metadata['mission_name']}")
    print(f"ID: {metadata['mission_id']}")
    
    # Create analyzer
    analyzer = MissionAnalyzer(metadata['mission_id'], metadata)
    
    # Test processing
    success, result = analyzer.process_files('dcs-3.log', 'debrief-3.log')
    print(f"Processing success: {success}")
    
    if success:
        print(f"Mission summary keys: {list(result.get('mission_summary', {}).keys())}")
        print(f"Total pilots: {len(result.get('pilots', {}))}")
        print(f"Total groups: {len(result.get('groups', {}))}")
        
        # Check if mission metadata was added
        mission_summary = result.get('mission_summary', {})
        print(f"Mission name in summary: {mission_summary.get('mission_name')}")
        print(f"Mission ID in summary: {mission_summary.get('mission_id')}")
        
        # Check if files were created
        session_dir = analyzer.session_dir
        print(f"Session directory: {session_dir}")
        print(f"Directory exists: {os.path.exists(session_dir)}")
        
        mission_stats_file = os.path.join(session_dir, 'mission_stats.json')
        print(f"Mission stats file exists: {os.path.exists(mission_stats_file)}")
        
        if os.path.exists(mission_stats_file):
            with open(mission_stats_file, 'r') as f:
                stats_data = json.load(f)
            print(f"Stats file mission name: {stats_data.get('mission_summary', {}).get('mission_name')}")
        
        return True, analyzer
    else:
        print(f"Error: {result}")
        return False, None

def main():
    """Run the test"""
    print("=" * 60)
    print("COMPLETE ANALYSIS PIPELINE TEST")
    print("=" * 60)
    
    try:
        success, analyzer = test_complete_analysis()
        
        if success:
            print("\n" + "=" * 60)
            print("COMPLETE ANALYSIS TEST PASSED! ✓")
            print("=" * 60)
            print(f"Mission analysis completed successfully.")
            print(f"Results stored in: {analyzer.session_dir}")
        else:
            print("\n❌ ANALYSIS FAILED")
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise

if __name__ == '__main__':
    main() 