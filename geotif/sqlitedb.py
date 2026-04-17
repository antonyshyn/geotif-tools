"""Convert a GeoTIFF into a .sqlitedb tile map.

SAS.Planet / RMaps / BigPlanet inverted-zoom format. Every tile at every zoom
is resampled directly from the source GeoTIFF with Lanczos, so there is no
cumulative blur across zoom levels.
"""

from __future__ import annotations

import io
import math
import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np
from PIL import Image

import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds


WEB_MERCATOR_EPSG = 3857
EARTH_CIRCUMFERENCE = 2 * math.pi * 6378137.0
ORIGIN_SHIFT = EARTH_CIRCUMFERENCE / 2.0
# Container stores z inverted: stored_z = 17 - osm_z. Lower stored_z = deeper.
STORED_Z_OFFSET = 17


def tile_bounds_merc(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    n = 2 ** z
    tile_size_m = EARTH_CIRCUMFERENCE / n
    minx = -ORIGIN_SHIFT + x * tile_size_m
    maxx = minx + tile_size_m
    maxy = ORIGIN_SHIFT - y * tile_size_m
    miny = maxy - tile_size_m
    return minx, miny, maxx, maxy


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def dataset_tile_range(src_path: str, z: int) -> tuple[int, int, int, int]:
    with rasterio.open(src_path) as ds:
        l, b, r, t = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=21)
    x0, y1 = lonlat_to_tile(l, b, z)
    x1, y0 = lonlat_to_tile(r, t, z)
    return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)


def auto_max_zoom(src_path: str, tile_size: int) -> int:
    """Deepest OSM zoom where the tile pixel size >= source GSD."""
    with rasterio.open(src_path) as ds:
        with WarpedVRT(ds, crs=f"EPSG:{WEB_MERCATOR_EPSG}") as vrt:
            gsd = abs(vrt.transform.a)
    retina = tile_size // 256
    z = math.floor(math.log2(156543.03392 / (gsd * retina)))
    return max(0, min(20, int(z)))


def tiles_intersecting_source(src_path: str, z: int) -> list[tuple[int, int]]:
    with rasterio.open(src_path) as ds:
        src_bounds = transform_bounds(ds.crs, f"EPSG:{WEB_MERCATOR_EPSG}",
                                       *ds.bounds, densify_pts=21)
    sminx, sminy, smaxx, smaxy = src_bounds
    x0, x1, y0, y1 = dataset_tile_range(src_path, z)
    out = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            tminx, tminy, tmaxx, tmaxy = tile_bounds_merc(x, y, z)
            if tmaxx <= sminx or tminx >= smaxx or tmaxy <= sminy or tminy >= smaxy:
                continue
            out.append((x, y))
    return out


@dataclass
class RenderJob:
    src_path: str
    x: int
    y: int
    osm_z: int
    tile_size: int
    jpeg_quality: int


def render_tile(job: RenderJob) -> tuple[int, int, int, bytes] | None:
    minx, miny, maxx, maxy = tile_bounds_merc(job.x, job.y, job.osm_z)
    dst_transform = transform_from_bounds(minx, miny, maxx, maxy,
                                          job.tile_size, job.tile_size)

    with rasterio.open(job.src_path) as ds:
        has_alpha = any(
            ci.name == "alpha" for ci in (ds.colorinterp or [])
        ) or ds.count == 4 or ds.count == 2
        vrt_kwargs = dict(
            crs=f"EPSG:{WEB_MERCATOR_EPSG}",
            transform=dst_transform,
            width=job.tile_size,
            height=job.tile_size,
            resampling=Resampling.lanczos,
        )
        if not has_alpha:
            vrt_kwargs["add_alpha"] = True
        with WarpedVRT(ds, **vrt_kwargs) as vrt:
            count = min(vrt.count, 4)
            data = vrt.read(indexes=list(range(1, count + 1)))

    if count == 1:
        arr = np.stack([data[0]] * 3, axis=0)
        alpha = None
    elif count == 2:
        arr = np.stack([data[0]] * 3, axis=0)
        alpha = data[1]
    elif count == 3:
        arr = data
        alpha = None
    else:
        arr = data[:3]
        alpha = data[3]

    arr = np.transpose(arr, (1, 2, 0)).astype(np.uint8)

    if alpha is not None and not alpha.any():
        return None
    if alpha is None and not arr.any():
        return None

    buf = io.BytesIO()
    if alpha is not None and alpha.min() < 255:
        rgba = np.concatenate([arr, alpha[..., None]], axis=2)
        Image.fromarray(rgba, mode="RGBA").save(
            buf, format="PNG", optimize=True, compress_level=9)
    else:
        Image.fromarray(arr, mode="RGB").save(
            buf, format="JPEG", quality=job.jpeg_quality,
            subsampling=0, progressive=False)
    return (job.x, job.y, STORED_Z_OFFSET - job.osm_z, buf.getvalue())


