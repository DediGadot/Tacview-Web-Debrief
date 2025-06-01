#!/usr/bin/env python3
"""
DCS Mission Debrief Web Server
A comprehensive web application for analyzing DCS World missions with interactive visualizations.
"""

import os
import json
import subprocess
import tempfile
import shutil
import uuid
import hashlib
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import plotly.graph_objects as go
import plotly.utils
from plotly.subplots import make_subplots
import pandas as pd

app = Flask(__name__)
app.secret_key = 'dcs_mission_debrief_secret_key_2024'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configuration
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'log'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_mission_metadata(debrief_log_path):
    """Extract mission metadata from debrief log to create unique identifier"""
    try:
        with open(debrief_log_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()
        
        metadata = {}
        
        # Extract mission file path
        mission_path_match = re.search(r'mission_file_path\s*=\s*"([^"]*)"', content)
        if mission_path_match:
            full_path = mission_path_match.group(1)
            # Extract just the mission filename without path and extension
            # Handle both Windows and Unix paths
            mission_filename = os.path.basename(full_path.replace('\\', '/'))
            if mission_filename.endswith('.miz'):
                mission_filename = mission_filename[:-4]  # Remove .miz extension
            # Clean up the filename for use in filesystem
            mission_filename = re.sub(r'[^\w\-_.]', '_', mission_filename)
            metadata['mission_name'] = mission_filename
        else:
            metadata['mission_name'] = 'unknown_mission'
        
        # Extract mission file mark (timestamp)
        file_mark_match = re.search(r'mission_file_mark\s*=\s*(\d+)', content)
        if file_mark_match:
            metadata['mission_file_mark'] = int(file_mark_match.group(1))
        else:
            metadata['mission_file_mark'] = 0
        
        # Extract mission time (duration)
        mission_time_match = re.search(r'mission_time\s*=\s*([0-9.]+)', content)
        if mission_time_match:
            metadata['mission_time'] = float(mission_time_match.group(1))
        else:
            metadata['mission_time'] = 0.0
        
        # Create a unique mission identifier
        # Format: missionname_timestamp_duration
        mission_id = f"{metadata['mission_name']}_{metadata['mission_file_mark']}_{int(metadata['mission_time'])}"
        
        # Add a short hash to ensure uniqueness in case of collisions
        content_hash = hashlib.md5(content[:1000].encode('utf-8')).hexdigest()[:8]
        mission_id = f"{mission_id}_{content_hash}"
        
        metadata['mission_id'] = mission_id
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting mission metadata: {e}")
        # Fallback to timestamp-based ID
        now = datetime.now()
        fallback_id = f"mission_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond:06d}"
        return {
            'mission_id': fallback_id,
            'mission_name': 'unknown_mission',
            'mission_file_mark': 0,
            'mission_time': 0.0
        }

class MissionAnalyzer:
    def __init__(self, mission_id, mission_metadata=None):
        self.mission_id = mission_id
        self.mission_metadata = mission_metadata or {}
        self.session_dir = os.path.join(RESULTS_FOLDER, mission_id)
        os.makedirs(self.session_dir, exist_ok=True)
        
    def process_files(self, dcs_log_path, debrief_log_path):
        """Process the uploaded files through the analysis pipeline"""
        try:
            # Step 1: Extract XML using dcs_xml_extractor.py
            xml_output_path = os.path.join(self.session_dir, 'unit_group_mapping.xml')
            
            result = subprocess.run([
                'python3', 'dcs_xml_extractor.py',
                '--log', dcs_log_path,
                '--output', xml_output_path
            ], capture_output=True, text=True, cwd='.')
            
            if result.returncode != 0:
                return False, f"XML extraction failed: {result.stderr}"
            
            # Step 2: Copy debrief log to session directory
            session_debrief_path = os.path.join(self.session_dir, 'debrief.log')
            shutil.copy2(debrief_log_path, session_debrief_path)
            
            # Step 3: Run mission analyzer
            json_output_path = os.path.join(self.session_dir, 'mission_stats.json')
            
            result = subprocess.run([
                'python3', 'dcs_mission_analyzer.py',
                '--debrief', session_debrief_path,
                '--mapping', xml_output_path,
                '--export', json_output_path,
                '--json-only'
            ], capture_output=True, text=True, cwd='.')
            
            if result.returncode != 0:
                return False, f"Mission analysis failed: {result.stderr}"
            
            # Step 4: Load and enhance the results with mission metadata
            with open(json_output_path, 'r') as f:
                mission_data = json.load(f)
            
            # Add mission metadata to the results
            if 'mission_summary' not in mission_data:
                mission_data['mission_summary'] = {}
            
            mission_data['mission_summary'].update({
                'mission_name': self.mission_metadata.get('mission_name', 'Unknown Mission'),
                'mission_file_mark': self.mission_metadata.get('mission_file_mark', 0),
                'mission_id': self.mission_id,
                'analysis_timestamp': datetime.now().isoformat()
            })
            
            # Save the enhanced mission data
            with open(json_output_path, 'w') as f:
                json.dump(mission_data, f, indent=2)
            
            return True, mission_data
            
        except Exception as e:
            return False, f"Processing error: {str(e)}"
    
    def create_visualizations(self, mission_data):
        """Create all visualizations from mission data"""
        visualizations = {}
        
        # 1. Mission Overview Chart
        visualizations['mission_overview'] = self.create_mission_overview(mission_data)
        
        # 2. Pilot Performance Radar Charts
        visualizations['pilot_performance'] = self.create_pilot_performance_charts(mission_data)
        
        # 3. Weapon Effectiveness Chart
        visualizations['weapon_effectiveness'] = self.create_weapon_effectiveness_chart(mission_data)
        
        # 4. Group Comparison Chart
        visualizations['group_comparison'] = self.create_group_comparison_chart(mission_data)
        
        # 5. Combat Timeline
        visualizations['combat_timeline'] = self.create_combat_timeline(mission_data)
        
        # 6. Kill/Death Network
        visualizations['kill_death_network'] = self.create_kill_death_network(mission_data)
        
        # 7. Efficiency Leaderboard
        visualizations['efficiency_leaderboard'] = self.create_efficiency_leaderboard(mission_data)
        
        # 8. Air-to-Ground Analysis
        visualizations['air_to_ground_analysis'] = self.create_air_to_ground_analysis(mission_data)
        
        # 9. Air-to-Ground per Pilot Dashboard
        visualizations['ag_pilot_dashboard'] = self.create_ag_pilot_dashboard(mission_data)
        
        # 10. Air-to-Ground per Group Dashboard
        visualizations['ag_group_dashboard'] = self.create_ag_group_dashboard(mission_data)
        
        return visualizations
    
    def create_mission_overview(self, data):
        """Create mission overview dashboard"""
        summary = data.get('mission_summary', {})
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Mission Duration', 'Combat Statistics', 'Pilot Count', 'Group Count'),
            specs=[[{"type": "indicator"}, {"type": "bar"}],
                   [{"type": "indicator"}, {"type": "indicator"}]]
        )
        
        # Mission duration indicator
        duration_min = summary.get('duration', 0) / 60
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=duration_min,
            title={'text': "Duration (minutes)"},
            gauge={'axis': {'range': [None, max(60, duration_min * 1.2)]},
                   'bar': {'color': "darkblue"},
                   'steps': [{'range': [0, 30], 'color': "lightgray"},
                            {'range': [30, 60], 'color': "gray"}],
                   'threshold': {'line': {'color': "red", 'width': 4},
                               'thickness': 0.75, 'value': 90}}
        ), row=1, col=1)
        
        # Combat statistics bar chart
        pilots = data.get('pilots', {})
        total_kills = sum(p.get('kills', 0) for p in pilots.values())
        total_shots = sum(p.get('shots_fired', 0) for p in pilots.values())
        
        fig.add_trace(go.Bar(
            x=['Kills', 'Shots'],
            y=[total_kills, total_shots],
            marker_color=['green', 'blue']
        ), row=1, col=2)
        
        # Pilot count indicator
        fig.add_trace(go.Indicator(
            mode="number",
            value=summary.get('active_pilots', 0),
            title={'text': "Active Pilots"}
        ), row=2, col=1)
        
        # Group count indicator
        fig.add_trace(go.Indicator(
            mode="number",
            value=summary.get('active_groups', 0),
            title={'text': "Active Groups"}
        ), row=2, col=2)
        
        fig.update_layout(
            title="Mission Overview Dashboard",
            showlegend=False,
            height=600
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_pilot_performance_charts(self, data):
        """Create radar charts for all pilots, organized by coalition"""
        pilots = data.get('pilots', {})
        
        # Separate pilots by coalition
        red_pilots = []
        blue_pilots = []
        
        for pilot_name, pilot_data in pilots.items():
            # Show all pilots, regardless of activity level
            pilot_info = {
                'name': pilot_name,
                'data': pilot_data,
                'coalition': pilot_data.get('coalition', 0),
                'is_player_controlled': pilot_data.get('is_player_controlled', False)
            }
            
            if pilot_data.get('coalition') == 1:  # Red coalition
                red_pilots.append(pilot_info)
            elif pilot_data.get('coalition') == 2:  # Blue coalition
                blue_pilots.append(pilot_info)
        
        # Sort pilots by efficiency rating within each coalition
        red_pilots.sort(key=lambda x: x['data'].get('efficiency_rating', 0), reverse=True)
        blue_pilots.sort(key=lambda x: x['data'].get('efficiency_rating', 0), reverse=True)
        
        charts = []
        
        # Create charts for Red coalition pilots
        for pilot_info in red_pilots:
            pilot_name = pilot_info['name']
            pilot_data = pilot_info['data']
            
            # Normalize metrics to 0-100 scale
            accuracy = pilot_data.get('accuracy', 0)
            kd_ratio = min(pilot_data.get('kd_ratio', 0) * 20, 100)  # Cap at 100
            efficiency = pilot_data.get('efficiency_rating', 0)
            shots_fired = min(pilot_data.get('shots_fired', 0) * 10, 100)  # Scale shots
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatterpolar(
                r=[accuracy, kd_ratio, efficiency, shots_fired],
                theta=['Accuracy', 'K/D Ratio', 'Efficiency', 'Activity'],
                fill='toself',
                name=pilot_name,
                line_color='red',
                fillcolor='rgba(255, 0, 0, 0.3)'
            ))
            
            # Add player type indicator to title
            player_type = "Human" if pilot_info['is_player_controlled'] else "AI"
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                title=f"{pilot_name} ({pilot_data.get('aircraft_type', 'Unknown')}) - Red [{player_type}]",
                showlegend=True,
                height=400
            )
            
            charts.append({
                'pilot': pilot_name,
                'coalition': 'red',
                'is_player_controlled': pilot_info['is_player_controlled'],
                'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            })
        
        # Create charts for Blue coalition pilots
        for pilot_info in blue_pilots:
            pilot_name = pilot_info['name']
            pilot_data = pilot_info['data']
            
            # Normalize metrics to 0-100 scale
            accuracy = pilot_data.get('accuracy', 0)
            kd_ratio = min(pilot_data.get('kd_ratio', 0) * 20, 100)  # Cap at 100
            efficiency = pilot_data.get('efficiency_rating', 0)
            shots_fired = min(pilot_data.get('shots_fired', 0) * 10, 100)  # Scale shots
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatterpolar(
                r=[accuracy, kd_ratio, efficiency, shots_fired],
                theta=['Accuracy', 'K/D Ratio', 'Efficiency', 'Activity'],
                fill='toself',
                name=pilot_name,
                line_color='blue',
                fillcolor='rgba(0, 0, 255, 0.3)'
            ))
            
            # Add player type indicator to title
            player_type = "Human" if pilot_info['is_player_controlled'] else "AI"
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                title=f"{pilot_name} ({pilot_data.get('aircraft_type', 'Unknown')}) - Blue [{player_type}]",
                showlegend=True,
                height=400
            )
            
            charts.append({
                'pilot': pilot_name,
                'coalition': 'blue',
                'is_player_controlled': pilot_info['is_player_controlled'],
                'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            })
        
        return charts
    
    def create_weapon_effectiveness_chart(self, data):
        """Create comprehensive weapon analysis dashboard with multiple engaging visualizations"""
        pilots = data.get('pilots', {})
        
        # Aggregate comprehensive weapon data
        weapon_stats = {}
        pilot_weapon_preferences = {}
        coalition_weapon_usage = {1: {}, 2: {}}
        
        for pilot_name, pilot_data in pilots.items():
            weapons_used = pilot_data.get('weapons_used', {})
            weapons_kills = pilot_data.get('weapons_kills', {})
            weapons_hits = pilot_data.get('weapons_hit_with', {})
            coalition = pilot_data.get('coalition', 0)
            
            pilot_weapon_preferences[pilot_name] = {
                'coalition': coalition,
                'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                'weapons': weapons_used,
                'kills': weapons_kills,
                'hits': weapons_hits
            }
            
            for weapon, shots in weapons_used.items():
                if weapon not in weapon_stats:
                    weapon_stats[weapon] = {
                        'shots': 0, 'kills': 0, 'hits': 0, 'pilots_used': 0,
                        'red_usage': 0, 'blue_usage': 0, 'aircraft_types': set()
                    }
                
                weapon_stats[weapon]['shots'] += shots
                weapon_stats[weapon]['kills'] += weapons_kills.get(weapon, 0)
                weapon_stats[weapon]['hits'] += weapons_hits.get(weapon, 0)
                weapon_stats[weapon]['pilots_used'] += 1
                weapon_stats[weapon]['aircraft_types'].add(pilot_data.get('aircraft_type', 'Unknown'))
                
                # Coalition usage tracking
                if coalition in [1, 2]:
                    if coalition == 1:
                        weapon_stats[weapon]['red_usage'] += shots
                    else:
                        weapon_stats[weapon]['blue_usage'] += shots
                    
                    if weapon not in coalition_weapon_usage[coalition]:
                        coalition_weapon_usage[coalition][weapon] = 0
                    coalition_weapon_usage[coalition][weapon] += shots
        
        if not weapon_stats:
            fig = go.Figure()
            fig.add_annotation(text="No weapon data available", 
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create comprehensive weapons dashboard
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                'Weapon Effectiveness Matrix', 'Coalition Weapon Preferences',
                'Weapon Performance Radar', 'Lethality vs Usage Analysis',
                'Pilot Weapon Mastery', 'Weapon Platform Analysis'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "bar"}],
                [{"type": "scatterpolar"}, {"type": "scatter"}],
                [{"type": "heatmap"}, {"type": "sunburst"}]
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # 1. Weapon Effectiveness Matrix (Row 1, Col 1)
        weapons = list(weapon_stats.keys())
        effectiveness_data = []
        accuracy_data = []
        lethality_data = []
        usage_data = []
        
        for weapon in weapons:
            stats = weapon_stats[weapon]
            shots = stats['shots']
            hits = stats['hits']
            kills = stats['kills']
            
            # Calculate metrics
            accuracy = (hits / shots * 100) if shots > 0 else 0
            effectiveness = (kills / shots * 100) if shots > 0 else 0
            lethality = (kills / hits * 100) if hits > 0 else 0
            
            effectiveness_data.append(effectiveness)
            accuracy_data.append(accuracy)
            lethality_data.append(lethality)
            usage_data.append(shots)
        
        # Create effectiveness matrix scatter plot
        fig.add_trace(go.Scatter(
            x=accuracy_data,
            y=effectiveness_data,
            mode='markers+text',
            text=weapons,
            textposition="top center",
            marker=dict(
                size=[max(10, min(u/2, 50)) for u in usage_data],  # Size based on usage
                color=lethality_data,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Lethality %", x=0.48),
                line=dict(width=2, color='white'),
                opacity=0.8
            ),
            name="Weapons",
            hovertemplate="<b>%{text}</b><br>" +
                         "Accuracy: %{x:.1f}%<br>" +
                         "Effectiveness: %{y:.1f}%<br>" +
                         "Usage: %{customdata} shots<br>" +
                         "Lethality: %{marker.color:.1f}%<extra></extra>",
            customdata=usage_data
        ), row=1, col=1)
        
        # 2. Coalition Weapon Preferences (Row 1, Col 2)
        red_weapons = []
        blue_weapons = []
        red_usage = []
        blue_usage = []
        
        for weapon in weapons:
            stats = weapon_stats[weapon]
            if stats['red_usage'] > 0:
                red_weapons.append(weapon)
                red_usage.append(stats['red_usage'])
            if stats['blue_usage'] > 0:
                blue_weapons.append(weapon)
                blue_usage.append(stats['blue_usage'])
        
        if red_weapons:
            fig.add_trace(go.Bar(
                x=red_weapons,
                y=red_usage,
                name="Red Coalition",
                marker_color='red',
                opacity=0.7,
                hovertemplate="<b>%{x}</b><br>Red Coalition Usage: %{y} shots<extra></extra>"
            ), row=1, col=2)
        
        if blue_weapons:
            fig.add_trace(go.Bar(
                x=blue_weapons,
                y=blue_usage,
                name="Blue Coalition",
                marker_color='blue',
                opacity=0.7,
                hovertemplate="<b>%{x}</b><br>Blue Coalition Usage: %{y} shots<extra></extra>"
            ), row=1, col=2)
        
        # 3. Weapon Performance Radar (Row 2, Col 1)
        # Select top 5 weapons by usage for radar chart
        top_weapons = sorted(weapons, key=lambda w: weapon_stats[w]['shots'], reverse=True)[:5]
        
        for i, weapon in enumerate(top_weapons):
            stats = weapon_stats[weapon]
            shots = stats['shots']
            hits = stats['hits']
            kills = stats['kills']
            
            # Normalize metrics to 0-100 scale
            accuracy = (hits / shots * 100) if shots > 0 else 0
            effectiveness = (kills / shots * 100) if shots > 0 else 0
            lethality = (kills / hits * 100) if hits > 0 else 0
            usage_score = min(shots * 10, 100)  # Scale usage
            reliability = min(stats['pilots_used'] * 20, 100)  # Based on how many pilots used it
            
            colors = ['red', 'blue', 'green', 'orange', 'purple']
            
            fig.add_trace(go.Scatterpolar(
                r=[accuracy, effectiveness, lethality, usage_score, reliability],
                theta=['Accuracy', 'Effectiveness', 'Lethality', 'Usage', 'Reliability'],
                fill='toself',
                name=weapon,
                line_color=colors[i % len(colors)],
                fillcolor=f'rgba({255 if i%2==0 else 0}, {128 if i%3==0 else 0}, {255 if i%2==1 else 0}, 0.3)',
                hovertemplate="<b>" + weapon + "</b><br>" +
                             "Accuracy: " + f"{accuracy:.1f}%" + "<br>" +
                             "Effectiveness: " + f"{effectiveness:.1f}%" + "<br>" +
                             "Lethality: " + f"{lethality:.1f}%" + "<br>" +
                             "Usage Score: " + f"{usage_score:.1f}" + "<br>" +
                             "Reliability: " + f"{reliability:.1f}" + "<extra></extra>"
            ), row=2, col=1)
        
        # 4. Lethality vs Usage Analysis (Row 2, Col 2)
        weapon_categories = []
        lethality_for_scatter = []  # Separate lethality array for this chart
        
        for weapon in weapons:
            stats = weapon_stats[weapon]
            shots = stats['shots']
            hits = stats['hits']
            kills = stats['kills']
            
            # Calculate lethality correctly
            lethality = (kills / hits * 100) if hits > 0 else 0
            lethality_for_scatter.append(lethality)
            
            # Categorize weapons
            if 'AIM' in weapon or 'missile' in weapon.lower():
                category = 'Air-to-Air Missile'
            elif 'PGU' in weapon or 'gun' in weapon.lower() or 'cannon' in weapon.lower():
                category = 'Gun/Cannon'
            elif 'bomb' in weapon.lower() or 'AGM' in weapon:
                category = 'Air-to-Ground'
            else:
                category = 'Other'
            
            weapon_categories.append(category)
        
        # Create lethality vs usage scatter
        fig.add_trace(go.Scatter(
            x=usage_data,
            y=lethality_for_scatter,  # Use the correctly calculated lethality
            mode='markers+text',
            text=weapons,
            textposition="top center",
            marker=dict(
                size=[max(15, min(e*2, 40)) for e in effectiveness_data],
                color=[{'Air-to-Air Missile': 'blue', 'Gun/Cannon': 'red', 
                       'Air-to-Ground': 'green', 'Other': 'gray'}[cat] for cat in weapon_categories],
                opacity=0.7,
                line=dict(width=2, color='white')
            ),
            name="Weapon Types",
            customdata=[[weapon_stats[w]['hits'], weapon_stats[w]['kills']] for w in weapons],
            hovertemplate="<b>%{text}</b><br>" +
                         "Usage: %{x} shots<br>" +
                         "Lethality: %{y:.1f}%<br>" +
                         "Hits: %{customdata[0]}<br>" +
                         "Kills: %{customdata[1]}<extra></extra>"
        ), row=2, col=2)
        
        # 5. Pilot Weapon Mastery Heatmap (Row 3, Col 1)
        # Create heatmap of pilot vs weapon effectiveness
        active_pilots = [p for p, data in pilot_weapon_preferences.items() 
                        if sum(data['weapons'].values()) > 0][:8]  # Top 8 active pilots
        
        if active_pilots and weapons:
            heatmap_data = []
            pilot_labels = []
            
            for pilot in active_pilots:
                pilot_data = pilot_weapon_preferences[pilot]
                row_data = []
                pilot_labels.append(f"{pilot}<br>({pilot_data['aircraft']})")
                
                for weapon in weapons:
                    pilot_shots = pilot_data['weapons'].get(weapon, 0)
                    pilot_kills = pilot_data['kills'].get(weapon, 0)
                    mastery = (pilot_kills / pilot_shots * 100) if pilot_shots > 0 else 0
                    row_data.append(mastery)
                
                heatmap_data.append(row_data)
            
            fig.add_trace(go.Heatmap(
                z=heatmap_data,
                x=weapons,
                y=pilot_labels,
                colorscale='RdYlBu_r',
                showscale=True,
                colorbar=dict(title="Mastery %", x=1.02),
                hovertemplate="<b>%{y}</b><br>Weapon: %{x}<br>Mastery: %{z:.1f}%<extra></extra>"
            ), row=3, col=1)
        
        # 6. Weapon Platform Analysis (Row 3, Col 2) - Sunburst chart
        # Create hierarchical data for sunburst
        sunburst_data = {
            'ids': [],
            'labels': [],
            'parents': [],
            'values': []
        }
        
        # Add root
        sunburst_data['ids'].append('weapons')
        sunburst_data['labels'].append('All Weapons')
        sunburst_data['parents'].append('')
        sunburst_data['values'].append(sum(weapon_stats[w]['shots'] for w in weapons))
        
        # Add weapon categories
        categories = {}
        for weapon in weapons:
            if 'AIM' in weapon or 'missile' in weapon.lower():
                cat = 'Missiles'
            elif 'PGU' in weapon or 'gun' in weapon.lower():
                cat = 'Guns'
            else:
                cat = 'Other'
            
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += weapon_stats[weapon]['shots']
        
        for cat, usage in categories.items():
            sunburst_data['ids'].append(cat)
            sunburst_data['labels'].append(cat)
            sunburst_data['parents'].append('weapons')
            sunburst_data['values'].append(usage)
        
        # Add individual weapons
        for weapon in weapons:
            if 'AIM' in weapon or 'missile' in weapon.lower():
                parent = 'Missiles'
            elif 'PGU' in weapon or 'gun' in weapon.lower():
                parent = 'Guns'
            else:
                parent = 'Other'
            
            sunburst_data['ids'].append(weapon)
            sunburst_data['labels'].append(weapon)
            sunburst_data['parents'].append(parent)
            sunburst_data['values'].append(weapon_stats[weapon]['shots'])
        
        fig.add_trace(go.Sunburst(
            ids=sunburst_data['ids'],
            labels=sunburst_data['labels'],
            parents=sunburst_data['parents'],
            values=sunburst_data['values'],
            branchvalues="total",
            hovertemplate="<b>%{label}</b><br>Usage: %{value} shots<br>Percentage: %{percentParent}<extra></extra>"
        ), row=3, col=2)
        
        # Update layout
        fig.update_layout(
            title={
                'text': "Comprehensive Weapon Analysis Dashboard - Combat Effectiveness & Usage Patterns",
                'x': 0.5,
                'font': {'size': 18}
            },
            showlegend=True,
            height=1200,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update polar chart
        fig.update_polars(
            radialaxis=dict(visible=True, range=[0, 100]),
            row=2, col=1
        )
        
        # Update axis labels
        fig.update_xaxes(title_text="Accuracy (%)", row=1, col=1)
        fig.update_yaxes(title_text="Effectiveness (%)", row=1, col=1)
        fig.update_xaxes(title_text="Weapon Type", row=1, col=2)
        fig.update_yaxes(title_text="Shots Fired", row=1, col=2)
        fig.update_xaxes(title_text="Total Usage (Shots)", row=2, col=2)
        fig.update_yaxes(title_text="Lethality (%)", row=2, col=2)
        fig.update_xaxes(title_text="Weapon", row=3, col=1)
        fig.update_yaxes(title_text="Pilot", row=3, col=1)
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_group_comparison_chart(self, data):
        """Create comprehensive group comparison with multiple engaging visualizations"""
        groups = data.get('groups', {})
        pilots = data.get('pilots', {})
        
        if not groups:
            fig = go.Figure()
            fig.add_annotation(text="No group data available", 
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Separate groups by coalition
        red_groups = []
        blue_groups = []
        
        for group_id, group_data in groups.items():
            group_info = {
                'id': group_id,
                'name': group_data.get('name', 'Unknown'),
                'data': group_data,
                'coalition': group_data.get('coalition', 0)
            }
            
            if group_data.get('coalition') == 1:  # Red coalition
                red_groups.append(group_info)
            elif group_data.get('coalition') == 2:  # Blue coalition
                blue_groups.append(group_info)
        
        # Create comprehensive comparison dashboard
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                'Formation Effectiveness Radar', 'Coalition Force Strength',
                'Combat Performance Matrix', 'Pilot Quality Distribution', 
                'Tactical Efficiency Comparison', 'Formation Survivability'
            ),
            specs=[
                [{"type": "scatterpolar"}, {"type": "bar"}],
                [{"type": "scatter"}, {"type": "histogram"}],
                [{"type": "bar"}, {"type": "indicator"}]
            ],
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # 1. Formation Effectiveness Radar Chart (Row 1, Col 1)
        for group_info in red_groups + blue_groups:
            group_data = group_info['data']
            group_name = group_info['name']
            coalition = group_info['coalition']
            
            # Normalize metrics for radar chart (0-100 scale)
            accuracy = group_data.get('group_accuracy', 0)
            survivability = group_data.get('group_survivability', 0)
            efficiency = group_data.get('average_pilot_efficiency', 0)
            activity = min(group_data.get('total_shots', 0) * 5, 100)  # Scale activity
            lethality = min(group_data.get('total_kills', 0) * 25, 100)  # Scale kills
            
            color = 'red' if coalition == 1 else 'blue'
            
            fig.add_trace(go.Scatterpolar(
                r=[accuracy, survivability, efficiency, activity, lethality],
                theta=['Accuracy', 'Survivability', 'Efficiency', 'Activity', 'Lethality'],
                fill='toself',
                name=f"{group_name} ({['Neutral', 'Red', 'Blue'][coalition]})",
                line_color=color,
                fillcolor=f'rgba({255 if coalition == 1 else 0}, 0, {255 if coalition == 2 else 0}, 0.3)'
            ), row=1, col=1)
        
        # 2. Coalition Force Strength (Row 1, Col 2)
        coalition_names = []
        coalition_pilots = []
        coalition_kills = []
        coalition_colors = []
        
        red_total_pilots = sum(g['data'].get('total_pilots', 0) for g in red_groups)
        blue_total_pilots = sum(g['data'].get('total_pilots', 0) for g in blue_groups)
        red_total_kills = sum(g['data'].get('total_kills', 0) for g in red_groups)
        blue_total_kills = sum(g['data'].get('total_kills', 0) for g in blue_groups)
        
        if red_total_pilots > 0:
            coalition_names.append('Red Coalition')
            coalition_pilots.append(red_total_pilots)
            coalition_kills.append(red_total_kills)
            coalition_colors.append('red')
        
        if blue_total_pilots > 0:
            coalition_names.append('Blue Coalition')
            coalition_pilots.append(blue_total_pilots)
            coalition_kills.append(blue_total_kills)
            coalition_colors.append('blue')
        
        fig.add_trace(go.Bar(
            x=coalition_names,
            y=coalition_pilots,
            name="Total Pilots",
            marker_color=coalition_colors,
            text=[f"{p} pilots<br>{k} kills" for p, k in zip(coalition_pilots, coalition_kills)],
            textposition="inside"
        ), row=1, col=2)
        
        # 3. Combat Performance Matrix (Row 2, Col 1)
        group_names = []
        group_accuracy = []
        group_kills = []
        group_colors = []
        group_sizes = []
        
        for group_info in red_groups + blue_groups:
            group_data = group_info['data']
            group_names.append(group_info['name'])
            group_accuracy.append(group_data.get('group_accuracy', 0))
            group_kills.append(group_data.get('total_kills', 0))
            group_colors.append('red' if group_info['coalition'] == 1 else 'blue')
            group_sizes.append(max(group_data.get('total_pilots', 1) * 10, 20))  # Size based on pilot count
        
        fig.add_trace(go.Scatter(
            x=group_accuracy,
            y=group_kills,
            mode='markers+text',
            text=group_names,
            textposition="top center",
            marker=dict(
                size=group_sizes,
                color=group_colors,
                opacity=0.7,
                line=dict(width=2, color='white')
            ),
            name="Groups",
            hovertemplate="<b>%{text}</b><br>Accuracy: %{x:.1f}%<br>Kills: %{y}<extra></extra>"
        ), row=2, col=1)
        
        # 4. Pilot Quality Distribution (Row 2, Col 2)
        all_pilot_efficiencies = []
        pilot_coalitions = []
        
        for pilot_name, pilot_data in pilots.items():
            efficiency = pilot_data.get('efficiency_rating', 0)
            coalition = pilot_data.get('coalition', 0)
            if efficiency > 0:  # Only include active pilots
                all_pilot_efficiencies.append(efficiency)
                pilot_coalitions.append(coalition)
        
        # Create histogram for each coalition
        red_efficiencies = [e for e, c in zip(all_pilot_efficiencies, pilot_coalitions) if c == 1]
        blue_efficiencies = [e for e, c in zip(all_pilot_efficiencies, pilot_coalitions) if c == 2]
        
        if red_efficiencies:
            fig.add_trace(go.Histogram(
                x=red_efficiencies,
                name="Red Pilots",
                marker_color='red',
                opacity=0.7,
                nbinsx=10
            ), row=2, col=2)
        
        if blue_efficiencies:
            fig.add_trace(go.Histogram(
                x=blue_efficiencies,
                name="Blue Pilots",
                marker_color='blue',
                opacity=0.7,
                nbinsx=10
            ), row=2, col=2)
        
        # 5. Tactical Efficiency Comparison (Row 3, Col 1)
        efficiency_names = []
        efficiency_values = []
        efficiency_colors = []
        
        for group_info in sorted(red_groups + blue_groups, 
                               key=lambda x: x['data'].get('average_pilot_efficiency', 0), 
                               reverse=True):
            group_data = group_info['data']
            efficiency_names.append(group_info['name'])
            efficiency_values.append(group_data.get('average_pilot_efficiency', 0))
            efficiency_colors.append('red' if group_info['coalition'] == 1 else 'blue')
        
        fig.add_trace(go.Bar(
            y=efficiency_names,
            x=efficiency_values,
            orientation='h',
            marker_color=efficiency_colors,
            text=[f"{v:.1f}" for v in efficiency_values],
            textposition="inside",
            name="Formation Efficiency"
        ), row=3, col=1)
        
        # 6. Formation Survivability Indicator (Row 3, Col 2)
        if red_groups and blue_groups:
            red_survivability = sum(g['data'].get('group_survivability', 0) for g in red_groups) / len(red_groups)
            blue_survivability = sum(g['data'].get('group_survivability', 0) for g in blue_groups) / len(blue_groups)
            
            # Determine winner
            if red_survivability > blue_survivability:
                winner_text = f"Red Coalition<br>Superior Survivability<br>{red_survivability:.1f}% vs {blue_survivability:.1f}%"
                winner_color = "red"
            elif blue_survivability > red_survivability:
                winner_text = f"Blue Coalition<br>Superior Survivability<br>{blue_survivability:.1f}% vs {red_survivability:.1f}%"
                winner_color = "blue"
            else:
                winner_text = f"Equal Survivability<br>{red_survivability:.1f}%"
                winner_color = "gray"
            
            fig.add_trace(go.Indicator(
                mode="number+delta+gauge",
                value=max(red_survivability, blue_survivability),
                delta={'reference': 50, 'relative': True},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': winner_color},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 75], 'color': "yellow"},
                        {'range': [75, 100], 'color': "lightgreen"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                },
                title={'text': winner_text, 'font': {'size': 14}},
                number={'font': {'size': 20}}
            ), row=3, col=2)
        
        # Update layout
        fig.update_layout(
            title={
                'text': "Formation Analysis Dashboard - Tactical Performance Comparison",
                'x': 0.5,
                'font': {'size': 20}
            },
            showlegend=True,
            height=1200,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update polar chart
        fig.update_polars(
            radialaxis=dict(visible=True, range=[0, 100]),
            row=1, col=1
        )
        
        # Update axis labels
        fig.update_xaxes(title_text="Accuracy (%)", row=2, col=1)
        fig.update_yaxes(title_text="Total Kills", row=2, col=1)
        fig.update_xaxes(title_text="Pilot Efficiency Rating", row=2, col=2)
        fig.update_yaxes(title_text="Number of Pilots", row=2, col=2)
        fig.update_xaxes(title_text="Average Efficiency", row=3, col=1)
        fig.update_yaxes(title_text="Formation", row=3, col=1)
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_combat_timeline(self, data):
        """Create comprehensive combat timeline with multiple event tracks"""
        pilots = data.get('pilots', {})
        
        # We need to reconstruct events from the available data
        # Since we don't have direct access to all events, we'll create a timeline
        # based on the data we have and simulate a comprehensive view
        
        events = []
        
        # Add mission start
        events.append({
            'time': 0,
            'event_type': 'Mission Start',
            'pilot': 'SYSTEM',
            'aircraft': '',
            'coalition': 0,
            'details': 'Mission begins',
            'track': 'System',
            'priority': 1,
            'color': 'green'
        })
        
        # Process pilot data to extract timeline events
        for pilot_name, pilot_data in pilots.items():
            coalition = pilot_data.get('coalition', 0)
            aircraft = pilot_data.get('aircraft_type', 'Unknown')
            coalition_color = 'red' if coalition == 1 else 'blue' if coalition == 2 else 'gray'
            
            # Engine startup / Mission entry (estimated)
            if pilot_data.get('flight_time', 0) > 0:
                events.append({
                    'time': max(0, pilot_data.get('time_to_first_shot', 60) - 30),  # Estimate 30s before first shot
                    'event_type': 'Engine Startup',
                    'pilot': pilot_name,
                    'aircraft': aircraft,
                    'coalition': coalition,
                    'details': f'{pilot_name} starts engines',
                    'track': 'Flight Operations',
                    'priority': 2,
                    'color': coalition_color
                })
            
            # First shot events
            if pilot_data.get('time_to_first_shot') is not None:
                events.append({
                    'time': pilot_data.get('time_to_first_shot', 0),
                    'event_type': 'First Shot',
                    'pilot': pilot_name,
                    'aircraft': aircraft,
                    'coalition': coalition,
                    'details': f'{pilot_name} fires first weapon',
                    'track': 'Combat Actions',
                    'priority': 3,
                    'color': coalition_color
                })
            
            # First kill events
            if pilot_data.get('time_to_first_kill') is not None:
                events.append({
                    'time': pilot_data.get('time_to_first_kill', 0),
                    'event_type': 'First Kill',
                    'pilot': pilot_name,
                    'aircraft': aircraft,
                    'coalition': coalition,
                    'details': f'{pilot_name} scores first kill',
                    'track': 'Combat Results',
                    'priority': 4,
                    'color': coalition_color
                })
            
            # Death events
            if pilot_data.get('deaths', 0) > 0:
                # Estimate death time based on other events or flight time
                death_time = pilot_data.get('flight_time', 300)  # Default to end of flight
                if pilot_data.get('killed_by'):
                    # If we know who killed them, try to estimate when
                    killer_data = pilots.get(pilot_data['killed_by'], {})
                    if killer_data.get('time_to_first_kill'):
                        death_time = killer_data['time_to_first_kill']
                
                events.append({
                    'time': death_time,
                    'event_type': 'Pilot Death',
                    'pilot': pilot_name,
                    'aircraft': aircraft,
                    'coalition': coalition,
                    'details': f'{pilot_name} KIA' + (f' by {pilot_data.get("killed_by", "unknown")}' if pilot_data.get('killed_by') else ''),
                    'track': 'Casualties',
                    'priority': 5,
                    'color': 'darkred'
                })
            
            # Ejection events (estimated based on deaths)
            if pilot_data.get('ejections', 0) > 0:
                eject_time = pilot_data.get('flight_time', 300) - 5  # 5 seconds before death/crash
                events.append({
                    'time': max(0, eject_time),
                    'event_type': 'Ejection',
                    'pilot': pilot_name,
                    'aircraft': aircraft,
                    'coalition': coalition,
                    'details': f'{pilot_name} ejects from {aircraft}',
                    'track': 'Flight Operations',
                    'priority': 4,
                    'color': 'orange'
                })
            
            # Add weapon usage events (spread throughout engagement)
            weapons_used = pilot_data.get('weapons_used', {})
            shots_fired = pilot_data.get('shots_fired', 0)
            
            if shots_fired > 0 and pilot_data.get('time_to_first_shot') is not None:
                first_shot_time = pilot_data['time_to_first_shot']
                flight_time = pilot_data.get('flight_time', first_shot_time + 60)
                
                # Distribute weapon usage over time
                for weapon, count in weapons_used.items():
                    if count > 0:
                        # Spread weapon usage over the engagement period
                        for i in range(min(count, 3)):  # Show up to 3 weapon events per type
                            weapon_time = first_shot_time + (i * (flight_time - first_shot_time) / max(count, 1))
                            events.append({
                                'time': weapon_time,
                                'event_type': 'Weapon Fire',
                                'pilot': pilot_name,
                                'aircraft': aircraft,
                                'coalition': coalition,
                                'details': f'{pilot_name} fires {weapon}',
                                'track': 'Weapons',
                                'priority': 2,
                                'color': coalition_color,
                                'weapon': weapon
                            })
        
        # Add mission end
        mission_duration = data.get('mission_summary', {}).get('duration', 600)
        events.append({
            'time': mission_duration,
            'event_type': 'Mission End',
            'pilot': 'SYSTEM',
            'aircraft': '',
            'coalition': 0,
            'details': 'Mission complete',
            'track': 'System',
            'priority': 1,
            'color': 'green'
        })
        
        if not events:
            fig = go.Figure()
            fig.add_annotation(text="No timeline data available", 
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Sort events by time
        events.sort(key=lambda x: x['time'])
        
        # Create comprehensive timeline with multiple tracks
        fig = make_subplots(
            rows=5, cols=1,
            subplot_titles=('System Events', 'Flight Operations', 'Combat Actions', 'Weapons Usage', 'Combat Results & Casualties'),
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.15, 0.2, 0.25, 0.2, 0.2]
        )
        
        # Define track mapping
        track_rows = {
            'System': 1,
            'Flight Operations': 2,
            'Combat Actions': 3,
            'Weapons': 4,
            'Combat Results': 5,
            'Casualties': 5
        }
        
        # Group events by track
        tracks = {}
        for event in events:
            track = event['track']
            if track not in tracks:
                tracks[track] = []
            tracks[track].append(event)
        
        # Create timeline for each track
        for track_name, track_events in tracks.items():
            if track_name not in track_rows:
                continue
                
            row = track_rows[track_name]
            
            # Separate events by coalition for better visualization
            red_events = [e for e in track_events if e['coalition'] == 1]
            blue_events = [e for e in track_events if e['coalition'] == 2]
            system_events = [e for e in track_events if e['coalition'] == 0]
            
            # Plot Red coalition events
            if red_events:
                fig.add_trace(go.Scatter(
                    x=[e['time'] for e in red_events],
                    y=[f"{e['pilot']} ({e['aircraft']})" if e['aircraft'] else e['pilot'] for e in red_events],
                    mode='markers+text',
                    text=[e['event_type'] for e in red_events],
                    textposition="top center",
                    marker=dict(
                        size=12,
                        color='red',
                        symbol=[self._get_event_symbol(e['event_type']) for e in red_events],
                        line=dict(width=2, color='white')
                    ),
                    name="Red Coalition",
                    hovertemplate="<b>%{text}</b><br>Time: %{x:.1f}s<br>%{y}<br><extra></extra>",
                    showlegend=(row == 1)  # Only show legend on first row
                ), row=row, col=1)
            
            # Plot Blue coalition events
            if blue_events:
                fig.add_trace(go.Scatter(
                    x=[e['time'] for e in blue_events],
                    y=[f"{e['pilot']} ({e['aircraft']})" if e['aircraft'] else e['pilot'] for e in blue_events],
                    mode='markers+text',
                    text=[e['event_type'] for e in blue_events],
                    textposition="top center",
                    marker=dict(
                        size=12,
                        color='blue',
                        symbol=[self._get_event_symbol(e['event_type']) for e in blue_events],
                        line=dict(width=2, color='white')
                    ),
                    name="Blue Coalition",
                    hovertemplate="<b>%{text}</b><br>Time: %{x:.1f}s<br>%{y}<br><extra></extra>",
                    showlegend=(row == 1)  # Only show legend on first row
                ), row=row, col=1)
            
            # Plot System events
            if system_events:
                fig.add_trace(go.Scatter(
                    x=[e['time'] for e in system_events],
                    y=[e['pilot'] for e in system_events],
                    mode='markers+text',
                    text=[e['event_type'] for e in system_events],
                    textposition="top center",
                    marker=dict(
                        size=15,
                        color='green',
                        symbol='star',
                        line=dict(width=2, color='white')
                    ),
                    name="System Events",
                    hovertemplate="<b>%{text}</b><br>Time: %{x:.1f}s<br><extra></extra>",
                    showlegend=(row == 1)  # Only show legend on first row
                ), row=row, col=1)
        
        # Add phase indicators
        phases = self._get_mission_phases(events, mission_duration)
        for phase in phases:
            fig.add_vrect(
                x0=phase['start'], x1=phase['end'],
                fillcolor=phase['color'], opacity=0.1,
                layer="below", line_width=0,
                annotation_text=phase['name'],
                annotation_position="top left"
            )
        
        # Update layout
        fig.update_layout(
            title={
                'text': "Comprehensive Combat Timeline - Multi-Track Event Analysis",
                'x': 0.5,
                'font': {'size': 18}
            },
            height=800,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            hovermode='closest'
        )
        
        # Update x-axes
        fig.update_xaxes(title_text="Mission Time (seconds)", row=5, col=1)
        for i in range(1, 6):
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray', row=i, col=1)
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray', row=i, col=1)
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def _get_event_symbol(self, event_type):
        """Get appropriate symbol for event type"""
        symbol_map = {
            'Engine Startup': 'circle',
            'First Shot': 'triangle-up',
            'First Kill': 'star',
            'Pilot Death': 'x',
            'Ejection': 'diamond',
            'Weapon Fire': 'square',
            'Mission Start': 'star',
            'Mission End': 'star'
        }
        return symbol_map.get(event_type, 'circle')
    
    def _get_mission_phases(self, events, duration):
        """Define mission phases based on events"""
        phases = []
        
        # Pre-combat phase (0 to first shot)
        first_shot_time = min([e['time'] for e in events if e['event_type'] == 'First Shot'], default=duration/4)
        if first_shot_time > 0:
            phases.append({
                'name': 'Pre-Combat',
                'start': 0,
                'end': first_shot_time,
                'color': 'blue'
            })
        
        # Combat phase (first shot to last kill/death)
        combat_events = [e for e in events if e['event_type'] in ['First Kill', 'Pilot Death', 'Weapon Fire']]
        if combat_events:
            combat_start = first_shot_time
            combat_end = max([e['time'] for e in combat_events], default=duration*0.8)
            phases.append({
                'name': 'Active Combat',
                'start': combat_start,
                'end': combat_end,
                'color': 'red'
            })
            
            # Post-combat phase
            if combat_end < duration:
                phases.append({
                    'name': 'Post-Combat',
                    'start': combat_end,
                    'end': duration,
                    'color': 'green'
                })
        
        return phases
    
    def create_kill_death_network(self, data):
        """Create comprehensive kill/death relationship network visualization including ground units"""
        pilots = data.get('pilots', {})
        
        # Find kill relationships and build network data
        pilot_to_pilot_relationships = []
        pilot_to_ground_relationships = []
        all_entities = set()  # Both pilots and ground units
        
        # Process pilot-to-pilot kills
        for pilot_name, pilot_data in pilots.items():
            all_entities.add(pilot_name)
            if pilot_data.get('killed_by'):
                killer = pilot_data['killed_by']
                all_entities.add(killer)
                pilot_to_pilot_relationships.append({
                    'killer': killer,
                    'victim': pilot_name,
                    'killer_data': pilots.get(killer, {}),
                    'victim_data': pilot_data,
                    'relationship_type': 'pilot_to_pilot'
                })
        
        # Process pilot-to-ground kills
        for pilot_name, pilot_data in pilots.items():
            ground_kills = pilot_data.get('ground_units_killed', [])
            for ground_kill in ground_kills:
                ground_unit_name = f"{ground_kill['unit_type']}_{int(ground_kill['time'])}"
                all_entities.add(ground_unit_name)
                pilot_to_ground_relationships.append({
                    'killer': pilot_name,
                    'victim': ground_unit_name,
                    'killer_data': pilot_data,
                    'victim_data': ground_kill,
                    'relationship_type': 'pilot_to_ground',
                    'weapon': ground_kill.get('weapon', 'Unknown'),
                    'time': ground_kill.get('time', 0),
                    'victim_coalition': ground_kill.get('coalition', 0)
                })
        
        all_relationships = pilot_to_pilot_relationships + pilot_to_ground_relationships
        
        if not all_relationships:
            # Create informative empty state
            fig = go.Figure()
            fig.add_annotation(
                text="No Kill Relationships Found<br><br>" +
                     "This could mean:<br>" +
                     "• No pilots were shot down by other pilots<br>" +
                     "• No ground units were destroyed by pilots<br>" +
                     "• Deaths were caused by crashes, system failures, or other causes<br>" +
                     "• Kill attribution data is not available in the logs",
                xref="paper", yref="paper",
                x=0.5, y=0.5, 
                showarrow=False,
                font=dict(size=16),
                align="center"
            )
            fig.update_layout(
                title="Kill/Death Network Analysis",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create network layout using a force-directed approach
        import math
        import random
        
        # Separate pilots from ground units for positioning
        pilot_entities = [entity for entity in all_entities if entity in pilots]
        ground_entities = [entity for entity in all_entities if entity not in pilots]
        
        # Position nodes in a circular layout with some randomization
        entity_positions = {}
        
        # Position pilots in the center area
        n_pilots = len(pilot_entities)
        if n_pilots > 0:
            if n_pilots == 1:
                entity_positions[pilot_entities[0]] = (0, 0)
            else:
                for i, pilot in enumerate(pilot_entities):
                    angle = 2 * math.pi * i / n_pilots
                    radius = max(1, n_pilots / 6)  # Smaller radius for pilots
                    x = radius * math.cos(angle) + random.uniform(-0.2, 0.2)
                    y = radius * math.sin(angle) + random.uniform(-0.2, 0.2)
                    entity_positions[pilot] = (x, y)
        
        # Position ground units in an outer ring
        n_ground = len(ground_entities)
        if n_ground > 0:
            outer_radius = max(2, n_pilots / 4 + 1.5)  # Outer ring for ground units
            for i, ground_unit in enumerate(ground_entities):
                angle = 2 * math.pi * i / n_ground
                x = outer_radius * math.cos(angle) + random.uniform(-0.3, 0.3)
                y = outer_radius * math.sin(angle) + random.uniform(-0.3, 0.3)
                entity_positions[ground_unit] = (x, y)
        
        # Create the network visualization
        fig = go.Figure()
        
        # Add edges (kill relationships) first so they appear behind nodes
        pilot_edge_x = []
        pilot_edge_y = []
        ground_edge_x = []
        ground_edge_y = []
        
        for rel in all_relationships:
            killer = rel['killer']
            victim = rel['victim']
            
            if killer in entity_positions and victim in entity_positions:
                x0, y0 = entity_positions[killer]
                x1, y1 = entity_positions[victim]
                
                if rel['relationship_type'] == 'pilot_to_pilot':
                    # Add pilot-to-pilot edge coordinates
                    pilot_edge_x.extend([x0, x1, None])
                    pilot_edge_y.extend([y0, y1, None])
                    
                    # Add arrow annotation for direction
                    fig.add_annotation(
                        x=(x0 + x1) / 2,
                        y=(y0 + y1) / 2,
                        ax=x0, ay=y0,
                        axref='x', ayref='y',
                        xref='x', yref='y',
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.5,
                        arrowwidth=2,
                        arrowcolor='darkred',
                        text="",
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="darkred",
                        borderwidth=1
                    )
                else:  # pilot_to_ground
                    # Add pilot-to-ground edge coordinates
                    ground_edge_x.extend([x0, x1, None])
                    ground_edge_y.extend([y0, y1, None])
                    
                    # Add arrow annotation for ground kills
                    fig.add_annotation(
                        x=(x0 + x1) / 2,
                        y=(y0 + y1) / 2,
                        ax=x0, ay=y0,
                        axref='x', ayref='y',
                        xref='x', yref='y',
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1.2,
                        arrowwidth=1.5,
                        arrowcolor='darkorange',
                        text="",
                        bgcolor="rgba(255,255,255,0.6)",
                        bordercolor="darkorange",
                        borderwidth=1
                    )
        
        # Add pilot-to-pilot edges
        if pilot_edge_x:
            fig.add_trace(go.Scatter(
                x=pilot_edge_x, y=pilot_edge_y,
                mode='lines',
                line=dict(width=3, color='darkred'),
                hoverinfo='none',
                showlegend=True,
                name='Pilot vs Pilot Kills'
            ))
        
        # Add pilot-to-ground edges
        if ground_edge_x:
            fig.add_trace(go.Scatter(
                x=ground_edge_x, y=ground_edge_y,
                mode='lines',
                line=dict(width=2, color='darkorange', dash='dot'),
                hoverinfo='none',
                showlegend=True,
                name='Ground Unit Kills'
            ))
        
        # Separate pilots by coalition and role
        red_pilots = []
        blue_pilots = []
        neutral_pilots = []
        killers = set([r['killer'] for r in all_relationships])
        victims = set([r['victim'] for r in all_relationships])
        
        for pilot in pilot_entities:
            pilot_data = pilots.get(pilot, {})
            coalition = pilot_data.get('coalition', 0)
            x, y = entity_positions[pilot]
            
            # Count different types of kills
            pilot_kills = pilot_data.get('kills', 0)
            ground_kills = len(pilot_data.get('ground_units_killed', []))
            total_kills = pilot_kills + ground_kills
            
            pilot_info = {
                'name': pilot,
                'x': x,
                'y': y,
                'coalition': coalition,
                'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                'pilot_kills': pilot_kills,
                'ground_kills': ground_kills,
                'total_kills': total_kills,
                'deaths': pilot_data.get('deaths', 0),
                'is_killer': pilot in killers,
                'is_victim': pilot in victims,
                'efficiency': pilot_data.get('efficiency_rating', 0)
            }
            
            if coalition == 1:
                red_pilots.append(pilot_info)
            elif coalition == 2:
                blue_pilots.append(pilot_info)
            else:
                neutral_pilots.append(pilot_info)
        
        # Add pilot nodes by coalition
        for coalition_pilots, color, name in [
            (red_pilots, 'red', 'Red Coalition Pilots'),
            (blue_pilots, 'blue', 'Blue Coalition Pilots'),
            (neutral_pilots, 'gray', 'Unknown Coalition Pilots')
        ]:
            if not coalition_pilots:
                continue
                
            # Determine node sizes based on total kills and role
            node_sizes = []
            node_symbols = []
            hover_texts = []
            
            for pilot in coalition_pilots:
                # Base size on total kills, minimum 15, maximum 50
                base_size = 15 + min(pilot['total_kills'] * 4, 35)
                
                # Increase size for killers, decrease for victims
                if pilot['is_killer'] and pilot['is_victim']:
                    size = base_size + 5  # Both killer and victim
                    symbol = 'diamond'
                elif pilot['is_killer']:
                    size = base_size + 8  # Pure killer
                    symbol = 'triangle-up'
                elif pilot['is_victim']:
                    size = base_size - 3  # Pure victim
                    symbol = 'x'
                else:
                    size = base_size  # No direct involvement
                    symbol = 'circle'
                
                node_sizes.append(size)
                node_symbols.append(symbol)
                
                # Create detailed hover text
                role_text = []
                if pilot['is_killer']:
                    role_text.append("Killer")
                if pilot['is_victim']:
                    role_text.append("Victim")
                if not role_text:
                    role_text.append("Observer")
                
                hover_text = (
                    f"<b>{pilot['name']}</b><br>"
                    f"Aircraft: {pilot['aircraft']}<br>"
                    f"Role: {', '.join(role_text)}<br>"
                    f"Pilot Kills: {pilot['pilot_kills']}<br>"
                    f"Ground Kills: {pilot['ground_kills']}<br>"
                    f"Total Kills: {pilot['total_kills']}<br>"
                    f"Deaths: {pilot['deaths']}<br>"
                    f"Efficiency: {pilot['efficiency']:.1f}"
                )
                hover_texts.append(hover_text)
            
            fig.add_trace(go.Scatter(
                x=[p['x'] for p in coalition_pilots],
                y=[p['y'] for p in coalition_pilots],
                mode='markers+text',
                marker=dict(
                    size=node_sizes,
                    color=color,
                    symbol=node_symbols,
                    line=dict(width=2, color='white'),
                    opacity=0.8
                ),
                text=[p['name'] for p in coalition_pilots],
                textposition="bottom center",
                textfont=dict(size=10, color='black'),
                hovertemplate='%{hovertext}<extra></extra>',
                hovertext=hover_texts,
                name=name,
                showlegend=True
            ))
        
        # Add ground units by coalition
        red_ground = []
        blue_ground = []
        neutral_ground = []
        
        for ground_unit in ground_entities:
            x, y = entity_positions[ground_unit]
            
            # Find the ground unit data from relationships
            ground_data = None
            for rel in pilot_to_ground_relationships:
                if rel['victim'] == ground_unit:
                    ground_data = rel['victim_data']
                    break
            
            if ground_data:
                coalition = ground_data.get('coalition', 0)
                unit_type = ground_data.get('unit_type', 'Unknown')
                weapon = ground_data.get('weapon', 'Unknown')
                time = ground_data.get('time', 0)
                
                ground_info = {
                    'name': ground_unit,
                    'x': x,
                    'y': y,
                    'coalition': coalition,
                    'unit_type': unit_type,
                    'weapon': weapon,
                    'time': time
                }
                
                if coalition == 1:
                    red_ground.append(ground_info)
                elif coalition == 2:
                    blue_ground.append(ground_info)
                else:
                    neutral_ground.append(ground_info)
        
        # Add ground unit nodes by coalition
        for coalition_ground, color, name in [
            (red_ground, 'darkred', 'Red Ground Units'),
            (blue_ground, 'darkblue', 'Blue Ground Units'),
            (neutral_ground, 'darkgray', 'Unknown Ground Units')
        ]:
            if not coalition_ground:
                continue
                
            hover_texts = []
            for ground in coalition_ground:
                hover_text = (
                    f"<b>{ground['unit_type']}</b><br>"
                    f"Destroyed by: {ground['weapon']}<br>"
                    f"Time: {ground['time']:.1f}s<br>"
                    f"Coalition: {['Neutral', 'Red', 'Blue'][ground['coalition']]}"
                )
                hover_texts.append(hover_text)
            
            fig.add_trace(go.Scatter(
                x=[g['x'] for g in coalition_ground],
                y=[g['y'] for g in coalition_ground],
                mode='markers+text',
                marker=dict(
                    size=12,
                    color=color,
                    symbol='square',
                    line=dict(width=1, color='white'),
                    opacity=0.7
                ),
                text=[g['unit_type'] for g in coalition_ground],
                textposition="bottom center",
                textfont=dict(size=8, color='black'),
                hovertemplate='%{hovertext}<extra></extra>',
                hovertext=hover_texts,
                name=name,
                showlegend=True
            ))
        
        # Add relationship summary as annotations
        pilot_relationships = len(pilot_to_pilot_relationships)
        ground_relationships = len(pilot_to_ground_relationships)
        total_entities = len(all_entities)
        
        summary_text = f"Network Analysis: {pilot_relationships} pilot kill(s), {ground_relationships} ground kill(s) among {total_entities} entities"
        fig.add_annotation(
            text=summary_text,
            xref="paper", yref="paper",
            x=0.5, y=0.95,
            showarrow=False,
            font=dict(size=14, color='black'),
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="gray",
            borderwidth=1
        )
        
        # Add detailed relationship list
        rel_text = "Kill Relationships:<br>"
        rel_count = 0
        
        # Add pilot-to-pilot relationships
        for rel in pilot_to_pilot_relationships:
            if rel_count >= 8:  # Limit to avoid clutter
                break
            killer_aircraft = rel['killer_data'].get('aircraft_type', 'Unknown')
            victim_aircraft = rel['victim_data'].get('aircraft_type', 'Unknown')
            rel_text += f"• {rel['killer']} ({killer_aircraft}) → {rel['victim']} ({victim_aircraft})<br>"
            rel_count += 1
        
        # Add pilot-to-ground relationships
        for rel in pilot_to_ground_relationships:
            if rel_count >= 8:  # Limit to avoid clutter
                break
            killer_aircraft = rel['killer_data'].get('aircraft_type', 'Unknown')
            victim_type = rel['victim_data'].get('unit_type', 'Unknown')
            weapon = rel.get('weapon', 'Unknown')
            rel_text += f"• {rel['killer']} ({killer_aircraft}) → {victim_type} [{weapon}]<br>"
            rel_count += 1
        
        if len(all_relationships) > 8:
            rel_text += f"... and {len(all_relationships) - 8} more"
        
        fig.add_annotation(
            text=rel_text,
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            font=dict(size=10, color='black'),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="gray",
            borderwidth=1,
            align="left",
            valign="top"
        )
        
        # Update layout
        fig.update_layout(
            title={
                'text': "Kill/Death Network - Combat Relationship Analysis (Pilots & Ground Units)",
                'x': 0.5,
                'font': {'size': 18}
            },
            xaxis=dict(
                visible=False,
                range=[min([pos[0] for pos in entity_positions.values()]) - 1,
                       max([pos[0] for pos in entity_positions.values()]) + 1]
            ),
            yaxis=dict(
                visible=False,
                range=[min([pos[1] for pos in entity_positions.values()]) - 1,
                       max([pos[1] for pos in entity_positions.values()]) + 1],
                scaleanchor="x",
                scaleratio=1
            ),
            height=700,
            plot_bgcolor='rgba(240,240,240,0.3)',
            paper_bgcolor='white',
            hovermode='closest',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_efficiency_leaderboard(self, data):
        """Create efficiency leaderboard with star ratings"""
        pilots = data.get('pilots', {})
        
        # Sort pilots by efficiency rating
        pilot_rankings = sorted(pilots.items(), 
                              key=lambda x: x[1].get('efficiency_rating', 0), 
                              reverse=True)
        
        names = []
        ratings = []
        aircraft = []
        colors = []
        stars = []
        
        for pilot_name, pilot_data in pilot_rankings[:10]:  # Top 10
            names.append(pilot_name)
            rating = pilot_data.get('efficiency_rating', 0)
            ratings.append(rating)
            aircraft.append(pilot_data.get('aircraft_type', 'Unknown'))
            
            # Color based on coalition
            coalition = pilot_data.get('coalition', 0)
            colors.append('red' if coalition == 1 else 'blue')
            
            # Star rating
            if rating >= 80:
                stars.append('★★★★★')
            elif rating >= 60:
                stars.append('★★★★☆')
            elif rating >= 40:
                stars.append('★★★☆☆')
            elif rating >= 20:
                stars.append('★★☆☆☆')
            else:
                stars.append('★☆☆☆☆')
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=names,
            x=ratings,
            orientation='h',
            marker_color=colors,
            text=[f"{rating:.1f} {star}" for rating, star in zip(ratings, stars)],
            textposition="inside"
        ))
        
        fig.update_layout(
            title="Pilot Efficiency Leaderboard",
            xaxis_title="Efficiency Rating (0-100)",
            yaxis_title="Pilot",
            height=max(400, len(names) * 40)
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    def create_air_to_ground_analysis(self, data):
        """Create comprehensive air-to-ground analysis dashboard"""
        pilots = data.get('pilots', {})
        
        # Collect air-to-ground data
        ag_pilots = []
        for pilot_name, pilot_data in pilots.items():
            ag_shots = pilot_data.get('ag_shots_fired', 0)
            ag_hits = pilot_data.get('ag_hits_scored', 0)
            ag_accuracy = pilot_data.get('ag_accuracy', 0)
            ground_kills = len(pilot_data.get('ground_units_killed', []))
            
            if ag_shots > 0 or ground_kills > 0:  # Include pilots with A2G activity or ground kills
                ag_pilots.append({
                    'name': pilot_name,
                    'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                    'coalition': pilot_data.get('coalition', 0),
                    'shots': ag_shots,
                    'hits': ag_hits,
                    'accuracy': ag_accuracy,
                    'ground_kills': ground_kills,
                    'weapons': pilot_data.get('ag_weapons_used', {}),
                    'time_to_first_ag': pilot_data.get('time_to_first_ag_shot', None)
                })
        
        if not ag_pilots:
            # No air-to-ground activity
            fig = go.Figure()
            fig.add_annotation(
                text="No air-to-ground weapon activity detected in this mission",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            fig.update_layout(
                title="Air-to-Ground Analysis",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=400
            )
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create dashboard with multiple subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'A2G Shots vs Accuracy', 'A2G Weapon Usage Distribution',
                'Coalition A2G Performance (Shots, Hits, Kills)', 'A2G Response Time'
            ),
            specs=[[{"type": "scatter"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "bar"}]]
        )
        
        # 1. Shots vs Accuracy scatter plot (with ground kills as marker size)
        red_pilots = [p for p in ag_pilots if p['coalition'] == 1]
        blue_pilots = [p for p in ag_pilots if p['coalition'] == 2]
        
        if red_pilots:
            fig.add_trace(go.Scatter(
                x=[p['shots'] for p in red_pilots],
                y=[p['accuracy'] for p in red_pilots],
                mode='markers+text',
                text=[p['name'] for p in red_pilots],
                textposition="top center",
                marker=dict(
                    size=[max(8, p['ground_kills'] * 3 + 8) for p in red_pilots],  # Size based on ground kills
                    color='red', 
                    symbol='circle',
                    line=dict(width=1, color='darkred')
                ),
                name='Red Coalition',
                hovertemplate='<b>%{text}</b><br>Shots: %{x}<br>Accuracy: %{y:.1f}%<br>Ground Kills: %{marker.size}<extra></extra>',
                customdata=[p['ground_kills'] for p in red_pilots]
            ), row=1, col=1)
        
        if blue_pilots:
            fig.add_trace(go.Scatter(
                x=[p['shots'] for p in blue_pilots],
                y=[p['accuracy'] for p in blue_pilots],
                mode='markers+text',
                text=[p['name'] for p in blue_pilots],
                textposition="top center",
                marker=dict(
                    size=[max(8, p['ground_kills'] * 3 + 8) for p in blue_pilots],  # Size based on ground kills
                    color='blue', 
                    symbol='circle',
                    line=dict(width=1, color='darkblue')
                ),
                name='Blue Coalition',
                hovertemplate='<b>%{text}</b><br>Shots: %{x}<br>Accuracy: %{y:.1f}%<br>Ground Kills: %{marker.size}<extra></extra>',
                customdata=[p['ground_kills'] for p in blue_pilots]
            ), row=1, col=1)
        
        # 2. Weapon usage pie chart
        all_weapons = {}
        for pilot in ag_pilots:
            for weapon, count in pilot['weapons'].items():
                all_weapons[weapon] = all_weapons.get(weapon, 0) + count
        
        if all_weapons:
            fig.add_trace(go.Pie(
                labels=list(all_weapons.keys()),
                values=list(all_weapons.values()),
                hole=.3
            ), row=1, col=2)
        
        # 3. Coalition performance comparison (now includes kills)
        red_total_shots = sum(p['shots'] for p in red_pilots)
        blue_total_shots = sum(p['shots'] for p in blue_pilots)
        red_total_hits = sum(p['hits'] for p in red_pilots)
        blue_total_hits = sum(p['hits'] for p in blue_pilots)
        red_total_kills = sum(p['ground_kills'] for p in red_pilots)
        blue_total_kills = sum(p['ground_kills'] for p in blue_pilots)
        
        fig.add_trace(go.Bar(
            x=['Red Coalition', 'Blue Coalition'],
            y=[red_total_shots, blue_total_shots],
            name='A2G Shots',
            marker_color=['red', 'blue'],
            opacity=0.5
        ), row=2, col=1)
        
        fig.add_trace(go.Bar(
            x=['Red Coalition', 'Blue Coalition'],
            y=[red_total_hits, blue_total_hits],
            name='A2G Hits',
            marker_color=['darkred', 'darkblue'],
            opacity=0.7
        ), row=2, col=1)
        
        fig.add_trace(go.Bar(
            x=['Red Coalition', 'Blue Coalition'],
            y=[red_total_kills, blue_total_kills],
            name='Ground Kills',
            marker_color=['firebrick', 'navy']
        ), row=2, col=1)
        
        # 4. Response time (time to first A2G shot)
        pilots_with_time = [p for p in ag_pilots if p['time_to_first_ag'] is not None]
        if pilots_with_time:
            fig.add_trace(go.Bar(
                x=[p['name'] for p in pilots_with_time[:10]],  # Top 10
                y=[p['time_to_first_ag'] for p in pilots_with_time[:10]],
                marker_color=['red' if p['coalition'] == 1 else 'blue' for p in pilots_with_time[:10]],
                name='Time to First A2G Shot'
            ), row=2, col=2)
        
        fig.update_layout(
            title="Air-to-Ground Combat Analysis",
            height=800,
            showlegend=True
        )
        
        # Update axis labels
        fig.update_xaxes(title_text="A2G Shots Fired", row=1, col=1)
        fig.update_yaxes(title_text="A2G Accuracy (%)", row=1, col=1)
        fig.update_yaxes(title_text="Count", row=2, col=1)
        fig.update_xaxes(title_text="Pilot", row=2, col=2)
        fig.update_yaxes(title_text="Time (seconds)", row=2, col=2)
        
        # Add annotation for scatter plot
        fig.add_annotation(
            text="Marker size = Ground Kills",
            xref="x", yref="y",
            x=0.02, y=0.98,
            xanchor='left', yanchor='top',
            showarrow=False,
            font=dict(size=10, color="gray"),
            row=1, col=1
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_ag_pilot_dashboard(self, data):
        """Create air-to-ground statistics per pilot"""
        pilots = data.get('pilots', {})
        
        # Collect and sort pilots by A2G activity
        ag_pilots = []
        for pilot_name, pilot_data in pilots.items():
            ag_shots = pilot_data.get('ag_shots_fired', 0)
            ag_hits = pilot_data.get('ag_hits_scored', 0)
            ag_accuracy = pilot_data.get('ag_accuracy', 0)
            ground_kills = len(pilot_data.get('ground_units_killed', []))
            
            ag_pilots.append({
                'name': pilot_name,
                'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                'coalition': pilot_data.get('coalition', 0),
                'shots': ag_shots,
                'hits': ag_hits,
                'accuracy': ag_accuracy,
                'ground_kills': ground_kills,
                'weapons': pilot_data.get('ag_weapons_used', {}),
                'efficiency': pilot_data.get('efficiency_rating', 0)
            })
        
        # Sort by total A2G activity (shots + ground kills)
        ag_pilots.sort(key=lambda x: x['shots'] + x['ground_kills'], reverse=True)
        
        # Take top 15 pilots
        top_pilots = ag_pilots[:15]
        
        if not any(p['shots'] > 0 or p['ground_kills'] > 0 for p in top_pilots):
            # No air-to-ground activity
            fig = go.Figure()
            fig.add_annotation(
                text="No air-to-ground weapon activity detected in this mission",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            fig.update_layout(
                title="Air-to-Ground Statistics per Pilot",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=600
            )
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create grouped bar chart
        pilot_names = [p['name'] for p in top_pilots]
        ag_shots = [p['shots'] for p in top_pilots]
        ag_hits = [p['hits'] for p in top_pilots]
        ag_kills = [p['ground_kills'] for p in top_pilots]
        ag_accuracy = [p['accuracy'] for p in top_pilots]
        colors = ['red' if p['coalition'] == 1 else 'blue' for p in top_pilots]
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Air-to-Ground Shots, Hits, and Kills per Pilot', 'Air-to-Ground Accuracy per Pilot'),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        # Shots, hits, and kills
        fig.add_trace(go.Bar(
            x=pilot_names,
            y=ag_shots,
            name='A2G Shots',
            marker_color=colors,
            opacity=0.5
        ), row=1, col=1)
        
        fig.add_trace(go.Bar(
            x=pilot_names,
            y=ag_hits,
            name='A2G Hits',
            marker_color=[c.replace('red', 'darkred').replace('blue', 'darkblue') for c in colors],
            opacity=0.7
        ), row=1, col=1)
        
        fig.add_trace(go.Bar(
            x=pilot_names,
            y=ag_kills,
            name='Ground Kills',
            marker_color=[c.replace('red', 'firebrick').replace('blue', 'navy') for c in colors]
        ), row=1, col=1)
        
        # Accuracy
        fig.add_trace(go.Bar(
            x=pilot_names,
            y=ag_accuracy,
            name='A2G Accuracy (%)',
            marker_color=colors,
            showlegend=False
        ), row=2, col=1)
        
        fig.update_layout(
            title="Air-to-Ground Performance by Pilot",
            height=800,
            barmode='group'
        )
        
        # Update axis labels
        fig.update_xaxes(title_text="Pilot", row=2, col=1)
        fig.update_yaxes(title_text="Count", row=1, col=1)
        fig.update_yaxes(title_text="Accuracy (%)", row=2, col=1)
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_ag_group_dashboard(self, data):
        """Create air-to-ground statistics per group"""
        groups = data.get('groups', {})
        pilots = data.get('pilots', {})
        
        # Aggregate A2G stats by group
        group_ag_stats = {}
        
        for group_id, group_data in groups.items():
            group_name = group_data.get('name', f'Group {group_id}')
            coalition = group_data.get('coalition', 0)
            
            # Calculate A2G stats from group data if available
            total_ag_shots = group_data.get('total_ag_shots', 0)
            total_ag_hits = group_data.get('total_ag_hits', 0)
            ag_accuracy = group_data.get('group_ag_accuracy', 0)
            most_ag_active = group_data.get('most_ag_active_pilot', '')
            
            # Calculate ground kills for this group from pilot data
            total_ground_kills = 0
            for pilot_name, pilot_data in pilots.items():
                if pilot_data.get('group_id') == int(group_id):
                    total_ground_kills += len(pilot_data.get('ground_units_killed', []))
            
            group_ag_stats[group_id] = {
                'name': group_name,
                'coalition': coalition,
                'total_ag_shots': total_ag_shots,
                'total_ag_hits': total_ag_hits,
                'total_ground_kills': total_ground_kills,
                'ag_accuracy': ag_accuracy,
                'most_ag_active': most_ag_active,
                'pilot_count': group_data.get('total_pilots', 0)
            }
        
        # Filter groups with A2G activity (shots or ground kills)
        active_groups = {gid: stats for gid, stats in group_ag_stats.items() 
                        if stats['total_ag_shots'] > 0 or stats['total_ground_kills'] > 0}
        
        if not active_groups:
            # No air-to-ground activity
            fig = go.Figure()
            fig.add_annotation(
                text="No air-to-ground weapon activity detected in any group",
                xref="paper", yref="paper",
                x=0.5, y=0.5, xanchor='center', yanchor='middle',
                showarrow=False, font=dict(size=16)
            )
            fig.update_layout(
                title="Air-to-Ground Statistics per Group",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                height=600
            )
            return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create comparison dashboard
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'A2G Shots by Group', 'A2G Accuracy by Group',
                'A2G Hits and Ground Kills by Group', 'Group Efficiency Comparison'
            ),
            specs=[[{"type": "bar"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        group_names = list(active_groups.keys())
        group_labels = [active_groups[gid]['name'] for gid in group_names]
        coalition_colors = ['red' if active_groups[gid]['coalition'] == 1 else 'blue' 
                          for gid in group_names]
        
        # A2G Shots by group
        ag_shots = [active_groups[gid]['total_ag_shots'] for gid in group_names]
        fig.add_trace(go.Bar(
            x=group_labels,
            y=ag_shots,
            marker_color=coalition_colors,
            name='A2G Shots',
            showlegend=False
        ), row=1, col=1)
        
        # A2G Accuracy by group
        ag_accuracy = [active_groups[gid]['ag_accuracy'] for gid in group_names]
        fig.add_trace(go.Bar(
            x=group_labels,
            y=ag_accuracy,
            marker_color=coalition_colors,
            name='A2G Accuracy',
            showlegend=False
        ), row=1, col=2)
        
        # A2G Hits and Ground Kills by group
        ag_hits = [active_groups[gid]['total_ag_hits'] for gid in group_names]
        ground_kills = [active_groups[gid]['total_ground_kills'] for gid in group_names]
        
        fig.add_trace(go.Bar(
            x=group_labels,
            y=ag_hits,
            name='A2G Hits',
            marker_color=coalition_colors,
            opacity=0.7
        ), row=2, col=1)
        
        fig.add_trace(go.Bar(
            x=group_labels,
            y=ground_kills,
            name='Ground Kills',
            marker_color=[c.replace('red', 'firebrick').replace('blue', 'navy') for c in coalition_colors]
        ), row=2, col=1)
        
        # Group efficiency comparison (A2G shots vs accuracy, with ground kills as marker size)
        fig.add_trace(go.Scatter(
            x=ag_shots,
            y=ag_accuracy,
            mode='markers+text',
            text=group_labels,
            textposition="top center",
            marker=dict(
                size=[max(10, gk * 5 + 10) for gk in ground_kills],  # Size based on ground kills
                color=coalition_colors,
                opacity=0.7,
                line=dict(width=1, color='black')
            ),
            name='Groups',
            showlegend=False,
            hovertemplate='<b>%{text}</b><br>A2G Shots: %{x}<br>A2G Accuracy: %{y:.1f}%<br>Ground Kills: %{marker.size}<extra></extra>',
            customdata=ground_kills
        ), row=2, col=2)
        
        fig.update_layout(
            title="Air-to-Ground Performance by Group",
            height=800
        )
        
        # Update axis labels
        fig.update_yaxes(title_text="Shots", row=1, col=1)
        fig.update_yaxes(title_text="Accuracy (%)", row=1, col=2)
        fig.update_yaxes(title_text="Count", row=2, col=1)
        fig.update_xaxes(title_text="A2G Shots", row=2, col=2)
        fig.update_yaxes(title_text="A2G Accuracy (%)", row=2, col=2)
        
        # Add annotation for scatter plot
        fig.add_annotation(
            text="Marker size = Ground Kills",
            xref="x", yref="y",
            x=0.02, y=0.98,
            xanchor='left', yanchor='top',
            showarrow=False,
            font=dict(size=10, color="gray"),
            row=2, col=2
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

def get_past_analyses():
    """Get list of past analyses from the results folder"""
    past_analyses = []
    
    try:
        if not os.path.exists(RESULTS_FOLDER):
            return past_analyses
            
        for mission_id in os.listdir(RESULTS_FOLDER):
            session_dir = os.path.join(RESULTS_FOLDER, mission_id)
            
            # Skip if not a directory
            if not os.path.isdir(session_dir):
                continue
                
            # Check if session has valid data
            session_file = os.path.join(session_dir, 'session_data.json')
            mission_stats_file = os.path.join(session_dir, 'mission_stats.json')
            
            if os.path.exists(session_file) and os.path.exists(mission_stats_file):
                try:
                    # Load session data to get mission metadata
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)
                    
                    # Load mission stats to get summary
                    with open(mission_stats_file, 'r') as f:
                        mission_data = json.load(f)
                    
                    # Extract analysis metadata
                    mission_summary = mission_data.get('mission_summary', {})
                    mission_metadata = session_data.get('mission_metadata', {})
                    pilots = mission_data.get('pilots', {})
                    groups = mission_data.get('groups', {})
                    
                    # Calculate some quick stats
                    total_kills = sum(p.get('kills', 0) for p in pilots.values())
                    total_shots = sum(p.get('shots_fired', 0) for p in pilots.values())
                    active_pilots = len([p for p in pilots.values() if p.get('shots_fired', 0) > 0])
                    
                    # Determine coalitions present
                    coalitions = set(p.get('coalition', 0) for p in pilots.values())
                    coalition_names = []
                    if 1 in coalitions:
                        coalition_names.append('Red')
                    if 2 in coalitions:
                        coalition_names.append('Blue')
                    
                    # Get mission name and metadata
                    mission_name = mission_metadata.get('mission_name', mission_summary.get('mission_name', 'Unknown Mission'))
                    mission_file_mark = mission_metadata.get('mission_file_mark', mission_summary.get('mission_file_mark', 0))
                    
                    # Format timestamp from mission file mark if available
                    if mission_file_mark > 0:
                        try:
                            # Convert Unix timestamp to readable format
                            mission_datetime = datetime.fromtimestamp(mission_file_mark)
                            formatted_timestamp = mission_datetime.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            formatted_timestamp = f"Mark: {mission_file_mark}"
                    else:
                        # Fallback to analysis timestamp
                        analysis_timestamp = session_data.get('timestamp', mission_summary.get('analysis_timestamp', ''))
                        if analysis_timestamp:
                            try:
                                dt = datetime.fromisoformat(analysis_timestamp.replace('Z', '+00:00'))
                                formatted_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                formatted_timestamp = analysis_timestamp
                        else:
                            formatted_timestamp = mission_id
                    
                    # Get file sizes
                    session_file_size = os.path.getsize(session_file)
                    mission_file_size = os.path.getsize(mission_stats_file)
                    
                    analysis_info = {
                        'session_id': mission_id,  # Keep this for URL compatibility
                        'mission_id': mission_id,
                        'mission_name': mission_name,
                        'timestamp': formatted_timestamp,
                        'duration': mission_summary.get('duration', mission_metadata.get('mission_time', 0)),
                        'duration_minutes': round(mission_summary.get('duration', mission_metadata.get('mission_time', 0)) / 60, 1),
                        'total_events': mission_summary.get('total_events', 0),
                        'active_pilots': active_pilots,
                        'total_pilots': len(pilots),
                        'active_groups': len(groups),
                        'total_kills': total_kills,
                        'total_shots': total_shots,
                        'coalitions': coalition_names,
                        'file_size_mb': round((session_file_size + mission_file_size) / (1024 * 1024), 2),
                        'has_air_to_ground': any(p.get('ag_shots_fired', 0) > 0 for p in pilots.values()),
                        'has_ground_kills': any(len(p.get('ground_units_killed', [])) > 0 for p in pilots.values()),
                        'mission_file_mark': mission_file_mark
                    }
                    
                    past_analyses.append(analysis_info)
                    
                except Exception as e:
                    print(f"Error processing mission {mission_id}: {e}")
                    continue
    
    except Exception as e:
        print(f"Error reading past analyses: {e}")
    
    # Sort by mission file mark (mission time) if available, otherwise by mission_id
    past_analyses.sort(key=lambda x: (x['mission_file_mark'], x['mission_id']), reverse=True)
    
    return past_analyses

@app.route('/')
def index():
    past_analyses = get_past_analyses()
    return render_template('index.html', past_analyses=past_analyses)

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'dcs_log' not in request.files or 'debrief_log' not in request.files:
        flash('Both DCS.log and debrief.log files are required')
        return redirect(request.url)
    
    dcs_file = request.files['dcs_log']
    debrief_file = request.files['debrief_log']
    
    if dcs_file.filename == '' or debrief_file.filename == '':
        flash('Please select both files')
        return redirect(request.url)
    
    if dcs_file and allowed_file(dcs_file.filename) and debrief_file and allowed_file(debrief_file.filename):
        # Save uploaded files temporarily to extract mission metadata
        temp_dcs_path = tempfile.mktemp(suffix='.log')
        temp_debrief_path = tempfile.mktemp(suffix='.log')
        
        try:
            dcs_file.save(temp_dcs_path)
            debrief_file.save(temp_debrief_path)
            
            # Extract mission metadata from debrief log
            mission_metadata = extract_mission_metadata(temp_debrief_path)
            mission_id = mission_metadata['mission_id']
            
            # Check if this mission has already been analyzed
            existing_session_dir = os.path.join(RESULTS_FOLDER, mission_id)
            if os.path.exists(existing_session_dir):
                # Mission already exists, redirect to existing analysis
                flash(f'Mission "{mission_metadata["mission_name"]}" has already been analyzed. Showing existing results.')
                return redirect(url_for('dashboard', session_id=mission_id))
            
            # Save files with mission-based naming
            dcs_filename = secure_filename(dcs_file.filename)
            debrief_filename = secure_filename(debrief_file.filename)
            
            dcs_path = os.path.join(UPLOAD_FOLDER, f"{mission_id}_dcs.log")
            debrief_path = os.path.join(UPLOAD_FOLDER, f"{mission_id}_debrief.log")
            
            # Move temp files to final locations
            shutil.move(temp_dcs_path, dcs_path)
            shutil.move(temp_debrief_path, debrief_path)
            
            # Process files with mission-based analyzer
            analyzer = MissionAnalyzer(mission_id, mission_metadata)
            success, result = analyzer.process_files(dcs_path, debrief_path)
            
            if success:
                # Create visualizations
                visualizations = analyzer.create_visualizations(result)
                
                # Store session data with mission metadata
                session_data = {
                    'mission_data': result,
                    'visualizations': visualizations,
                    'mission_metadata': mission_metadata,
                    'timestamp': datetime.now().isoformat()
                }
                
                session_file = os.path.join(analyzer.session_dir, 'session_data.json')
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
                
                flash(f'Successfully analyzed mission: "{mission_metadata["mission_name"]}"')
                return redirect(url_for('dashboard', session_id=mission_id))
            else:
                flash(f'Processing failed: {result}')
                return redirect(url_for('index'))
                
        except Exception as e:
            flash(f'Error processing files: {str(e)}')
            return redirect(url_for('index'))
        finally:
            # Clean up temp files if they still exist
            for temp_file in [temp_dcs_path, temp_debrief_path]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    flash('Invalid file format. Please upload .log files only.')
    return redirect(url_for('index'))

@app.route('/dashboard/<session_id>')
def dashboard(session_id):
    try:
        session_file = os.path.join(RESULTS_FOLDER, session_id, 'session_data.json')
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        return render_template('dashboard.html', 
                             session_data=session_data,
                             session_id=session_id)
    except Exception as e:
        flash(f'Session not found or invalid: {str(e)}')
        return redirect(url_for('index'))

@app.route('/api/mission_data/<session_id>')
def get_mission_data(session_id):
    try:
        session_file = os.path.join(RESULTS_FOLDER, session_id, 'session_data.json')
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        return jsonify(session_data['mission_data'])
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/download/<session_id>/<file_type>')
def download_file(session_id, file_type):
    try:
        session_dir = os.path.join(RESULTS_FOLDER, session_id)
        
        if file_type == 'json':
            file_path = os.path.join(session_dir, 'mission_stats.json')
            return send_file(file_path, as_attachment=True, download_name=f'mission_stats_{session_id}.json')
        elif file_type == 'xml':
            file_path = os.path.join(session_dir, 'unit_group_mapping.xml')
            return send_file(file_path, as_attachment=True, download_name=f'unit_mapping_{session_id}.xml')
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    # app.run(debug=True, host='0.0.0.0', port=5002) 
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)