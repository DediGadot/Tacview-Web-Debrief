#!/usr/bin/env python3
"""
DCS Unit/Group XML Extractor
Extracts the latest XML mapping data from DCS.log file and saves it to a standalone XML file.
Enhanced to handle chunked XML output and provide comprehensive debugging.
"""

import re
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Dict
import argparse

class DCSXMLExtractor:
    def __init__(self, log_file_path: str = "dcs.log", output_file: str = "unit_group_mapping.xml"):
        self.log_file_path = log_file_path
        self.output_file = output_file
        self.start_marker = "=== DCS_MAPPER_XML_START ==="
        self.end_marker = "=== DCS_MAPPER_XML_END ==="
        self.chunk_pattern = r'XML_CHUNK_(\d+)_OF_(\d+): (.*)'
        self.verify_pattern = r'DCS_MAPPER_VERIFY: XML written with (\d+) characters, (\d+) groups, (\d+) units'
        
    def debug_log(self, message: str, level: str = "INFO"):
        """Enhanced debug logging with timestamps."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        
        if level == "ERROR":
            # Write errors to stderr so they can be captured by subprocess
            print(log_message, file=sys.stderr)
        else:
            print(log_message)
        
    def extract_xml_blocks(self) -> List[Dict]:
        """Extract all XML blocks from the DCS log file, handling both regular and chunked output."""
        xml_blocks = []
        
        if not os.path.exists(self.log_file_path):
            self.debug_log(f"Log file '{self.log_file_path}' not found.", "ERROR")
            return xml_blocks
            
        self.debug_log(f"Reading log file: {self.log_file_path}")
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()
                
            self.debug_log(f"Read {len(lines)} lines from log file")
                
            current_xml = []
            in_xml_block = False
            current_timestamp = None
            current_chunks = {}
            expected_chunks = 0
            current_verification = None
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Check for start marker
                if self.start_marker in line:
                    in_xml_block = True
                    current_xml = []
                    current_chunks = {}
                    expected_chunks = 0
                    # Extract timestamp from the log line
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
                    current_timestamp = timestamp_match.group(1) if timestamp_match else f"Line {line_num}"
                    self.debug_log(f"Found XML block start at line {line_num}, timestamp: {current_timestamp}")
                    continue
                    
                # Check for end marker
                elif self.end_marker in line:
                    if in_xml_block:
                        xml_content = None
                        
                        # Handle chunked XML if we have chunks
                        if current_chunks and expected_chunks > 0:
                            self.debug_log(f"Processing chunked XML: {len(current_chunks)}/{expected_chunks} chunks")
                            if len(current_chunks) == expected_chunks:
                                # Reconstruct XML from chunks
                                reconstructed = ""
                                for i in range(1, expected_chunks + 1):
                                    if i in current_chunks:
                                        reconstructed += current_chunks[i]
                                    else:
                                        self.debug_log(f"Missing chunk {i}/{expected_chunks}", "WARNING")
                                        break
                                else:
                                    xml_content = reconstructed
                                    self.debug_log(f"Successfully reconstructed XML from {expected_chunks} chunks")
                            else:
                                self.debug_log(f"Incomplete chunked XML: {len(current_chunks)}/{expected_chunks}", "WARNING")
                        
                        # Handle regular XML if we have content
                        elif current_xml:
                            xml_content_lines = []
                            for xml_line in current_xml:
                                # Remove the DCS log prefix (timestamp, INFO SCRIPTING, etc.)
                                clean_line = re.sub(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} INFO\s+SCRIPTING \([^)]+\): ', '', xml_line)
                                if clean_line.strip():
                                    xml_content_lines.append(clean_line)
                            
                            if xml_content_lines:
                                xml_content = '\n'.join(xml_content_lines)
                                self.debug_log(f"Extracted regular XML content ({len(xml_content)} characters)")
                        
                        # Validate and store XML
                        if xml_content:
                            validation_result = self.validate_xml(xml_content)
                            xml_blocks.append({
                                'timestamp': current_timestamp,
                                'line_number': line_num,
                                'xml_content': xml_content,
                                'is_valid': validation_result['valid'],
                                'validation_error': validation_result.get('error'),
                                'verification': current_verification,
                                'was_chunked': bool(current_chunks)
                            })
                            
                            if validation_result['valid']:
                                self.debug_log(f"Valid XML block added (length: {len(xml_content)})")
                            else:
                                self.debug_log(f"Invalid XML block: {validation_result['error']}", "WARNING")
                    
                    in_xml_block = False
                    current_xml = []
                    current_chunks = {}
                    expected_chunks = 0
                    current_timestamp = None
                    current_verification = None
                    
                # Check for chunked XML
                elif in_xml_block:
                    chunk_match = re.search(self.chunk_pattern, line)
                    if chunk_match:
                        chunk_num = int(chunk_match.group(1))
                        total_chunks = int(chunk_match.group(2))
                        chunk_content = chunk_match.group(3)
                        
                        current_chunks[chunk_num] = chunk_content
                        expected_chunks = max(expected_chunks, total_chunks)
                        self.debug_log(f"Found chunk {chunk_num}/{total_chunks}")
                    else:
                        # Regular XML line
                        current_xml.append(line)
                
                # Check for verification info
                verify_match = re.search(self.verify_pattern, line)
                if verify_match:
                    current_verification = {
                        'characters': int(verify_match.group(1)),
                        'groups': int(verify_match.group(2)),
                        'units': int(verify_match.group(3))
                    }
                    
        except Exception as e:
            self.debug_log(f"Error reading log file: {e}", "ERROR")
            
        self.debug_log(f"Extracted {len(xml_blocks)} XML blocks total")
        return xml_blocks
    
    def validate_xml(self, xml_content: str) -> Dict:
        """Validate XML content and return validation result."""
        try:
            # Try to parse the XML
            root = ET.fromstring(xml_content)
            
            # Basic structure validation
            if root.tag != 'dcs_mapping':
                return {'valid': False, 'error': f"Root element should be 'dcs_mapping', found '{root.tag}'"}
            
            # Check for required attributes
            required_attrs = ['timestamp']
            for attr in required_attrs:
                if attr not in root.attrib:
                    return {'valid': False, 'error': f"Missing required attribute: {attr}"}
            
            # Check for required child elements
            groups_elem = root.find('groups')
            units_elem = root.find('units')
            
            if groups_elem is None:
                return {'valid': False, 'error': "Missing 'groups' element"}
            if units_elem is None:
                return {'valid': False, 'error': "Missing 'units' element"}
            
            # Count elements
            group_count = len(groups_elem.findall('group'))
            unit_count = len(units_elem.findall('unit'))
            
            return {
                'valid': True, 
                'group_count': group_count, 
                'unit_count': unit_count,
                'has_summary': root.find('summary') is not None
            }
            
        except ET.ParseError as e:
            return {'valid': False, 'error': f"XML parse error: {e}"}
        except Exception as e:
            return {'valid': False, 'error': f"Validation error: {e}"}
    
    def get_latest_xml(self) -> Optional[Dict]:
        """Get the most recent valid XML block from the log."""
        xml_blocks = self.extract_xml_blocks()
        
        if not xml_blocks:
            self.debug_log("No XML blocks found in the log file.", "WARNING")
            return None
        
        # Filter for valid XML blocks
        valid_blocks = [block for block in xml_blocks if block['is_valid']]
        
        if not valid_blocks:
            self.debug_log("No valid XML blocks found in the log file.", "ERROR")
            # Show invalid blocks for debugging
            for i, block in enumerate(xml_blocks[-5:], 1):  # Show last 5 invalid blocks
                self.debug_log(f"Invalid block {i}: {block['validation_error']}", "DEBUG")
            return None
            
        # Return the latest valid XML block
        latest_block = valid_blocks[-1]
        self.debug_log(f"Found {len(xml_blocks)} total XML blocks ({len(valid_blocks)} valid)")
        self.debug_log(f"Using latest valid block from {latest_block['timestamp']} (line {latest_block['line_number']})")
        
        if latest_block['verification']:
            ver = latest_block['verification']
            self.debug_log(f"Verification data: {ver['characters']} chars, {ver['groups']} groups, {ver['units']} units")
        
        return latest_block
    
    def save_xml_file(self, xml_content: str, pretty_print: bool = True) -> bool:
        """Save the XML content to a file with optional pretty printing."""
        try:
            if pretty_print:
                # Pretty print the XML
                root = ET.fromstring(xml_content)
                self.indent_xml(root)
                pretty_xml = ET.tostring(root, encoding='unicode', xml_declaration=True)
                
                with open(self.output_file, 'w', encoding='utf-8') as file:
                    file.write(pretty_xml)
            else:
                with open(self.output_file, 'w', encoding='utf-8') as file:
                    file.write(xml_content)
            
            return True
        except Exception as e:
            self.debug_log(f"Error writing XML file: {e}", "ERROR")
            return False
    
    def indent_xml(self, elem, level=0):
        """Add pretty-printing indentation to XML elements."""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent_xml(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
    
    def extract_and_save(self, pretty_print: bool = True) -> bool:
        """Main method to extract and save the latest XML data."""
        self.debug_log("DCS Unit/Group XML Extractor")
        self.debug_log(f"Source: {self.log_file_path}")
        self.debug_log(f"Output: {self.output_file}")
        self.debug_log("-" * 50)
        
        # Extract the latest XML
        latest_block = self.get_latest_xml()
        if not latest_block:
            return False
            
        xml_content = latest_block['xml_content']
        
        # Save to file
        if self.save_xml_file(xml_content, pretty_print):
            file_size = os.path.getsize(self.output_file)
            self.debug_log(f"✓ XML data successfully extracted to: {self.output_file}")
            self.debug_log(f"✓ File size: {file_size} bytes")
            self.debug_log(f"✓ Chunked XML: {latest_block['was_chunked']}")
            
            # Validate the saved file
            try:
                with open(self.output_file, 'r', encoding='utf-8') as file:
                    saved_content = file.read()
                validation = self.validate_xml(saved_content)
                
                if validation['valid']:
                    self.debug_log(f"✓ Saved XML is valid: {validation.get('group_count', 0)} groups, {validation.get('unit_count', 0)} units")
                else:
                    self.debug_log(f"✗ Saved XML validation failed: {validation['error']}", "WARNING")
                    
            except Exception as e:
                self.debug_log(f"✗ Could not validate saved file: {e}", "WARNING")
            
            # Show a preview of the content
            self.debug_log("\nXML Preview:")
            self.debug_log("-" * 30)
            lines = xml_content.split('\n')
            for i, line in enumerate(lines[:10]):  # Show first 10 lines
                self.debug_log(line)
            if len(lines) > 10:
                self.debug_log(f"... and {len(lines) - 10} more lines")
                
            return True
        else:
            self.debug_log("✗ Failed to save XML file", "ERROR")
            return False
            
    def show_all_blocks_info(self):
        """Display information about all XML blocks found."""
        xml_blocks = self.extract_xml_blocks()
        
        if not xml_blocks:
            self.debug_log("No XML blocks found in the log file.", "WARNING")
            return
            
        self.debug_log(f"Found {len(xml_blocks)} XML blocks:")
        self.debug_log("-" * 80)
        
        valid_count = 0
        chunked_count = 0
        
        for i, block in enumerate(xml_blocks, 1):
            # Extract mission time from XML content
            mission_time_match = re.search(r'mission_time="([^"]+)"', block['xml_content'])
            mission_time = mission_time_match.group(1) if mission_time_match else "Unknown"
            
            # Count units and groups
            group_count = len(re.findall(r'<group ', block['xml_content']))
            unit_count = len(re.findall(r'<unit ', block['xml_content']))
            
            # Status indicators
            status = "✓" if block['is_valid'] else "✗"
            chunked = "C" if block['was_chunked'] else " "
            
            if block['is_valid']:
                valid_count += 1
            if block['was_chunked']:
                chunked_count += 1
            
            self.debug_log(f"{i:3d}. {status}{chunked} {block['timestamp']} | Mission: {mission_time:>10} | "
                          f"Groups: {group_count:2d} | Units: {unit_count:2d}")
            
            if not block['is_valid']:
                self.debug_log(f"     Error: {block['validation_error']}")
        
        self.debug_log("-" * 80)
        self.debug_log(f"Summary: {valid_count}/{len(xml_blocks)} valid blocks, {chunked_count} chunked")


def main():
    """Main function with command line argument handling."""
    parser = argparse.ArgumentParser(description='Extract XML mapping data from DCS log file')
    parser.add_argument('--log', '-l', default='dcs.log', 
                       help='DCS log file path (default: dcs.log)')
    parser.add_argument('--output', '-o', default='unit_group_mapping.xml',
                       help='Output XML file path (default: unit_group_mapping.xml)')
    parser.add_argument('--list', action='store_true',
                       help='List all XML blocks found in the log file')
    parser.add_argument('--no-pretty', action='store_true',
                       help='Disable pretty printing of XML output')
    parser.add_argument('--debug', action='store_true',
                       help='Enable verbose debug output')
    
    args = parser.parse_args()
    
    extractor = DCSXMLExtractor(args.log, args.output)
    
    if args.list:
        extractor.show_all_blocks_info()
    else:
        success = extractor.extract_and_save(pretty_print=not args.no_pretty)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 