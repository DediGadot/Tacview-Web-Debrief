# DCS World Mission Statistics Analyzer

A comprehensive Python script that analyzes DCS World mission data to generate detailed per-pilot and per-group statistics from debrief logs.

## Features

### Per-Pilot Statistics
- **Combat Performance**: Kills, deaths, K/D ratio, ejections
- **Weapon Effectiveness**: Shots fired, hits scored, accuracy percentage
- **Mission Activity**: Engine startups, takeoffs, landings, crashes
- **Flight Time**: Time active in mission
- **Weapon Usage**: Detailed breakdown of weapons used and hit rates

### Per-Group Statistics
- **Group Performance**: Aggregated combat statistics
- **Group Effectiveness**: Combined accuracy and K/D ratios
- **Top Performers**: Most active pilot and top killer per group
- **Coalition Analysis**: Red vs Blue coalition performance

### Analysis Features
- **Mission Summary**: Overall mission statistics and duration
- **Top Performers**: Ranked lists by kills, shots fired, and accuracy
- **Weapon Analysis**: Most used weapons and their effectiveness
- **JSON Export**: Complete statistics export for further analysis

## Requirements

The script uses only Python standard library modules - no external dependencies required!

- Python 3.7+ (for dataclasses support)
- Built-in modules: `re`, `xml.etree.ElementTree`, `json`, `collections`, `dataclasses`, `typing`, `argparse`

## Usage

### Basic Usage

```bash
# Analyze mission with default files
python dcs_mission_analyzer.py

# Specify custom input files
python dcs_mission_analyzer.py --debrief my_mission.log --mapping my_units.xml

# Export only to JSON (no console output)
python dcs_mission_analyzer.py --json-only

# Show top 15 pilots instead of default 10
python dcs_mission_analyzer.py --top 15
```

### Command Line Options

```
usage: dcs_mission_analyzer.py [-h] [--debrief DEBRIEF] [--mapping MAPPING] 
                              [--export EXPORT] [--top TOP] [--json-only]

Analyze DCS World mission statistics

optional arguments:
  -h, --help            show this help message and exit
  --debrief DEBRIEF, -d DEBRIEF
                        Debrief log file path (default: debrief.log)
  --mapping MAPPING, -m MAPPING
                        Unit group mapping XML file (default: unit_group_mapping.xml)
  --export EXPORT, -e EXPORT
                        Export JSON file path (default: mission_stats.json)
  --top TOP, -t TOP     Number of top pilots to show (default: 10)
  --json-only           Only export JSON, skip console output
```

## Input Files

### 1. `debrief.log`
The DCS World debrief log file containing mission events in Lua table format. This file includes:
- Combat events (shots, hits, kills)
- Aircraft events (takeoffs, landings, crashes)
- Pilot actions (engine startup, ejections)
- Timing information

### 2. `unit_group_mapping.xml`
XML file mapping units to groups and coalitions. This can be generated using the existing `dcs_xml_extractor.py` script from your DCS.log file.

Example structure:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<dcs_mapping timestamp="Mission Time 08:00:39" mission_time="28839.501">
<groups>
<group id="1" name="Aerial-1" category="0" coalition="2"/>
</groups>
<units>
<unit id="16777728" name="Aerial-1-1" type="F-16C_50" group_id="1" group_name="Aerial-1" coalition="2"/>
</units>
</dcs_mapping>
```

## Output Examples

### Console Output

```
Starting DCS Mission Analysis...
==================================================
Loading unit mapping...
Parsing debrief log...
Found 42 events to process
Calculating derived statistics...
Analysis complete!

============================================================
MISSION SUMMARY
============================================================
Mission Duration: 36.0 seconds (0.6 minutes)
Total Events Processed: 42
Active Pilots: 3
Active Groups: 2

Overall Combat Statistics:
  Total Shots Fired: 8
  Total Hits: 1
  Total Kills: 0
  Total Deaths: 0
  Overall Accuracy: 12.5%

============================================================
TOP PILOT STATISTICS
============================================================

Top 10 Pilots by Kills:
----------------------------------------
 1. F-16C_50            (F-16C_50    ) [Blue]
     Kills:   0 | Deaths:   0 | K/D: 0.00

Top 10 Pilots by Shots Fired:
----------------------------------------
 1. F-16C_50            (F-16C_50    ) [Blue]
     Shots:   8 | Hits:   1 | Accuracy: 12.5%
```

### JSON Export

The script exports comprehensive statistics to `mission_stats.json`:

```json
{
  "mission_summary": {
    "duration": 36.0,
    "total_events": 42,
    "active_pilots": 3,
    "active_groups": 2
  },
  "pilots": {
    "F-16C_50": {
      "aircraft_type": "F-16C_50",
      "coalition": 2,
      "group_id": 1,
      "group_name": "Aerial-1",
      "kills": 0,
      "deaths": 0,
      "shots_fired": 8,
      "hits_scored": 1,
      "accuracy": 12.5,
      "kd_ratio": 0.0,
      "flight_time": 33.0,
      "weapons_used": {
        "AIM-9X": 6,
        "AIM-120C": 1
      }
    }
  },
  "groups": {
    "1": {
      "name": "Aerial-1",
      "coalition": 2,
      "total_pilots": 1,
      "total_kills": 0,
      "total_deaths": 0,
      "total_shots": 8,
      "total_hits": 1,
      "group_accuracy": 12.5,
      "group_kd_ratio": 0.0,
      "most_active_pilot": "F-16C_50",
      "most_kills_pilot": "F-16C_50"
    }
  }
}
```

## Event Types Analyzed

The script processes these DCS World event types:
- `shot` - Weapon fired
- `hit` - Weapon impact
- `kill` - Unit destroyed
- `pilot death` - Pilot killed
- `eject` - Pilot ejection
- `engine startup` - Engine started
- `takeoff` - Aircraft takeoff
- `landing` - Aircraft landing
- `crash` - Aircraft crash

## Statistics Calculated

### Pilot-Level Metrics
- **Accuracy**: (Hits / Shots) × 100%
- **Kill/Death Ratio**: Kills / max(Deaths, 1)
- **Flight Time**: Last seen - First seen
- **Weapon Preferences**: Most used weapons by pilot

### Group-Level Metrics
- **Group Accuracy**: Total group hits / Total group shots
- **Group K/D Ratio**: Total group kills / Total group deaths
- **Most Active Pilot**: Pilot with most shots fired
- **Top Killer**: Pilot with most kills

## Extending the Script

The script is designed to be easily extensible. You can add new event types by:

1. Adding a new `process_*_event()` method
2. Adding the event type to the `process_event()` method
3. Adding new statistics fields to the `PilotStats` or `GroupStats` dataclasses

## Troubleshooting

### Common Issues

1. **"No events array found in debrief log"**
   - Check that your debrief.log file contains the `events = {` section
   - Ensure the file is in Lua table format

2. **"Error loading XML mapping"**
   - Verify your unit_group_mapping.xml file is valid XML
   - Check that the file contains both `<groups>` and `<units>` sections

3. **Missing pilot statistics**
   - Some events may not have proper pilot identification
   - The script attempts to map aircraft types to pilot names when possible

### File Generation

To generate the required input files:
1. Use the existing `dcs_xml_extractor.py` to create `unit_group_mapping.xml` from your DCS.log
2. Ensure your DCS World mission generates a debrief log with events

## License

This script is provided as-is for DCS World mission analysis. Feel free to modify and extend as needed.
