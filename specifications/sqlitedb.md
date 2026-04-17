# `.sqlitedb` Raster Tile Format

SAS.Planet / RMaps / "BigPlanet"-style container, read by a range of Android
map viewers (Locus, OsmAnd, AlpineQuest, GuruMaps, etc.).

## Container

- **File:** SQLite 3 database.
- **Extension:** `.sqlitedb`.
- **Text encoding:** UTF-8 or UTF-16LE, both accepted.

## Schema

```sql
CREATE TABLE tiles (
    x     INT,
    y     INT,
    z     INT,
    s     INT,
    image BLOB,
    PRIMARY KEY (x, y, z, s)
);

CREATE TABLE info (
    maxzoom INT,
    minzoom INT
);
```

Exactly two tables. No indices beyond the primary key.

### `tiles`

| Column  | Meaning                                                                  |
|---------|--------------------------------------------------------------------------|
| `x`     | Tile column, standard Google/OSM XYZ indexing (origin NW, 2^osm_z wide). |
| `y`     | Tile row, standard Google/OSM XYZ (origin N, increasing south).          |
| `z`     | **Inverted** zoom: `z = 17 − osm_z`.                                     |
| `s`     | Storage slot / layer. Reserved; use `0`.                                 |
| `image` | Raw tile bytes. JPEG or PNG; may mix per tile.                           |

### `info`

One row. `minzoom` / `maxzoom` are the smallest and largest `tiles.z` values
present, in the **inverted** `z` space. Lower `z` = deeper detail.

## Zoom convention

```
stored_z = 17 − osm_z        osm_z = 17 − stored_z
```

## Tile geometry

- **Projection:** Web Mercator (EPSG:3857).
- **Tile indexing:** standard XYZ (same numbering as OSM / Google).
- **Tile pixel size:** 256 × 256 or 512 × 512 (the latter is the "retina" / 2×
  variant).
  Effective ground resolution at osm zoom `z`:
  `gsd = 156543.03392 / (2^z × retina)` metres/pixel at the equator
  (`retina = tile_px / 256`).
- **Encoding:** JPEG (RGB) or PNG (RGBA); may mix per tile.
- **Coverage:** sparse — only tiles containing data are stored; missing
  `(x, y, z)` means "no data".

## Lookup

Readers query tiles as:

```sql
SELECT image FROM tiles WHERE x = ? AND y = ? AND z = ? AND s = 0;
```

Duplicate `(x, y, z, s)` is an error — the primary key enforces uniqueness.
Writers should use `INSERT OR REPLACE`.
