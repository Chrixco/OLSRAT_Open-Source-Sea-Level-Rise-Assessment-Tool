# -*- coding: utf-8 -*-
"""
DEM → Flooded extent + AOI stats (AR6 CSV + CODEC return levels)

- AR6 CSV expected at:  Data/slr_ipcc_ar6_sea_level_projection_global_total.csv
  Columns: process, confidence, scenario (ssp119/126/245/370/585),
           quantile (5/17/50/83/95), years 2020..2150 (metres)

- CODEC CSV (e.g. Data/codec_global_station_metadata_present_RLs.csv)
  Must contain lon/lat columns, a station ID/name column, and RL columns such as
  rl1, rl10, rl50, rl100, rl1000 (any case; underscores/spaces/extra suffixes tolerated).
"""

import os, csv, re, math
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFile, QgsProcessingParameterEnum,
    QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFeatureSink, QgsProcessingContext, QgsProcessingUtils,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsUnitTypes,
    QgsFeatureSink, QgsFeature, QgsField, QgsFields, QgsRasterLayer, QgsVectorLayer,
    QgsPointXY, QgsProcessingParameterDefinition, QgsProcessingParameterString
)
from qgis import processing


# ---------- tolerant header helpers ----------
def _norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())

def _find_id_key(fieldnames):
    """Pick a sensible station identifier column, robust to naming."""
    wants = ['stationid', 'id', 'station', 'name', 'sitename', 'siteid', 'code']
    slug = {k: _norm(k) for k in (fieldnames or [])}
    for want in wants:
        for k in fieldnames:
            if slug[k] == want:
                return k
    for k in fieldnames:
        if 'station' in (k or '').lower():
            return k
    return None

def _find_rl_cols(fieldnames):
    """
    Return dict {1: colname, 10: colname, ...} using forgiving patterns:
    matches 'rl10', 'RL_1000', 'rl 100 (m)', 'present_RLs_rl50', 'rl1000_m', etc.
    """
    rl_cols = {}
    for k in fieldnames or []:
        txt = k or ''
        m = (re.search(r'(?i)\brl\s*[_\-\s]*\s*(1|10|50|100|1000)\b', txt)
             or re.search(r'(?i)\brl\s*[_\-\s]*\s*(1|10|50|100|1000)(?!\d)', txt)
             or re.search(r'(?i)\brl\s*[:_ \-]*\s*(1|10|50|100|1000)\D', txt))
        if m:
            rl_cols[int(m.group(1))] = k
    return rl_cols


