# DCS Mission Debrief Web Application

A comprehensive web-based solution for analyzing DCS World missions with engaging interactive visualizations and detailed statistics.

## 🚀 Features

### **Automated Analysis Pipeline**
- **File Upload**: Drag-and-drop interface for DCS.log and debrief.log files
- **Automatic Processing**: Executes `dcs_xml_extractor.py` → `dcs_mission_analyzer.py` pipeline
- **Real-time Feedback**: Progress indicators and error handling

### **Interactive Visualizations**
1. **Mission Overview Dashboard**
   - Mission duration gauge
   - Combat statistics bar charts
   - Pilot and group count indicators

2. **Pilot Performance Radar Charts**
   - Individual pilot analysis
   - Accuracy, K/D ratio, efficiency, and activity metrics
   - Top 5 performers highlighted

3. **Weapon Effectiveness Analysis**
   - Usage vs. effectiveness scatter plots
   - Lethality percentages
   - Weapon comparison charts

4. **Group Performance Comparison**
   - Coalition-based color coding
   - Accuracy, survivability, efficiency metrics
   - Group vs. group analysis

5. **Combat Timeline**
   - Chronological event visualization
   - First shot and first kill tracking
   - Interactive timeline markers

6. **Efficiency Leaderboard**
   - Star-based rating system (★☆☆☆☆ to ★★★★★)
   - Coalition-colored rankings
   - Comprehensive efficiency scoring

7. **Kill/Death Networks**
   - Relationship mapping
   - Who killed whom analysis

### **Modern Web Interface**
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark Theme**: Military-inspired color scheme
- **Interactive Navigation**: Sidebar with section switching
- **Print Support**: Optimized for report printing
- **Download Options**: Export JSON and XML data

## 📋 Requirements

### **Python Dependencies**
```bash
pip install Flask plotly pandas
```

### **System Requirements**
- Python 3.7+
- Modern web browser with JavaScript enabled
- 50MB+ available storage for session data

## 🛠 Installation & Setup

### **1. Install Dependencies**
```bash
# Install required Python packages
pip install -r web_requirements.txt

# Or install individually
pip install Flask plotly pandas
```

### **2. Verify Existing Scripts**
Ensure these files are in your project directory:
- `dcs_xml_extractor.py` - Extracts XML from DCS.log
- `dcs_mission_analyzer.py` - Analyzes mission statistics
- `debrief.log` - Your mission debrief file
- `dcs.log` - Your DCS log file

### **3. Start the Web Server**
```bash
python3 app.py
```

The server will start on `http://localhost:5000`

## 🎯 Usage Guide

### **Step 1: Upload Files**
1. Navigate to `http://localhost:5000` in your browser
2. Drag and drop or click to select your `dcs.log` file
3. Drag and drop or click to select your `debrief.log` file
4. Click "Analyze Mission" to start processing

### **Step 2: View Analysis**
After processing (usually 10-30 seconds), you'll be redirected to the dashboard featuring:

- **Mission Overview**: Quick stats and duration
- **Pilot Performance**: Individual radar charts for top pilots
- **Weapon Analysis**: Effectiveness and usage statistics
- **Group Comparison**: Coalition and group performance
- **Combat Timeline**: Chronological event analysis
- **Efficiency Rankings**: Star-rated pilot leaderboard
- **Kill Networks**: Relationship mapping
- **Mission Summary**: Detailed tables and statistics

### **Step 3: Export & Share**
- Download JSON data for further analysis
- Download XML mapping for reference
- Print comprehensive reports
- Share session URLs with team members

## 📊 Understanding the Visualizations

### **Efficiency Rating System**
- **★★★★★ Elite (80-100)**: Exceptional performance across all metrics
- **★★★★☆ Excellent (60-79)**: Strong performance with minor areas for improvement
- **★★★☆☆ Good (40-59)**: Solid performance with some improvement opportunities
- **★★☆☆☆ Average (20-39)**: Basic performance, significant room for growth
- **★☆☆☆☆ Needs Improvement (0-19)**: Requires focused training and development

### **Color Coding**
- **Red**: Red Coalition forces
- **Blue**: Blue Coalition forces
- **Green**: Positive metrics (survivability, accuracy)
- **Orange/Yellow**: Neutral metrics
- **Dark**: System elements and headers

