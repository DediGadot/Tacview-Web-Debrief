#!/usr/bin/env python3
"""
Create test analysis for dashboard verification
"""

from app import extract_mission_metadata, MissionAnalyzer
from datetime import datetime
import json

def create_test_analysis():
    """Create analysis for testing dashboard changes"""
    print("Creating test analysis...")
    
    # Extract metadata and create analysis
    metadata = extract_mission_metadata('debrief-3.log')
    analyzer = MissionAnalyzer(metadata['mission_id'], metadata)
    success, result = analyzer.process_files('dcs-3.log', 'debrief-3.log')
    
    if success:
        # Create visualizations
        print("Creating visualizations...")
        visualizations = analyzer.create_visualizations(result)
        
        # Store session data
        session_data = {
            'mission_data': result,
            'visualizations': visualizations,
            'mission_metadata': metadata,
            'timestamp': datetime.now().isoformat()
        }
        
        session_file = f'{analyzer.session_dir}/session_data.json'
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"✓ Analysis created: {metadata['mission_id']}")
        print(f"Mission: {metadata['mission_name']}")
        print(f"Dashboard URL: http://localhost:5002/dashboard/{metadata['mission_id']}")
        
        # Show pilot kill breakdown
        pilots = result.get('pilots', {})
        print('\nPilot Kill Breakdown:')
        for name, data in pilots.items():
            air_kills = data.get('kills', 0)
            ground_kills = len(data.get('ground_units_killed', []))
            if air_kills > 0 or ground_kills > 0:
                print(f'  {name}: {air_kills} air kills, {ground_kills} ground kills')
        
        return metadata['mission_id']
    else:
        print(f"❌ Analysis failed: {result}")
        return None

if __name__ == '__main__':
    create_test_analysis() 