#!/usr/bin/env python3
"""
Create test analysis for dashboard verification
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dcs_mission_analyzer import DCSMissionAnalyzer
from datetime import datetime
import json

def main():
    print("Creating test analysis with debrief-4.log...")
    
    # Use debrief-4.log for testing
    debrief_file = "debrief-4.log"
    
    if not os.path.exists(debrief_file):
        print(f"Error: {debrief_file} not found!")
        return
    
    # Create analyzer and process the file
    analyzer = DCSMissionAnalyzer(debrief_file)
    
    print(f"Processing {debrief_file}...")
    analyzer.analyze()
    
    # Debug output
    print(f"\nDEBUG: Human controlled units: {analyzer.human_controlled_units}")
    print(f"DEBUG: Unit to pilot mapping: {analyzer.unit_to_pilot}")
    print(f"DEBUG: Unit to group mapping: {analyzer.unit_to_group}")
    
    print("\nMission Summary:")
    analyzer.print_mission_summary()
    
    print("\nPilot Statistics:")
    analyzer.print_pilot_statistics()
    
    # Export to JSON for web interface
    print(f"\nExporting analysis...")
    analyzer.export_to_json("mission_stats_4.json")
    
    print(f"Analysis complete!")
    print(f"Found {len(analyzer.pilot_stats)} pilots:")
    for pilot_name, pilot_data in analyzer.pilot_stats.items():
        human_status = "HUMAN" if any(obj_id in analyzer.human_controlled_units for obj_id in analyzer.unit_to_pilot.keys() if analyzer.unit_to_pilot[obj_id] == pilot_name) else "AI"
        print(f"  - {pilot_name} ({pilot_data.aircraft_type}) [{human_status}]")

if __name__ == "__main__":
    main() 