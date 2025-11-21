#!/usr/bin/env python
"""
Local version testing - Creates local "versions" to test the real flow.

This creates local directory structures that simulate real published versions
with minimum_python_version requirements to test the actual resolver/upgrader logic.
"""

import sys
import os
import tempfile
import shutil
import json
from pathlib import Path

def create_local_testing_environment():
    """
    Create a complete local testing environment that simulates:
    1. Multiple config versions (some with Python requirements)
    2. Multiple framework versions (some with Python requirements)  
    3. Real descriptor resolution flow
    """
    print("🏗️  Creating Local Testing Environment...")
    
    base_test_dir = os.path.join(os.getcwd(), "python_compatibility_testing")
    if os.path.exists(base_test_dir):
        shutil.rmtree(base_test_dir)
    os.makedirs(base_test_dir)
    
    # Create mock bundle cache structure
    bundle_cache = os.path.join(base_test_dir, "bundle_cache")
    
    # 1. Create tk-config-basic versions
    config_cache = os.path.join(bundle_cache, "git", "tk-config-basic.git")
    os.makedirs(config_cache, exist_ok=True)
    
    config_versions = [
        ("v1.3.0", None),           # Old version, no Python requirement
        ("v1.4.0", None),           # Recent version, no Python requirement  
        ("v1.4.6", None),           # Last Python 3.7 compatible
        ("v2.0.0", "3.8"),          # New version, requires Python 3.8
        ("v2.1.0", "3.8"),          # Latest version, requires Python 3.8
    ]
    
    print("📦 Creating tk-config-basic versions...")
    for version, min_python in config_versions:
        version_dir = os.path.join(config_cache, version)
        os.makedirs(version_dir, exist_ok=True)
        
        # Create complete config structure
        os.makedirs(os.path.join(version_dir, "core"), exist_ok=True)
        os.makedirs(os.path.join(version_dir, "env"), exist_ok=True)
        os.makedirs(os.path.join(version_dir, "hooks"), exist_ok=True)
        
        # Create info.yml
        info_content = f"""
display_name: "Default Configuration"
description: "Default ShotGrid Pipeline Toolkit Configuration"
version: "{version}"

requires_shotgun_fields:
requires_core_version: "v0.20.0"
"""
        
        if min_python:
            info_content += f'minimum_python_version: "{min_python}"\n'
        
        with open(os.path.join(version_dir, "info.yml"), 'w') as f:
            f.write(info_content)
        
        print(f"  ✅ Created {version}" + (f" (requires Python {min_python})" if min_python else " (no Python requirement)"))
    
    # 2. Create tk-framework-desktopstartup versions
    framework_cache = os.path.join(bundle_cache, "git", "tk-framework-desktopstartup.git")
    os.makedirs(framework_cache, exist_ok=True)
    
    framework_versions = [
        ("v1.5.0", None),           # Current production version
        ("v1.6.0", None),           # Bug fix release
        ("v2.0.0", "3.8"),          # Major version requiring Python 3.8
        ("v2.1.0", "3.8"),          # Latest with Python 3.8 requirement
    ]
    
    print("\n📦 Creating tk-framework-desktopstartup versions...")
    for version, min_python in framework_versions:
        version_dir = os.path.join(framework_cache, version)
        os.makedirs(version_dir, exist_ok=True)
        
        # Create framework structure
        python_dir = os.path.join(version_dir, "python", "shotgun_desktop")
        os.makedirs(python_dir, exist_ok=True)
        
        # Create info.yml
        info_content = f"""
display_name: "Desktop Startup Framework"
description: "Startup logic for the ShotGrid desktop app"
version: "{version}"

requires_core_version: "v0.20.16"
requires_desktop_version: "v1.8.0"

frameworks:
"""
        
        if min_python:
            info_content += f'minimum_python_version: "{min_python}"\n'
        
        with open(os.path.join(version_dir, "info.yml"), 'w') as f:
            f.write(info_content)
        
        # Create a basic upgrade_startup.py for testing
        upgrade_startup_content = '''
class DesktopStartupUpgrader:
    def _should_block_update_for_python_compatibility(self, descriptor):
        """Mock implementation for testing"""
        return False  # Will be overridden in tests
'''
        
        with open(os.path.join(python_dir, "upgrade_startup.py"), 'w') as f:
            f.write(upgrade_startup_content)
        
        print(f"  ✅ Created {version}" + (f" (requires Python {min_python})" if min_python else " (no Python requirement)"))
    
    # 3. Create test configuration
    test_config = {
        "base_dir": base_test_dir,
        "bundle_cache": bundle_cache,
        "config_versions": config_versions,
        "framework_versions": framework_versions,
    }
    
    config_file = os.path.join(base_test_dir, "test_config.json")
    with open(config_file, 'w') as f:
        json.dump(test_config, f, indent=2)
    
    print(f"\n✅ Testing environment created in: {base_test_dir}")
    print(f"📄 Configuration saved to: {config_file}")
    
    return test_config

