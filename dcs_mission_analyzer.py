#!/usr/bin/env python3
"""
DCS World Mission Statistics Analyzer
Analyzes debrief.log and unit_group_mapping.xml to generate comprehensive per-pilot and per-group statistics.
"""

import re
import xml.etree.ElementTree as ET
import json
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import argparse
from datetime import datetime

@dataclass
class PilotStats:
    """Statistics for a single pilot"""
    name: str
    aircraft_type: str = ""
    coalition: int = 0
    group_id: Optional[int] = None
    group_name: str = ""
    
    # Combat statistics
    shots_fired: int = 0
    hits_scored: int = 0
    kills: int = 0
    deaths: int = 0
    ejections: int = 0
    
    # Weapon usage
    weapons_used: Counter = field(default_factory=Counter)
    weapons_hit_with: Counter = field(default_factory=Counter)
    weapons_kills_with: Counter = field(default_factory=Counter)
    
    # Mission events
    engine_startups: int = 0
    takeoffs: int = 0
    landings: int = 0
    crashes: int = 0
    
    # Time tracking
    first_seen: float = 0.0
    last_seen: float = 0.0
    flight_time: float = 0.0
    time_to_first_shot: Optional[float] = None
    time_to_first_kill: Optional[float] = None
    
    # Advanced combat metrics
    missiles_defeated: int = 0  # Times evaded incoming missiles
    friendly_fire_incidents: int = 0
    targets_engaged: Set[str] = field(default_factory=set)
    killed_by: Optional[str] = None
    kill_streak: int = 0
    max_kill_streak: int = 0
    
    # Efficiency metrics
    shots_per_kill: float = 0.0
    average_engagement_time: float = 0.0
    total_damage_dealt: float = 0.0
    
    def accuracy(self) -> float:
        """Calculate weapon accuracy percentage"""
        return (self.hits_scored / self.shots_fired * 100) if self.shots_fired > 0 else 0.0
    
    def kill_death_ratio(self) -> float:
        """Calculate kill/death ratio"""
        return self.kills / max(self.deaths, 1)
    
    def efficiency_rating(self) -> float:
        """Calculate overall pilot efficiency (0-100)"""
        if self.shots_fired == 0:
            return 0.0
        
        # Factors: accuracy, K/D ratio, shots per kill
        accuracy_score = self.accuracy() * 0.3
        kd_score = min(self.kill_death_ratio() * 20, 30)  # Cap at 30 points
        efficiency_score = 0
        
        if self.kills > 0:
            shots_per_kill = self.shots_fired / self.kills
            efficiency_score = max(0, 40 - (shots_per_kill * 2))  # Lower shots per kill is better
        
        return min(100, accuracy_score + kd_score + efficiency_score)

@dataclass 
class GroupStats:
    """Statistics for a group of units"""
    id: int
    name: str
    category: int = 0
    coalition: int = 0
    
    # Group-level aggregated stats
    total_pilots: int = 0
    total_shots: int = 0
    total_hits: int = 0
    total_kills: int = 0
    total_deaths: int = 0
    
    # Most active pilot
    most_active_pilot: str = ""
    most_kills_pilot: str = ""
    most_accurate_pilot: str = ""
    
    # Group effectiveness
    pilots: List[str] = field(default_factory=list)
    
    # Advanced metrics
    total_friendly_fire: int = 0
    total_missiles_defeated: int = 0
    group_cohesion_score: float = 0.0  # How well the group works together
    average_pilot_efficiency: float = 0.0
    total_flight_hours: float = 0.0
    
    def group_accuracy(self) -> float:
        """Calculate group accuracy percentage"""
        return (self.total_hits / self.total_shots * 100) if self.total_shots > 0 else 0.0
    
    def group_kd_ratio(self) -> float:
        """Calculate group kill/death ratio"""
        return self.total_kills / max(self.total_deaths, 1)
    
    def group_survivability(self) -> float:
        """Calculate group survivability percentage"""
        if self.total_pilots == 0:
            return 0.0
        return ((self.total_pilots - self.total_deaths) / self.total_pilots) * 100

