#!/usr/bin/env python3
"""
DCS Unit/Group XML Extractor
Extracts the latest XML mapping data from DCS.log file and saves it to a standalone XML file.
"""

import re
import os
import sys
from datetime import datetime
from typing import List, Optional

class DCSXMLExtractor:
    def __init__(self, log_file_path: str = "dcs.log", output_file: str = "unit_group_mapping.xml"):
        self.log_file_path = log_file_path
        self.output_file = output_file
        self.start_marker = "=== DCS_MAPPER_XML_START ==="
        self.end_marker = "=== DCS_MAPPER_XML_END ==="
        
    def extract_xml_blocks(self) -> List[dict]:
        """Extract all XML blocks from the DCS log file."""
        xml_blocks = []
        
        if not os.path.exists(self.log_file_path):
            print(f"Error: Log file '{self.log_file_path}' not found.")
            return xml_blocks
            
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()
                
            current_xml = []
            in_xml_block = False
            current_timestamp = None
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Check for start marker
                if self.start_marker in line:
                    in_xml_block = True
                    current_xml = []
                    # Extract timestamp from the log line
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
                    current_timestamp = timestamp_match.group(1) if timestamp_match else f"Line {line_num}"
                    continue
                    
                # Check for end marker
                elif self.end_marker in line:
                    if in_xml_block and current_xml:
                        # Join the XML lines and clean them
                        xml_content = []
                        for xml_line in current_xml:
                            # Remove the DCS log prefix (timestamp, INFO SCRIPTING, etc.)
                            clean_line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} INFO\s+SCRIPTING \(Main\): ', '', xml_line)
                            if clean_line.strip():
                                xml_content.append(clean_line)
                        
                        if xml_content:
                            xml_blocks.append({
                                'timestamp': current_timestamp,
                                'line_number': line_num,
                                'xml_content': '\n'.join(xml_content)
                            })
                    
                    in_xml_block = False
                    current_xml = []
                    current_timestamp = None
                    
                # Collect XML content
                elif in_xml_block:
                    current_xml.append(line)
                    
        except Exception as e:
            print(f"Error reading log file: {e}")
            
        return xml_blocks
    
    def get_latest_xml(self) -> Optional[str]:
        """Get the most recent XML block from the log."""
        xml_blocks = self.extract_xml_blocks()
        
        if not xml_blocks:
            print("No XML blocks found in the log file.")
            return None
            
        # Return the latest XML block
        latest_block = xml_blocks[-1]
        print(f"Found {len(xml_blocks)} XML blocks in log file.")
        print(f"Using latest block from {latest_block['timestamp']} (line {latest_block['line_number']})")
        
        return latest_block['xml_content']
    
    def save_xml_file(self, xml_content: str) -> bool:
        """Save the XML content to a file."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as file:
                file.write(xml_content)
            return True
        except Exception as e:
            print(f"Error writing XML file: {e}")
            return False
    
    def extract_and_save(self) -> bool:
        """Main method to extract and save the latest XML data."""
        print(f"DCS Unit/Group XML Extractor")
        print(f"Source: {self.log_file_path}")
        print(f"Output: {self.output_file}")
        print("-" * 50)
        
        # Extract the latest XML
        xml_content = self.get_latest_xml()
        if not xml_content:
            return False
            
        # Save to file
        if self.save_xml_file(xml_content):
            print(f"✓ XML data successfully extracted to: {self.output_file}")
            
            # Display file info
            file_size = os.path.getsize(self.output_file)
            print(f"✓ File size: {file_size} bytes")
            
            # Show a preview of the content
            print("\nXML Preview:")
            print("-" * 30)
            lines = xml_content.split('\n')
            for i, line in enumerate(lines[:10]):  # Show first 10 lines
                print(line)
            if len(lines) > 10:
                print(f"... and {len(lines) - 10} more lines")
                
            return True
        else:
            print("✗ Failed to save XML file")
            return False
            
    def show_all_blocks_info(self):
        """Display information about all XML blocks found."""
        xml_blocks = self.extract_xml_blocks()
        
        if not xml_blocks:
            print("No XML blocks found in the log file.")
            return
            
        print(f"Found {len(xml_blocks)} XML blocks:")
        print("-" * 60)
        
        for i, block in enumerate(xml_blocks, 1):
            # Extract mission time from XML content
            mission_time_match = re.search(r'mission_time="([^"]+)"', block['xml_content'])
            mission_time = mission_time_match.group(1) if mission_time_match else "Unknown"
            
            # Count units and groups
            group_count = len(re.findall(r'<group ', block['xml_content']))
            unit_count = len(re.findall(r'<unit ', block['xml_content']))
            
            print(f"{i:3d}. {block['timestamp']} | Mission Time: {mission_time:>10} | "
                  f"Groups: {group_count:2d} | Units: {unit_count:2d}")

def main():
    """Main function with command line argument handling."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract XML mapping data from DCS log file')
    parser.add_argument('--log', '-l', default='dcs.log', 
                       help='DCS log file path (default: dcs.log)')
    parser.add_argument('--output', '-o', default='unit_group_mapping.xml',
                       help='Output XML file path (default: unit_group_mapping.xml)')
    parser.add_argument('--list', action='store_true',
                       help='List all XML blocks found in the log file')
    
    args = parser.parse_args()
    
    extractor = DCSXMLExtractor(args.log, args.output)
    
    if args.list:
        extractor.show_all_blocks_info()
    else:
        success = extractor.extract_and_save()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 