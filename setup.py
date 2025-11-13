#!/usr/bin/env python3
"""
Quick setup script for Lidarr Music Importer
"""

import os
import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is 3.7+"""
    if sys.version_info < (3, 7):
        print("❌ Error: Python 3.7 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version OK: {sys.version.split()[0]}")
    return True

def install_requirements():
    """Install required packages"""
    print("\n📦 Installing required packages...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements")
        return False

def setup_config():
    """Create configuration file from template"""
    config_template = "config.template.py"
    config_file = "config.py"
    
    if os.path.exists(config_file):
        print(f"⚠️  Configuration file {config_file} already exists")
        return True
    
    if not os.path.exists(config_template):
        print(f"❌ Template file {config_template} not found")
        return False
    
    try:
        shutil.copy2(config_template, config_file)
        print(f"✅ Created configuration file: {config_file}")
        print(f"   📝 Please edit {config_file} with your Lidarr settings")
        return True
    except Exception as e:
        print(f"❌ Failed to create config file: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported"""
    print("\n🔍 Testing package imports...")
    required_modules = ["requests", "musicbrainzngs", "tqdm"]
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module} - not available")
            return False
    
    return True

def main():
    print("🎵 Lidarr Music Importer Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # NOTE: Do not attempt to install requirements automatically when this
    # script is executed as part of a package build (pip / PEP 517). Installing
    # dependencies from inside setup scripts can fail in isolated build
    # environments where `pip` may not be available. Instead, instruct users
    # and CI to install the requirements explicitly.
    print("\n📦 Please install project requirements manually before running setup:")
    print("   python -m pip install -r requirements.txt")

    # Setup configuration (create config.py from template if missing)
    setup_config()
    
    print("\n" + "=" * 40)
    print("🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Edit config.py with your Lidarr settings")
    print("2. Test connection: py -3 scripts/test_lidarr_connection.py")
    print("3. Run example: py -3 scripts/add_albums_to_lidarr.py examples/example_albums.csv --dry-run")
    print("\n📖 See README.md for detailed usage instructions")

if __name__ == "__main__":
    main()