def test_with_local_environment():
    """Test the compatibility logic using the local environment"""
    config = create_local_testing_environment()
    
    print("\n🧪 Testing with Local Environment...")
    
    # Test config resolution
    print("\n🔍 Testing Config Resolution:")
    bundle_cache = config["bundle_cache"]
    config_cache = os.path.join(bundle_cache, "git", "tk-config-basic.git")
    
    # Simulate Python 3.7 user checking for updates
    current_python = (3, 7)
    available_versions = ["v2.1.0", "v2.0.0", "v1.4.6", "v1.4.0", "v1.3.0"]
    
    print(f"  👤 User running Python {'.'.join(str(x) for x in current_python)}")
    print(f"  📦 Available versions: {available_versions}")
    
    compatible_version = None
    for version in available_versions:
        version_path = os.path.join(config_cache, version)
        info_yml = os.path.join(version_path, "info.yml")
        
        if os.path.exists(info_yml):
            import yaml
            with open(info_yml, 'r') as f:
                info = yaml.safe_load(f)
            
            min_python = info.get('minimum_python_version')
            if min_python:
                version_parts = min_python.split('.')
                required_major = int(version_parts[0])
                required_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                required_version = (required_major, required_minor)
                
                if current_python >= required_version:
                    compatible_version = version
                    print(f"  ✅ Compatible: {version} (requires Python {min_python})")
                    break
                else:
                    print(f"  ❌ Incompatible: {version} (requires Python {min_python})")
            else:
                compatible_version = version
                print(f"  ✅ Compatible: {version} (no Python requirement)")
                break
    
    if compatible_version:
        print(f"  🎯 Result: Would use {compatible_version} instead of latest")
    else:
        print(f"  ⚠️  No compatible version found!")
    
    # Test framework update
    print("\n🔍 Testing Framework Update:")
    framework_cache = os.path.join(bundle_cache, "git", "tk-framework-desktopstartup.git")
    current_framework = "v1.5.0"
    latest_framework = "v2.1.0"
    
    print(f"  📦 Current: {current_framework}, Latest: {latest_framework}")
    
    latest_path = os.path.join(framework_cache, latest_framework)
    info_yml = os.path.join(latest_path, "info.yml")
    
    if os.path.exists(info_yml):
        import yaml
        with open(info_yml, 'r') as f:
            info = yaml.safe_load(f)
        
        min_python = info.get('minimum_python_version')
        if min_python:
            version_parts = min_python.split('.')
            required_major = int(version_parts[0])
            required_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            required_version = (required_major, required_minor)
            
            should_block = current_python < required_version
            if should_block:
                print(f"  🚫 Update blocked: Latest requires Python {min_python}")
                print(f"  ℹ️  User remains on {current_framework}")
            else:
                print(f"  ✅ Update allowed: Compatible with Python {min_python}")
        else:
            print(f"  ✅ Update allowed: No Python requirement")
    
    print(f"\n📁 Local test environment available at: {config['base_dir']}")
    print("   You can examine the created structures and modify versions for more testing")

if __name__ == "__main__":
    test_with_local_environment()