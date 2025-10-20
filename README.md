# GridLab - Seismic Grid Transformation Tool

A comprehensive PyQt6 GUI application for transforming seismic grid data between different coordinate reference systems (CRS). Built specifically for geophysicists and seismic data analysts who need to convert coordinate systems for seismic grid files.

## 🚀 Features

### Core Functionality
- **Coordinate System Transformation**: Transform seismic grid data between any EPSG-defined coordinate systems
- **Comprehensive CRS Support**: Access to 2,500+ EPSG coordinate reference systems with search functionality
- **Batch Processing**: Convert multiple grid files simultaneously with progress tracking
- **Real-time Preview**: Live preview of transformed coordinates
- **File Format Support**: Handles both comma-separated (.dat) and fixed-width format files

### User Interface
- **Intuitive 3-Panel Layout**:
  - Left sidebar for controls and file management
  - Top-right panel for input file viewing
  - Bottom-right panel for transformation preview
- **CRS Selection Dialog**: Searchable interface for selecting input/output coordinate systems
- **File Tree View**: Browse and select grid files from any folder structure
- **Progress Tracking**: Visual progress bars for batch operations

### Advanced Features
- **Overwrite Protection**: Optional confirmation dialogs to prevent accidental file overwrites
- **Background Processing**: Non-blocking transformations using multi-threading
- **Error Handling**: Graceful fallbacks and comprehensive error reporting
- **Virtual Environment**: Pre-configured setup for easy deployment

## 📋 Requirements

- Python 3.8+
- PyQt6
- matplotlib
- numpy
- pyproj

## 🛠️ Installation

### Option 1: Using Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/bzlmnop/GridLab.git
cd GridLab

# Create virtual environment
python -m venv gridlab_env

# Activate virtual environment
# Windows:
gridlab_env\Scripts\activate
# Linux/Mac:
source gridlab_env/bin/activate

# Install dependencies
pip install PyQt6 matplotlib numpy pyproj
```

### Option 2: Direct Installation

```bash
# Install dependencies globally
pip install PyQt6 matplotlib numpy pyproj
```

## 🎯 Usage

### Basic Workflow

1. **Launch the Application**:
   ```bash
   python seismic_grid_app.py
   ```

2. **Select Coordinate Systems**:
   - Click "Select Input CRS" to choose the source coordinate system
   - Click "Select Output CRS" to choose the target coordinate system
   - Use the search bar to find specific EPSG codes or CRS names

3. **Configure File Locations**:
   - Click "Select Input Folder" to choose the folder containing your grid files
   - Click "Select Output Folder" to choose where transformed files will be saved

4. **Process Files**:
   - Browse files in the tree view
   - Click a file to preview its content and transformation
   - Use "Save Selected Output" for individual files
   - Use "Convert and Save All" for batch processing

### Supported File Formats

#### Comma-Separated Format (.dat files)
```
2069796.95394,641202.17144,1.5778
2069906.95442,641202.74858,1.5775
```

#### Fixed-Width Format (Fault files)
```
  2070376.44   658741.74      1e+030         1
  2070367.95   658740.90      1e+030         1
```

## 🔧 Configuration

### Coordinate Reference Systems

The application supports transformation between any EPSG-defined coordinate systems. Common examples:

- **EPSG:4326**: WGS84 (latitude/longitude)
- **EPSG:32025**: NAD27 Oklahoma South
- **EPSG:32104**: NAD83 Oklahoma South
- **EPSG:26913**: UTM Zone 13N NAD83
- **EPSG:3857**: Web Mercator

### Overwrite Behavior

- **Checkbox Unchecked**: Prompts for confirmation before overwriting existing files
- **Checkbox Checked**: Automatically overwrites existing files without confirmation

## 🏗️ Architecture

### Core Components

- **`seismic_grid_app.py`**: Main PyQt6 application with GUI
- **`transform_coordinates.py`**: Command-line transformation utilities
- **`CRSSelectionDialog`**: Searchable CRS selection interface
- **`TransformationWorker`**: Background processing thread
- **`OutputTextViewer`**: Text display for transformed data

### Key Classes

- **`SeismicGridApp`**: Main application window
- **`CRSSelectionDialog`**: EPSG code selection dialog
- **`TransformationWorker`**: Multi-threaded transformation processor
- **`OutputTextViewer`**: Text preview widget

## 🐛 Troubleshooting

### Common Issues

**PyQt6 Import Error**:
```bash
pip install PyQt6
```

**pyproj DLL Issues**:
- The application includes fallback transformation methods
- For precise transformations, ensure pyproj is properly installed

**File Loading Issues**:
- Ensure input files are plain text format
- Check file permissions and folder access

### Virtual Environment Issues

If you encounter issues with the virtual environment:

```bash
# Remove old environment
rmdir /s seismic_app_env

# Create new environment
python -m venv seismic_app_env
seismic_app_env\Scripts\activate
pip install PyQt6 matplotlib numpy pyproj
```

## 📊 Technical Details

### Transformation Methods

1. **Primary**: pyproj library for accurate EPSG transformations
2. **Fallback**: Coordinate shift approximations when pyproj fails

### Performance

- **Batch Processing**: Multi-threaded for large file sets
- **Memory Efficient**: Streams large files without loading entirely into memory
- **Progress Tracking**: Real-time updates for long operations

### File Handling

- **Automatic Format Detection**: Recognizes comma-separated and fixed-width formats
- **Header Preservation**: Maintains file headers and comments
- **Error Recovery**: Continues processing despite individual line errors

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is open source. Please check the license file for details.

## 📞 Support

For issues, questions, or feature requests, please create an issue in the GitHub repository.

---

**Built with ❤️ for the geophysics community**