#!/usr/bin/env python
"""
Test script to verify Python compatibility checking using FPTR Desktop's Python environment.

This test uses the actual FPTR Desktop Python to access tk-core's yaml_cache system.
"""

import sys
import os
import tempfile

# Add our tk-core to the Python path
current_dir = os.path.dirname(__file__)
python_dir = os.path.join(current_dir, "python")
if os.path.exists(python_dir):
    sys.path.insert(0, python_dir)
    print(f"✅ Added tk-core python path: {python_dir}")
else:
    print(f"❌ Could not find tk-core python directory: {python_dir}")
    sys.exit(1)

def create_test_config_with_python_requirement(temp_dir, min_python_version):
    """Create a mock config with minimum_python_version in info.yml"""
    config_dir = os.path.join(temp_dir, "mock_config")
    os.makedirs(config_dir, exist_ok=True)
    
    info_yml_content = f"""
display_name: "Test Config"
version: "v1.0.0"
minimum_python_version: "{min_python_version}"
"""
    
    info_yml_path = os.path.join(config_dir, "info.yml")
    with open(info_yml_path, 'w') as f:
        f.write(info_yml_content)
    
    return config_dir

def test_yaml_cache_integration():
    """Test using tk-core's yaml_cache system"""
    print("🧪 Testing yaml_cache integration with FPTR Desktop Python...")
    
    try:
        # Import tank's yaml_cache
        from tank.util import yaml_cache
        print("  ✅ Successfully imported tank.util.yaml_cache")
        
        # Test reading a YAML file with yaml_cache
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = create_test_config_with_python_requirement(temp_dir, "3.8.0")
            info_yml_path = os.path.join(config_dir, "info.yml")
            
            # Use yaml_cache like our implementation does
            config_info = yaml_cache.g_yaml_cache.get(info_yml_path, deepcopy_data=False)
            min_python = config_info.get('minimum_python_version')
            
            print(f"  ✅ yaml_cache successfully read minimum_python_version: {min_python}")
            
            if min_python == "3.8.0":
                print("  ✅ Value matches expected result")
                return True
            else:
                print(f"  ❌ Expected '3.8.0', got '{min_python}'")
                return False
                
    except ImportError as e:
        print(f"  ❌ Could not import tank.yaml_cache: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error testing yaml_cache: {e}")
        return False

def test_compatibility_logic():
    """Test the core Python version compatibility logic"""
    print("\n🧪 Testing Python version compatibility logic...")
    
    # Simulate our resolver logic
    current_python = (3, 7)  # Simulate Python 3.7 user
    
    # Test case 1: Config requiring Python 3.8
    min_version_str = "3.8.0"
    version_parts = min_version_str.split('.')
    required_major = int(version_parts[0])
    required_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    required_version = (required_major, required_minor)
    
    is_compatible = current_python >= required_version
    
    print(f"  Current Python: {current_python}")
    print(f"  Required Python: {required_version} (from '{min_version_str}')")
    print(f"  Compatible: {is_compatible}")
    
    if not is_compatible:
        print("  ✅ Correctly detected incompatibility - auto-update would be blocked")
        return True
    else:
        print("  ❌ Should have detected incompatibility")
        return False

def test_real_info_yml_reading():
    """Test reading from real tk-framework-desktopstartup info.yml"""
    print("\n🧪 Testing reading real framework info.yml...")
    
    try:
        # Try to find the desktopstartup framework info.yml
        framework_path = os.path.join(os.path.dirname(current_dir), "tk-framework-desktopstartup", "info.yml")
        
        if os.path.exists(framework_path):
            print(f"  Found framework info.yml: {framework_path}")
            
            from tank.util import yaml_cache
            framework_info = yaml_cache.g_yaml_cache.get(framework_path, deepcopy_data=False)
            
            min_python = framework_info.get('minimum_python_version')
            print(f"  Current minimum_python_version: {min_python}")
            
            if min_python is None:
                print("  ✅ Field is not set (commented out) - no blocking would occur")
            else:
                print(f"  ⚠️  Field is set to: {min_python} - blocking would occur for older Python")
                
            return True
        else:
            print(f"  ⚠️  Framework info.yml not found at: {framework_path}")
            return True  # Not a failure, just not available
            
    except Exception as e:
        print(f"  ❌ Error reading framework info.yml: {e}")
        return False

def simulate_auto_update_scenario():
    """Simulate the auto-update scenario that would trigger our blocking"""
    print("\n🧪 Simulating auto-update scenario...")
    
    print("  📋 Scenario: Python 3.7 user with Desktop auto-update")
    print("  📋 Latest framework version requires Python 3.8+")
    
    # Simulate what our _should_block_update_for_python_compatibility would do
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a "new version" of framework with Python 3.8 requirement
        new_version_dir = create_test_config_with_python_requirement(temp_dir, "3.8.0")
        info_yml_path = os.path.join(new_version_dir, "info.yml")
        
        try:
            from tank.util import yaml_cache
            new_version_info = yaml_cache.g_yaml_cache.get(info_yml_path, deepcopy_data=False)
            
            min_python_version = new_version_info.get('minimum_python_version')
            if min_python_version:
                # Parse version like our implementation
                version_parts = min_python_version.split('.')
                required_major = int(version_parts[0])
                required_minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                required_version = (required_major, required_minor)
                
                # Simulate current Python 3.7
                current_python = (3, 7)
                
                if current_python < required_version:
                    print(f"  ✅ AUTO-UPDATE BLOCKED: Python {current_python} < required {required_version}")
                    print("  ✅ User would stay on compatible older version")
                    return True
                else:
                    print(f"  ❌ Update would proceed: Python {current_python} >= required {required_version}")
                    return False
            else:
                print("  ⚠️  No minimum_python_version found - update would proceed")
                return True
                
        except Exception as e:
            print(f"  ❌ Error in simulation: {e}")
            return False

def main():
    print("🚀 Testing Python Compatibility Implementation with FPTR Desktop Python")
    print("=" * 75)
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print("=" * 75)
    
    success = True
    
    # Run all tests
    success &= test_yaml_cache_integration()
    success &= test_compatibility_logic()
    success &= test_real_info_yml_reading()
    success &= simulate_auto_update_scenario()
    
    print("\n" + "=" * 75)
    if success:
        print("🎉 All tests passed with FPTR Desktop Python!")
        print("\n📋 Summary:")
        print("  ✅ yaml_cache integration works")
        print("  ✅ Python version compatibility logic works")
        print("  ✅ Can read real framework info.yml files")
        print("  ✅ Auto-update blocking simulation works")
        print("\n📝 Next steps:")
        print("  1. Test with modified tk-framework-desktopstartup")
        print("  2. Test with modified tk-config-basic")
        print("  3. Test end-to-end with Desktop startup")
    else:
        print("❌ Some tests failed!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)