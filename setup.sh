#!/bin/bash

# TOKYO SIGINT Setup Script
# Automatically installs dependencies and builds the OOT module

echo "------------------------------------------------"
echo "🚀 Starting TOKYO SIGINT Setup"
echo "------------------------------------------------"

# 1. Install Python Dependencies
echo "📦 Installing Python libraries..."
pip3 install pyzmq vosk deep-translator noisereduce scipy numpy pyrtlsdr

# 2. Build and Install GNU Radio OOT Module
echo "🛠️  Building gr-nrp OOT module..."

if [ -d "gr-nrp" ]; then
    cd gr-nrp
    # Remove old build directory if it exists to ensure a clean build
    rm -rf build
    mkdir build
    cd build
    
    echo "⚙️  Running CMake..."
    cmake ..
    
    echo "🔨 Compiling..."
    # Use all available CPU cores for speed
    make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)
    
    echo "📥 Installing module..."
    sudo make install
    
    # Update shared library cache (Linux specific)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo ldconfig
    fi
    
    cd ../..
    echo "✅ OOT Module installed successfully."
else
    echo "❌ Error: gr-nrp directory not found!"
    exit 1
fi

echo "------------------------------------------------"
echo "🎉 Setup Complete!"
echo "------------------------------------------------"
echo "Instructions:"
echo "1. Place your Vosk Japanese model in the 'model/' directory."
echo "2. Run the GNU Radio flowgraph (Numerical Research Project.grc)."
echo "3. Run the dashboard: python3 dashboard.py"
