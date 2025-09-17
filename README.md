# GeoTIFF to OsmAnd SQLiteDB Converter

Convert GeoTIFF files to OsmAnd-compatible SQLiteDB format for offline map usage.

## Prerequisites

### System Requirements

- **GDAL**: Required for GeoTIFF processing
- **Python 3.9+**: For running the conversion script
- **UV**: For dependency management

### Install GDAL

**macOS (Homebrew):**
```bash
brew install gdal
```

**Ubuntu/Debian:**
```bash
sudo apt-get install gdal-bin python3-gdal
```

**Windows:**
Download from [OSGeo4W](https://trac.osgeo.org/osgeo4w/) or use conda:
```bash
conda install -c conda-forge gdal
```

## Installation

1. **Clone or download** this project
2. **Install dependencies** using UV:
   ```bash
   uv sync
   ```

### Basic Usage

```bash
# Convert GeoTIFF to OsmAnd SQLiteDB
uv run python main.py input.tif output.sqlitedb
```

### Command Line Options

```
positional arguments:
  input                 Input GeoTIFF file path
  output                Output SQLiteDB file name/path

optional arguments:
  -h, --help            Show help message
  --dpi DPI             DPI setting for conversion (default: 600)
  --zlevel ZLEVEL       Compression level for MBTiles (default: 9)
  --jpeg-quality QUALITY Convert tiles to JPEG with quality 1-100
  -v, --verbose         Enable verbose logging
  -f, --force           Overwrite output file if exists
```

### Typical Workflow

```bash
# 1. Convert high-quality PNG map
uv run python main.py detailed_map.png detailed_map.sqlitedb --dpi 600 -v

# 2. Convert with JPEG compression for smaller size
uv run python main.py large_map.tif compressed_map.sqlitedb --jpeg-quality 80

# 3. Quick conversion for testing
uv run python main.py test_map.tif test.sqlitedb --dpi 300 --zlevel 6
```