class DemFloodScenarioAlgorithmWithReturnPeriod(QgsProcessingAlgorithm):
    # ---- parameter keys
    P_DEM = "DEM"
    P_AOI = "AOI"
    P_CSV = "AR6_CSV"
    P_SSP = "SCENARIO"
    P_YEAR = "YEAR"
    P_PCTL = "PERCENTILE"
    P_VLM = "VERTICAL_OFFSET"

    P_CODEC = "CODEC_CSV"
    P_CODEC_STATION = "CODEC_STATION"               # dropdown (0 = Auto)
    P_CODEC_STATION_MANUAL = "CODEC_STATION_MANUAL" # manual override (text)
    P_RPS = "RETURN_PERIODS"                        # multi-select (extra rasters)
    P_PRIMARY_RP = "PRIMARY_RP"                     # single-select (drives outputs)
    P_MAXKM = "MAX_STATION_KM"

    # ---- outputs
    O_RASTER = "FLOODED_RASTER"
    O_AOI = "AOI_WITH_STATS"

    # AR6 UI → codes
    SSP_OPTIONS = ["SSP1-1.9", "SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"]
    _SSP_MAP = {"SSP1-1.9":"ssp119","SSP1-2.6":"ssp126","SSP2-4.5":"ssp245","SSP3-7.0":"ssp370","SSP5-8.5":"ssp585"}
    PCTL_OPTIONS = ["p50 (median)","p17 (likely lower)","p83 (likely upper)","p05 (low)","p95 (high)"]
    _PCTL_MAP = {"p50 (median)":50,"p17 (likely lower)":17,"p83 (likely upper)":83,"p05 (low)":5,"p95 (high)":95}

    # CSV-informed at init (safe defaults if CSV unavailable):
    RP_OPTIONS = ["SLR only"]   # e.g. ["SLR only","Annual (1-yr)","10-yr","50-yr","100-yr","1000-yr"]
    RP_KEYS = [None]            # e.g. [None, 1, 10, 50, 100, 1000]
    CODEC_STATION_OPTIONS = ["Auto (nearest to AOI)"]  # ["Auto (nearest to AOI)", "STATION_A", ...]

    # Primary RP choices (fixed, additive to SLR):
    PRIMARY_RP_OPTIONS = ["SLR only", "SLR + 10-yr", "SLR + 50-yr", "SLR + 100-yr", "SLR + 1000-yr"]
    PRIMARY_RP_KEYS    = [None,        10,            50,            100,             1000]

    # ------------- QGIS metadata -------------
    def tr(self, s): return QCoreApplication.translate("DemFloodScenarioAlgorithmWithReturnPeriod", s)
    def name(self): return "dem_flood_scenario_codec"
    def displayName(self): return self.tr("DEM → Flooded extent + AOI stats (AR6 + CODEC RPs)")
    def group(self): return self.tr("Flood Exposure")
    def groupId(self): return "flood_exposure"
    def shortHelpString(self):
        return self.tr(
            "Thresholds a DEM by sea level from IPCC AR6 (process=total) and optional CODEC return levels. "
            "Provides CSV-informed pull-downs for Return Periods and Station (with manual override). "
            "Returns raster + AOI stats for the chosen Primary RP; other selected RPs are also generated as temporary rasters."
        )
    def createInstance(self): return DemFloodScenarioAlgorithmWithReturnPeriod()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    # ------------- helpers -------------
    @staticmethod
    def _plugin_root_from_here() -> str:
        here = os.path.dirname(os.path.abspath(__file__))   # .../scripts
        return os.path.dirname(here)                         # plugin root

    @staticmethod
    def _default_ar6_csv_path() -> str:
        return os.path.join(DemFloodScenarioAlgorithmWithReturnPeriod._plugin_root_from_here(),
                            "Data", "slr_ipcc_ar6_sea_level_projection_global_total.csv")

    @staticmethod
    def _default_codec_csv_path() -> str:
        return os.path.join(DemFloodScenarioAlgorithmWithReturnPeriod._plugin_root_from_here(),
                            "Data", "codec_global_station_metadata_present_RLs.csv")

    def _read_years_from_csv(self, csv_path):
        """Safely read year columns from CSV, returning empty list on any error"""
        try:
            if not os.path.exists(csv_path):
                return []
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                rdr = csv.reader(f)
                headers = next(rdr)
                return [h for h in headers if h.isdigit()]
        except Exception:
            # Return empty list if any error during CSV read (file corrupt, permissions, etc)
            return []

    def _level_from_csv(self, csv_path, ssp_ui, year_str, pctl_ui):
        if not os.path.exists(csv_path):
            raise QgsProcessingException(f"AR6 CSV not found: {csv_path}")
        scenario_code = self._SSP_MAP[ssp_ui]; quant = self._PCTL_MAP[pctl_ui]
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            required = {"process","scenario","quantile",year_str}
            missing = required.difference(set(rdr.fieldnames or []))
            if missing: raise QgsProcessingException(f"CSV missing columns: {', '.join(sorted(missing))}")
            for row in rdr:
                if row.get("process","").strip().lower() != "total": continue
                if row.get("scenario","").strip().lower() != scenario_code: continue
                try:
                    if int(row.get("quantile","-1")) != quant: continue
                except Exception:
                    continue
                try:
                    return float(row[year_str])
                except Exception:
                    raise QgsProcessingException(
                        f"Non-numeric SLR for {ssp_ui}/{year_str}/{pctl_ui}: {row.get(year_str)}"
                    )
        raise QgsProcessingException("No AR6 match for the selected scenario/year/percentile.")

    @staticmethod
    def _pick(cols, cand):
        for k in cols or []:
            if k and k.strip().lower() in cand: return k
        return None

    @staticmethod
    def _detect_codec_csv(csv_path):
        """Return (available_rps [ints], station_ids [list], keys dict). Safe - returns defaults on error."""
        try:
            if not (csv_path and os.path.exists(csv_path)):
                return [], ["Auto (nearest to AOI)"], {'lon':None,'lat':None,'id':None,'rl_cols':{}}
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                rdr = csv.DictReader(f)
                if not rdr.fieldnames:
                    return [], ["Auto (nearest to AOI)"], {'lon':None,'lat':None,'id':None,'rl_cols':{}}
                lon_key = DemFloodScenarioAlgorithmWithReturnPeriod._pick(rdr.fieldnames, {"lon","longitude","x","lon_dd"})
                lat_key = DemFloodScenarioAlgorithmWithReturnPeriod._pick(rdr.fieldnames, {"lat","latitude","y","lat_dd"})
                id_key  = _find_id_key(rdr.fieldnames)
                rl_cols = _find_rl_cols(rdr.fieldnames)

                stations = ["Auto (nearest to AOI)"]
                if id_key:
                    seen = set()
                    for i, row in enumerate(rdr):
                        sid = (row.get(id_key) or "").strip()
                        if sid and sid not in seen:
                            stations.append(sid); seen.add(sid)
                        if len(stations) > 3000: break

            return sorted(list(rl_cols.keys())), stations, {'lon':lon_key,'lat':lat_key,'id':id_key,'rl_cols':rl_cols}
        except Exception:
            # Return safe defaults if any error during CSV read
            return [], ["Auto (nearest to AOI)"], {'lon':None,'lat':None,'id':None,'rl_cols':{}}

    def _aoi_center_lonlat(self, layer, context: QgsProcessingContext):
        if not (layer and layer.isValid()): return None
        tr = QgsCoordinateTransform(layer.crs(), QgsCoordinateReferenceSystem.fromEpsgId(4326), context.transformContext())
        c = layer.extent().center(); p = tr.transform(QgsPointXY(c))
        return (float(p.x()), float(p.y()))

    @staticmethod
    def _haversine_km_vec(lons_deg, lats_deg, lon0, lat0):
        R = 6371.0088
        lons = np.radians(np.asarray(lons_deg, dtype=float))
        lats = np.radians(np.asarray(lats_deg, dtype=float))
        lon0 = math.radians(float(lon0)); lat0 = math.radians(float(lat0))
        dlon = lons - lon0; dlat = lats - lat0
        a = np.sin(dlat/2.0)**2 + np.cos(lats)*math.cos(lat0)*np.sin(dlon/2.0)**2
        return 2.0 * R * np.arcsin(np.sqrt(a))

    def _codec_nearest_rls(self, csv_path, lon, lat):
        if not os.path.exists(csv_path):
            raise QgsProcessingException(f"CODEC CSV not found: {csv_path}")
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            lon_key = self._pick(rdr.fieldnames, {"lon","longitude","x","lon_dd"})
            lat_key = self._pick(rdr.fieldnames, {"lat","latitude","y","lat_dd"})
            id_key  = _find_id_key(rdr.fieldnames)
            rl_cols = _find_rl_cols(rdr.fieldnames)

            rows = []
            for row in rdr:
                try:
                    lo = float(row[lon_key]); la = float(row[lat_key])
                except Exception:
                    continue
                sid = (row.get(id_key, "") if id_key else "").strip()
                if not sid:
                    sid = f"{lo:.4f},{la:.4f}"  # fallback ID = coords
                d = {'id': sid, 'lon': lo, 'lat': la}
                for rp, col in rl_cols.items():
                    try: d[rp] = float(row[col])
                    except Exception: d[rp] = None
                rows.append(d)

        if not rows: raise QgsProcessingException("No usable rows in CODEC CSV.")
        arr_lon = [r['lon'] for r in rows]; arr_lat = [r['lat'] for r in rows]
        idx = int(np.nanargmin(self._haversine_km_vec(arr_lon, arr_lat, lon, lat)))
        sel = rows[idx]
        rls = {rp: sel.get(rp) for rp in (1,10,50,100,1000) if sel.get(rp) is not None}
        dist_km = float(self._haversine_km_vec([sel['lon']], [sel['lat']], lon, lat)[0])
        return {'station_id': sel.get('id',''), 'lon': sel['lon'], 'lat': sel['lat'], 'dist_km': dist_km, 'rls': rls}

    def _codec_station_rls(self, csv_path, station_id):
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            lon_key = self._pick(rdr.fieldnames, {"lon","longitude","x","lon_dd"})
            lat_key = self._pick(rdr.fieldnames, {"lat","latitude","y","lat_dd"})
            id_key  = _find_id_key(rdr.fieldnames)
            rl_cols = _find_rl_cols(rdr.fieldnames)

            if not id_key:
                raise QgsProcessingException("No station ID column in CODEC CSV.")
            for row in rdr:
                sid = (row.get(id_key) or "").strip()
                if sid == station_id:
                    try: lo = float(row[lon_key]); la = float(row[lat_key])
                    except Exception: lo = float('nan'); la = float('nan')
                    rls = {}
                    for rp, col in rl_cols.items():
                        try: rls[rp] = float(row[col])
                        except Exception: pass
                    if not sid:
                        sid = f"{lo:.4f},{la:.4f}"
                    return {'station_id': sid, 'lon': lo, 'lat': la, 'dist_km': float('nan'), 'rls': rls}
        raise QgsProcessingException(f"Station '{station_id}' not found in CODEC CSV.")

    # ------------- parameters -------------
    def initAlgorithm(self, config=None):
        # AR6 defaults (safe fallback to default years if CSV unavailable)
        try:
            ar6_default = self._default_ar6_csv_path()
            years = self._read_years_from_csv(ar6_default) or [str(y) for y in range(2020, 2151, 10)]
        except Exception:
            years = [str(y) for y in range(2020, 2151, 10)]
        self._year_options = years

        # CODEC-informed menus from default CSV (built once at dialog creation)
        # Safe fallback if CSV detection fails
        try:
            codec_default = self._default_codec_csv_path()
            available_rps, station_opts, _ = self._detect_codec_csv(codec_default)
        except Exception:
            available_rps, station_opts = [], ["Auto (nearest to AOI)"]

        # Multi-select RP menu
        rp_labels = ["SLR only"]
        rp_keys = [None]
        try:
            if 1 in available_rps:
                rp_labels.append("Annual (1-yr)")
                rp_keys.append(1)
            for rp in (10, 50, 100, 1000):
                if rp in available_rps:
                    rp_labels.append(f"{rp}-yr")
                    rp_keys.append(rp)
        except Exception:
            pass  # Keep default ["SLR only"]
        self.RP_OPTIONS, self.RP_KEYS = rp_labels, rp_keys
        self.CODEC_STATION_OPTIONS = station_opts or ["Auto (nearest to AOI)"]

        # ---- Parameters
        self.addParameter(QgsProcessingParameterRasterLayer(self.P_DEM, self.tr("DEM (m)")))
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.P_AOI, self.tr("AOI polygons (optional)"),
            types=[QgsProcessing.TypeVectorPolygon], optional=True
        ))

        self.addParameter(QgsProcessingParameterFile(
            self.P_CSV, self.tr("AR6 CSV"),
            behavior=QgsProcessingParameterFile.File, fileFilter="CSV (*.csv)",
            defaultValue=ar6_default
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.P_SSP, self.tr("Scenario (SSP)"), options=self.SSP_OPTIONS, defaultValue=1
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_YEAR, self.tr("Year"), options=years,
            defaultValue=years.index("2100") if "2100" in years else 0
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_PCTL, self.tr("Percentile"), options=self.PCTL_OPTIONS, defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.P_VLM, self.tr("Vertical offset (m, optional)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0
        ))

        # CODEC CSV (optional)
        param_codec = QgsProcessingParameterFile(
            self.P_CODEC, self.tr("CODEC return levels CSV"),
            behavior=QgsProcessingParameterFile.File, fileFilter="CSV (*.csv)",
            defaultValue=codec_default
        )
        try:
            param_codec.setOptional(True)
        except AttributeError:
            param_codec.setFlags(param_codec.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(param_codec)

        # Station selection + manual override
        self.addParameter(QgsProcessingParameterEnum(
            self.P_CODEC_STATION, self.tr("Station"),
            options=self.CODEC_STATION_OPTIONS, defaultValue=0  # 0 = Auto
        ))
        p_manual = QgsProcessingParameterString(
            self.P_CODEC_STATION_MANUAL, self.tr("Station ID (manual override, optional)"),
            defaultValue="", multiLine=False
        )
        try:
            p_manual.setOptional(True)
        except AttributeError:
            p_manual.setFlags(p_manual.flags() | QgsProcessingParameterDefinition.FlagOptional)
        self.addParameter(p_manual)

        # Return periods (extra rasters): multi-select from CSV
        default_rp_idx = [0]  # Always include first option (SLR only)
        try:
            if "Annual (1-yr)" in self.RP_OPTIONS:
                default_rp_idx.append(self.RP_OPTIONS.index("Annual (1-yr)"))
            if "100-yr" in self.RP_OPTIONS:
                default_rp_idx.append(self.RP_OPTIONS.index("100-yr"))
        except (ValueError, IndexError):
            pass  # Safe fallback to [0] if options not found
        self.addParameter(QgsProcessingParameterEnum(
            self.P_RPS, self.tr("Return periods to include (extra rasters)"),
            options=self.RP_OPTIONS, allowMultiple=True, defaultValue=default_rp_idx
        ))

        # Primary return period (fixed, additive to SLR)
        self.addParameter(QgsProcessingParameterEnum(
            self.P_PRIMARY_RP, self.tr("Primary return period"),
            options=self.PRIMARY_RP_OPTIONS, defaultValue=3  # SLR + 100-yr
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.P_MAXKM, self.tr("Max distance to nearest CODEC station (km)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=500.0, minValue=1.0
        ))

        self.addParameter(QgsProcessingParameterRasterDestination(self.O_RASTER, self.tr("Flooded raster (GeoTIFF)")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.O_AOI, self.tr("AOI with flooded statistics")))

    # ------------- main -------------
    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        # DEM
        dem_layer = self.parameterAsRasterLayer(parameters, self.P_DEM, context)
        if dem_layer is None: raise QgsProcessingException("DEM is required.")

        # AOI (optional)
        aoi_layer = self.parameterAsVectorLayer(parameters, self.P_AOI, context)
        if aoi_layer and aoi_layer.isValid() and aoi_layer.featureCount() == 0:
            feedback.pushWarning("AOI layer is empty (no features). It will be ignored.")
            aoi_layer = None

        # AR6 inputs
        csv_path = self.parameterAsFile(parameters, self.P_CSV, context) or self._default_ar6_csv_path()
        if not os.path.isabs(csv_path):
            csv_path = os.path.normpath(os.path.join(self._plugin_root_from_here(), csv_path))
        ssp_ui  = self.SSP_OPTIONS[self.parameterAsEnum(parameters, self.P_SSP, context)]
        year_str = self._year_options[self.parameterAsEnum(parameters, self.P_YEAR, context)]
        pctl_ui = self.PCTL_OPTIONS[self.parameterAsEnum(parameters, self.P_PCTL, context)]
        vlm    = float(self.parameterAsDouble(parameters, self.P_VLM, context))

        level_csv = self._level_from_csv(csv_path, ssp_ui, year_str, pctl_ui)
        base_level_m = level_csv + vlm
        feedback.pushInfo(f"AR6 total SLR: {ssp_ui} {year_str} {pctl_ui} = {level_csv:.3f} m; offset {vlm:.3f} m → base {base_level_m:.3f} m")

        # Ensure DEM in metres
        dem_for_calc = dem_layer
        if (not dem_layer.crs().isValid()) or (dem_layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters):
            target_crs = (aoi_layer.crs() if (aoi_layer and aoi_layer.isValid())
                          else QgsCoordinateReferenceSystem.fromEpsgId(3857))
            dem_for_calc = processing.run(
                "gdal:warpreproject",
                {"INPUT": dem_layer.source(), "SOURCE_CRS": dem_layer.crs(), "TARGET_CRS": target_crs,
                 "RESAMPLING": 0, "NODATA": dem_layer.dataProvider().sourceNoDataValue(1),
                 "TARGET_RESOLUTION": None, "OPTIONS": "TILED=YES|COMPRESS=DEFLATE",
                 "DATA_TYPE": 6, "MULTITHREADING": True, "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                context=context, feedback=feedback
            )["OUTPUT"]
        dem_src = dem_for_calc if isinstance(dem_for_calc, str) else dem_for_calc.source()

        # CODEC resolve station & RPs
        codec_csv = self.parameterAsFile(parameters, self.P_CODEC, context)

        # Station selection + manual override
        station_idx = self.parameterAsEnum(parameters, self.P_CODEC_STATION, context)
        station_choice = None
        if self.CODEC_STATION_OPTIONS and 0 <= station_idx < len(self.CODEC_STATION_OPTIONS):
            station_choice = self.CODEC_STATION_OPTIONS[station_idx]
        station_manual = (self.parameterAsString(parameters, self.P_CODEC_STATION_MANUAL, context) or "").strip()

        # Extra RP multi-select (indices)
        try:
            rps_selected_idx = self.parameterAsEnums(parameters, self.P_RPS, context) or [0]
        except AttributeError:
            val = self.parameterAsInt(parameters, self.P_RPS, context); rps_selected_idx = [val] if isinstance(val, int) else [0]

        # Primary RP (single) from fixed list
        primary_idx = self.parameterAsEnum(parameters, self.P_PRIMARY_RP, context)
        if 0 <= primary_idx < len(self.PRIMARY_RP_OPTIONS):
            primary_label_fixed = self.PRIMARY_RP_OPTIONS[primary_idx]     # e.g. "SLR + 100-yr"
            primary_rp_key = self.PRIMARY_RP_KEYS[primary_idx]             # None or 10/50/100/1000
        else:
            primary_label_fixed, primary_rp_key = "SLR only", None

        # Runtime RP detection (if user changed CSV in dialog)
        detected_rps, _, _ = self._detect_codec_csv(codec_csv or self._default_codec_csv_path())
        runtime_labels = ["SLR only"]; runtime_keys = [None]
        if 1 in detected_rps: runtime_labels.append("Annual (1-yr)"); runtime_keys.append(1)
        for rp in (10, 50, 100, 1000):
            if rp in detected_rps:
                runtime_labels.append(f"{rp}-yr"); runtime_keys.append(rp)

        # Map multi-select to runtime pairs (label, rp_key)
        selected_pairs = []
        for idx in rps_selected_idx:
            if 0 <= idx < len(self.RP_OPTIONS or []):
                lab = self.RP_OPTIONS[idx]
                if lab in runtime_labels:
                    selected_pairs.append((lab, runtime_keys[runtime_labels.index(lab)]))
        if not selected_pairs:
            selected_pairs = [("SLR only", None)]

        # Ensure the chosen primary is included as a scenario
        if primary_rp_key is None:
            primary_pair = ("SLR only", None)
        else:
            primary_pair = (f"{primary_rp_key}-yr", primary_rp_key)
        if primary_pair not in selected_pairs:
            selected_pairs.append(primary_pair)

        max_km = float(self.parameterAsDouble(parameters, self.P_MAXKM, context))

        # AOI centre fallback
        aoi_lonlat = self._aoi_center_lonlat(aoi_layer, context) if aoi_layer else None
        if not aoi_lonlat:
            tr = QgsCoordinateTransform(dem_layer.crs(), QgsCoordinateReferenceSystem.fromEpsgId(4326), context.transformContext())
            c = dem_layer.extent().center(); p = tr.transform(QgsPointXY(c))
            aoi_lonlat = (float(p.x()), float(p.y()))
        lon0, lat0 = aoi_lonlat

        # Resolve station info
        codec_info = {'station_id':'', 'lon':float('nan'), 'lat':float('nan'), 'dist_km':float('nan'), 'rls':{}}
        if codec_csv:
            if station_manual:
                codec_info = self._codec_station_rls(codec_csv, station_manual)
                try: codec_info['dist_km'] = float(self._haversine_km_vec([codec_info['lon']], [codec_info['lat']], lon0, lat0)[0])
                except Exception: pass
                feedback.pushInfo(f"Using CODEC station (manual): '{codec_info['station_id']}'")
            elif station_choice and station_choice != "Auto (nearest to AOI)":
                codec_info = self._codec_station_rls(codec_csv, station_choice)
                try: codec_info['dist_km'] = float(self._haversine_km_vec([codec_info['lon']], [codec_info['lat']], lon0, lat0)[0])
                except Exception: pass
                feedback.pushInfo(f"Using CODEC station (selected): '{codec_info['station_id']}'")
            else:
                codec_info = self._codec_nearest_rls(codec_csv, lon0, lat0)
                feedback.pushInfo(f"Using CODEC station (auto-nearest): '{codec_info['station_id']}'")
            if codec_info['dist_km'] > max_km:
                feedback.pushWarning(f"Station distance {codec_info['dist_km']:.1f} km exceeds {max_km} km.")
            # Print available RLs for transparency
            if codec_info['rls']:
                feedback.pushInfo("Detected RLs at station: " + ", ".join(f"{k}-yr={v:.3f} m" for k, v in sorted(codec_info['rls'].items())))
        else:
            selected_pairs = [("SLR only", None)]
            primary_label_fixed, primary_rp_key = "SLR only", None

        # Build concrete scenarios: (label_for_logs, threshold_m, rp_key)
        scenarios = []
        missing_primary = False
        for lab, rp_key in selected_pairs:
            if rp_key is None:
                scenarios.append(("SLR only", base_level_m, None))
            else:
                rl_val = codec_info['rls'].get(rp_key)
                if rl_val is None:
                    if rp_key == primary_rp_key:
                        missing_primary = True
                    feedback.pushWarning(f"Missing RL {rp_key}-yr in CODEC CSV; skipping '{lab}'.")
                else:
                    if rl_val <= 0:
                        feedback.pushWarning(f"RL {rp_key}-yr value is {rl_val:.3f} m (≤ 0). Check datum/units.")
                    scenarios.append((f"SLR + {rp_key}-yr", base_level_m + float(rl_val), rp_key))

        # If chosen primary unavailable, fall back to SLR only
        if missing_primary:
            feedback.pushWarning(f"Primary '{primary_label_fixed}' unavailable — falling back to 'SLR only'.")
            primary_rp_key = None
            if not any(rk is None for _,_,rk in scenarios):
                scenarios.insert(0, ("SLR only", base_level_m, None))

        if not scenarios:
            raise QgsProcessingException("No valid scenarios after resolving CODEC RLs.")

        # Identify primary scenario by rp_key (None or 10/50/100/1000)
        primary_idx_runtime = next((i for i,(_,_,rk) in enumerate(scenarios) if rk == primary_rp_key), 0)
        primary_label_runtime = scenarios[primary_idx_runtime][0]

        # Run scenarios; primary drives returned outputs
        out_primary_raster = self.parameterAsOutputLayer(parameters, self.O_RASTER, context)
        out_primary_aoi_sink = None
        results_info = []

        for s_i, (label, threshold_m, rp_key) in enumerate(scenarios):
            is_primary = (s_i == primary_idx_runtime)
            out_ras = out_primary_raster if is_primary else QgsProcessing.TEMPORARY_OUTPUT
            feedback.pushInfo(f"[{s_i+1}/{len(scenarios)}] {label}: threshold {threshold_m:.3f} m")

            calc = processing.run(
                "gdal:rastercalculator",
                {"INPUT_A": dem_src, "BAND_A": 1, "FORMULA": f"(A <= {threshold_m}) * 1",
                 "NO_DATA": 0, "RTYPE": 0,
                 "EXTRA": "--creation-option TILED=YES --creation-option COMPRESS=DEFLATE --creation-option PREDICTOR=2",
                 "OPTIONS": "", "OUTPUT": out_ras},
                context=context, feedback=feedback
            )
            flooded_path = calc["OUTPUT"]
            results_info.append((label, flooded_path))
            if not is_primary:
                feedback.pushInfo(f"  → Raster [{label}] at: {flooded_path}")

            # AOI stats only for the primary
            if not is_primary or not (aoi_layer and aoi_layer.isValid()):
                continue

            flooded_rlayer = QgsProcessingUtils.mapLayerFromString(flooded_path, context) or QgsRasterLayer(flooded_path, f"mask_{label}", "gdal")
            if not flooded_rlayer or not flooded_rlayer.isValid():
                raise QgsProcessingException("Failed to load flooded raster output.")

            # Reproject AOI to raster CRS if needed
            if aoi_layer.crs() != flooded_rlayer.crs():
                aoi_reproj = processing.run(
                    "native:reprojectlayer",
                    {"INPUT": aoi_layer, "TARGET_CRS": flooded_rlayer.crs(),
                     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                    context=context, feedback=feedback
                )["OUTPUT"]
            else:
                aoi_reproj = aoi_layer

            # Zonal stats: COUNT & MEAN on binary mask
            zs = processing.run(
                "native:zonalstatisticsfb",
                {"INPUT": aoi_reproj, "INPUT_RASTER": flooded_rlayer, "RASTER_BAND": 1,
                 "COLUMN_PREFIX": "f_", "STATISTICS": [0, 2], "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                context=context, feedback=feedback
            )
            stats_layer = zs["OUTPUT"] if isinstance(zs["OUTPUT"], QgsVectorLayer) else QgsProcessingUtils.mapLayerFromString(zs["OUTPUT"], context)
            if not stats_layer or not stats_layer.isValid():
                raise QgsProcessingException("Failed to obtain zonal statistics output layer.")

            # Prepare sink schema
            fields_out = QgsFields()
            for f in stats_layer.fields(): fields_out.append(f)
            fields_out.append(QgsField("flooded", QVariant.Double))     # fraction [0,1] over sampled raster cells
            fields_out.append(QgsField("flood_pct", QVariant.Double))   # % polygon area (capped ≤100)
            fields_out.append(QgsField("flood_m2", QVariant.Double))    # m² (fraction × effective sampled area)
            fields_out.append(QgsField("cov_pct", QVariant.Double))     # sampled area / polygon area (%)
            fields_out.append(QgsField("codec_station", QVariant.String))
            fields_out.append(QgsField("codec_dist_km", QVariant.Double))

            sink, out_primary_aoi_sink = self.parameterAsSink(
                parameters, self.O_AOI, context,
                fields_out, stats_layer.wkbType(), stats_layer.crs()
            )
            if sink is None:
                raise QgsProcessingException("Could not initialise output sink for AOI stats.")

            idx_mean  = stats_layer.fields().lookupField("f_mean");   idx_mean  = idx_mean  if idx_mean  != -1 else stats_layer.fields().lookupField("f_MEAN")
            idx_count = stats_layer.fields().lookupField("f_count");  idx_count = idx_count if idx_count != -1 else stats_layer.fields().lookupField("f_COUNT")
            px = abs(flooded_rlayer.rasterUnitsPerPixelX()); py = abs(flooded_rlayer.rasterUnitsPerPixelY())
            pix_area = float(px * py) if px and py else 0.0

            total = max(1, stats_layer.featureCount())
            for i, feat in enumerate(stats_layer.getFeatures()):
                if feedback.isCanceled(): break
                attrs = feat.attributes(); geom = feat.geometry()

                flooded_frac = float(feat[idx_mean]) if (idx_mean != -1 and feat[idx_mean] is not None) else 0.0
                flooded_frac = max(0.0, min(1.0, flooded_frac))

                sampled_area_m2 = (float(feat[idx_count]) * pix_area) if (idx_count != -1 and feat[idx_count] is not None and pix_area > 0.0) else 0.0
                poly_area_m2 = geom.area() if (geom and not geom.isEmpty()) else 0.0
                cov_pct = (sampled_area_m2 / poly_area_m2) * 100.0 if poly_area_m2 > 0 else 0.0

                effective_area = min(sampled_area_m2, poly_area_m2) if poly_area_m2 > 0 else sampled_area_m2
                flood_m2 = flooded_frac * effective_area
                flood_pct = (flood_m2 / poly_area_m2) * 100.0 if poly_area_m2 > 0 else 0.0
                if flood_pct > 100.0: flood_pct = 100.0

                out_feat = QgsFeature(fields_out)
                out_feat.setGeometry(geom)
                out_feat.setAttributes(attrs + [
                    flooded_frac, flood_pct, flood_m2, cov_pct,
                    codec_info.get('station_id',''), codec_info.get('dist_km', float('nan'))
                ])
                sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

                if i % 1000 == 0 or i == total - 1:
                    feedback.setProgress(80 + int(20 * (i + 1) / total))

        # Report extra rasters
        if len(results_info) > 1:
            feedback.pushInfo("Additional scenario rasters created:")
            for lbl, path in results_info:
                if lbl != primary_label_runtime:
                    feedback.pushInfo(f"  - {lbl}: {path}")

        # Determine primary path
        primary_path = dict(results_info).get(primary_label_runtime, results_info[0][1])

        # ---- Final summary in the Processing panel / Python console ----
        try:
            rl_used = float(codec_info['rls'].get(primary_rp_key, 0.0)) if primary_rp_key else 0.0
        except Exception:
            rl_used = 0.0

        station_id = codec_info.get('station_id', '')
        lon = codec_info.get('lon', float('nan'))
        lat = codec_info.get('lat', float('nan'))
        dist_km = codec_info.get('dist_km', float('nan'))

        # Station selection mode
        if not codec_csv:
            station_mode = "None (SLR only)"
        elif station_manual:
            station_mode = "Manual override"
        elif station_choice and station_choice != "Auto (nearest to AOI)":
            station_mode = "User-selected"
        else:
            station_mode = "Auto (nearest to AOI)"

        # Primary raster info (CRS & pixel size)
        try:
            prim_rl = QgsRasterLayer(primary_path, "primary", "gdal")
            px = abs(prim_rl.rasterUnitsPerPixelX()) if prim_rl.isValid() else float('nan')
            py = abs(prim_rl.rasterUnitsPerPixelY()) if prim_rl.isValid() else float('nan')
            cell_area = (px * py) if (px and py) else float('nan')
            rcrs = prim_rl.crs().authid() if (prim_rl.isValid() and prim_rl.crs().isValid()) else "unknown"
        except Exception:
            px = py = cell_area = float('nan')
            rcrs = "unknown"

        # AOI info
        if aoi_layer and aoi_layer.isValid():
            aoi_name = aoi_layer.name()
            aoi_cnt = aoi_layer.featureCount()
            aoi_crs = aoi_layer.crs().authid() if aoi_layer.crs().isValid() else "unknown"
            aoi_line = f"{aoi_name} — {aoi_cnt} features, CRS {aoi_crs}"
        else:
            aoi_line = "None"

        # List scenarios with thresholds and output paths
        # (thresholds come from the `scenarios` list; paths from `results_info`)
        thr_map = {lbl: thr for (lbl, thr, _rk) in scenarios}
        lines = []
        for lbl, path in results_info:
            t = thr_map.get(lbl, float('nan'))
            lines.append(f"  - {lbl:>14}: threshold {t:.3f} m  →  {path}")
        scenarios_block = "\n".join(lines)

        rp_label_txt = ("none" if primary_rp_key is None else f"{primary_rp_key}-yr")
        ar6_csv_name = os.path.basename(csv_path) if csv_path else "—"
        codec_csv_name = os.path.basename(codec_csv) if codec_csv else "—"
        dem_crs = dem_layer.crs().authid() if dem_layer.crs().isValid() else "unknown"

        feedback.pushInfo(
            "===== RUN SUMMARY =====\n"
            "Inputs:\n"
            f"  AR6 CSV: {ar6_csv_name}; Scenario={ssp_ui}, Year={year_str}, Percentile={pctl_ui}\n"
            f"  Vertical offset: {vlm:.3f} m\n"
            f"  DEM CRS: {dem_crs}\n"
            f"  CODEC CSV: {codec_csv_name}; Station mode: {station_mode}\n"
            f"  Station ID: {station_id}\n"
            f"  Station coords: ({lon:.5f}, {lat:.5f})  distance: {dist_km:.1f} km\n"
            "\n"
            "Levels (metres):\n"
            f"  AR6 SLR:      {level_csv:.3f}\n"
            f"  Offset:       {vlm:.3f}\n"
            f"  Base SLR:     {base_level_m:.3f}\n"
            f"  RP ({rp_label_txt:>6}): {rl_used:.3f}\n"
            f"  TOTAL thresh: {base_level_m + rl_used:.3f}\n"
            "\n"
            "Outputs:\n"
            f"  Primary raster: {primary_label_runtime}  →  {primary_path}\n"
            f"  Raster CRS: {rcrs}; pixel {px:.2f} × {py:.2f} m (area {cell_area:.2f} m²)\n"
            f"  AOI: {aoi_line}\n"
            "\n"
            "Scenarios & thresholds:\n"
            f"{scenarios_block}\n"
        )

        # Generate dynamic names for outputs
        ssp_short = ssp_ui.replace("SSP", "").replace("-", "").replace(".", "")  # "245" from "SSP2-4.5"
        pctl_short = pctl_ui.split()[0]  # "p50" from "p50 (median)"
        rp_short = primary_label_fixed.replace("SLR + ", "RP").replace("-yr", "")  # "RP100" from "SLR + 100-yr"
        if rp_short == "SLR only":
            rp_short = "SLRonly"

        # Dynamic name format: "Flood_SSP245_2050_p50_RP100"
        dynamic_name_raster = f"Flood_{ssp_short}_{year_str}_{pctl_short}_{rp_short}"
        dynamic_name_aoi = f"AOI_Stats_{ssp_short}_{year_str}_{pctl_short}_{rp_short}"

        # Set layer names for better identification
        try:
            primary_layer = QgsProcessingUtils.mapLayerFromString(primary_path, context)
            if primary_layer:
                primary_layer.setName(dynamic_name_raster)
                feedback.pushInfo(f"✓ Output raster named: {dynamic_name_raster}")
        except:
            pass  # Layer naming is optional, don't fail if it doesn't work

        if out_primary_aoi_sink:
            try:
                aoi_layer = QgsProcessingUtils.mapLayerFromString(out_primary_aoi_sink, context)
                if aoi_layer:
                    aoi_layer.setName(dynamic_name_aoi)
                    feedback.pushInfo(f"✓ Output AOI named: {dynamic_name_aoi}")
            except:
                pass

        return {self.O_RASTER: primary_path, self.O_AOI: out_primary_aoi_sink}
