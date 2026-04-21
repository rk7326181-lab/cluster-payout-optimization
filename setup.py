#!/usr/bin/env python3
"""
Automated Setup Script
======================
Sets up the Hub Cluster Optimizer with one command.
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(step_num, text):
    """Print step indicator"""
    print(f"\n[{step_num}/5] {text}...")

def run_command(command, description):
    """Run shell command and handle errors"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is adequate"""
    version = sys.version_info
    if version >= (3, 8):
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} detected. 3.8+ required.")
        return False

def install_dependencies():
    """Install Python packages from requirements.txt"""
    print_step(2, "Installing Python dependencies")
    
    # Upgrade pip first
    run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Upgraded pip"
    )
    
    # Install requirements
    success = run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installed all dependencies"
    )
    
    return success

def create_directories():
    """Create necessary directories"""
    print_step(3, "Creating directory structure")
    
    directories = [
        'data',
        'config',
        'assets',
        'outputs',
        'logs'
    ]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Created {dir_name}/")
    
    return True

def setup_config():
    """Setup configuration files"""
    print_step(4, "Setting up configuration")
    
    # Copy .env.example to .env if it doesn't exist
    env_example = Path('.env.example')
    env_file = Path('.env')
    
    if env_example.exists() and not env_file.exists():
        import shutil
        shutil.copy(env_example, env_file)
        print("✅ Created .env from template")
    elif env_file.exists():
        print("✅ .env already exists")
    
    return True

def verify_data_files():
    """Check if data files exist"""
    print_step(5, "Verifying data files")
    
    data_dir = Path('data')
    required_files = [
        'clustering_live_02042026.csv',
        'hub_Lat_Long02042026.csv'
    ]
    
    all_present = True
    for filename in required_files:
        filepath = data_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / (1024 * 1024)
            print(f"✅ {filename} ({size:.2f} MB)")
        else:
            print(f"⚠️  {filename} not found (optional)")
            all_present = False
    
    if not all_present:
        print("\nNote: Sample data files are optional.")
        print("You can add your own CSV files to the data/ directory.")
    
    return True

def run_tests():
    """Run installation tests"""
    print("\n" + "=" * 60)
    print("  Running Installation Tests")
    print("=" * 60 + "\n")
    
    # Run test script
    try:
        result = subprocess.run(
            [sys.executable, 'test_installation.py'],
            check=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Could not run tests: {e}")
        return False

def print_next_steps():
    """Print what to do next"""
    print("\n" + "=" * 60)
    print("  SETUP COMPLETE! 🎉")
    print("=" * 60 + "\n")
    
    print("Next steps:\n")
    print("1. Run the application:")
    print("   $ streamlit run app.py\n")
    print("2. Open browser to: http://localhost:8501\n")
    print("3. In the sidebar:")
    print("   - Select data source")
    print("   - Click 'Load Data'")
    print("   - Start exploring!\n")
    
    print("Documentation:")
    print("  - Quick Start: QUICKSTART.md")
    print("  - User Guide:  USER_GUIDE.md")
    print("  - Deployment:  DEPLOYMENT.md\n")
    
    print("Optional:")
    print("  - For BigQuery: Add credentials to config/credentials.json")
    print("  - For deployment: See DEPLOYMENT.md\n")

def main():
    """Main setup process"""
    print_header("HUB CLUSTER OPTIMIZER - AUTOMATED SETUP")
    
    # Step 1: Check Python version
    print_step(1, "Checking Python version")
    if not check_python_version():
        print("\n❌ Setup failed: Python 3.8+ required")
        return 1
    
    # Step 2: Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed: Could not install dependencies")
        print("Try manually: pip install -r requirements.txt")
        return 1
    
    # Step 3: Create directories
    if not create_directories():
        print("\n❌ Setup failed: Could not create directories")
        return 1
    
    # Step 4: Setup config
    if not setup_config():
        print("\n❌ Setup failed: Could not setup configuration")
        return 1
    
    # Step 5: Verify data
    verify_data_files()
    
    # Run tests
    tests_passed = run_tests()
    
    # Print next steps
    print_next_steps()
    
    if tests_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed, but basic setup is complete.")
        print("   You can still run the app, but some features may not work.")
        return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