### **Key Metrics Explained**
- **Accuracy**: (Hits / Shots) × 100%
- **K/D Ratio**: Kills / max(Deaths, 1)
- **Efficiency Rating**: Composite score of accuracy, K/D, and shots per kill
- **Lethality**: (Kills / Hits) × 100% for weapons
- **Survivability**: (Surviving Pilots / Total Pilots) × 100%

## 🏗 Architecture

### **Backend Components**
```
app.py                 # Flask web server
├── MissionAnalyzer    # Core analysis class
├── File Processing    # Upload and pipeline management
├── Visualization      # Plotly chart generation
└── Session Management # Data persistence
```

### **Frontend Structure**
```
templates/
├── base.html         # Common layout and styling
├── index.html        # Upload interface
└── dashboard.html    # Analysis dashboard

static/
├── css/             # Custom styles
└── js/              # Interactive functionality
```

### **Data Flow**
1. **Upload**: Files saved to `uploads/` with session ID
2. **Extract**: `dcs_xml_extractor.py` creates unit mapping XML
3. **Analyze**: `dcs_mission_analyzer.py` generates statistics JSON
4. **Visualize**: Plotly charts created from JSON data
5. **Store**: Session data saved to `results/{session_id}/`
6. **Display**: Interactive dashboard renders all visualizations

## 🔧 Configuration

### **File Size Limits**
- Maximum upload size: 50MB per file
- Adjustable in `app.py`: `app.config['MAX_CONTENT_LENGTH']`

### **Session Management**
- Sessions stored in: `results/{YYYYMMDD_HHMMSS}/`
- Automatic cleanup not implemented (manual cleanup required)
- Session data includes: JSON stats, XML mapping, visualizations

### **Development Mode**
```python
# In app.py, change debug settings
app.run(debug=True, host='0.0.0.0', port=5000)
```

## 🐛 Troubleshooting

### **Common Issues**

1. **"ModuleNotFoundError: No module named 'plotly'"**
   ```bash
   pip install plotly pandas Flask
   ```

2. **"XML extraction failed"**
   - Verify `dcs_xml_extractor.py` is in the project directory
   - Check that DCS.log contains valid XML mapping data
   - Ensure Python script has execution permissions

3. **"Mission analysis failed"**
   - Verify `dcs_mission_analyzer.py` is in the project directory
   - Check debrief.log format and content
   - Ensure all required Python modules are installed

4. **Charts not displaying**
   - Check browser JavaScript console for errors
   - Verify Plotly.js is loading from CDN
   - Ensure session data is properly formatted

5. **Upload fails**
   - Check file size (must be < 50MB)
   - Verify file extensions are `.log`
   - Ensure sufficient disk space

### **Debug Mode**
Enable debug mode for detailed error messages:
```python
# In app.py
app.run(debug=True)
```

### **Log Files**
Check server logs for detailed error information when running in debug mode.

## 🚀 Production Deployment

### **Security Considerations**
- Change the secret key in production
- Implement user authentication if needed
- Set up proper file upload validation
- Configure firewall rules for port access

### **Performance Optimization**
- Use a production WSGI server (gunicorn, uWSGI)
- Implement session cleanup jobs
- Add database storage for better scalability
- Configure proper logging

### **Example Production Setup**
```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📈 Future Enhancements

### **Planned Features**
- [ ] Real-time mission monitoring
- [ ] Historical mission comparison
- [ ] Advanced statistical analysis
- [ ] Team collaboration features
- [ ] API endpoints for external integration
- [ ] Database storage for persistence
- [ ] User authentication and permissions
- [ ] Mobile app companion

### **Visualization Improvements**
- [ ] 3D flight path visualization
- [ ] Heat maps for engagement zones
- [ ] Animated timeline playback
- [ ] Real-time dashboard updates
- [ ] Custom chart configuration

## 📄 License

This project is provided as-is for DCS World mission analysis. Feel free to modify and extend as needed.

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional chart types and visualizations
- Enhanced mobile responsiveness
- Performance optimizations
- Extended statistical analysis
- Better error handling and user feedback

## 📞 Support

For issues and questions:
1. Check the troubleshooting section above
2. Verify all dependencies are installed correctly
3. Ensure input files are valid DCS World logs
4. Check server logs for detailed error information

---

**Built for DCS World pilots seeking comprehensive mission analysis and performance insights.** 