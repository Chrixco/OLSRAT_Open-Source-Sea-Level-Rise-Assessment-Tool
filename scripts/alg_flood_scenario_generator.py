# -*- coding: utf-8 -*-
"""
Flood Scenarios from IPCC SLR Projections (AOI Polygon, FAST)
- Builds a binary inundation raster (DEM <= SLR)
- FAST AOI classification via rasterized AOI IDs + NumPy bincount
- Writes Shapefile(s) that include a 'Flooded' Int (0/1) column
- Optional detailed output with 'Flood_Pct'
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from osgeo import gdal
import processing

from qgis.PyQt.QtCore import QVariant, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFileDestination,
    QgsProcessingException,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsVectorFileWriter,
)
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry


class AlgIPCCScenarios(QgsProcessingAlgorithm):
    # Params / outputs
    INPUT_DEM = "INPUT_DEM"
    INPUT_AOI = "INPUT_AOI"
    USE_CSV = "USE_CSV"
    SLR_SCENARIO = "SLR_SCENARIO"
    SLR_LEVEL = "SLR_LEVEL"
    OUTPUT_RASTER = "OUTPUT_RASTER"
    OUTPUT_VECTOR_SHP = "OUTPUT_VECTOR_SHP"
    OUTPUT_DETAILED_SHP = "OUTPUT_DETAILED_SHP"
    OUTPUT_SPLIT_SHP = "OUTPUT_SPLIT_SHP"

    # Data
    DATA_FILENAME = "slr_ipcc_ar6_sea_level_projection_global_total.csv"

    # perf knobs
    BATCH_SIZE = 2000
    PROGRESS_UPDATE_INTERVAL = 2000

    # ------------ UI ------------
    def initAlgorithm(self, _config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM, self.tr("Digital Elevation Model (DEM)")))

        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT_AOI, self.tr("Area of Interest (Polygon, SHP recommended)"),
            [QgsProcessing.TypeVectorPolygon], optional=True))

        options, self._scenario_map, error_note = self._build_scenario_enum()

        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_CSV, self.tr("Use SLR from CSV scenario (recommended)"),
            defaultValue=(error_note is None)
        ))

        self.addParameter(QgsProcessingParameterEnum(
            self.SLR_SCENARIO,
            self.tr("Select ONE SLR Scenario (Scenario | Quantile | Year)"),
            options=options, allowMultiple=False, defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.SLR_LEVEL, self.tr("Manual SLR (m) — used only if CSV is OFF"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.0))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_RASTER, self.tr("Inundation Raster (binary GTiff)")))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_VECTOR_SHP,
            self.tr("AOI with Flooded flag (Shapefile, adds 'Flooded' Int 0/1)"),
            fileFilter="ESRI Shapefile (*.shp)"))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_DETAILED_SHP,
            self.tr("AOI with Flooded & Flood_Pct (Shapefile) [optional]"),
            fileFilter="ESRI Shapefile (*.shp)"))

        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_SPLIT_SHP,
            self.tr("AOI split (two shapefiles: Flooded / Non-Flooded) [optional]"),
            fileFilter="ESRI Shapefile (*.shp)"))

    # ------------ CORE ------------
    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        aoi = self.parameterAsVectorLayer(parameters, self.INPUT_AOI, context)
        use_csv = self.parameterAsBool(parameters, self.USE_CSV, context)
        scen_idx = self.parameterAsEnum(parameters, self.SLR_SCENARIO, context)
        manual_slr = self.parameterAsDouble(parameters, self.SLR_LEVEL, context)
        out_raster = self.parameterAsOutputLayer(parameters, self.OUTPUT_RASTER, context)
        shp_path = self.parameterAsFileOutput(parameters, self.OUTPUT_VECTOR_SHP, context)
        detailed_shp_path = self.parameterAsFileOutput(parameters, self.OUTPUT_DETAILED_SHP, context)
        split_shp_path = self.parameterAsFileOutput(parameters, self.OUTPUT_SPLIT_SHP, context)

        if not dem or not dem.isValid():
            raise QgsProcessingException("DEM layer is missing or invalid.")

        # Ensure AOI CRS matches DEM CRS
        if aoi and aoi.isValid():
            if aoi.crs() != dem.crs():
                feedback.pushInfo("Reprojecting AOI to match DEM CRS…")
                aoi = processing.run(
                    "native:reprojectlayer",
                    {"INPUT": aoi, "TARGET_CRS": dem.crs(), "OUTPUT": "TEMPORARY_OUTPUT"},
                    context=context, feedback=feedback
                )["OUTPUT"]

        # SLR value
        if use_csv:
            if not self._scenario_map or (len(self._scenario_map) == 1 and self._scenario_map[0][0] == "NA"):
                raise QgsProcessingException(
                    f"CSV not available. Expected at <plugin_root>/data/{self.DATA_FILENAME}."
                )
            if scen_idx is None or scen_idx < 0 or scen_idx >= len(self._scenario_map):
                raise QgsProcessingException("Invalid SLR scenario selection.")
            scenario, quantile, year, slr_value = self._scenario_map[scen_idx]
            feedback.pushInfo(f"Using CSV scenario → {scenario} | {quantile} | {year} → SLR={slr_value} m")
        else:
            slr_value = float(manual_slr)
            feedback.pushInfo(f"Using manual SLR value → {slr_value} m")

        # 1) Binary inundation raster
        inund_layer = self._create_inundation_raster(dem, slr_value, out_raster, context, feedback)

        # 2) AOI fast classification (optional)
        shp_written = None
        detailed_written = None
        split_written = None
        if aoi and shp_path:
            self._process_aoi_with_flooding(
                aoi=aoi, inund_layer=inund_layer, slr_value=slr_value,
                shp_path=shp_path, detailed_shp_path=detailed_shp_path,
                split_shp_path=split_shp_path, context=context, feedback=feedback
            )
            shp_written = shp_path
            detailed_written = detailed_shp_path or None
            split_written = split_shp_path or None
        else:
            feedback.pushInfo("No AOI supplied → skipping AOI outputs.")

        feedback.setProgress(100)
        return {
            self.OUTPUT_RASTER: out_raster,
            self.OUTPUT_VECTOR_SHP: shp_written,
            self.OUTPUT_DETAILED_SHP: detailed_written,
            self.OUTPUT_SPLIT_SHP: split_written
        }

    # ------------ helpers ------------
    def _create_inundation_raster(self, dem, slr_value, out_raster, context, feedback):
        """Create a binary inundation raster (0/1)."""
        entries = []
        dem_entry = QgsRasterCalculatorEntry()
        dem_entry.ref = "dem@1"
        dem_entry.raster = dem
        dem_entry.bandNumber = 1
        entries.append(dem_entry)

        expr = f"(dem@1 <= {slr_value})"
        feedback.pushInfo(f"Raster calculation expression: {expr}")

        tmp_calc = os.path.join(tempfile.mkdtemp(), "calc.tif")
        calc = QgsRasterCalculator(expr, tmp_calc, "GTiff",
                                   dem.extent(), dem.width(), dem.height(), entries)
        rc = calc.processCalculation(feedback)
        if rc != 0:
            raise QgsProcessingException(f"Raster calculation failed (code {rc}).")

        processing.run(
            "gdal:translate",
            {
                "INPUT": tmp_calc,
                "TARGET_CRS": None,
                "NODATA": 0,
                "COPY_SUBDATASETS": False,
                "OPTIONS": "TILED=YES|COMPRESS=DEFLATE|PREDICTOR=2",
                "EXTRA": "",
                "DATA_TYPE": 1,
                "OUTPUT": out_raster
            },
            context=context, feedback=feedback
        )

        inund_layer = QgsRasterLayer(out_raster, "inundation_0_1")
        if not inund_layer.isValid():
            raise QgsProcessingException("Inundation raster written but could not be opened.")
        feedback.pushInfo(f"✓ Inundation raster written: {out_raster}")
        return inund_layer

    def _process_aoi_with_flooding(self, aoi, inund_layer, slr_value,
                                   shp_path, detailed_shp_path, split_shp_path,
                                   context, feedback):
        """AOI classification via rasterized IDs + NumPy bincount."""
        feedback.pushInfo("Fast AOI processing: rasterize IDs + NumPy bincount…")
        feedback.setProgress(30)

        # Extent check
        dem_extent = inund_layer.extent()
        aoi_extent = aoi.extent()
        if not dem_extent.intersects(aoi_extent):
            feedback.reportError("AOI does not overlap DEM extent → skipping AOI outputs.")
            self._create_output_shapefile_no_flood(aoi, shp_path, context, feedback)
            return

        # Ensure AOI has integer ID
        id_field = None
        for f in aoi.fields():
            if f.typeName().lower().startswith("int"):
                id_field = f.name()
                break
        if id_field is None:
            aoi_with_id = processing.run(
                "native:fieldcalculator",
                {
                    "INPUT": aoi,
                    "FIELD_NAME": "zz_id",
                    "FIELD_TYPE": 1,
                    "FIELD_LENGTH": 10,
                    "NEW_FIELD": True,
                    "FORMULA": "$id",
                    "OUTPUT": "TEMPORARY_OUTPUT"
                },
                context=context, feedback=feedback
            )["OUTPUT"]
            id_field = "zz_id"
            aoi_use = aoi_with_id
        else:
            aoi_use = aoi

        # Save inundation raster
        tmpdir = tempfile.mkdtemp(prefix="slr_fast_")
        inund_path = os.path.join(tmpdir, "inund.tif")
        processing.run(
            "gdal:translate",
            {
                "INPUT": inund_layer,
                "TARGET_CRS": None,
                "NODATA": 0,
                "COPY_SUBDATASETS": False,
                "OPTIONS": "TILED=YES|COMPRESS=DEFLATE|PREDICTOR=2",
                "EXTRA": "",
                "DATA_TYPE": 1,
                "OUTPUT": inund_path
            },
            context=context, feedback=feedback
        )
        ds_in = gdal.Open(inund_path)
        if ds_in is None:
            raise QgsProcessingException("Failed to open inundation raster.")

        width, height = ds_in.RasterXSize, ds_in.RasterYSize
        gt = ds_in.GetGeoTransform()
        xmin, px_w, _, ymax, _, px_h = gt
        xmax = xmin + width * px_w
        ymin = ymax + height * px_h
        xres = float(abs(px_w))
        yres = float(abs(px_h))
        feedback.pushInfo(f"DEM pixel size: {px_w}, {px_h}")
        feedback.pushInfo(f"Rasterizing with resolution: {xres}, {yres}")
        feedback.pushInfo(f"DEM extent: {xmin},{ymin} - {xmax},{ymax}")

        # Rasterize AOI IDs
        aoi_ras = os.path.join(tmpdir, "aoi_ids.tif")
        processing.run(
            "gdal:rasterize",
            {
                "INPUT": aoi_use,
                "FIELD": id_field,
                "BURN": 0,
                "USE_Z": False,
                "UNITS": 1,
                "X_RES": xres,
                "Y_RES": yres,
                "EXTENT": f"{xmin},{xmax},{ymin},{ymax}",
                "NODATA": 0,
                "OPTIONS": "TILED=YES|COMPRESS=DEFLATE|PREDICTOR=2",
                "DATA_TYPE": 5,
                "INIT": 0,
                "INVERT": False,
                "EXTRA": "",
                "OUTPUT": aoi_ras
            },
            context=context, feedback=feedback
        )
        ds_id = gdal.Open(aoi_ras)
        if ds_id is None:
            raise QgsProcessingException("Failed to open rasterized AOI IDs.")

        arr_in = ds_in.ReadAsArray()
        arr_id = ds_id.ReadAsArray()
        feedback.pushInfo(f"Inundation raster shape: {arr_in.shape}, AOI raster shape: {arr_id.shape}")

        valid = arr_id > 0
        if not np.any(valid):
            feedback.pushWarning("No AOI pixels overlapped the inundation raster extent.")
            self._create_output_shapefile_no_flood(aoi_use, shp_path, context, feedback)
            return

        # Zonal bincount
        max_id = int(arr_id.max())
        flood_counts = np.bincount(arr_id[valid].ravel(),
                                   weights=arr_in[valid].ravel(),
                                   minlength=max_id + 1)
        tot_counts = np.bincount(arr_id[valid].ravel(),
                                 minlength=max_id + 1)

        rows = []
        for oid in range(1, max_id + 1):
            t = int(tot_counts[oid])
            f = float(flood_counts[oid])
            Flooded = 1 if f > 0 else 0
            Flood_Pct = (f / t) * 100.0 if t > 0 else 0.0
            rows.append({"__oid__": oid, "Flooded": Flooded, "Flood_Pct": Flood_Pct})

        join_csv = os.path.join(tmpdir, "join.csv")
        pd.DataFrame(rows).to_csv(join_csv, index=False)

        joined = processing.run(
            "native:joinattributestable",
            {
                "INPUT": aoi_use,
                "FIELD": id_field,
                "INPUT_2": join_csv,
                "FIELD_2": "__oid__",
                "FIELDS_TO_COPY": ["Flooded", "Flood_Pct"],
                "METHOD": 1,
                "DISCARD_NONMATCHING": False,
                "PREFIX": "",
                "OUTPUT": "TEMPORARY_OUTPUT"
            },
            context=context, feedback=feedback
        )["OUTPUT"]

        out = QgsVectorLayer(joined, "aoi_flooded", "ogr")
        if not out.isValid():
            raise QgsProcessingException("Join result is invalid.")

        # Write outputs
        if shp_path:
            self._write_shapefile(self._strip_to_flooded(out), shp_path, context, feedback)
        if detailed_shp_path:
            self._write_shapefile(out, detailed_shp_path, context, feedback)
        if split_shp_path:
            base = Path(split_shp_path)
            flooded_path = str(base.parent / f"{base.stem}_flooded.shp")
            nonflooded_path = str(base.parent / f"{base.stem}_nonflooded.shp")

            fl = processing.run(
                "native:extractbyattribute",
                {"INPUT": out, "FIELD": "Flooded", "OPERATOR": 0, "VALUE": 1, "OUTPUT": "TEMPORARY_OUTPUT"},
                context=context, feedback=feedback
            )["OUTPUT"]
            nfl = processing.run(
                "native:extractbyattribute",
                {"INPUT": out, "FIELD": "Flooded", "OPERATOR": 0, "VALUE": 0, "OUTPUT": "TEMPORARY_OUTPUT"},
                context=context, feedback=feedback
            )["OUTPUT"]

            self._write_shapefile(QgsVectorLayer(fl, "aoi_flooded_only", "ogr"), flooded_path, context, feedback)
            self._write_shapefile(QgsVectorLayer(nfl, "aoi_nonflooded_only", "ogr"), nonflooded_path, context, feedback)

        feedback.setProgress(100)

    def _strip_to_flooded(self, layer):
        """Return AOI with only original attrs + Flooded column."""
        out_fields = QgsFields()
        for f in layer.fields():
            if f.name() != "Flood_Pct":
                out_fields.append(f)

        mem = QgsVectorLayer(f"{layer.wkbType()}?crs={layer.crs().authid()}", "mem", "memory")
        prov = mem.dataProvider()
        prov.addAttributes(out_fields)
        mem.updateFields()

        feats = []
        for feat in layer.getFeatures():
            attrs = [feat[field.name()] for field in out_fields]
            newf = QgsFeature(out_fields)
            newf.setGeometry(feat.geometry())
            newf.setAttributes(attrs)
            feats.append(newf)
        prov.addFeatures(feats)
        mem.updateExtents()
        return mem

    def _create_output_shapefile_no_flood(self, aoi, shp_path, context, feedback):
        out_fields = QgsFields()
        for f in aoi.fields():
            out_fields.append(f)
        out_fields.append(QgsField("Flooded", QVariant.Int))

        mem = QgsVectorLayer(f"Polygon?crs={aoi.crs().authid()}", "mem", "memory")
        prov = mem.dataProvider()
        prov.addAttributes(out_fields)
        mem.updateFields()

        feats = []
        total = aoi.featureCount() or 1
        for i, feat in enumerate(aoi.getFeatures()):
            outf = QgsFeature(out_fields)
            outf.setGeometry(feat.geometry())
            outf.setAttributes(list(feat.attributes()) + [0])  # Always not flooded
            feats.append(outf)
            if len(feats) >= self.BATCH_SIZE:
                prov.addFeatures(feats)
                feats = []
            if i % self.PROGRESS_UPDATE_INTERVAL == 0:
                feedback.setProgress(80 + int(20 * i / total))
        if feats:
            prov.addFeatures(feats)

        self._write_shapefile(mem, shp_path, context, feedback)

    def _write_shapefile(self, layer, shp_path, context, feedback):
        Path(shp_path).parent.mkdir(parents=True, exist_ok=True)
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "ESRI Shapefile"
        opts.fileEncoding = "UTF-8"
        opts.layerName = Path(shp_path).stem[:10]  # Respect shapefile name length limits
        res = QgsVectorFileWriter.writeAsVectorFormatV3(layer, shp_path, context.transformContext(), opts)
        if isinstance(res, tuple):
            err, msg = res[0], (res[1] if len(res) > 1 else "")
        else:
            err, msg = res, ""
        if err != QgsVectorFileWriter.NoError:
            raise QgsProcessingException(f"Failed to write shapefile: {msg or err}")
        feedback.pushInfo(f"✓ Wrote: {shp_path}")

    def _build_scenario_enum(self):
        try:
            df = self._load_projection_table()
        except Exception as e:
            msg = str(e)
            return ([f"[CSV Error: {msg}]"], [("NA", "NA", "NA", 0.0)], msg)

        cols_lower = {c.lower(): c for c in df.columns}
        for need in ("scenario", "quantile"):
            if need not in cols_lower:
                msg = f'missing "{need}"'
                return ([f"[CSV error: {msg}]"], [("NA", "NA", "NA", 0.0)], msg)

        scen_col = cols_lower["scenario"]
        quant_col = cols_lower["quantile"]
        year_cols = [c for c in df.columns if str(c).isdigit() and len(str(c)) == 4]
        if not year_cols:
            year_cols = [c for c in df.columns if c not in (scen_col, quant_col)]

        options = []
        scenario_map = []
        for _, row in df.iterrows():
            scenario = str(row[scen_col]).strip()
            quant = str(row[quant_col]).strip()
            for ycol in year_cols:
                try:
                    slr = float(row[ycol])
                except Exception:
                    continue
                options.append(f"{scenario} | {quant} | {ycol}")
                scenario_map.append((scenario, quant, str(ycol), slr))

        if not options:
            msg = "no valid entries"
            return ([f"[CSV error: {msg}]"], [("NA", "NA", "NA", 0.0)], msg)

        return (options, scenario_map, None)

    def _load_projection_table(self):
        script_dir = Path(__file__).resolve().parent
        plugin_root = script_dir.parent
        candidate_dirs = [plugin_root / "data", plugin_root / "Data", plugin_root]
        canonical = self.DATA_FILENAME
        variants = [
            canonical,
            canonical + ".csv",
            canonical.replace("global", "globa"),
            canonical.replace("global", "globa") + ".csv",
            "slr_ipcc_ar6_sea_level_projection.csv",
            "ipcc_slr_projections.csv",
        ]
        for d in candidate_dirs:
            for v in variants:
                p = d / v
                if p.exists() and p.is_file():
                    return pd.read_csv(p)
        for d in candidate_dirs:
            if d.exists():
                for p in d.rglob("*slr*global*total*.csv"):
                    try:
                        df = pd.read_csv(p)
                        if not df.empty:
                            return df
                    except Exception:
                        pass
        raise QgsProcessingException(f"Cannot find '{self.DATA_FILENAME}' under plugin 'data' folder.")

    # ------------ metadata ------------
    def name(self): 
        return "ipcc_flood_scenarios_polygon_fast"

    def displayName(self): 
        return self.tr("Flood Scenarios (AOI Polygon, FAST)")

    def group(self): 
        return self.tr("Flood Exposure")

    def groupId(self): 
        return "flood_exposure"

    def shortHelpString(self):
        return self.tr(
            "Creates a binary inundation raster (DEM <= SLR) and classifies polygon AOI via a fast "
            "rasterized-ID + NumPy bincount method. Outputs Shapefile(s) with 'Flooded' (0/1) and "
            "optional 'Flood_Pct'. Split AOI output is written as two separate files: "
            "one for flooded features and one for non-flooded."
        )

    def createInstance(self):
        return AlgIPCCScenarios()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def tr(self, m): 
        return QCoreApplication.translate("AlgIPCCScenarios", m)

