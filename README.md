# GeoTIFF to OsmAnd SQLiteDB Converter

Convert GeoTIFF files to OsmAnd-compatible SQLiteDB format for offline map usage.

## Features

- **Complete conversion pipeline**: GeoTIFF ’ MBTiles ’ OsmAnd SQLiteDB
- **High-quality resampling**: Uses cubic interpolation for smooth zoom levels
- **Configurable parameters**: DPI, compression, and JPEG quality settings
- **Progress tracking**: Real-time progress bars and detailed logging
- **Automatic cleanup**: Removes temporary files after conversion
- **PNG optimization**: Preserves maximum quality for PNG inputs
- **Error handling**: Comprehensive validation and error reporting

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

## Usage

### Basic Usage

```bash
# Convert GeoTIFF to OsmAnd SQLiteDB
uv run python main.py input.tif output.sqlitedb
```

### High-Quality PNG Conversion (Recommended)

For maximum quality with PNG files, use these settings:

```bash
# High-quality conversion with maximum DPI
uv run python main.py map.tif map.sqlitedb --dpi 600 --zlevel 9 -v

# Ultra high-quality for detailed maps
uv run python main.py map.tif map.sqlitedb --dpi 1200 --zlevel 9 -v
```

### Advanced Usage Examples

**Custom DPI and compression:**
```bash
uv run python main.py input.tif output.sqlitedb --dpi 300 --zlevel 6
```

**Convert to JPEG for smaller file size:**
```bash
uv run python main.py input.tif output.sqlitedb --jpeg-quality 85
```

**Verbose output with custom settings:**
```bash
uv run python main.py input.tif output.sqlitedb --dpi 600 --zlevel 9 --verbose
```

**Force overwrite existing files:**
```bash
uv run python main.py input.tif output.sqlitedb --force
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

## Configuration Guidelines

### For PNG Files (Maximum Quality)

PNG files typically provide the best quality for maps with sharp details:

```bash
# Recommended settings for PNG maps
uv run python main.py map.png map.sqlitedb --dpi 600 --zlevel 9

# For very detailed maps (larger file size)
uv run python main.py map.png map.sqlitedb --dpi 1200 --zlevel 9
```

**Why these settings?**
- `--dpi 600`: High resolution for crisp details
- `--zlevel 9`: Maximum compression without quality loss
- No `--jpeg-quality`: Keeps original PNG format for best quality

### For File Size Optimization

If you need smaller files and can accept some quality loss:

```bash
# Balanced quality/size with JPEG conversion
uv run python main.py map.tif map.sqlitedb --dpi 300 --jpeg-quality 85

# Smaller files with moderate quality
uv run python main.py map.tif map.sqlitedb --dpi 300 --jpeg-quality 75 --zlevel 6
```

### Parameter Reference

| Parameter | Range | Default | Purpose |
|-----------|-------|---------|---------|
| `--dpi` | 72-2400 | 600 | Image resolution (higher = better quality, larger size) |
| `--zlevel` | 1-9 | 9 | PNG compression (9 = maximum compression) |
| `--jpeg-quality` | 1-100 | None | JPEG quality (85+ recommended, omit for PNG) |

## Output

The script generates an OsmAnd-compatible SQLiteDB file with:
- **tiles** table: Contains map tiles with OsmAnd coordinate system
- **info** table: Zoom level information (minzoom, maxzoom)

## Performance Notes

- **Conversion time** depends on input file size and DPI setting
- **High DPI values** (1200+) significantly increase processing time
- **Cubic resampling** provides better quality than nearest neighbor
- **Temporary files** are automatically cleaned up after conversion

## Troubleshooting

### Common Issues

**"GDAL tools not found" error:**
```bash
# Verify GDAL installation
which gdal_translate
which gdaladdo
```

**"Cannot open file with GDAL" error:**
- Check if the input file exists and is readable
- Verify the file is a valid GeoTIFF/raster format

**"Permission denied" error:**
- Check write permissions for the output directory
- Use `--force` to overwrite existing files

### Verbose Output

Use the `--verbose` flag to see detailed processing information:
```bash
uv run python main.py input.tif output.sqlitedb --verbose
```

This shows:
- GDAL command execution
- Processing progress
- File operations
- Cleanup activities

## Technical Details

### Conversion Process

1. **Validation**: Checks input file with GDAL
2. **GeoTIFF ’ MBTiles**: Uses `gdal_translate` with specified settings
3. **Zoom Levels**: Generates overview levels with `gdaladdo` (cubic resampling)
4. **Coordinate Transform**: Converts MBTiles to OsmAnd coordinate system
5. **Optimization**: Optional JPEG conversion for size reduction
6. **Cleanup**: Removes temporary MBTiles file

### Coordinate System

The conversion transforms coordinates from MBTiles format to OsmAnd format:
- **Y-coordinate**: Flipped (`y = 2^z - 1 - y`)
- **Zoom levels**: Inverted (`z = 17 - z`)
- **S parameter**: Set to 0 (standard for OsmAnd)

## Examples

### Typical Workflow

```bash
# 1. Convert high-quality PNG map
uv run python main.py detailed_map.png detailed_map.sqlitedb --dpi 600 -v

# 2. Convert with JPEG compression for smaller size
uv run python main.py large_map.tif compressed_map.sqlitedb --jpeg-quality 80

# 3. Quick conversion for testing
uv run python main.py test_map.tif test.sqlitedb --dpi 300 --zlevel 6
```

### File Size Expectations

| Input Size | DPI | JPEG Quality | Approx Output Size |
|------------|-----|--------------|-------------------|
| 25MB TIF | 300 | None (PNG) | 3-8MB |
| 25MB TIF | 600 | None (PNG) | 8-15MB |
| 25MB TIF | 300 | 85 | 2-5MB |
| 25MB TIF | 600 | 85 | 4-10MB |

*Actual sizes vary based on map complexity and detail level.*

## License

This project is provided as-is for converting GeoTIFF files to OsmAnd format.