#!/usr/bin/env python3
"""
Installation Test Script
========================
Verifies that all dependencies are installed correctly.
"""

import sys

def test_imports():
    """Test that all required packages can be imported"""
    print("Testing package imports...")
    
    packages = [
        ('streamlit', 'Streamlit'),
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('folium', 'Folium'),
        ('shapely', 'Shapely'),
    ]
    
    optional_packages = [
        ('google.cloud.bigquery', 'BigQuery (optional)'),
        ('geopandas', 'GeoPandas (optional)'),
    ]
    
    failed = []
    
    # Test required packages
    print("\n--- Required Packages ---")
    for module, name in packages:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} - NOT INSTALLED")
            failed.append(name)
    
    # Test optional packages
    print("\n--- Optional Packages ---")
    for module, name in optional_packages:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"⚠️  {name} - not installed (optional)")
    
    return failed

def test_data_files():
    """Test that data files exist"""
    from pathlib import Path
    
    print("\n--- Data Files ---")
    data_dir = Path(__file__).parent / "data"
    
    required_files = [
        "clustering_live_02042026.csv",
        "hub_Lat_Long02042026.csv"
    ]
    
    missing = []
    
    for filename in required_files:
        filepath = data_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size / (1024 * 1024)  # MB
            print(f"✅ {filename} ({size:.2f} MB)")
        else:
            print(f"❌ {filename} - NOT FOUND")
            missing.append(filename)
    
    return missing

def test_modules():
    """Test that custom modules can be imported"""
    print("\n--- Custom Modules ---")
    sys.path.insert(0, str(Path(__file__).parent / "modules"))
    
    modules = [
        'data_loader',
        'map_renderer',
        'cost_analyzer',
        'utils'
    ]
    
    failed = []
    
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name} - {str(e)}")
            failed.append(module_name)
    
    return failed

def test_python_version():
    """Test Python version"""
    print("\n--- Python Version ---")
    version = sys.version_info
    
    if version >= (3, 8):
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (3.8+ required)")
        return False

def main():
    """Run all tests"""
    from pathlib import Path
    
    print("=" * 60)
    print("HUB CLUSTER OPTIMIZER - INSTALLATION TEST")
    print("=" * 60)
    
    # Test Python version
    python_ok = test_python_version()
    
    # Test imports
    failed_packages = test_imports()
    
    # Test data files
    missing_files = test_data_files()
    
    # Test custom modules
    failed_modules = test_modules()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if python_ok and not failed_packages and not missing_files and not failed_modules:
        print("✅ All tests passed! You're ready to run the app.")
        print("\nNext steps:")
        print("  1. Run: streamlit run app.py")
        print("  2. Open browser to http://localhost:8501")
        print("  3. Click 'Load Data' in the sidebar")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        
        if failed_packages:
            print(f"\nMissing packages: {', '.join(failed_packages)}")
            print("Fix: pip install -r requirements.txt")
        
        if missing_files:
            print(f"\nMissing data files: {', '.join(missing_files)}")
            print("Fix: Ensure data files are in the 'data/' directory")
        
        if failed_modules:
            print(f"\nFailed custom modules: {', '.join(failed_modules)}")
            print("Fix: Check that all module files are present in 'modules/' directory")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
