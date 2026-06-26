#!/usr/bin/env python3
"""
Script to add dependency checks to all test functions

This script:
1. Finds all test files
2. Adds import for check_test_dependencies
3. Adds dependency check call at start of each test function
4. Determines dependencies based on test name and content
"""

import re
from pathlib import Path
from typing import List, Tuple

def determine_dependencies(test_name: str, test_content: str) -> Tuple[bool, bool, bool]:
    """Determine what dependencies a test needs based on name and content"""
    test_lower = test_name.lower()
    content_lower = test_content.lower()
    
    requires_llm = (
        'llm' in test_lower or
        'french' in test_lower or
        'translation' in test_lower or
        'summary' in test_lower or
        'format' in test_lower or
        'pdf' in test_lower or
        'html' in test_lower or
        'llm' in content_lower[:500]  # Check first 500 chars
    )
    
    requires_smtp = (
        'email' in test_lower or
        'smtp' in test_lower or
        'email' in content_lower[:500]
    )
    
    requires_slack = (
        'slack' in test_lower or
        'slack' in content_lower[:500]
    )
    
    return requires_llm, requires_smtp, requires_slack


def add_dependency_check_to_file(file_path: Path) -> Tuple[bool, str]:
    """Add dependency checks to all test functions in a file"""
    try:
        content = file_path.read_text()
        
        # Skip if already has dependency checks
        if 'check_test_dependencies' in content:
            return False, "Already has dependency checks"
        
        # Skip conftest and setup files
        if 'conftest' in file_path.name or 'setup' in file_path.name:
            return False, "Skipping conftest/setup file"
        
        lines = content.split('\n')
        new_lines = []
        i = 0
        
        # Add imports
        imports_added = False
        sys_import_idx = -1
        pathlib_import_idx = -1
        
        while i < len(lines):
            line = lines[i]
            
            # Track import positions
            if line.strip().startswith('import sys') or line.strip().startswith('from sys'):
                sys_import_idx = i
            if 'Path' in line and ('from pathlib' in line or 'import pathlib' in line):
                pathlib_import_idx = i
            
            # Find last import block
            if (line.strip().startswith('import ') or line.strip().startswith('from ')) and not imports_added:
                # Check if we need to add sys and pathlib imports
                if sys_import_idx == -1 and 'sys' not in content:
                    # Add after this import
                    new_lines.append(line)
                    i += 1
                    if i < len(lines) and lines[i].strip() == '':
                        new_lines.append('')
                        i += 1
                    new_lines.append('import sys')
                    new_lines.append('')
                    new_lines.append('# Add project root to path')
                    new_lines.append('project_root = Path(__file__).parent.parent.parent')
                    new_lines.append('sys.path.insert(0, str(project_root))')
                    new_lines.append('')
                    new_lines.append('from tests.utils.test_helpers import check_test_dependencies')
                    imports_added = True
                    continue
                elif 'from tests.utils.test_helpers import check_test_dependencies' not in content:
                    # Add import after existing imports
                    new_lines.append(line)
                    i += 1
                    # Skip blank lines after import
                    while i < len(lines) and lines[i].strip() == '':
                        new_lines.append('')
                        i += 1
                    if not imports_added:
                        if 'sys.path.insert' not in content:
                            new_lines.append('import sys')
                            new_lines.append('')
                            new_lines.append('# Add project root to path')
                            new_lines.append('project_root = Path(__file__).parent.parent.parent')
                            new_lines.append('sys.path.insert(0, str(project_root))')
                            new_lines.append('')
                        new_lines.append('from tests.utils.test_helpers import check_test_dependencies')
                        imports_added = True
                        continue
            
            # Find test function definitions
            test_func_match = re.match(r'^(\s*)def (test_\w+)\([^)]*\):\s*$', line)
            if test_func_match:
                indent = test_func_match.group(1)
                test_name = test_func_match.group(2)
                
                # Get function content to determine dependencies
                func_content = line
                j = i + 1
                # Get next 20 lines for context
                context_lines = []
                while j < len(lines) and len(context_lines) < 20:
                    context_lines.append(lines[j])
                    j += 1
                context = '\n'.join(context_lines)
                
                requires_llm, requires_smtp, requires_slack = determine_dependencies(test_name, context)
                
                # Add the function definition
                new_lines.append(line)
                i += 1
                
                # Skip docstring if present
                if i < len(lines) and '"""' in lines[i]:
                    new_lines.append(lines[i])
                    i += 1
                    while i < len(lines) and '"""' not in lines[i]:
                        new_lines.append(lines[i])
                        i += 1
                    if i < len(lines):
                        new_lines.append(lines[i])
                        i += 1
                
                # Skip blank lines
                while i < len(lines) and lines[i].strip() == '':
                    new_lines.append('')
                    i += 1
                
                # Add dependency check
                new_lines.append(f'{indent}# CRITICAL: Check dependencies BEFORE any test logic')
                new_lines.append(f'{indent}check_test_dependencies(')
                new_lines.append(f'{indent}    requires_llm={str(requires_llm).lower()},')
                new_lines.append(f'{indent}    requires_smtp={str(requires_smtp).lower()},')
                new_lines.append(f'{indent}    requires_slack={str(requires_slack).lower()},')
                new_lines.append(f'{indent}    requires_api=True,')
                new_lines.append(f'{indent}    test_name="{test_name}"')
                new_lines.append(f'{indent})')
                new_lines.append('')
                continue
            
            new_lines.append(line)
            i += 1
        
        # Write updated content
        new_content = '\n'.join(new_lines)
        if new_content != content:
            file_path.write_text(new_content)
            return True, "Updated"
        else:
            return False, "No changes needed"
            
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Main function to process all test files"""
    test_dirs = [
        Path('tests/application'),
        Path('tests/integration'),
        Path('tests/system')
    ]
    
    test_files = []
    for test_dir in test_dirs:
        if test_dir.exists():
            test_files.extend(test_dir.rglob('test_*.py'))
    
    print(f"Found {len(test_files)} test files")
    
    updated = 0
    skipped = 0
    errors = 0
    
    for test_file in sorted(test_files):
        if 'conftest' in test_file.name:
            continue
        
        success, message = add_dependency_check_to_file(test_file)
        if success:
            updated += 1
            print(f"✅ {test_file}: {message}")
        elif "Already" in message or "Skipping" in message:
            skipped += 1
        else:
            errors += 1
            print(f"❌ {test_file}: {message}")
    
    print(f"\nSummary: {updated} updated, {skipped} skipped, {errors} errors")


if __name__ == '__main__':
    main()

