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

class MissionAnalyzer:
    def __init__(self, session_id):
        self.session_id = session_id
        self.session_dir = os.path.join(RESULTS_FOLDER, session_id)
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
            
            # Step 4: Load and return the results
            with open(json_output_path, 'r') as f:
                mission_data = json.load(f)
            
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
        total_deaths = sum(p.get('deaths', 0) for p in pilots.values())
        total_shots = sum(p.get('shots_fired', 0) for p in pilots.values())
        total_hits = sum(p.get('hits_scored', 0) for p in pilots.values())
        
        fig.add_trace(go.Bar(
            x=['Kills', 'Deaths', 'Shots', 'Hits'],
            y=[total_kills, total_deaths, total_shots, total_hits],
            marker_color=['green', 'red', 'blue', 'orange']
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
        """Create radar charts for top pilots"""
        pilots = data.get('pilots', {})
        
        # Get top 5 pilots by efficiency rating
        top_pilots = sorted(pilots.items(), 
                          key=lambda x: x[1].get('efficiency_rating', 0), 
                          reverse=True)[:5]
        
        charts = []
        
        for pilot_name, pilot_data in top_pilots:
            if pilot_data.get('shots_fired', 0) == 0:
                continue
                
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
                name=pilot_name
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                title=f"{pilot_name} ({pilot_data.get('aircraft_type', 'Unknown')})",
                showlegend=True,
                height=400
            )
            
            charts.append({
                'pilot': pilot_name,
                'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
            })
        
        return charts
    
    def create_weapon_effectiveness_chart(self, data):
        """Create weapon effectiveness visualization"""
        pilots = data.get('pilots', {})
        
        # Aggregate weapon data
        weapon_stats = {}
        for pilot_data in pilots.values():
            weapons_used = pilot_data.get('weapons_used', {})
            weapons_kills = pilot_data.get('weapons_kills', {})
            
            for weapon, shots in weapons_used.items():
                if weapon not in weapon_stats:
                    weapon_stats[weapon] = {'shots': 0, 'kills': 0}
                weapon_stats[weapon]['shots'] += shots
                weapon_stats[weapon]['kills'] += weapons_kills.get(weapon, 0)
        
        # Calculate effectiveness metrics
        weapons = []
        shots = []
        kills = []
        effectiveness = []
        
        for weapon, stats in weapon_stats.items():
            if stats['shots'] > 0:
                weapons.append(weapon)
                shots.append(stats['shots'])
                kills.append(stats['kills'])
                effectiveness.append((stats['kills'] / stats['shots']) * 100)
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Weapon Usage', 'Weapon Effectiveness'),
            specs=[[{"type": "bar"}, {"type": "scatter"}]]
        )
        
        # Weapon usage bar chart
        fig.add_trace(go.Bar(
            x=weapons,
            y=shots,
            name="Shots Fired",
            marker_color='lightblue'
        ), row=1, col=1)
        
        # Weapon effectiveness scatter plot
        fig.add_trace(go.Scatter(
            x=shots,
            y=effectiveness,
            mode='markers+text',
            text=weapons,
            textposition="top center",
            marker=dict(size=kills, sizemode='diameter', sizeref=max(kills)/50 if kills else 1),
            name="Effectiveness %"
        ), row=1, col=2)
        
        fig.update_layout(
            title="Weapon Analysis",
            height=500
        )
        
        fig.update_xaxes(title_text="Weapon Type", row=1, col=1)
        fig.update_yaxes(title_text="Shots Fired", row=1, col=1)
        fig.update_xaxes(title_text="Total Shots", row=1, col=2)
        fig.update_yaxes(title_text="Effectiveness %", row=1, col=2)
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_group_comparison_chart(self, data):
        """Create group performance comparison"""
        groups = data.get('groups', {})
        
        group_names = []
        accuracy = []
        survivability = []
        efficiency = []
        kills = []
        
        for group_data in groups.values():
            group_names.append(group_data.get('name', 'Unknown'))
            accuracy.append(group_data.get('group_accuracy', 0))
            survivability.append(group_data.get('group_survivability', 0))
            efficiency.append(group_data.get('average_pilot_efficiency', 0))
            kills.append(group_data.get('total_kills', 0))
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Group Accuracy', 'Group Survivability', 'Average Efficiency', 'Total Kills'),
            specs=[[{"type": "bar"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "bar"}]]
        )
        
        colors = ['red' if 'Red' in name or group_data.get('coalition') == 1 else 'blue' 
                 for name, group_data in zip(group_names, groups.values())]
        
        fig.add_trace(go.Bar(x=group_names, y=accuracy, marker_color=colors, name="Accuracy"), row=1, col=1)
        fig.add_trace(go.Bar(x=group_names, y=survivability, marker_color=colors, name="Survivability"), row=1, col=2)
        fig.add_trace(go.Bar(x=group_names, y=efficiency, marker_color=colors, name="Efficiency"), row=2, col=1)
        fig.add_trace(go.Bar(x=group_names, y=kills, marker_color=colors, name="Kills"), row=2, col=2)
        
        fig.update_layout(
            title="Group Performance Comparison",
            showlegend=False,
            height=600
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_combat_timeline(self, data):
        """Create combat timeline visualization"""
        pilots = data.get('pilots', {})
        
        events = []
        
        for pilot_name, pilot_data in pilots.items():
            # Add first shot events
            if pilot_data.get('time_to_first_shot') is not None:
                events.append({
                    'time': pilot_data.get('time_to_first_shot', 0),
                    'pilot': pilot_name,
                    'event': 'First Shot',
                    'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                    'value': 1
                })
            
            # Add first kill events
            if pilot_data.get('time_to_first_kill') is not None:
                events.append({
                    'time': pilot_data.get('time_to_first_kill', 0),
                    'pilot': pilot_name,
                    'event': 'First Kill',
                    'aircraft': pilot_data.get('aircraft_type', 'Unknown'),
                    'value': 2
                })
        
        if not events:
            # Create empty timeline
            fig = go.Figure()
            fig.add_annotation(text="No timeline data available", 
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
        else:
            # Sort events by time
            events.sort(key=lambda x: x['time'])
            
            fig = go.Figure()
            
            # Group events by type
            for event_type in ['First Shot', 'First Kill']:
                type_events = [e for e in events if e['event'] == event_type]
                if type_events:
                    fig.add_trace(go.Scatter(
                        x=[e['time'] for e in type_events],
                        y=[e['pilot'] for e in type_events],
                        mode='markers+text',
                        text=[f"{e['aircraft']}" for e in type_events],
                        textposition="middle right",
                        marker=dict(size=12, symbol='diamond' if event_type == 'First Kill' else 'circle'),
                        name=event_type
                    ))
        
        fig.update_layout(
            title="Combat Timeline",
            xaxis_title="Time (seconds)",
            yaxis_title="Pilot",
            height=400
        )
        
        return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    def create_kill_death_network(self, data):
        """Create kill/death relationship network"""
        pilots = data.get('pilots', {})
        
        # Find kill relationships
        relationships = []
        for pilot_name, pilot_data in pilots.items():
            if pilot_data.get('killed_by'):
                relationships.append({
                    'killer': pilot_data['killed_by'],
                    'victim': pilot_name
                })
        
        if not relationships:
            fig = go.Figure()
            fig.add_annotation(text="No kill/death relationships to display", 
                             xref="paper", yref="paper",
                             x=0.5, y=0.5, showarrow=False)
        else:
            # Create network visualization
            fig = go.Figure()
            
            # Simple layout - just show the relationships as a table-like structure
            killers = list(set([r['killer'] for r in relationships]))
            victims = list(set([r['victim'] for r in relationships]))
            
            # Create arrows showing kill relationships
            for i, rel in enumerate(relationships):
                fig.add_annotation(
                    x=0.2, y=0.8 - i * 0.2,
                    text=f"{rel['killer']} → {rel['victim']}",
                    showarrow=False,
                    font=dict(size=14)
                )
        
        fig.update_layout(
            title="Kill/Death Relationships",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=300
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

@app.route('/')
def index():
    return render_template('index.html')

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
        # Create session ID
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save uploaded files
        dcs_filename = secure_filename(dcs_file.filename)
        debrief_filename = secure_filename(debrief_file.filename)
        
        dcs_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_dcs.log")
        debrief_path = os.path.join(UPLOAD_FOLDER, f"{session_id}_debrief.log")
        
        dcs_file.save(dcs_path)
        debrief_file.save(debrief_path)
        
        # Process files
        analyzer = MissionAnalyzer(session_id)
        success, result = analyzer.process_files(dcs_path, debrief_path)
        
        if success:
            # Create visualizations
            visualizations = analyzer.create_visualizations(result)
            
            # Store session data
            session_data = {
                'mission_data': result,
                'visualizations': visualizations,
                'timestamp': datetime.now().isoformat()
            }
            
            session_file = os.path.join(analyzer.session_dir, 'session_data.json')
            with open(session_file, 'w') as f:
                json.dump(session_data, f)
            
            return redirect(url_for('dashboard', session_id=session_id))
        else:
            flash(f'Processing failed: {result}')
            return redirect(url_for('index'))
    
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
    app.run(debug=True, host='0.0.0.0', port=5001) 