class DCSMissionAnalyzer:
    def __init__(self, debrief_log: str = "debrief.log", mapping_xml: str = "unit_group_mapping.xml"):
        self.debrief_log = debrief_log
        self.mapping_xml = mapping_xml
        
        # Data structures
        self.pilot_stats: Dict[str, PilotStats] = {}
        self.group_stats: Dict[int, GroupStats] = {}
        self.unit_to_group: Dict[int, int] = {}  # unit_id -> group_id
        self.unit_to_pilot: Dict[int, str] = {}  # unit_id -> pilot_name
        self.coalition_names = {1: "Red", 2: "Blue", 0: "Neutral"}
        
        # Mission metadata
        self.mission_time_start: float = 0.0
        self.mission_time_end: float = 0.0
        self.total_events: int = 0
        
    def load_unit_mapping(self):
        """Load unit to group mappings from XML file"""
        try:
            tree = ET.parse(self.mapping_xml)
            root = tree.getroot()
            
            # Load groups
            for group in root.find('groups').findall('group'):
                group_id = int(group.get('id'))
                self.group_stats[group_id] = GroupStats(
                    id=group_id,
                    name=group.get('name'),
                    category=int(group.get('category')),
                    coalition=int(group.get('coalition'))
                )
            
            # Load units and their group mappings
            for unit in root.find('units').findall('unit'):
                unit_id = int(unit.get('id'))
                group_id = int(unit.get('group_id'))
                pilot_name = unit.get('name')
                
                self.unit_to_group[unit_id] = group_id
                self.unit_to_pilot[unit_id] = pilot_name
                
                # Initialize pilot stats
                if pilot_name not in self.pilot_stats:
                    self.pilot_stats[pilot_name] = PilotStats(
                        name=pilot_name,
                        aircraft_type=unit.get('type'),
                        coalition=int(unit.get('coalition')),
                        group_id=group_id,
                        group_name=unit.get('group_name')
                    )
                
                # Add pilot to group
                if group_id in self.group_stats:
                    if pilot_name not in self.group_stats[group_id].pilots:
                        self.group_stats[group_id].pilots.append(pilot_name)
                        self.group_stats[group_id].total_pilots += 1
                        
        except Exception as e:
            print(f"Error loading XML mapping: {e}")
    
    def parse_lua_value(self, line: str) -> tuple:
        """Parse a Lua key-value pair from a line"""
        # Handle string values
        string_match = re.match(r'\s*(\w+)\s*=\s*"([^"]*)",?\s*', line)
        if string_match:
            return string_match.group(1), string_match.group(2)
        
        # Handle numeric values
        numeric_match = re.match(r'\s*(\w+)\s*=\s*([0-9.-]+),?\s*', line)
        if numeric_match:
            key = numeric_match.group(1)
            value = numeric_match.group(2)
            try:
                # Try to convert to int first, then float
                if '.' in value:
                    return key, float(value)
                else:
                    return key, int(value)
            except ValueError:
                return key, value
        
        return None, None
    
    def parse_debrief_log(self):
        """Parse the debrief log file and extract events"""
        try:
            with open(self.debrief_log, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
            
            # Find all event blocks in the events array
            events_match = re.search(r'events\s*=\s*\{(.*?)\}\s*--\s*end\s+of\s+events', content, re.DOTALL)
            if not events_match:
                print("No events array found in debrief log")
                return
            
            events_content = events_match.group(1)
            
            # Split into individual events
            event_blocks = re.findall(r'\[(\d+)\]\s*=\s*\{(.*?)\},?\s*--\s*end\s+of\s+\[\d+\]', events_content, re.DOTALL)
            
            self.total_events = len(event_blocks)
            print(f"Found {self.total_events} events to process")
            
            for event_num, event_content in event_blocks:
                self.process_event(event_content)
                
        except Exception as e:
            print(f"Error parsing debrief log: {e}")
    
    def process_event(self, event_content: str):
        """Process a single event from the debrief log"""
        event_data = {}
        
        # Parse all key-value pairs in the event
        for line in event_content.split('\n'):
            key, value = self.parse_lua_value(line)
            if key:
                event_data[key] = value
        
        if not event_data:
            return
        
        # Track mission time range
        if 't' in event_data:
            time_val = event_data['t']
            if self.mission_time_start == 0.0:
                self.mission_time_start = time_val
            self.mission_time_end = max(self.mission_time_end, time_val)
        
        # Process different event types
        event_type = event_data.get('type', '')
        
        if event_type == 'shot':
            self.process_shot_event(event_data)
        elif event_type == 'hit':
            self.process_hit_event(event_data)
        elif event_type == 'kill':
            self.process_kill_event(event_data)
        elif event_type == 'pilot dead':
            self.process_death_event(event_data)
        elif event_type == 'eject':
            self.process_eject_event(event_data)
        elif event_type == 'engine startup':
            self.process_engine_startup_event(event_data)
        elif event_type == 'takeoff':
            self.process_takeoff_event(event_data)
        elif event_type == 'landing':
            self.process_landing_event(event_data)
        elif event_type == 'crash':
            self.process_crash_event(event_data)
    
    def get_pilot_from_event(self, event_data: dict, role: str = 'initiator') -> Optional[str]:
        """Extract pilot name from event data"""
        pilot_key = f"{role}PilotName"
        if pilot_key in event_data:
            pilot_name = event_data[pilot_key]
            # Sometimes pilot name is the aircraft type, try to map to actual pilot
            if pilot_name and pilot_name not in self.pilot_stats:
                # Look up by object ID if available
                object_key = f"{role}_object_id"
                if object_key in event_data:
                    object_id = event_data[object_key]
                    if object_id in self.unit_to_pilot:
                        return self.unit_to_pilot[object_id]
            return pilot_name
        return None
    
    def ensure_pilot_exists(self, pilot_name: str, event_data: dict):
        """Ensure pilot exists in stats, create if needed"""
        if pilot_name and pilot_name not in self.pilot_stats:
            # Try to get more info from event
            aircraft_type = event_data.get('initiator_unit_type', pilot_name)
            coalition = event_data.get('initiator_coalition', 0)
            
            self.pilot_stats[pilot_name] = PilotStats(
                name=pilot_name,
                aircraft_type=aircraft_type,
                coalition=coalition
            )
    
    def process_shot_event(self, event_data: dict):
        """Process weapon shot event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        
        pilot = self.pilot_stats[pilot_name]
        pilot.shots_fired += 1
        
        weapon = event_data.get('weapon', 'Unknown')
        pilot.weapons_used[weapon] += 1
        
        # Track time to first shot
        if pilot.time_to_first_shot is None and 't' in event_data:
            pilot.time_to_first_shot = event_data['t'] - pilot.first_seen if pilot.first_seen > 0 else 0
        
        # Track targets engaged
        target_name = event_data.get('targetPilotName') or event_data.get('target')
        if target_name:
            pilot.targets_engaged.add(target_name)
        
        # Check for friendly fire
        initiator_coalition = event_data.get('initiator_coalition', 0)
        target_coalition = event_data.get('target_coalition', 0)
        if initiator_coalition == target_coalition and initiator_coalition != 0:
            pilot.friendly_fire_incidents += 1
        
        # Update timing
        if 't' in event_data:
            if pilot.first_seen == 0.0:
                pilot.first_seen = event_data['t']
            pilot.last_seen = event_data['t']
    
    def process_hit_event(self, event_data: dict):
        """Process weapon hit event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        
        pilot = self.pilot_stats[pilot_name]
        pilot.hits_scored += 1
        
        weapon = event_data.get('weapon', 'Unknown')
        pilot.weapons_hit_with[weapon] += 1
    
    def process_kill_event(self, event_data: dict):
        """Process kill event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.kills += 1
        
        # Track weapon kills
        weapon = event_data.get('weapon', 'Unknown')
        pilot.weapons_kills_with[weapon] += 1
        
        # Track time to first kill
        if pilot.time_to_first_kill is None and 't' in event_data and pilot.first_seen > 0:
            pilot.time_to_first_kill = event_data['t'] - pilot.first_seen
        
        # Update kill streak
        pilot.kill_streak += 1
        pilot.max_kill_streak = max(pilot.max_kill_streak, pilot.kill_streak)
        
        # Track who killed whom (for the victim)
        target_name = event_data.get('targetPilotName') or event_data.get('target')
        if target_name and target_name in self.pilot_stats:
            self.pilot_stats[target_name].killed_by = pilot_name
    
    def process_death_event(self, event_data: dict):
        """Process pilot death event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.deaths += 1
        
        # Reset kill streak on death
        pilot.kill_streak = 0
    
    def process_eject_event(self, event_data: dict):
        """Process pilot ejection event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.ejections += 1
    
    def process_engine_startup_event(self, event_data: dict):
        """Process engine startup event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.engine_startups += 1
    
    def process_takeoff_event(self, event_data: dict):
        """Process takeoff event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.takeoffs += 1
    
    def process_landing_event(self, event_data: dict):
        """Process landing event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.landings += 1
    
    def process_crash_event(self, event_data: dict):
        """Process crash event"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        pilot.crashes += 1
    
    def calculate_flight_times(self):
        """Calculate flight times for all pilots"""
        for pilot in self.pilot_stats.values():
            if pilot.last_seen > pilot.first_seen:
                pilot.flight_time = pilot.last_seen - pilot.first_seen
    
    def calculate_advanced_statistics(self):
        """Calculate advanced derived statistics"""
        for pilot in self.pilot_stats.values():
            # Calculate shots per kill
            if pilot.kills > 0:
                pilot.shots_per_kill = pilot.shots_fired / pilot.kills
            
            # Calculate average engagement time (simplified - time active divided by targets engaged)
            if len(pilot.targets_engaged) > 0 and pilot.flight_time > 0:
                pilot.average_engagement_time = pilot.flight_time / len(pilot.targets_engaged)
    
    def aggregate_group_stats(self):
        """Aggregate pilot statistics into group statistics"""
        for pilot in self.pilot_stats.values():
            if pilot.group_id and pilot.group_id in self.group_stats:
                group = self.group_stats[pilot.group_id]
                
                # Aggregate combat stats
                group.total_shots += pilot.shots_fired
                group.total_hits += pilot.hits_scored
                group.total_kills += pilot.kills
                group.total_deaths += pilot.deaths
                group.total_friendly_fire += pilot.friendly_fire_incidents
                group.total_flight_hours += pilot.flight_time / 3600  # Convert to hours
                
                # Track most active pilots
                if not group.most_active_pilot or pilot.shots_fired > self.pilot_stats.get(group.most_active_pilot, PilotStats("")).shots_fired:
                    group.most_active_pilot = pilot.name
                
                if not group.most_kills_pilot or pilot.kills > self.pilot_stats.get(group.most_kills_pilot, PilotStats("")).kills:
                    group.most_kills_pilot = pilot.name
                
                if not group.most_accurate_pilot or (pilot.accuracy() > self.pilot_stats.get(group.most_accurate_pilot, PilotStats("")).accuracy() and pilot.shots_fired >= 3):
                    group.most_accurate_pilot = pilot.name
        
        # Calculate average pilot efficiency for each group
        for group in self.group_stats.values():
            if group.pilots:
                total_efficiency = sum(self.pilot_stats[p].efficiency_rating() for p in group.pilots if p in self.pilot_stats)
                group.average_pilot_efficiency = total_efficiency / len(group.pilots)
    
    def analyze(self):
        """Run the complete analysis"""
        print("Starting DCS Mission Analysis...")
        print("=" * 50)
        
        # Load data
        print("Loading unit mapping...")
        self.load_unit_mapping()
        
        print("Parsing debrief log...")
        self.parse_debrief_log()
        
        print("Calculating derived statistics...")
        self.calculate_flight_times()
        self.calculate_advanced_statistics()
        self.aggregate_group_stats()
        
        print("Analysis complete!")
    
    def print_mission_summary(self):
        """Print overall mission summary"""
        print("\n" + "="*60)
        print("MISSION SUMMARY")
        print("="*60)
        
        mission_duration = self.mission_time_end - self.mission_time_start
        print(f"Mission Duration: {mission_duration:.1f} seconds ({mission_duration/60:.1f} minutes)")
        print(f"Total Events Processed: {self.total_events}")
        print(f"Active Pilots: {len(self.pilot_stats)}")
        print(f"Active Groups: {len(self.group_stats)}")
        
        # Overall combat statistics
        total_shots = sum(p.shots_fired for p in self.pilot_stats.values())
        total_hits = sum(p.hits_scored for p in self.pilot_stats.values())
        total_kills = sum(p.kills for p in self.pilot_stats.values())
        total_deaths = sum(p.deaths for p in self.pilot_stats.values())
        
        print(f"\nOverall Combat Statistics:")
        print(f"  Total Shots Fired: {total_shots}")
        print(f"  Total Hits: {total_hits}")
        print(f"  Total Kills: {total_kills}")
        print(f"  Total Deaths: {total_deaths}")
        print(f"  Overall Accuracy: {(total_hits/total_shots*100) if total_shots > 0 else 0:.1f}%")
    
    def print_pilot_statistics(self, top_n: int = 10):
        """Print detailed pilot statistics"""
        print(f"\n" + "="*60)
        print("TOP PILOT STATISTICS")
        print("="*60)
        
        if not self.pilot_stats:
            print("No pilot data available.")
            return
        
        # Sort pilots by different criteria
        pilots_by_kills = sorted(self.pilot_stats.values(), key=lambda p: p.kills, reverse=True)
        pilots_by_shots = sorted(self.pilot_stats.values(), key=lambda p: p.shots_fired, reverse=True)
        pilots_by_accuracy = sorted([p for p in self.pilot_stats.values() if p.shots_fired > 0], 
                                  key=lambda p: p.accuracy(), reverse=True)
        
        # Top killers
        print(f"\nTop {top_n} Pilots by Kills:")
        print("-" * 40)
        for i, pilot in enumerate(pilots_by_kills[:top_n], 1):
            coalition_name = self.coalition_names.get(pilot.coalition, "Unknown")
            print(f"{i:2d}. {pilot.name:<20} ({pilot.aircraft_type:<12}) [{coalition_name}]")
            print(f"     Kills: {pilot.kills:3d} | Deaths: {pilot.deaths:3d} | K/D: {pilot.kill_death_ratio():.2f}")
        
        # Most active shooters
        print(f"\nTop {top_n} Pilots by Shots Fired:")
        print("-" * 40)
        for i, pilot in enumerate(pilots_by_shots[:top_n], 1):
            coalition_name = self.coalition_names.get(pilot.coalition, "Unknown")
            print(f"{i:2d}. {pilot.name:<20} ({pilot.aircraft_type:<12}) [{coalition_name}]")
            print(f"     Shots: {pilot.shots_fired:3d} | Hits: {pilot.hits_scored:3d} | Accuracy: {pilot.accuracy():.1f}%")
        
        # Best accuracy (minimum 3 shots)
        accurate_pilots = [p for p in pilots_by_accuracy if p.shots_fired >= 3]
        if accurate_pilots:
            print(f"\nTop {top_n} Pilots by Accuracy (min 3 shots):")
            print("-" * 40)
            for i, pilot in enumerate(accurate_pilots[:top_n], 1):
                coalition_name = self.coalition_names.get(pilot.coalition, "Unknown")
                print(f"{i:2d}. {pilot.name:<20} ({pilot.aircraft_type:<12}) [{coalition_name}]")
                print(f"     Accuracy: {pilot.accuracy():.1f}% ({pilot.hits_scored}/{pilot.shots_fired})")
        
        # Detailed stats for top 5 pilots
        print(f"\nDetailed Statistics for Top 5 Pilots:")
        print("-" * 60)
        for i, pilot in enumerate(pilots_by_kills[:5], 1):
            coalition_name = self.coalition_names.get(pilot.coalition, "Unknown")
            print(f"\n{i}. {pilot.name} ({pilot.aircraft_type}) - {coalition_name} Coalition")
            print(f"   Group: {pilot.group_name} (ID: {pilot.group_id})")
            print(f"   Combat: {pilot.kills} kills, {pilot.deaths} deaths, {pilot.ejections} ejections")
            print(f"   Shooting: {pilot.shots_fired} shots, {pilot.hits_scored} hits ({pilot.accuracy():.1f}% accuracy)")
            
            if pilot.kills > 0:
                print(f"   Efficiency: {pilot.shots_per_kill:.1f} shots/kill, {pilot.efficiency_rating():.1f}/100 rating")
            
            if pilot.max_kill_streak > 0:
                print(f"   Best kill streak: {pilot.max_kill_streak}")
            
            if pilot.time_to_first_kill is not None:
                print(f"   Time to first kill: {pilot.time_to_first_kill:.1f}s")
            
            if len(pilot.targets_engaged) > 0:
                print(f"   Targets engaged: {len(pilot.targets_engaged)}")
            
            print(f"   Flight: {pilot.engine_startups} startups, {pilot.takeoffs} takeoffs, {pilot.landings} landings")
            print(f"   Time: {pilot.flight_time:.1f}s active ({pilot.flight_time/60:.1f} minutes)")
            
            if pilot.weapons_used:
                print(f"   Weapons used: {', '.join([f'{w}({n})' for w, n in pilot.weapons_used.most_common(3)])}")
            
            if pilot.weapons_kills_with:
                print(f"   Lethal weapons: {', '.join([f'{w}({n} kills)' for w, n in pilot.weapons_kills_with.most_common()])}")
    
    def print_group_statistics(self):
        """Print group-level statistics"""
        print(f"\n" + "="*60)
        print("GROUP STATISTICS")
        print("="*60)
        
        if not self.group_stats:
            print("No group data available.")
            return
        
        # Sort groups by effectiveness
        groups_by_kills = sorted(self.group_stats.values(), key=lambda g: g.total_kills, reverse=True)
        
        print(f"Group Performance Summary:")
        print("-" * 60)
        
        for group in groups_by_kills:
            coalition_name = self.coalition_names.get(group.coalition, "Unknown")
            print(f"\nGroup: {group.name} (ID: {group.id}) - {coalition_name} Coalition")
            print(f"  Pilots: {group.total_pilots}")
            print(f"  Combat: {group.total_kills} kills, {group.total_deaths} deaths")
            print(f"  Shooting: {group.total_shots} shots, {group.total_hits} hits ({group.group_accuracy():.1f}% accuracy)")
            print(f"  Group K/D Ratio: {group.group_kd_ratio():.2f}")
            
            if group.most_active_pilot:
                print(f"  Most Active Pilot: {group.most_active_pilot}")
            if group.most_kills_pilot and group.most_kills_pilot != group.most_active_pilot:
                print(f"  Top Killer: {group.most_kills_pilot}")
    
    def print_weapon_analysis(self):
        """Print weapon usage analysis"""
        print(f"\n" + "="*60)
        print("WEAPON ANALYSIS")
        print("="*60)
        
        # Aggregate weapon stats
        all_weapons_used = Counter()
        all_weapons_hit = Counter()
        all_weapons_kills = Counter()
        
        for pilot in self.pilot_stats.values():
            all_weapons_used.update(pilot.weapons_used)
            all_weapons_hit.update(pilot.weapons_hit_with)
            all_weapons_kills.update(pilot.weapons_kills_with)
        
        print("Most Used Weapons:")
        print("-" * 30)
        for weapon, count in all_weapons_used.most_common(10):
            hits = all_weapons_hit.get(weapon, 0)
            kills = all_weapons_kills.get(weapon, 0)
            accuracy = (hits / count * 100) if count > 0 else 0
            lethality = (kills / hits * 100) if hits > 0 else 0
            print(f"  {weapon:<20}: {count:3d} shots, {hits:3d} hits ({accuracy:.1f}% accuracy), {kills:2d} kills ({lethality:.1f}% lethality)")
    
    def print_advanced_combat_analysis(self):
        """Print advanced combat statistics and interesting facts"""
        print(f"\n" + "="*60)
        print("ADVANCED COMBAT ANALYSIS")
        print("="*60)
        
        if not self.pilot_stats:
            print("No pilot data available.")
            return
        
        # Most efficient pilots
        pilots_with_kills = [p for p in self.pilot_stats.values() if p.kills > 0]
        if pilots_with_kills:
            print("\nMost Efficient Killers (shots per kill):")
            print("-" * 40)
            efficient_killers = sorted(pilots_with_kills, key=lambda p: p.shots_per_kill)
            for i, pilot in enumerate(efficient_killers[:5], 1):
                print(f"{i}. {pilot.name:<20}: {pilot.shots_per_kill:.1f} shots per kill")
        
        # Fastest to first kill
        pilots_with_first_kill = [p for p in self.pilot_stats.values() if p.time_to_first_kill is not None]
        if pilots_with_first_kill:
            print("\nFastest Time to First Kill:")
            print("-" * 40)
            fastest_killers = sorted(pilots_with_first_kill, key=lambda p: p.time_to_first_kill)
            for i, pilot in enumerate(fastest_killers[:5], 1):
                print(f"{i}. {pilot.name:<20}: {pilot.time_to_first_kill:.1f} seconds")
        
        # Best kill streaks
        pilots_with_streaks = [p for p in self.pilot_stats.values() if p.max_kill_streak > 0]
        if pilots_with_streaks:
            print("\nBest Kill Streaks:")
            print("-" * 40)
            streak_leaders = sorted(pilots_with_streaks, key=lambda p: p.max_kill_streak, reverse=True)
            for i, pilot in enumerate(streak_leaders[:5], 1):
                print(f"{i}. {pilot.name:<20}: {pilot.max_kill_streak} kills in a row")
        
        # Pilot efficiency ratings
        print("\nPilot Efficiency Ratings (0-100):")
        print("-" * 40)
        all_pilots = sorted(self.pilot_stats.values(), key=lambda p: p.efficiency_rating(), reverse=True)
        for i, pilot in enumerate(all_pilots[:10], 1):
            rating = pilot.efficiency_rating()
            print(f"{i:2d}. {pilot.name:<20}: {rating:5.1f} - ", end="")
            if rating >= 80:
                print("★★★★★ Elite")
            elif rating >= 60:
                print("★★★★☆ Excellent")
            elif rating >= 40:
                print("★★★☆☆ Good")
            elif rating >= 20:
                print("★★☆☆☆ Average")
            else:
                print("★☆☆☆☆ Needs Improvement")
        
        # Interesting facts
        print("\nInteresting Facts:")
        print("-" * 40)
        
        # Most engaged pilot
        most_engaged = max(self.pilot_stats.values(), key=lambda p: len(p.targets_engaged), default=None)
        if most_engaged and len(most_engaged.targets_engaged) > 0:
            print(f"• Most targets engaged: {most_engaged.name} ({len(most_engaged.targets_engaged)} different targets)")
        
        # Friendly fire incidents
        ff_incidents = sum(p.friendly_fire_incidents for p in self.pilot_stats.values())
        if ff_incidents > 0:
            print(f"• Total friendly fire incidents: {ff_incidents}")
            worst_ff = max(self.pilot_stats.values(), key=lambda p: p.friendly_fire_incidents)
            if worst_ff.friendly_fire_incidents > 0:
                print(f"  Worst offender: {worst_ff.name} ({worst_ff.friendly_fire_incidents} incidents)")
        
        # Kill/Death matchups
        print("\nNotable Kill/Death Matchups:")
        print("-" * 40)
        for pilot in self.pilot_stats.values():
            if pilot.killed_by:
                print(f"• {pilot.name} was killed by {pilot.killed_by}")
        
        # Group performance comparison
        if len(self.group_stats) > 1:
            print("\nGroup Performance Comparison:")
            print("-" * 40)
            groups_sorted = sorted(self.group_stats.values(), key=lambda g: g.average_pilot_efficiency, reverse=True)
            for group in groups_sorted:
                print(f"• {group.name}: {group.average_pilot_efficiency:.1f} avg efficiency, "
                      f"{group.group_survivability():.1f}% survivability")
    
    def print_engagement_timeline(self):
        """Print a timeline of key combat events"""
        print(f"\n" + "="*60)
        print("COMBAT TIMELINE")
        print("="*60)
        
        # Collect key events with timestamps
        timeline_events = []
        
        for pilot in self.pilot_stats.values():
            if pilot.time_to_first_shot is not None and pilot.first_seen > 0:
                timeline_events.append({
                    'time': pilot.first_seen + pilot.time_to_first_shot,
                    'event': f"{pilot.name} fired first shot",
                    'type': 'first_shot'
                })
            
            if pilot.time_to_first_kill is not None and pilot.first_seen > 0:
                timeline_events.append({
                    'time': pilot.first_seen + pilot.time_to_first_kill,
                    'event': f"{pilot.name} scored first kill",
                    'type': 'first_kill'
                })
        
        # Sort by time
        timeline_events.sort(key=lambda x: x['time'])
        
        # Print timeline
        if timeline_events:
            print("Key Combat Events (in chronological order):")
            print("-" * 50)
            for event in timeline_events[:20]:  # Limit to first 20 events
                print(f"T+{event['time']:6.1f}s: {event['event']}")
        else:
            print("No combat events with timing data available.")
    
    def export_to_json(self, filename: str = "mission_stats.json"):
        """Export all statistics to JSON file"""
        data = {
            'mission_summary': {
                'duration': self.mission_time_end - self.mission_time_start,
                'total_events': self.total_events,
                'active_pilots': len(self.pilot_stats),
                'active_groups': len(self.group_stats)
            },
            'pilots': {},
            'groups': {}
        }
        
        # Export pilot stats
        for pilot_name, pilot in self.pilot_stats.items():
            data['pilots'][pilot_name] = {
                'aircraft_type': pilot.aircraft_type,
                'coalition': pilot.coalition,
                'group_id': pilot.group_id,
                'group_name': pilot.group_name,
                'kills': pilot.kills,
                'deaths': pilot.deaths,
                'shots_fired': pilot.shots_fired,
                'hits_scored': pilot.hits_scored,
                'accuracy': pilot.accuracy(),
                'kd_ratio': pilot.kill_death_ratio(),
                'flight_time': pilot.flight_time,
                'weapons_used': dict(pilot.weapons_used),
                'weapons_kills': dict(pilot.weapons_kills_with),
                'efficiency_rating': pilot.efficiency_rating(),
                'time_to_first_shot': pilot.time_to_first_shot,
                'time_to_first_kill': pilot.time_to_first_kill,
                'max_kill_streak': pilot.max_kill_streak,
                'targets_engaged': list(pilot.targets_engaged),
                'friendly_fire_incidents': pilot.friendly_fire_incidents,
                'killed_by': pilot.killed_by,
                'shots_per_kill': pilot.shots_per_kill,
                'ejections': pilot.ejections
            }
        
        # Export group stats
        for group_id, group in self.group_stats.items():
            data['groups'][str(group_id)] = {
                'name': group.name,
                'coalition': group.coalition,
                'total_pilots': group.total_pilots,
                'total_kills': group.total_kills,
                'total_deaths': group.total_deaths,
                'total_shots': group.total_shots,
                'total_hits': group.total_hits,
                'group_accuracy': group.group_accuracy(),
                'group_kd_ratio': group.group_kd_ratio(),
                'group_survivability': group.group_survivability(),
                'average_pilot_efficiency': group.average_pilot_efficiency,
                'total_flight_hours': group.total_flight_hours,
                'total_friendly_fire': group.total_friendly_fire,
                'most_active_pilot': group.most_active_pilot,
                'most_kills_pilot': group.most_kills_pilot,
                'most_accurate_pilot': group.most_accurate_pilot
            }
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\nStatistics exported to: {filename}")
        except Exception as e:
            print(f"Error exporting to JSON: {e}")

def main():
    """Main function with command line argument handling"""
    parser = argparse.ArgumentParser(description='Analyze DCS World mission statistics')
    parser.add_argument('--debrief', '-d', default='debrief.log',
                       help='Debrief log file path (default: debrief.log)')
    parser.add_argument('--mapping', '-m', default='unit_group_mapping.xml',
                       help='Unit group mapping XML file (default: unit_group_mapping.xml)')
    parser.add_argument('--export', '-e', default='mission_stats.json',
                       help='Export JSON file path (default: mission_stats.json)')
    parser.add_argument('--top', '-t', type=int, default=10,
                       help='Number of top pilots to show (default: 10)')
    parser.add_argument('--json-only', action='store_true',
                       help='Only export JSON, skip console output')
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = DCSMissionAnalyzer(args.debrief, args.mapping)
    
    # Run analysis
    analyzer.analyze()
    
    if not args.json_only:
        # Print all reports
        analyzer.print_mission_summary()
        analyzer.print_pilot_statistics(args.top)
        analyzer.print_group_statistics()
        analyzer.print_weapon_analysis()
        analyzer.print_advanced_combat_analysis()
        analyzer.print_engagement_timeline()
    
    # Export to JSON
    analyzer.export_to_json(args.export)

if __name__ == "__main__":
    main() 