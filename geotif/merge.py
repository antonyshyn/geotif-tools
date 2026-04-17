"""Merge GeoTIFFs into one RGBA GeoTIFF.

Order matters: earlier args are under, later args over. Transparent / nodata
pixels of upper layers do NOT overwrite lower layers. Inputs are reprojected
to the CRS of the first input at the finest resolution among them.
"""

from __future__ import annotations

import sys

import numpy as np
import rasterio
from rasterio.enums import ColorInterp, Resampling
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds


def input_footprint(path: str, dst_crs) -> tuple[float, float, float, float, float]:
    with rasterio.open(path) as ds:
        b = transform_bounds(ds.crs, dst_crs, *ds.bounds, densify_pts=21)
        with WarpedVRT(ds, crs=dst_crs) as vrt:
            gsd = abs(vrt.transform.a)
    return (*b, gsd)


def merge(inputs: list[str], out_path: str) -> None:
    with rasterio.open(inputs[0]) as ds0:
        dst_crs = ds0.crs

    foots = [input_footprint(p, dst_crs) for p in inputs]
    minx = min(f[0] for f in foots)
    miny = min(f[1] for f in foots)
    maxx = max(f[2] for f in foots)
    maxy = max(f[3] for f in foots)
    gsd = min(f[4] for f in foots)

    width = max(1, int(round((maxx - minx) / gsd)))
    height = max(1, int(round((maxy - miny) / gsd)))
    dst_transform = transform_from_bounds(minx, miny, maxx, maxy, width, height)

    print(f"output CRS : {dst_crs}")
    print(f"output size: {width} x {height}  gsd={gsd:.4f}")
    print(f"bounds     : {minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f}")

    rgba = np.zeros((4, height, width), dtype=np.uint8)

    for i, path in enumerate(inputs):
        print(f"[{i+1}/{len(inputs)}] {path}", flush=True)
        with rasterio.open(path) as ds:
            has_alpha = any(
                ci.name == "alpha" for ci in (ds.colorinterp or [])
            ) or ds.count == 4 or ds.count == 2
            kwargs = dict(
                crs=dst_crs,
                transform=dst_transform,
                width=width,
                height=height,
                resampling=Resampling.lanczos,
            )
            if not has_alpha:
                kwargs["add_alpha"] = True
            with WarpedVRT(ds, **kwargs) as vrt:
                count = min(vrt.count, 4)
                data = vrt.read(indexes=list(range(1, count + 1)))

        if count == 1:
            rgb = np.stack([data[0]] * 3, axis=0)
            a = np.full_like(data[0], 255)
        elif count == 2:
            rgb = np.stack([data[0]] * 3, axis=0)
            a = data[1]
        elif count == 3:
            rgb = data
            a = np.full(data.shape[1:], 255, dtype=np.uint8)
        else:
            rgb = data[:3]
            a = data[3]

        mask = a > 0
        for b in range(3):
            rgba[b] = np.where(mask, rgb[b], rgba[b])
        rgba[3] = np.where(mask, np.maximum(rgba[3], a), rgba[3])

    profile = dict(
        driver="GTiff",
        width=width,
        height=height,
        count=4,
        dtype="uint8",
        crs=dst_crs,
        transform=dst_transform,
        tiled=True,
        blockxsize=512,
        blockysize=512,
        compress="LZW",
        predictor=2,
        photometric="RGB",
    )
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(rgba)
        dst.colorinterp = [
            ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha,
        ]

    print(f"Wrote {out_path}")


def add_args(p) -> None:
    p.add_argument("paths", nargs="+",
                   help="inputs (under -> over), last arg is the output .tif")


def run(a) -> int:
    if len(a.paths) < 3:
        print("need at least 2 inputs + 1 output", file=sys.stderr)
        return 2
    inputs, out = a.paths[:-1], a.paths[-1]
    merge(inputs, out)
    return 0
