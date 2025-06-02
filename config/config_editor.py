#!/usr/bin/env python3
"""
Dashboard Configuration Editor
A command-line tool for managing dashboard layout configurations.
"""

import json
import argparse
from layout_manager import LayoutManager, get_layout_manager

def print_current_config():
    """Print the current configuration"""
    layout_manager = get_layout_manager()
    navigation = layout_manager.get_navigation_structure()
    
    print(f"\n📊 {navigation['config']['title']}")
    print(f"📝 {navigation['config']['description']}")
    print(f"🎯 Total modules: {navigation['total_modules']}")
    print(f"📑 Active tabs: {len(navigation['tabs'])}")
    
    print("\n📋 Tab Configuration:")
    for i, tab in enumerate(navigation['tabs'], 1):
        status = "✅" if len(tab['modules']) > 0 else "❌"
        print(f"  {i}. {status} {tab['name']} ({tab['module_count']} modules)")
        for module in tab['modules']:
            print(f"     • {module['name']} ({module['type']})")

def list_available_layouts():
    """List available example layouts"""
    try:
        with open('example_layouts.json', 'r') as f:
            examples = json.load(f)
        
        print("\n🎨 Available Layout Templates:")
        for layout_id, layout_info in examples['layouts'].items():
            print(f"  • {layout_id}: {layout_info['name']}")
            print(f"    {layout_info['description']}")
            print()
    except FileNotFoundError:
        print("❌ example_layouts.json not found")

def apply_layout(layout_name):
    """Apply a layout from examples"""
    try:
        with open('example_layouts.json', 'r') as f:
            examples = json.load(f)
        
        if layout_name not in examples['layouts']:
            print(f"❌ Layout '{layout_name}' not found")
            list_available_layouts()
            return False
        
        layout_config = examples['layouts'][layout_name]['config']
        
        # Add required configuration sections
        full_config = {
            "dashboard_config": {
                "title": "DCS Mission Debrief Dashboard",
                "description": f"Layout: {examples['layouts'][layout_name]['name']}",
                "version": "1.0"
            },
            "tab_order": layout_config['tab_order'],
            "module_types": {
                "chart": {
                    "container_class": "chart-container",
                    "loading_message": "Loading visualization...",
                    "error_message": "Failed to load chart"
                },
                "table": {
                    "container_class": "table-container",
                    "loading_message": "Loading data...",
                    "error_message": "Failed to load table"
                }
            },
            "display_options": {
                "show_module_descriptions": True,
                "show_tab_icons": True,
                "enable_module_collapse": True
            },
            "theme": {
                "primary_color": "#007bff",
                "secondary_color": "#6c757d"
            }
        }
        
        layout_manager = get_layout_manager()
        success = layout_manager.save_config(full_config)
        
        if success:
            print(f"✅ Applied layout: {examples['layouts'][layout_name]['name']}")
            print_current_config()
        else:
            print("❌ Failed to save configuration")
        
        return success
        
    except FileNotFoundError:
        print("❌ example_layouts.json not found")
        return False
    except Exception as e:
        print(f"❌ Error applying layout: {e}")
        return False

def toggle_tab(tab_id, enabled=None):
    """Toggle a tab's enabled status"""
    layout_manager = get_layout_manager()
    
    tab = layout_manager.get_tab_by_id(tab_id)
    if not tab:
        print(f"❌ Tab '{tab_id}' not found")
        return False
    
    if enabled is None:
        enabled = not tab.get('enabled', True)
    
    tab['enabled'] = enabled
    success = layout_manager.save_config(layout_manager.config)
    
    if success:
        status = "enabled" if enabled else "disabled"
        print(f"✅ Tab '{tab['name']}' {status}")
    else:
        print(f"❌ Failed to toggle tab '{tab_id}'")
    
    return success

def toggle_module(tab_id, module_id, enabled=None):
    """Toggle a module's enabled status"""
    layout_manager = get_layout_manager()
    
    module = layout_manager.get_module_by_id(tab_id, module_id)
    if not module:
        print(f"❌ Module '{module_id}' not found in tab '{tab_id}'")
        return False
    
    if enabled is None:
        enabled = not module.get('enabled', True)
    
    module['enabled'] = enabled
    success = layout_manager.save_config(layout_manager.config)
    
    if success:
        status = "enabled" if enabled else "disabled"
        print(f"✅ Module '{module['name']}' {status}")
    else:
        print(f"❌ Failed to toggle module '{module_id}'")
    
    return success

def backup_config(filename=None):
    """Backup current configuration"""
    if filename is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dashboard_layout_backup_{timestamp}.json"
    
    layout_manager = get_layout_manager()
    
    try:
        with open(filename, 'w') as f:
            json.dump(layout_manager.config, f, indent=2)
        print(f"✅ Configuration backed up to {filename}")
        return True
    except Exception as e:
        print(f"❌ Failed to backup configuration: {e}")
        return False

def restore_config(filename):
    """Restore configuration from backup"""
    try:
        with open(filename, 'r') as f:
            config = json.load(f)
        
        layout_manager = get_layout_manager()
        success = layout_manager.save_config(config)
        
        if success:
            print(f"✅ Configuration restored from {filename}")
            print_current_config()
        else:
            print(f"❌ Failed to restore configuration")
        
        return success
        
    except FileNotFoundError:
        print(f"❌ Backup file '{filename}' not found")
        return False
    except Exception as e:
        print(f"❌ Error restoring configuration: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Dashboard Configuration Editor')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Show current configuration
    subparsers.add_parser('show', help='Show current configuration')
    
    # List available layouts
    subparsers.add_parser('layouts', help='List available layout templates')
    
    # Apply layout
    apply_parser = subparsers.add_parser('apply', help='Apply a layout template')
    apply_parser.add_argument('layout', help='Layout name to apply')
    
    # Toggle tab
    tab_parser = subparsers.add_parser('toggle-tab', help='Toggle tab enabled status')
    tab_parser.add_argument('tab_id', help='Tab ID to toggle')
    tab_parser.add_argument('--enable', action='store_true', help='Enable the tab')
    tab_parser.add_argument('--disable', action='store_true', help='Disable the tab')
    
    # Toggle module
    module_parser = subparsers.add_parser('toggle-module', help='Toggle module enabled status')
    module_parser.add_argument('tab_id', help='Tab ID containing the module')
    module_parser.add_argument('module_id', help='Module ID to toggle')
    module_parser.add_argument('--enable', action='store_true', help='Enable the module')
    module_parser.add_argument('--disable', action='store_true', help='Disable the module')
    
    # Backup configuration
    backup_parser = subparsers.add_parser('backup', help='Backup current configuration')
    backup_parser.add_argument('--filename', help='Backup filename (optional)')
    
    # Restore configuration
    restore_parser = subparsers.add_parser('restore', help='Restore configuration from backup')
    restore_parser.add_argument('filename', help='Backup filename to restore')
    
    args = parser.parse_args()
    
    if args.command == 'show':
        print_current_config()
    elif args.command == 'layouts':
        list_available_layouts()
    elif args.command == 'apply':
        apply_layout(args.layout)
    elif args.command == 'toggle-tab':
        enabled = None
        if args.enable:
            enabled = True
        elif args.disable:
            enabled = False
        toggle_tab(args.tab_id, enabled)
    elif args.command == 'toggle-module':
        enabled = None
        if args.enable:
            enabled = True
        elif args.disable:
            enabled = False
        toggle_module(args.tab_id, args.module_id, enabled)
    elif args.command == 'backup':
        backup_config(args.filename)
    elif args.command == 'restore':
        restore_config(args.filename)
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 