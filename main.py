#!/usr/bin/env python3
import argparse
import io
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
from tqdm import tqdm


class TiffToOsmandConverter:
    """Convert GeoTIFF files to OsmAnd SQLiteDB format."""

    def __init__(self, dpi=600, zlevel=9, jpeg_quality=None, verbose=False):
        self.dpi = dpi
        self.zlevel = zlevel
        self.jpeg_quality = jpeg_quality
        self.verbose = verbose
        self.temp_files = []

        # Setup logging
        log_level = logging.INFO if verbose else logging.WARNING
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Check for required GDAL tools
        self._check_gdal_tools()

    def _check_gdal_tools(self):
        """Check if required GDAL tools are available."""
        required_tools = ['gdal_translate', 'gdaladdo']
        missing_tools = []

        for tool in required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)

        if missing_tools:
            raise RuntimeError(
                f"Required GDAL tools not found: {', '.join(missing_tools)}. "
                "Please install GDAL system package."
            )

    def cleanup_temp_files(self):
        """Remove temporary files."""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    self.logger.info(f"Removed temporary file: {temp_file}")
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary file {temp_file}: {e}")

    def validate_input(self, input_path):
        """Validate input GeoTIFF file."""
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file does not exist: {input_path}")

        # Check if file is readable by GDAL using gdalinfo
        try:
            result = subprocess.run(
                ['gdalinfo', input_path],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.info(f"Input file validated: {input_path}")
        except subprocess.CalledProcessError:
            raise ValueError(f"Cannot open file with GDAL: {input_path}")
        except FileNotFoundError:
            raise RuntimeError("gdalinfo not found. Please install GDAL system package.")

    def geotiff_to_mbtiles(self, input_path, output_path):
        """Convert GeoTIFF to MBTiles using GDAL."""
        self.logger.info("Starting GeoTIFF to MBTiles conversion...")

        try:
            # Convert to MBTiles using gdal_translate
            print("Converting GeoTIFF to MBTiles...")
            translate_cmd = [
                'gdal_translate',
                '-co', f'ZLEVEL={self.zlevel}',
                '-of', 'mbtiles',
                '--config', 'GDAL_PDF_DPI', str(self.dpi),
                input_path,
                output_path
            ]

            if self.verbose:
                print(f"Running: {' '.join(translate_cmd)}")

            result = subprocess.run(translate_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"gdal_translate failed: {result.stderr}")

            if self.verbose and result.stdout:
                print(f"gdal_translate output: {result.stdout}")

            # Build overviews (zoom levels) using gdaladdo with cubic resampling
            print("Generating zoom levels...")
            addo_cmd = ['gdaladdo', '-r', 'cubic', output_path]

            if self.verbose:
                print(f"Running: {' '.join(addo_cmd)}")

            result = subprocess.run(addo_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"gdaladdo failed: {result.stderr}")

            if self.verbose and result.stdout:
                print(f"gdaladdo output: {result.stdout}")

            self.logger.info(f"MBTiles file created: {output_path}")

        except FileNotFoundError as e:
            raise RuntimeError(f"GDAL tool not found. Please install GDAL system package: {e}")
        except Exception as e:
            raise RuntimeError(f"GDAL conversion failed: {e}")

    def to_jpeg(self, raw_bytes, quality):
        """Convert image bytes to JPEG format."""
        im = Image.open(io.BytesIO(raw_bytes))
        im = im.convert('RGB')
        stream = io.BytesIO()
        im.save(stream, format="JPEG", subsampling=0, quality=quality)
        return stream.getvalue()

    def mbtiles_to_osmand(self, mbtiles_path, output_path):
        """Convert MBTiles to OsmAnd SQLiteDB format."""
        self.logger.info("Starting MBTiles to OsmAnd conversion...")

        if os.path.exists(output_path):
            os.remove(output_path)
            self.logger.info(f"Removed existing output file: {output_path}")

        # Connect to databases
        source = sqlite3.connect(mbtiles_path)
        dest = sqlite3.connect(output_path)

        try:
            scur = source.cursor()
            dcur = dest.cursor()

            # Create OsmAnd table structure
            dcur.execute('''CREATE TABLE tiles (x int, y int, z int, s int, image blob, PRIMARY KEY (x,y,z,s));''')
            dcur.execute('''CREATE TABLE info (maxzoom Int, minzoom Int);''')

            # Get total number of tiles for progress bar
            scur.execute("SELECT COUNT(*) FROM tiles")
            total_tiles = scur.fetchone()[0]

            print(f"Converting {total_tiles} tiles to OsmAnd format...")

            # Convert tiles with progress bar
            with tqdm(total=total_tiles, desc="Converting tiles") as pbar:
                for row in scur.execute("SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles"):
                    image = row[3]

                    # Convert to JPEG if quality specified
                    if self.jpeg_quality is not None:
                        image = self.to_jpeg(image, self.jpeg_quality)

                    # Transform coordinates for OsmAnd format
                    z, x, y, s = int(row[0]), int(row[1]), int(row[2]), 0
                    y = 2 ** z - 1 - y  # Flip Y coordinate
                    z = 17 - z  # Invert zoom level

                    dcur.execute(
                        "INSERT INTO tiles (x, y, z, s, image) VALUES (?, ?, ?, ?, ?)",
                        [x, y, z, s, sqlite3.Binary(image)]
                    )

                    pbar.update(1)

            # Insert zoom level info
            dcur.execute("INSERT INTO info (maxzoom, minzoom) SELECT max(z), min(z) FROM tiles")
            dest.commit()

            self.logger.info(f"OsmAnd SQLiteDB file created: {output_path}")

        finally:
            source.close()
            dest.close()

    def convert(self, input_path, output_path):
        """Main conversion method."""
        try:
            # Validate input
            self.validate_input(input_path)

            # Create temporary MBTiles file
            temp_dir = tempfile.gettempdir()
            temp_mbtiles = os.path.join(temp_dir, f"temp_{os.getpid()}.mbtiles")
            self.temp_files.append(temp_mbtiles)

            # Step 1: Convert GeoTIFF to MBTiles
            self.geotiff_to_mbtiles(input_path, temp_mbtiles)

            # Step 2: Convert MBTiles to OsmAnd SQLiteDB
            self.mbtiles_to_osmand(temp_mbtiles, output_path)

            print(f"✅ Conversion completed successfully!")
            print(f"Output file: {output_path}")

        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            raise
        finally:
            # Always cleanup temporary files
            self.cleanup_temp_files()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Convert GeoTIFF files to OsmAnd SQLiteDB format',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        'input',
        help='Input GeoTIFF file path'
    )

    parser.add_argument(
        'output',
        help='Output SQLiteDB file name/path'
    )

    parser.add_argument(
        '--dpi',
        type=int,
        default=600,
        help='DPI setting for conversion'
    )

    parser.add_argument(
        '--zlevel',
        type=int,
        default=9,
        help='Compression level for MBTiles'
    )

    parser.add_argument(
        '--jpeg-quality',
        type=int,
        help='Convert tiles to JPEG with specified quality (1-100)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Overwrite output file if it exists'
    )

    args = parser.parse_args()

    # Validate JPEG quality
    if args.jpeg_quality is not None and not (1 <= args.jpeg_quality <= 100):
        parser.error("JPEG quality must be between 1 and 100")

    # Check if output file exists
    if os.path.exists(args.output) and not args.force:
        print(f"Error: Output file '{args.output}' already exists. Use -f/--force to overwrite.")
        sys.exit(1)

    # Create converter and run conversion
    converter = TiffToOsmandConverter(
        dpi=args.dpi,
        zlevel=args.zlevel,
        jpeg_quality=args.jpeg_quality,
        verbose=args.verbose
    )

    try:
        converter.convert(args.input, args.output)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
