"""
Dashboard Layout Manager
Manages configuration for tab order and module layout in the DCS Mission Debrief dashboard.
"""

import json
import os
from typing import Dict, List, Any, Optional

class LayoutManager:
    """Manages dashboard layout configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'dashboard_layout.json')
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate configuration structure
            self._validate_config(config)
            return config
            
        except FileNotFoundError:
            print(f"Configuration file not found: {self.config_path}")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in configuration file: {e}")
            return self._get_default_config()
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return self._get_default_config()
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure"""
        required_keys = ['dashboard_config', 'tab_order', 'module_types', 'display_options']
        
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")
        
        # Validate tab structure
        for tab in config['tab_order']:
            required_tab_keys = ['id', 'name', 'enabled', 'modules']
            for key in required_tab_keys:
                if key not in tab:
                    raise ValueError(f"Missing required tab key: {key}")
            
            # Validate module structure
            for module in tab['modules']:
                required_module_keys = ['id', 'name', 'type', 'enabled', 'order']
                for key in required_module_keys:
                    if key not in module:
                        raise ValueError(f"Missing required module key: {key}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if config file is not available"""
        return {
            "dashboard_config": {
                "title": "DCS Mission Debrief Dashboard",
                "description": "Default configuration",
                "version": "1.0"
            },
            "tab_order": [
                {
                    "id": "overview",
                    "name": "Mission Overview",
                    "icon": "fas fa-chart-pie",
                    "enabled": True,
                    "modules": [
                        {
                            "id": "mission_overview",
                            "name": "Mission Statistics",
                            "type": "chart",
                            "enabled": True,
                            "order": 1
                        }
                    ]
                }
            ],
            "module_types": {
                "chart": {"container_class": "chart-container"},
                "table": {"container_class": "table-container"}
            },
            "display_options": {
                "show_module_descriptions": True,
                "show_tab_icons": True
            }
        }
    
    def get_enabled_tabs(self) -> List[Dict[str, Any]]:
        """Get list of enabled tabs in configured order"""
        return [tab for tab in self.config['tab_order'] if tab.get('enabled', True)]
    
    def get_tab_by_id(self, tab_id: str) -> Optional[Dict[str, Any]]:
        """Get tab configuration by ID"""
        for tab in self.config['tab_order']:
            if tab['id'] == tab_id:
                return tab
        return None
    
    def get_enabled_modules(self, tab_id: str) -> List[Dict[str, Any]]:
        """Get enabled modules for a tab, sorted by order"""
        tab = self.get_tab_by_id(tab_id)
        if not tab:
            return []
        
        enabled_modules = [module for module in tab['modules'] if module.get('enabled', True)]
        return sorted(enabled_modules, key=lambda x: x.get('order', 999))
    
    def get_module_by_id(self, tab_id: str, module_id: str) -> Optional[Dict[str, Any]]:
        """Get module configuration by tab ID and module ID"""
        tab = self.get_tab_by_id(tab_id)
        if not tab:
            return None
        
        for module in tab['modules']:
            if module['id'] == module_id:
                return module
        return None
    
    def get_module_type_config(self, module_type: str) -> Dict[str, Any]:
        """Get configuration for a module type"""
        return self.config['module_types'].get(module_type, {})
    
    def get_display_options(self) -> Dict[str, Any]:
        """Get display options"""
        return self.config.get('display_options', {})
    
    def get_theme_config(self) -> Dict[str, Any]:
        """Get theme configuration"""
        return self.config.get('theme', {})
    
    def is_tab_enabled(self, tab_id: str) -> bool:
        """Check if a tab is enabled"""
        tab = self.get_tab_by_id(tab_id)
        return tab.get('enabled', False) if tab else False
    
    def is_module_enabled(self, tab_id: str, module_id: str) -> bool:
        """Check if a module is enabled"""
        module = self.get_module_by_id(tab_id, module_id)
        return module.get('enabled', False) if module else False
    
    def get_navigation_structure(self) -> Dict[str, Any]:
        """Get complete navigation structure for the dashboard"""
        navigation = {
            'tabs': [],
            'total_modules': 0,
            'config': self.config['dashboard_config']
        }
        
        for tab in self.get_enabled_tabs():
            enabled_modules = self.get_enabled_modules(tab['id'])
            
            tab_info = {
                'id': tab['id'],
                'name': tab['name'],
                'icon': tab.get('icon', 'fas fa-chart-line'),
                'description': tab.get('description', ''),
                'module_count': len(enabled_modules),
                'modules': [
                    {
                        'id': module['id'],
                        'name': module['name'],
                        'type': module['type'],
                        'description': module.get('description', ''),
                        'order': module.get('order', 999)
                    }
                    for module in enabled_modules
                ]
            }
            
            navigation['tabs'].append(tab_info)
            navigation['total_modules'] += len(enabled_modules)
        
        return navigation
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file"""
        try:
            self._validate_config(config)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.config = config
            return True
            
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def add_custom_module(self, tab_id: str, module_config: Dict[str, Any]) -> bool:
        """Add a custom module to a tab"""
        try:
            tab = self.get_tab_by_id(tab_id)
            if not tab:
                return False
            
            # Validate module configuration
            required_keys = ['id', 'name', 'type', 'enabled', 'order']
            for key in required_keys:
                if key not in module_config:
                    return False
            
            # Check if module ID already exists
            if self.get_module_by_id(tab_id, module_config['id']):
                return False
            
            # Add module to tab
            tab['modules'].append(module_config)
            
            # Save configuration
            return self.save_config(self.config)
            
        except Exception as e:
            print(f"Error adding custom module: {e}")
            return False
    
    def remove_module(self, tab_id: str, module_id: str) -> bool:
        """Remove a module from a tab"""
        try:
            tab = self.get_tab_by_id(tab_id)
            if not tab:
                return False
            
            # Find and remove module
            tab['modules'] = [m for m in tab['modules'] if m['id'] != module_id]
            
            # Save configuration
            return self.save_config(self.config)
            
        except Exception as e:
            print(f"Error removing module: {e}")
            return False
    
    def reorder_modules(self, tab_id: str, module_orders: Dict[str, int]) -> bool:
        """Reorder modules in a tab"""
        try:
            tab = self.get_tab_by_id(tab_id)
            if not tab:
                return False
            
            # Update module orders
            for module in tab['modules']:
                if module['id'] in module_orders:
                    module['order'] = module_orders[module['id']]
            
            # Save configuration
            return self.save_config(self.config)
            
        except Exception as e:
            print(f"Error reordering modules: {e}")
            return False

# Global instance
layout_manager = LayoutManager()

def get_layout_manager() -> LayoutManager:
    """Get the global layout manager instance"""
    return layout_manager 