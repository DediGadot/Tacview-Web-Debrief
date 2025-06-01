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
from typing import Dict, List, Optional, Set, Any
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
    is_player_controlled: bool = False
    
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
    
    # Air-to-ground specific statistics
    ag_shots_fired: int = 0
    ag_hits_scored: int = 0
    ag_weapons_used: Counter = field(default_factory=Counter)
    ag_weapons_hit_with: Counter = field(default_factory=Counter)
    
    # Ground unit kills tracking
    ground_units_killed: List[Dict] = field(default_factory=list)
    
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
    time_to_first_ag_shot: Optional[float] = None
    
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
    
    # Hit tracking to prevent double counting
    _hit_events_seen: Set[str] = field(default_factory=set)
    
    def accuracy(self) -> float:
        """Calculate weapon accuracy percentage"""
        return (self.hits_scored / self.shots_fired * 100) if self.shots_fired > 0 else 0.0
    
    def ag_accuracy(self) -> float:
        """Calculate air-to-ground accuracy percentage"""
        return (self.ag_hits_scored / self.ag_shots_fired * 100) if self.ag_shots_fired > 0 else 0.0
    
    def kill_death_ratio(self) -> float:
        """Calculate kill/death ratio using air kills only"""
        return self.kills / max(self.deaths, 1)
    
    def total_kills(self) -> int:
        """Calculate total kills (air + ground)"""
        return self.kills + len(self.ground_units_killed)
    
    def total_kill_death_ratio(self) -> float:
        """Calculate kill/death ratio using total kills (air + ground)"""
        return self.total_kills() / max(self.deaths, 1)
    
    def efficiency_rating(self) -> float:
        """Calculate overall pilot efficiency (0-100)"""
        if self.shots_fired == 0:
            return 0.0
        
        # Factors: accuracy, K/D ratio (using total kills), shots per kill
        accuracy_score = self.accuracy() * 0.3
        kd_score = min(self.total_kill_death_ratio() * 20, 30)  # Cap at 30 points
        efficiency_score = 0
        
        total_kills = self.total_kills()
        if total_kills > 0:
            shots_per_kill = self.shots_fired / total_kills
            efficiency_score = max(0, 40 - (shots_per_kill * 2))  # Lower shots per kill is better
        
        return min(100, accuracy_score + kd_score + efficiency_score)
    
    @staticmethod
    def is_air_to_ground_weapon(weapon_name: str) -> bool:
        """Determine if a weapon is air-to-ground"""
        weapon = weapon_name.lower()
        
        # Air-to-ground weapons
        ag_weapons = [
            'mk-82', 'mk-84', 'gbu', 'jdam', 'agm', 'hellfire', 'maverick',
            'bomb', 'rocket', 'hydra', 'ffar', 'cbk', 'rbs', 'kab', 'fab',
            'betab', 'ofab', 'kgm', 'grom', 'storm shadow', 'jassm', 'jsow',
            'ter_', 'mer_', 'blu', 'cbu', 'bru', 'tgp', 'targeting pod',
            'pgm', 'walleye', 'skipper', 'shrike', 'harm', 'sidearm'
        ]
        
        return any(ag_weapon in weapon for ag_weapon in ag_weapons)

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
    total_ground_kills: int = 0
    
    # Air-to-ground aggregated stats
    total_ag_shots: int = 0
    total_ag_hits: int = 0
    
    # Most active pilot
    most_active_pilot: str = ""
    most_kills_pilot: str = ""
    most_accurate_pilot: str = ""
    most_ag_active_pilot: str = ""
    
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
    
    def group_ag_accuracy(self) -> float:
        """Calculate group air-to-ground accuracy percentage"""
        return (self.total_ag_hits / self.total_ag_shots * 100) if self.total_ag_shots > 0 else 0.0
    
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
        self.human_controlled_units: Set[int] = set()  # Track human-controlled object IDs
        self.mission_metadata: Dict[str, Any] = {}
        
        # Mission metadata
        self.mission_time_start: float = 0.0
        self.mission_time_end: float = 0.0
        self.total_events: int = 0
        
    def is_ground_unit_type(self, unit_type: str) -> bool:
        """Check if a unit type represents a ground unit (not a pilot)"""
        if not unit_type:
            return False
            
        unit_type_lower = unit_type.lower()
        
        # Comprehensive list of ground unit types in DCS
        ground_unit_keywords = [
            # Tanks
            'm-1', 'abrams', 't-80', 't-72', 't-90', 'leopard', 'challenger', 'leclerc', 
            'merkava', 'zttz96', 'type 99', 'chieftain', 'centurion',
            
            # Infantry Fighting Vehicles / APCs
            'bmp-', 'btr-', 'bradley', 'm-113', 'warrior', 'marder', 'cv90', 'lav-25',
            'aav7', 'mtlb', 'bmd-', 'bmpt',
            
            # Artillery
            'mlrs', 'smerch', 'uragan', 'grad', 'katyusha', 'paladin', 'caesar', 
            'pzh 2000', 'msta', 'nona', 'gvozdika', 'akatsiya', 'giatsint',
            
            # Missiles and Launchers
            'scud', 'tochka', 'iskander', 'elbrus', 'luna', 'frog', 'ss-', 'r-',
            'launcher', 'tei', 'mim-', 'sam', 'missile',
            
            # Air Defense
            'sa-', 's-300', 's-400', 'patriot', 'nasams', 'hawk', 'roland', 'rapier',
            'stinger', 'zu-23', 'vulcan', 'gepard', 'tunguska', 'shilka', 'tor',
            'kub', 'osa', 'buk', 'strela', 'igla', 'chaparral', 'avenger',
            
            # Logistics and Support
            'hemtt', 'ural', 'kamaz', 'maz', 'zil', 'gaz', 'hmmwv', 'humvee',
            'fuel truck', 'ammo truck', 'supply', 'farp', 'invisible farp',
            
            # Infantry
            'soldier', 'infantry', 'paratrooper', 'manpads', 'mortar', 'sniper',
            'rpg', 'at team', 'aa team', 'mg team',
            
            # Static Objects
            'comms tower', 'power plant', 'warehouse', 'hangar', 'bunker', 'shelter',
            'fuel tank', 'ammo depot', 'radar', 'ewr', 'command center',
            
            # Naval (should also be excluded from pilot stats)
            'ship', 'boat', 'carrier', 'cruiser', 'destroyer', 'frigate', 'corvette',
            'submarine', 'lha', 'lhd', 'cvn', 'cv', 'ddg', 'cg', 'ffg',
            'arleigh', 'burke', 'oliver', 'perry', 'ticonderoga', 'nimitz', 'stennis'
        ]
        
        return any(keyword in unit_type_lower for keyword in ground_unit_keywords)
    
    def is_aircraft_unit(self, group_id: int) -> bool:
        """Check if a group represents aircraft units (pilots)"""
        if group_id in self.group_stats:
            category = self.group_stats[group_id].category
            # Category 0: Aircraft, Category 1: Helicopters
            # Category 2: Ground units, Category 3: Ships, Category 4: Static objects
            return category in [0, 1]  # Only aircraft and helicopters are pilots
        return False
    
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
                is_player_controlled = unit.get('is_player_controlled', 'false').lower() == 'true'
                
                self.unit_to_group[unit_id] = group_id
                self.unit_to_pilot[unit_id] = pilot_name
                
                # Only initialize pilot stats for aircraft units (exclude ground units, ships, static objects)
                if self.is_aircraft_unit(group_id):
                    # Initialize pilot stats
                    if pilot_name not in self.pilot_stats:
                        self.pilot_stats[pilot_name] = PilotStats(
                            name=pilot_name,
                            aircraft_type=unit.get('type'),
                            coalition=int(unit.get('coalition')),
                            group_id=group_id,
                            group_name=unit.get('group_name'),
                            is_player_controlled=is_player_controlled
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
        elif event_type == 'under control':
            self.process_under_control_event(event_data)
    
    def get_pilot_from_event(self, event_data: dict, role: str = 'initiator') -> Optional[str]:
        """Extract pilot name from event data with improved human vs AI pilot detection"""
        # Get object ID first to check if it's human-controlled
        object_key = f"{role}_object_id"
        object_id = event_data.get(object_key)
        
        # Check if this is an aircraft unit before proceeding
        if object_id and object_id in self.unit_to_group:
            group_id = self.unit_to_group[object_id]
            if not self.is_aircraft_unit(group_id):
                return None  # Skip ground units, ships, static objects
        
        # Additional check for unit type in event data
        unit_type_key = f"{role}_unit_type"
        if unit_type_key in event_data:
            unit_type = event_data[unit_type_key]
            # Filter out ground unit types
            if self.is_ground_unit_type(unit_type):
                return None  # Skip ground units
        
        # Check if we already have a mapping for this object ID
        if object_id and object_id in self.unit_to_pilot:
            return self.unit_to_pilot[object_id]
        
        # Determine if this is a human-controlled unit
        is_human_controlled = object_id and object_id in self.human_controlled_units
        
        if is_human_controlled:
            # For human pilots, use the pilot name field
            pilot_key = f"{role}PilotName"
            pilot_name = event_data.get(pilot_key)
            
            # Create mapping for future use
            if pilot_name and object_id:
                self.unit_to_pilot[object_id] = pilot_name
            
            return pilot_name
        else:
            # For AI pilots, use the target field (unit name) or create unique name from aircraft type
            if role == 'target':
                # For targets, use the target field (unit name)
                unit_name = event_data.get('target')
                if unit_name:
                    return unit_name
            
            # For AI initiators or when target field is not available, use aircraft type + object ID
            pilot_key = f"{role}PilotName"
            aircraft_type = event_data.get(pilot_key)
            
            if aircraft_type and object_id:
                # Check if this is a generic aircraft type
                if aircraft_type in ['F-16C_50', 'F-15C', 'MiG-23MLD', 'F/A-18C', 'A-10C', 'A-10C_2']:
                    # Create unique name: aircraft_type + object_id
                    unique_name = f"{aircraft_type}_{object_id}"
                    self.unit_to_pilot[object_id] = unique_name
                    return unique_name
                else:
                    # Use the aircraft type as-is if it's not generic
                    self.unit_to_pilot[object_id] = aircraft_type
                    return aircraft_type
            
            return aircraft_type
    
    def ensure_pilot_exists(self, pilot_name: str, event_data: dict):
        """Ensure pilot exists in stats, create if needed with improved data extraction"""
        if pilot_name and pilot_name not in self.pilot_stats:
            # Try to get object ID to check if this is an aircraft unit
            object_id = event_data.get('initiator_object_id')
            if object_id and object_id in self.unit_to_group:
                group_id = self.unit_to_group[object_id]
                # Only create pilot stats for aircraft units
                if not self.is_aircraft_unit(group_id):
                    return  # Skip ground units, ships, static objects
            
            # Try to get more info from event
            aircraft_type = event_data.get('initiator_unit_type', pilot_name)
            coalition = event_data.get('initiator_coalition', 0)
            group_id = None
            group_name = ""
            is_player_controlled = False
            
            # Try to get object ID for better mapping
            if object_id:
                # Check if we have group mapping for this object ID
                if object_id in self.unit_to_group:
                    group_id = self.unit_to_group[object_id]
                    if group_id in self.group_stats:
                        group_name = self.group_stats[group_id].name
                
                # Check if this pilot already exists in our loaded units (from XML)
                # and get the proper aircraft type and coalition
                for existing_pilot in self.pilot_stats.values():
                    if existing_pilot.name == pilot_name:
                        aircraft_type = existing_pilot.aircraft_type
                        coalition = existing_pilot.coalition
                        group_id = existing_pilot.group_id
                        group_name = existing_pilot.group_name
                        is_player_controlled = existing_pilot.is_player_controlled
                        break
            
            # Additional check: filter out obvious ground unit types
            if self.is_ground_unit_type(aircraft_type):
                return  # Skip ground units
            
            # If pilot name contains object ID suffix, extract aircraft type from it
            if '_' in pilot_name and pilot_name.split('_')[0] in ['F-16C_50', 'F-15C', 'MiG-23MLD', 'F/A-18C']:
                aircraft_type = pilot_name.split('_')[0]
            
            self.pilot_stats[pilot_name] = PilotStats(
                name=pilot_name,
                aircraft_type=aircraft_type,
                coalition=coalition,
                group_id=group_id,
                group_name=group_name,
                is_player_controlled=is_player_controlled
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
        
        # Track air-to-ground shots
        if PilotStats.is_air_to_ground_weapon(weapon):
            pilot.ag_shots_fired += 1
            pilot.ag_weapons_used[weapon] += 1
            
            # Track time to first air-to-ground shot
            if pilot.time_to_first_ag_shot is None and 't' in event_data:
                pilot.time_to_first_ag_shot = event_data['t'] - pilot.first_seen if pilot.first_seen > 0 else 0
        
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
        """Process weapon hit event with improved hit tracking"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        
        # Create a hit signature that groups hits by weapon burst rather than individual bullets
        # For gun weapons, group hits within a small time window (0.5 seconds)
        # For missiles, each hit is separate
        weapon = event_data.get('weapon', 'Unknown')
        time_val = event_data.get('t', 0)
        target_id = event_data.get('target_object_id', 'unknown')
        
        # For gun weapons (like PGU-28/B SAPHEI), group hits within 0.5 second window
        if 'PGU' in weapon or 'gun' in weapon.lower() or 'cannon' in weapon.lower():
            # Round time to nearest 0.5 second to group gun bursts
            time_window = round(time_val * 2) / 2  # 0.5 second windows
            hit_signature = f"{weapon}_{target_id}_{time_window}"
        else:
            # For missiles and other weapons, each hit is separate
            hit_signature = f"{time_val}_{weapon}_{target_id}_{event_data.get('initiator_object_id', 'unknown')}"
        
        # Only count this hit if we haven't seen this hit signature before
        if hit_signature not in pilot._hit_events_seen:
            pilot._hit_events_seen.add(hit_signature)
            pilot.hits_scored += 1
            pilot.weapons_hit_with[weapon] += 1
            
            # Track air-to-ground hits
            if PilotStats.is_air_to_ground_weapon(weapon):
                pilot.ag_hits_scored += 1
                pilot.ag_weapons_hit_with[weapon] += 1
    
    def process_kill_event(self, event_data: dict):
        """Process kill event with improved pilot tracking and ground unit kill detection"""
        killer_name = self.get_pilot_from_event(event_data, 'initiator')
        victim_name = self.get_pilot_from_event(event_data, 'target')
        
        if not killer_name:
            return
            
        self.ensure_pilot_exists(killer_name, event_data)
        killer = self.pilot_stats[killer_name]
        
        # Check if this is a ground unit kill
        target_unit_type = event_data.get('target_unit_type', '')
        target_ws_type1 = event_data.get('target_ws_type1', 0)
        
        # Ground units typically have ws_type1 = 2 (ground) vs 1 (air)
        # Also check if the target unit type is a known ground unit
        is_ground_kill = (target_ws_type1 == 2 or 
                         self.is_ground_unit_type(target_unit_type) or
                         (target_unit_type and not victim_name))  # No pilot name usually means ground unit
        
        if is_ground_kill:
            # Track ground unit kill
            ground_kill_data = {
                'unit_type': target_unit_type,
                'weapon': event_data.get('weapon', 'Unknown'),
                'time': event_data.get('t', 0),
                'coalition': event_data.get('target_coalition', 0),
                'target_object_id': event_data.get('target_object_id'),
                'mission_id': event_data.get('targetMissionID', '')
            }
            killer.ground_units_killed.append(ground_kill_data)
            
            # DO NOT count ground kills as regular kills - only track in ground_units_killed
        else:
            # Regular pilot-to-pilot kill - only count these as 'kills'
            killer.kills += 1
        
        # Track weapon kills
        weapon = event_data.get('weapon', 'Unknown')
        killer.weapons_kills_with[weapon] += 1
        
        # Track time to first kill (for any type of kill)
        if killer.time_to_first_kill is None and 't' in event_data and killer.first_seen > 0:
            killer.time_to_first_kill = event_data['t'] - killer.first_seen
        
        # Update kill streak (for any type of kill)
        killer.kill_streak += 1
        killer.max_kill_streak = max(killer.max_kill_streak, killer.kill_streak)
        
        # Track who killed whom (for the victim) - improved victim tracking
        if victim_name and not is_ground_kill:
            # Ensure victim exists in our tracking
            victim_event_data = {
                'initiator_unit_type': event_data.get('target_unit_type', 'Unknown'),
                'initiator_coalition': event_data.get('target_coalition', 0),
                'initiator_object_id': event_data.get('target_object_id')
            }
            self.ensure_pilot_exists(victim_name, victim_event_data)
            
            # Set the killer relationship
            self.pilot_stats[victim_name].killed_by = killer_name
            
            # Also increment victim's death count if not already done by death event
            # (some logs might have kill events without corresponding death events)
            if self.pilot_stats[victim_name].deaths == 0:
                self.pilot_stats[victim_name].deaths += 1
                # Reset victim's kill streak
                self.pilot_stats[victim_name].kill_streak = 0
    
    def process_death_event(self, event_data: dict):
        """Process pilot death event with improved tracking"""
        pilot_name = self.get_pilot_from_event(event_data, 'initiator')
        if not pilot_name:
            return
            
        self.ensure_pilot_exists(pilot_name, event_data)
        pilot = self.pilot_stats[pilot_name]
        
        # Only increment deaths if not already counted from kill event
        if pilot.deaths == 0 or not pilot.killed_by:
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
    
    def process_under_control_event(self, event_data: dict):
        """Process under control event to track human-controlled units"""
        object_id = event_data.get('initiator_object_id')
        pilot_name = event_data.get('initiatorPilotName')
        
        if object_id and pilot_name:
            # Mark this object ID as human-controlled
            self.human_controlled_units.add(object_id)
            # Create mapping from object ID to pilot name
            self.unit_to_pilot[object_id] = pilot_name
    
    def calculate_flight_times(self):
        """Calculate flight times for all pilots"""
        for pilot in self.pilot_stats.values():
            if pilot.last_seen > pilot.first_seen:
                pilot.flight_time = pilot.last_seen - pilot.first_seen
    
    def calculate_advanced_statistics(self):
        """Calculate advanced derived statistics"""
        for pilot in self.pilot_stats.values():
            # Calculate shots per kill using total kills (air + ground)
            total_kills = pilot.total_kills()
            if total_kills > 0:
                pilot.shots_per_kill = pilot.shots_fired / total_kills
            
            # Calculate average engagement time (simplified - time active divided by targets engaged)
            if len(pilot.targets_engaged) > 0 and pilot.flight_time > 0:
                pilot.average_engagement_time = pilot.flight_time / len(pilot.targets_engaged)
    
    def aggregate_group_stats(self):
        """Aggregate pilot statistics into group statistics"""
        for pilot in self.pilot_stats.values():
            if pilot.group_id and pilot.group_id in self.group_stats:
                group = self.group_stats[pilot.group_id]
                
                # Aggregate combat stats (using total kills for group totals)
                group.total_shots += pilot.shots_fired
                group.total_hits += pilot.hits_scored
                group.total_kills += pilot.total_kills()  # Use total kills (air + ground)
                group.total_deaths += pilot.deaths
                group.total_friendly_fire += pilot.friendly_fire_incidents
                group.total_flight_hours += pilot.flight_time / 3600  # Convert to hours
                
                # Aggregate air-to-ground stats
                group.total_ag_shots += pilot.ag_shots_fired
                group.total_ag_hits += pilot.ag_hits_scored
                group.total_ground_kills += len(pilot.ground_units_killed)  # Add ground kills
                
                # Track most active pilots
                if not group.most_active_pilot or pilot.shots_fired > self.pilot_stats.get(group.most_active_pilot, PilotStats("")).shots_fired:
                    group.most_active_pilot = pilot.name
                
                # Track pilot with most total kills (air + ground)
                if not group.most_kills_pilot or pilot.total_kills() > self.pilot_stats.get(group.most_kills_pilot, PilotStats("")).total_kills():
                    group.most_kills_pilot = pilot.name
                
                if not group.most_accurate_pilot or (pilot.accuracy() > self.pilot_stats.get(group.most_accurate_pilot, PilotStats("")).accuracy() and pilot.shots_fired >= 3):
                    group.most_accurate_pilot = pilot.name
                
                # Track most air-to-ground active pilot (by shots + ground kills)
                current_ag_activity = pilot.ag_shots_fired + len(pilot.ground_units_killed)
                if not group.most_ag_active_pilot:
                    group.most_ag_active_pilot = pilot.name
                else:
                    current_best = self.pilot_stats.get(group.most_ag_active_pilot, PilotStats(""))
                    current_best_activity = current_best.ag_shots_fired + len(current_best.ground_units_killed)
                    if current_ag_activity > current_best_activity:
                        group.most_ag_active_pilot = pilot.name
        
        # Calculate average pilot efficiency for each group
        for group in self.group_stats.values():
            if group.pilots:
                total_efficiency = sum(self.pilot_stats[p].efficiency_rating() for p in group.pilots if p in self.pilot_stats)
                group.average_pilot_efficiency = total_efficiency / len(group.pilots)
    
    def cleanup_inactive_pilots(self):
        """Remove pilots that have no activity in the debrief log"""
        inactive_pilots = []
        
        for pilot_name, pilot in self.pilot_stats.items():
            # Check if pilot has any activity
            has_activity = (
                pilot.shots_fired > 0 or
                pilot.hits_scored > 0 or
                pilot.kills > 0 or
                pilot.deaths > 0 or
                pilot.takeoffs > 0 or
                pilot.landings > 0 or
                pilot.crashes > 0 or
                pilot.ejections > 0 or
                pilot.engine_startups > 0 or
                len(pilot.ground_units_killed) > 0 or
                pilot.flight_time > 0
            )
            
            if not has_activity:
                inactive_pilots.append(pilot_name)
        
        # Remove inactive pilots
        for pilot_name in inactive_pilots:
            print(f"Removing inactive pilot: {pilot_name}")
            del self.pilot_stats[pilot_name]
            
            # Also remove from group pilot lists
            for group in self.group_stats.values():
                if pilot_name in group.pilots:
                    group.pilots.remove(pilot_name)
                    group.total_pilots -= 1
    
    def analyze(self):
        """Run the complete analysis"""
        print("Starting DCS Mission Analysis...")
        print("=" * 50)
        
        # Load data
        print("Loading unit mapping...")
        self.load_unit_mapping()
        
        print("Parsing debrief log...")
        self.parse_debrief_log()
        
        print("Cleaning up inactive pilots...")
        self.cleanup_inactive_pilots()
        
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
        total_air_kills = sum(p.kills for p in self.pilot_stats.values())
        total_ground_kills = sum(len(p.ground_units_killed) for p in self.pilot_stats.values())
        total_kills = total_air_kills + total_ground_kills
        total_deaths = sum(p.deaths for p in self.pilot_stats.values())
        
        print(f"\nOverall Combat Statistics:")
        print(f"  Total Shots Fired: {total_shots}")
        print(f"  Total Hits: {total_hits}")
        print(f"  Total Air Kills: {total_air_kills}")
        print(f"  Total Ground Kills: {total_ground_kills}")
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
        pilots_by_kills = sorted(self.pilot_stats.values(), key=lambda p: p.total_kills(), reverse=True)
        pilots_by_shots = sorted(self.pilot_stats.values(), key=lambda p: p.shots_fired, reverse=True)
        pilots_by_accuracy = sorted([p for p in self.pilot_stats.values() if p.shots_fired > 0], 
                                  key=lambda p: p.accuracy(), reverse=True)
        
        # Top killers
        print(f"\nTop {top_n} Pilots by Total Kills:")
        print("-" * 40)
        for i, pilot in enumerate(pilots_by_kills[:top_n], 1):
            coalition_name = self.coalition_names.get(pilot.coalition, "Unknown")
            air_kills = pilot.kills
            ground_kills = len(pilot.ground_units_killed)
            total_kills = pilot.total_kills()
            print(f"{i:2d}. {pilot.name:<20} ({pilot.aircraft_type:<12}) [{coalition_name}]")
            print(f"     Total Kills: {total_kills:3d} ({air_kills}A+{ground_kills}G) | Deaths: {pilot.deaths:3d} | K/D: {pilot.total_kill_death_ratio():.2f}")
        
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
            air_kills = pilot.kills
            ground_kills = len(pilot.ground_units_killed)
            total_kills = pilot.total_kills()
            print(f"\n{i}. {pilot.name} ({pilot.aircraft_type}) - {coalition_name} Coalition")
            print(f"   Group: {pilot.group_name} (ID: {pilot.group_id})")
            print(f"   Combat: {total_kills} total kills ({air_kills} air + {ground_kills} ground), {pilot.deaths} deaths, {pilot.ejections} ejections")
            print(f"   Shooting: {pilot.shots_fired} shots, {pilot.hits_scored} hits ({pilot.accuracy():.1f}% accuracy)")
            
            if total_kills > 0:
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
            
            # Show ground kills details if any
            if ground_kills > 0:
                ground_targets = [gk["unit_type"] for gk in pilot.ground_units_killed]
                print(f"   Ground targets destroyed: {', '.join(ground_targets)}")
    
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
        pilots_with_kills = [p for p in self.pilot_stats.values() if p.total_kills() > 0]
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
                'is_player_controlled': pilot.is_player_controlled,
                'kills': pilot.kills,
                'deaths': pilot.deaths,
                'shots_fired': pilot.shots_fired,
                'hits_scored': pilot.hits_scored,
                'accuracy': pilot.accuracy(),
                'kd_ratio': pilot.kill_death_ratio(),
                'flight_time': pilot.flight_time,
                'weapons_used': dict(pilot.weapons_used),
                'weapons_hit_with': dict(pilot.weapons_hit_with),
                'weapons_kills': dict(pilot.weapons_kills_with),
                'efficiency_rating': pilot.efficiency_rating(),
                'time_to_first_shot': pilot.time_to_first_shot,
                'time_to_first_kill': pilot.time_to_first_kill,
                'max_kill_streak': pilot.max_kill_streak,
                'targets_engaged': list(pilot.targets_engaged),
                'friendly_fire_incidents': pilot.friendly_fire_incidents,
                'killed_by': pilot.killed_by,
                'shots_per_kill': pilot.shots_per_kill,
                'ejections': pilot.ejections,
                # Air-to-ground statistics
                'ag_shots_fired': pilot.ag_shots_fired,
                'ag_hits_scored': pilot.ag_hits_scored,
                'ag_accuracy': pilot.ag_accuracy(),
                'ag_weapons_used': dict(pilot.ag_weapons_used),
                'ag_weapons_hit_with': dict(pilot.ag_weapons_hit_with),
                'time_to_first_ag_shot': pilot.time_to_first_ag_shot,
                # Ground unit kills
                'ground_units_killed': pilot.ground_units_killed
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
                'most_accurate_pilot': group.most_accurate_pilot,
                # Air-to-ground group statistics
                'total_ag_shots': group.total_ag_shots,
                'total_ag_hits': group.total_ag_hits,
                'total_ground_kills': group.total_ground_kills,
                'group_ag_accuracy': group.group_ag_accuracy(),
                'most_ag_active_pilot': group.most_ag_active_pilot
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