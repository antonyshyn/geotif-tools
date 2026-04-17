# geotif

Small collection of GeoTIFF tools, behind one CLI.

## Install

```bash
uv sync
```

## Usage

```bash
uv run geotif <command> [options]
```

Commands:

- **`sqlitedb`** — convert a GeoTIFF into a `.sqlitedb` raster-tile map
  (SAS.Planet / RMaps / BigPlanet inverted-zoom format). Every zoom level is
  resampled directly from the source with Lanczos — no cumulative blur.
- **`merge`** — merge multiple GeoTIFFs into one RGBA GeoTIFF, with later
  inputs layered on top of earlier ones. Handy for stitching a base raster
  with an overlay (e.g. roads) before tiling.

Run `uv run geotif <command> --help` for flags.

## sqlitedb

```bash
uv run geotif sqlitedb <src.tif> <out.sqlitedb> [options]
```

| Flag | Default | Meaning |
|---|---|---|
| `--min-zoom N` | auto (max − 4) | shallowest OSM zoom |
| `--max-zoom N` | auto (from source GSD) | deepest OSM zoom |
| `--tile-size 256\|512` | 512 | pixel size per tile (512 = retina) |
| `--jpeg-quality 1..100` | 90 | JPEG quality for opaque tiles |
| `--workers N` | CPU count | parallel renderers |

Example:

```bash
uv run geotif sqlitedb input.tif output.sqlitedb \
    --min-zoom 7 --max-zoom 15 \
    --jpeg-quality 90 \
    --workers 8
```

Notes:

- Input CRS can be anything rasterio reads; output is Web Mercator (EPSG:3857).
- `info.maxzoom` / `info.minzoom` are written in the inverted `z` space
  (`stored_z = 17 − osm_z`), matching reader expectations.
- Fully-transparent / fully-empty tiles are skipped. Edge tiles with partial
  transparency are stored as PNG (RGBA); opaque interior tiles as JPEG.

Container format: [`specifications/sqlitedb.md`](specifications/sqlitedb.md).

## merge

```bash
uv run geotif merge <under.tif> [<mid.tif> ...] <over.tif> <out.tif>
```

- Order matters: earlier args are UNDER, later args OVER.
- Transparent / nodata pixels of upper layers do **not** overwrite lower layers.
- All inputs are reprojected to the first input's CRS, at the finest resolution
  among them; union of their bounds becomes the output extent.
- Output is tiled LZW-compressed RGBA GeoTIFF.

## License

MIT — see [`LICENSE`](LICENSE).
