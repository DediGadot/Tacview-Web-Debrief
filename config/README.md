# Dashboard Layout Configuration System

The DCS Mission Debrief dashboard now supports flexible configuration of tab order and module layout through JSON configuration files.

## Overview

This system allows you to:
- **Control tab order** in the left sidebar navigation
- **Enable/disable tabs** and modules
- **Reorder modules** within each tab
- **Customize tab icons and descriptions**
- **Add custom modules** (for future extensions)
- **Set display options** and theme preferences

## Configuration File Structure

The main configuration file is `config/dashboard_layout.json`. Here's the structure:

```json
{
  "dashboard_config": {
    "title": "DCS Mission Debrief Dashboard",
    "description": "Configuration for dashboard tab order and module layout",
    "version": "1.0"
  },
  "tab_order": [
    {
      "id": "overview",
      "name": "Mission Overview",
      "icon": "fas fa-chart-pie",
      "description": "High-level mission statistics",
      "enabled": true,
      "modules": [...]
    }
  ],
  "module_types": {...},
  "display_options": {...},
  "theme": {...}
}
```

## Tab Configuration

Each tab in the `tab_order` array supports:

- **id**: Unique identifier (used in HTML/CSS)
- **name**: Display name in the sidebar
- **icon**: FontAwesome icon class
- **description**: Tooltip/subtitle text
- **enabled**: Whether the tab is visible
- **modules**: Array of modules within the tab

## Module Configuration

Each module supports:

- **id**: Unique identifier matching visualization keys
- **name**: Display name for the module
- **type**: Module type (`chart`, `table`, `widget`)
- **description**: Explanatory text
- **enabled**: Whether the module is shown
- **order**: Sort order within the tab (lower numbers first)

## Available Module IDs

The following module IDs correspond to visualizations:

### Charts
- `mission_overview` - Mission statistics dashboard
- `pilot_performance` - Individual pilot radar charts
- `weapon_effectiveness` - Weapon analysis dashboard
- `group_comparison` - Formation radar charts
- `combat_timeline` - Event timeline
- `kill_death_network` - Kill relationship network
- `efficiency_leaderboard` - Pilot rankings
- `air_to_ground_analysis` - A2G combat analysis
- `ag_pilot_dashboard` - A2G statistics per pilot
- `ag_group_dashboard` - A2G statistics per group

### Future Module Types
- `mission_summary_table` - Tabular mission data
- `pilot_statistics_table` - Detailed pilot table
- `custom_widgets` - Extensible widget system

## Usage Examples

### Change Tab Order

To reorder tabs, simply change their position in the `tab_order` array:

```json
"tab_order": [
  {"id": "pilots", "name": "Pilot Performance", ...},
  {"id": "overview", "name": "Mission Overview", ...},
  {"id": "weapons", "name": "Weapons Analysis", ...}
]
```

### Disable a Tab

Set `enabled: false`:

```json
{
  "id": "timeline",
  "name": "Combat Timeline",
  "enabled": false,
  "modules": [...]
}
```

### Reorder Modules Within a Tab

Change the `order` values:

```json
"modules": [
  {"id": "efficiency_leaderboard", "order": 1, ...},
  {"id": "pilot_performance", "order": 2, ...}
]
```

### Add a Custom Module

```json
{
  "id": "custom_analysis",
  "name": "Custom Analysis",
  "type": "chart",
  "description": "Custom analysis module",
  "enabled": true,
  "order": 3
}
```

## Python API

### Basic Usage

```python
from config.layout_manager import get_layout_manager

layout_manager = get_layout_manager()

# Get enabled tabs
tabs = layout_manager.get_enabled_tabs()

# Get modules for a tab
modules = layout_manager.get_enabled_modules('pilots')

# Check if tab/module is enabled
if layout_manager.is_tab_enabled('overview'):
    print("Overview tab is enabled")

# Get navigation structure (for templates)
navigation = layout_manager.get_navigation_structure()
```

### Dynamic Configuration

```python
# Get current configuration
config = layout_manager.config

# Modify configuration
config['tab_order'][0]['enabled'] = False

# Save changes
layout_manager.save_config(config)

# Add custom module
module_config = {
    "id": "custom_chart",
    "name": "Custom Chart",
    "type": "chart",
    "enabled": True,
    "order": 10
}
layout_manager.add_custom_module('overview', module_config)
```

## REST API Endpoints

### Get Configuration

```http
GET /api/config/navigation
GET /api/config/layout
```

### Update Configuration

```http
POST /api/config/layout
Content-Type: application/json

{...configuration...}
```

### Toggle Tab/Module

```http
POST /api/config/tabs/overview/enabled
Content-Type: application/json

{"enabled": false}
```

```http
POST /api/config/tabs/pilots/modules/pilot_performance/enabled
Content-Type: application/json

{"enabled": true}
```

### Reorder Modules

```http
POST /api/config/tabs/pilots/modules/reorder
Content-Type: application/json

{
  "module_orders": {
    "pilot_performance": 1,
    "efficiency_leaderboard": 2
  }
}
```

## Configuration Panel

Access the configuration panel through the dashboard by clicking "Layout Settings" in the sidebar. The panel provides:

- **Tab Management**: Enable/disable tabs
- **Module Configuration**: Configure modules per tab
- **Reordering**: Drag-and-drop interface (future)
- **Export/Import**: Save and load configurations

## Template Integration

The dashboard template uses the navigation structure:

```html
{% for tab in navigation.tabs %}
  <div class="sidebar-item" data-target="{{ tab.id }}">
    <i class="{{ tab.icon }} me-2"></i>
    {{ tab.name }}
    {% if tab.description %}
      <small class="text-muted">{{ tab.description }}</small>
    {% endif %}
  </div>
{% endfor %}
```

## Best Practices

### 1. Backup Configuration
Always backup `dashboard_layout.json` before making changes.

### 2. Module Order
Use increments of 10 for order values (10, 20, 30) to allow easy insertion.

### 3. Tab Organization
Group related modules in the same tab for better user experience.

### 4. Enable/Disable Strategy
Disable unused modules rather than deleting them for easy re-enabling.

### 5. Testing
Test configuration changes with different mission data to ensure compatibility.

## Troubleshooting

### Configuration Not Loading
- Check JSON syntax with a validator
- Verify file permissions
- Check application logs for errors

### Missing Modules
- Ensure module IDs match visualization keys
- Check that modules are enabled
- Verify tab is enabled

### Layout Issues
- Clear browser cache
- Check for JavaScript errors
- Verify template syntax

## Default Configuration

If the configuration file is missing or invalid, the system falls back to a minimal default configuration with just the mission overview tab.

## Future Enhancements

- Drag-and-drop reordering in the UI
- Custom module templates
- User-specific configurations
- Configuration versioning
- Advanced theming options
- Module dependencies and conditionals 