def open_db(path: str) -> sqlite3.Connection:
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA page_size=65536")
    conn.execute(
        "CREATE TABLE tiles (x int, y int, z int, s int, image blob, "
        "PRIMARY KEY (x,y,z,s))"
    )
    conn.execute("CREATE TABLE info (maxzoom Int, minzoom Int)")
    return conn


def write_info(conn: sqlite3.Connection, osm_min: int, osm_max: int) -> None:
    stored_min = STORED_Z_OFFSET - osm_max
    stored_max = STORED_Z_OFFSET - osm_min
    conn.execute("DELETE FROM info")
    conn.execute("INSERT INTO info (maxzoom, minzoom) VALUES (?,?)",
                 (stored_max, stored_min))


def build(src_path: str, dst_path: str, osm_min: int, osm_max: int,
          tile_size: int, jpeg_quality: int, workers: int) -> None:
    conn = open_db(dst_path)
    total = 0
    try:
        for osm_z in range(osm_max, osm_min - 1, -1):
            coords = tiles_intersecting_source(src_path, osm_z)
            jobs = [
                RenderJob(src_path, x, y, osm_z, tile_size, jpeg_quality)
                for (x, y) in coords
            ]
            if coords:
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                print(f"[z={osm_z:2d}  stored_z={STORED_Z_OFFSET - osm_z:2d}] "
                      f"{len(jobs)} tiles  x=[{min(xs)}..{max(xs)}] "
                      f"y=[{min(ys)}..{max(ys)}]", flush=True)
            else:
                print(f"[z={osm_z:2d}] no tiles", flush=True)
                continue

            batch: list[tuple[int, int, int, bytes]] = []
            flush_every = 256

            def flush():
                if batch:
                    conn.executemany(
                        "INSERT OR REPLACE INTO tiles (x,y,z,s,image) "
                        "VALUES (?,?,?,0,?)",
                        batch,
                    )
                    conn.commit()
                    batch.clear()

            if workers <= 1:
                for j in jobs:
                    r = render_tile(j)
                    if r:
                        batch.append(r)
                        total += 1
                        if len(batch) >= flush_every:
                            flush()
            else:
                with ProcessPoolExecutor(max_workers=workers) as ex:
                    futs = [ex.submit(render_tile, j) for j in jobs]
                    for f in as_completed(futs):
                        r = f.result()
                        if r:
                            batch.append(r)
                            total += 1
                            if len(batch) >= flush_every:
                                flush()
            flush()

        write_info(conn, osm_min, osm_max)
        conn.commit()
        # VACUUM refuses to run inside a transaction.
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()

    print(f"Done. {total} tiles written to {dst_path}")


def add_args(p) -> None:
    p.add_argument("src", help="input GeoTIFF")
    p.add_argument("dst", help="output .sqlitedb")
    p.add_argument("--min-zoom", type=int, default=None,
                   help="shallowest OSM zoom; default max-4")
    p.add_argument("--max-zoom", type=int, default=None,
                   help="deepest OSM zoom; default auto from source GSD")
    p.add_argument("--tile-size", type=int, default=512, choices=[256, 512])
    p.add_argument("--jpeg-quality", type=int, default=90)


def run(a) -> int:
    osm_max = a.max_zoom if a.max_zoom is not None else auto_max_zoom(a.src, a.tile_size)
    osm_min = a.min_zoom if a.min_zoom is not None else max(0, osm_max - 4)
    if osm_min > osm_max:
        osm_min, osm_max = osm_max, osm_min
    workers = max(1, os.cpu_count() or 1)

    print(f"source     : {a.src}")
    print(f"output     : {a.dst}")
    print(f"osm zoom   : {osm_min}..{osm_max}  "
          f"(stored z {STORED_Z_OFFSET - osm_max}..{STORED_Z_OFFSET - osm_min})")
    print(f"tile size  : {a.tile_size} px  jpeg q={a.jpeg_quality}  workers={workers}")

    build(a.src, a.dst, osm_min, osm_max, a.tile_size, a.jpeg_quality, workers)
    return 0
