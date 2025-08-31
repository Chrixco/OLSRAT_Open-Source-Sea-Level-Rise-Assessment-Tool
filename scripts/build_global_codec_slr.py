#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Combine CoDEC ESL return levels (metres above MSL) with IPCC AR6 SLR (global total)
to produce global tables suitable for analysis/mapping.

Outputs (CSV) written by default into the sibling ..\Data\ folder:
- Long table: rows per station × scenario × year × quantile × metric (SLR_only / SLR_plus_RP), with heights above MSL
  and (optionally) above MHHW if offsets are provided.
- Station metadata: one row per CoDEC station with coordinates, Gumbel(μ,β), and present RLs.
- Sample: same structure as long table but only the first N stations for quick inspection.
"""

import argparse
import csv
from pathlib import Path
import sys
import re

import numpy as np
import pandas as pd
import xarray as xr


# ---------- Defaults anchored to your plugin layout ----------
# This file lives in: ...\slr_vulnerability_mapper\scripts\
# Data lives in:      ...\slr_vulnerability_mapper\Data\
BASE_DIR = Path(__file__).resolve().parent.parent  # plugin root
DATA_DIR = BASE_DIR / "Data"
DATA_DIR.mkdir(parents=True, exist_ok=True)  # ensure exists for outputs

DEF_CODEC = DATA_DIR / "CODEC_amax_ERA5_1979_2017_coor_mask_GUM_RPS.nc"
DEF_SLR   = DATA_DIR / "slr_ipcc_ar6_sea_level_projection_global_total.csv"
DEF_OUT_LONG   = DATA_DIR / "codec_global_slr_esl_long.csv"
DEF_OUT_META   = DATA_DIR / "codec_global_station_metadata_present_RLs.csv"
DEF_OUT_SAMPLE = DATA_DIR / "codec_global_slr_esl_sample.csv"


def norm_scen(s: str) -> str:
    """Normalise scenario strings."""
    s = str(s).replace(" ", "").replace("_", "").lower()
    return {"ssp2-4.5": "ssp245", "ssp245": "ssp245",
            "ssp5-8.5": "ssp585", "ssp585": "ssp585"}.get(s, s)


def gumbel_return_level(mu: np.ndarray, beta: np.ndarray, T: float) -> np.ndarray:
    """
    Return level z_T for Gumbel (annual maxima) with location=mu, scale=beta.
    z_T = mu - beta * ln( -ln(1 - 1/T) )
    Vectorised over stations.
    """
    if T <= 1:
        raise ValueError("Return period T must be > 1 year")
    y = -np.log(-np.log(1.0 - 1.0/float(T)))
    return mu - beta * y


def parse_list_of_ints(text: str) -> list:
    return [int(x) for x in re.split(r"[,\s]+", str(text).strip()) if x]


def open_codec(codec_path: Path):
    """Open CoDEC NetCDF and return dictionary of arrays + RP values."""
    ds = xr.open_dataset(codec_path)
    try:
        lats = ds["station_y_coordinate"].values
        lons = ds["station_x_coordinate"].values
        rps_vals = ds["return_periods"].values.astype(int)
        RPS = ds["RPS"].values  # (stations, n_rp)
        GUM = ds["GUM"].values  # (stations, 2) -> [mu, beta]
    except Exception as e:
        raise RuntimeError(f"Unexpected CoDEC structure: {list(ds.data_vars)} / {list(ds.coords)}") from e
    if RPS.shape[0] != len(lats) or RPS.shape[1] != len(rps_vals):
        raise RuntimeError(f"RPS shape {RPS.shape} does not match stations/return_periods lengths")
    return {
        "lats": lats.astype(float),
        "lons": lons.astype(float),
        "rps_vals": rps_vals.tolist(),
        "RPS": RPS.astype(float),
        "GUM_mu": GUM[:, 0].astype(float),
        "GUM_beta": GUM[:, 1].astype(float),
    }


def load_ar6_slr_global_total(slr_csv: Path,
                              years: list,
                              keep_scenarios: set,
                              keep_quantiles: set) -> pd.DataFrame:
    """
    Load IPCC AR6 global-total SLR CSV (wide years).
    Expected columns e.g.: scenario, model, process, quantile, 2030, 2050, 2100
    Returns long DF with columns: scenario(year-normalised), year, quantile(p##), slr_m
    """
    df = pd.read_csv(slr_csv)
    if "process" in df.columns:
        df = df[df["process"].str.lower() == "total"]
    if "scenario" not in df.columns:
        raise ValueError("SLR CSV must have a 'scenario' column")
    if "quantile" not in df.columns:
        raise ValueError("SLR CSV must have a 'quantile' column")

    df["scenario_norm"] = df["scenario"].apply(norm_scen)
    df = df[df["scenario_norm"].isin(keep_scenarios)]
    year_cols = [str(y) for y in years if str(y) in df.columns]
    if not year_cols:
        raise ValueError(f"None of the requested years {years} found as columns in SLR CSV")

    recs = []
    for _, r in df.iterrows():
        q = int(r["quantile"])
        if q not in keep_quantiles:
            continue
        for yc in year_cols:
            val = r[yc]
            if pd.isna(val):
                continue
            recs.append({
                "scenario": r["scenario_norm"],
                "year": int(yc),
                "quantile": f"p{q:02d}",
                "slr_m": float(val),
            })
    out = pd.DataFrame.from_records(recs)
    if out.empty:
        raise ValueError("No SLR records after filtering by scenario/year/quantile.")
    return out


def load_mhhw_offsets(offset_csv: Path | None,
                      constant_offset: float | None,
                      n_stations: int) -> np.ndarray:
    """
    Returns an array of length n_stations with (MHHW - MSL) offsets in metres.
    Priority: offset_csv (by station_index), else constant, else NaN.
    """
    arr = np.full(n_stations, np.nan, dtype=float)
    if offset_csv is not None and offset_csv.exists():
        table = pd.read_csv(offset_csv)
        if "station_index" not in table.columns or "mhhw_minus_msl_m" not in table.columns:
            raise ValueError("Offset CSV must have columns: station_index, mhhw_minus_msl_m")
        valid = table.dropna(subset=["station_index", "mhhw_minus_msl_m"])
        for _, r in valid.iterrows():
            idx = int(r["station_index"])
            if 0 <= idx < n_stations:
                arr[idx] = float(r["mhhw_minus_msl_m"])
    if np.isnan(arr).all() and constant_offset is not None:
        arr[:] = float(constant_offset)
    return arr


def main():
    ap = argparse.ArgumentParser(
        description="Combine CoDEC ESL (MSL) with IPCC AR6 SLR (global total) to build global tables."
    )
    ap.add_argument("--codec", default=str(DEF_CODEC),
                    help=f"Path to CoDEC NetCDF (default: {DEF_CODEC})")
    ap.add_argument("--slr_csv", default=str(DEF_SLR),
                    help=f"Path to AR6 global-total SLR CSV (default: {DEF_SLR})")
    ap.add_argument("--years", default="2030,2050,2100",
                    help="Comma-separated years (e.g., 2030,2050,2100)")
    ap.add_argument("--scenarios", default="ssp245,ssp585",
                    help="Comma-separated scenarios (ssp245,ssp585)")
    ap.add_argument("--quantiles", default="5,17,50,83,95",
                    help="Comma-separated quantiles (integers): e.g., 5,17,50,83,95")
    ap.add_argument("--rps", default="",
                    help="Comma-separated return periods to include (e.g., 10,100,1000). "
                         "If omitted, all CoDEC RPs are used. "
                         "If you include RPs not in CoDEC, they will be computed from Gumbel(μ,β).")
    ap.add_argument("--include_present", action="store_true",
                    help="Also write present-day RL rows (scenario='present', year=2017, metric='Present_RP_only').")
    ap.add_argument("--present_year", type=int, default=2017,
                    help="Year label to use for present-day rows (default 2017 = end of ERA5 period).")
    ap.add_argument("--mhhw_offset_csv", default="",
                    help="Optional CSV with columns: station_index,mhhw_minus_msl_m (per-station offsets).")
    ap.add_argument("--mhhw_offset_constant", type=float, default=None,
                    help="Optional constant (MHHW - MSL) to add globally if CSV not provided.")
    ap.add_argument("--out_long", default=str(DEF_OUT_LONG),
                    help=f"Output long CSV (default: {DEF_OUT_LONG})")
    ap.add_argument("--out_meta", default=str(DEF_OUT_META),
                    help=f"Station metadata CSV (default: {DEF_OUT_META})")
    ap.add_argument("--out_sample", default=str(DEF_OUT_SAMPLE),
                    help=f"Sample CSV (default: {DEF_OUT_SAMPLE})")
    ap.add_argument("--sample_n", type=int, default=100,
                    help="Number of stations to include in sample CSV")
    args = ap.parse_args()

    codec_path = Path(args.codec)
    slr_path = Path(args.slr_csv)
    if not codec_path.exists():
        sys.exit(f"[ERROR] CoDEC file not found: {codec_path}")
    if not slr_path.exists():
        sys.exit(f"[ERROR] SLR CSV not found: {slr_path}")

    print(f"[INFO] Using CoDEC:   {codec_path}")
    print(f"[INFO] Using SLR CSV: {slr_path}")
    print(f"[INFO] Outputs → Data/: {DEF_OUT_LONG.name}, {DEF_OUT_META.name}, {DEF_OUT_SAMPLE.name}")

    # 1) Load CoDEC
    C = open_codec(codec_path)
    lats = C["lats"]; lons = C["lons"]
    rps_codec_all = C["rps_vals"]
    RPS = C["RPS"]
    mu = C["GUM_mu"]; beta = C["GUM_beta"]
    n_stations = len(lats)
    print(f"[INFO] CoDEC: {n_stations} stations; RPs available: {rps_codec_all}")

    # 2) Decide which RPs to use
    if args.rps.strip():
        rps_req = parse_list_of_ints(args.rps)
    else:
        rps_req = list(rps_codec_all)

    # Prepare rp -> vector[stations] of present return levels above MSL
    rp_to_vector = {}
    rp_index_map = {rp: j for j, rp in enumerate(rps_codec_all)}
    for rp in set(rps_req) & set(rps_codec_all):
        rp_to_vector[rp] = RPS[:, rp_index_map[rp]].astype(float)

    # Compute missing requested RPs from Gumbel if needed
    missing = sorted([rp for rp in rps_req if rp not in rp_to_vector])
    if missing:
        print(f"[INFO] Computing missing RPs from Gumbel for: {missing}")
        for rp in missing:
            rp_vec = gumbel_return_level(mu, beta, float(rp))
            rp_to_vector[rp] = rp_vec.astype(float)

    rps_final = sorted(rp_to_vector.keys())
    print(f"[INFO] Using RPs: {rps_final}")

    # 3) Load AR6 SLR (global total)
    years = parse_list_of_ints(args.years)
    keep_scen = {norm_scen(s) for s in args.scenarios.split(",")}
    keep_q = {int(q) for q in args.quantiles.split(",")}
    df_slr = load_ar6_slr_global_total(slr_path, years, keep_scen, keep_q)
    print(f"[INFO] Loaded SLR records: {len(df_slr)} "
      f"({sorted(df_slr['scenario'].unique())} × {sorted(df_slr['year'].unique())} × {sorted(df_slr['quantile'].unique())})")

    # 4) Load MHHW offsets (optional)
    offset_csv = Path(args.mhhw_offset_csv) if args.mhhw_offset_csv else None
    offsets = load_mhhw_offsets(offset_csv, args.mhhw_offset_constant, n_stations)
    have_mhhw = not np.isnan(offsets).all()
    if have_mhhw:
        print("[INFO] MHHW offsets available: will write 'height_m_above_MHHW' column")
    else:
        print("[INFO] No MHHW offsets provided: will write only 'height_m_above_MSL'")

    # 5) Station metadata (present RLs)
    meta_rows = []
    for i in range(n_stations):
        row = {"station_index": i, "lat": float(lats[i]), "lon": float(lons[i]),
               "gumbel_loc_mu": float(mu[i]), "gumbel_scale_beta": float(beta[i])}
        for rp in rps_final:
            row[f"RL_{rp}_present_msl_m"] = float(rp_to_vector[rp][i])
        meta_rows.append(row)
    pd.DataFrame(meta_rows).to_csv(args.out_meta, index=False)
    print(f"[OK] Wrote station metadata: {args.out_meta}")

    # 6) Stream long table (big)
    out_long = Path(args.out_long)
    out_sample = Path(args.out_sample)

    # Header (always include MHHW column; blank if not available)
    header = ["station_index", "lat", "lon", "scenario", "year", "quantile",
              "metric", "rp_years", "height_m_above_MSL", "height_m_above_MHHW"]

    # Open writers
    with out_long.open("w", newline="", encoding="utf-8") as f_long, \
         out_sample.open("w", newline="", encoding="utf-8") as f_sample:

        writer_long = csv.writer(f_long); writer_sample = csv.writer(f_sample)
        writer_long.writerow(header);    writer_sample.writerow(header)

        sample_n = int(args.sample_n)

        # Optional: present-only rows
        if args.include_present:
            print("[INFO] Writing present-day RL rows...")
            for i in range(n_stations):
                for rp in rps_final:
                    msl = float(rp_to_vector[rp][i])
                    mhhw = (msl + float(offsets[i])) if have_mhhw else ""
                    row = [i, float(lats[i]), float(lons[i]),
                           "present", int(args.present_year), "NA",
                           "Present_RP_only", int(rp), msl, mhhw]
                    writer_long.writerow(row)
                    if i < sample_n:
                        writer_sample.writerow(row)

        # SLR-based rows
        print("[INFO] Writing SLR rows (SLR_only and SLR_plus_RP)...")
        for s in df_slr.itertuples(index=False):
            # SLR_only per station
            for i in range(n_stations):
                msl = float(s.slr_m)
                mhhw = (msl + float(offsets[i])) if have_mhhw else ""
                row = [i, float(lats[i]), float(lons[i]),
                       s.scenario, int(s.year), s.quantile,
                       "SLR_only", "", msl, mhhw]
                writer_long.writerow(row)
                if i < sample_n:
                    writer_sample.writerow(row)

            # SLR_plus_RP per station × RP
            for rp in rps_final:
                rp_vec = rp_to_vector[rp]  # vector over stations
                for i in range(n_stations):
                    msl = float(rp_vec[i] + s.slr_m)
                    mhhw = (msl + float(offsets[i])) if have_mhhw else ""
                    row = [i, float(lats[i]), float(lons[i]),
                           s.scenario, int(s.year), s.quantile,
                           "SLR_plus_RP", int(rp), msl, mhhw]
                    writer_long.writerow(row)
                    if i < sample_n:
                        writer_sample.writerow(row)

    print(f"[OK] Wrote long table:   {args.out_long}")
    print(f"[OK] Wrote sample table: {args.out_sample}")
    print(f"[OK] Wrote metadata:     {args.out_meta}")
    print("[DONE]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
