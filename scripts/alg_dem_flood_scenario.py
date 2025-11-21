# -*- coding: utf-8 -*-
"""
DEM → Flooded extent + AOI stats (AR6 CSV; matches your Data schema)

CSV expected at:  Data/slr_ipcc_ar6_sea_level_projection_global_total.csv
Columns: process, confidence, scenario (ssp119/126/245/370/585),
         quantile (5/17/50/83/95), years 2020..2150 (metres)
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterVectorLayer,
    QgsProcessingParameterFile, QgsProcessingParameterEnum,
    QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFeatureSink, QgsProcessingContext,
    QgsProcessingUtils, QgsCoordinateReferenceSystem, QgsFeatureSink,
    QgsField, QgsUnitTypes, QgsRasterLayer, QgsVectorLayer, QgsFeature, QgsFields, QgsWkbTypes
)
from qgis import processing
import csv, os


class DemFloodScenarioAlgorithm(QgsProcessingAlgorithm):
    # parameter keys
    P_DEM="DEM"; P_AOI="AOI"; P_CSV="AR6_CSV"; P_SSP="SCENARIO"; P_YEAR="YEAR"; P_PCTL="PERCENTILE"; P_VLM="VERTICAL_OFFSET"
    O_RASTER="FLOODED_RASTER"; O_AOI="AOI_WITH_STATS"

    # UI options (mapped internally to CSV codes)
    SSP_OPTIONS = ["SSP1-1.9","SSP1-2.6","SSP2-4.5","SSP3-7.0","SSP5-8.5"]
    _SSP_MAP = {"SSP1-1.9":"ssp119","SSP1-2.6":"ssp126","SSP2-4.5":"ssp245","SSP3-7.0":"ssp370","SSP5-8.5":"ssp585"}
    PCTL_OPTIONS = ["p50 (median)","p17 (likely lower)","p83 (likely upper)","p05 (low)","p95 (high)"]
    _PCTL_MAP = {"p50 (median)":50,"p17 (likely lower)":17,"p83 (likely upper)":83,"p05 (low)":5,"p95 (high)":95}

    def tr(self, s): return QCoreApplication.translate("DemFloodScenarioAlgorithm", s)
    def name(self): return "dem_flood_scenario"
    def displayName(self): return self.tr("DEM → Flooded extent + AOI stats (AR6 CSV)")
    def group(self): return self.tr("Flood Exposure")
    def groupId(self): return "flood_exposure"
    def shortHelpString(self):
        return self.tr("Derives sea level from the bundled IPCC AR6 CSV (process=total) by scenario/year/percentile, "
                       "applies an optional vertical offset (m), thresholds the DEM to a flooded mask, and computes "
                       "flooded area statistics per AOI polygon.")
    def createInstance(self): return DemFloodScenarioAlgorithm()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    # ---------- helpers ----------
    @staticmethod
    def _default_csv_path():
        here = os.path.dirname(os.path.abspath(__file__))   # .../plugins/<plugin>/scripts
        plugin_root = os.path.dirname(here)                 # .../plugins/<plugin>
        return os.path.join(plugin_root, "Data", "slr_ipcc_ar6_sea_level_projection_global_total.csv")

    def _read_years_from_csv(self, csv_path):
        """Safely read year columns from CSV, returning empty list on any error"""
        try:
            if not os.path.exists(csv_path):
                return []
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                rdr = csv.reader(f)
                headers = next(rdr)
                # first 4 are process, confidence, scenario, quantile
                return [h for h in headers if h.isdigit()]
        except Exception:
            # Return empty list if any error during CSV read (file corrupt, permissions, etc)
            return []

    def _level_from_csv(self, csv_path, ssp_ui, year_str, pctl_ui):
        """
        Safely read sea level rise value from CSV with validation against CSV injection
        """
        if not os.path.exists(csv_path):
            raise QgsProcessingException(f"AR6 CSV not found: {csv_path}")

        # Validate file size (prevent memory exhaustion)
        file_size = os.path.getsize(csv_path)
        MAX_CSV_SIZE = 10 * 1024 * 1024  # 10 MB
        if file_size > MAX_CSV_SIZE:
            raise QgsProcessingException(
                f"CSV file too large ({file_size / 1024 / 1024:.1f} MB). Maximum: {MAX_CSV_SIZE / 1024 / 1024:.0f} MB"
            )

        scenario_code = self._SSP_MAP[ssp_ui]
        quant = self._PCTL_MAP[pctl_ui]

        try:
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                rdr = csv.DictReader(f)
                required = {"process","scenario","quantile",year_str}
                missing = required.difference(set(rdr.fieldnames or []))
                if missing:
                    raise QgsProcessingException(f"CSV missing columns: {', '.join(sorted(missing))}")

                for row_num, row in enumerate(rdr, start=2):  # Start at 2 (header is row 1)
                    # Limit number of rows processed (prevent DoS)
                    if row_num > 10000:
                        raise QgsProcessingException("CSV has too many rows (>10000). File may be corrupted.")

                    if row.get("process","").strip().lower() != "total":
                        continue
                    if row.get("scenario","").strip().lower() != scenario_code:
                        continue
                    try:
                        if int(row.get("quantile","-1")) != quant:
                            continue
                    except (ValueError, TypeError):
                        continue

                    # Get and validate the sea level value
                    slr_value_str = row.get(year_str, "").strip()

                    # Prevent CSV injection: reject values starting with formula characters
                    if slr_value_str and slr_value_str[0] in ('=', '+', '-', '@', '\t', '\r'):
                        raise QgsProcessingException(
                            f"Invalid data format in CSV at row {row_num}. "
                            "Value appears to contain formula characters."
                        )

                    try:
                        slr_value = float(slr_value_str)
                        # Sanity check: sea level rise should be reasonable (-5m to +10m by 2150)
                        if not (-5.0 <= slr_value <= 10.0):
                            raise ValueError(f"Sea level value {slr_value} outside reasonable range")
                        return slr_value
                    except (ValueError, TypeError) as e:
                        raise QgsProcessingException(
                            f"Non-numeric SLR for {ssp_ui}/{year_str}/{pctl_ui} at row {row_num}: '{slr_value_str}'"
                        )

        except csv.Error as e:
            raise QgsProcessingException(f"CSV parsing error: {str(e)}")
        except UnicodeDecodeError as e:
            raise QgsProcessingException(f"CSV encoding error: {str(e)}. File may be corrupted.")

        raise QgsProcessingException(
            f"No CSV match for process=total, scenario={scenario_code}, quantile={quant}, year={year_str}."
        )

    # ---------- parameters ----------
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.P_DEM, self.tr("DEM (m)")))
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.P_AOI, self.tr("AOI polygons (optional)"),
            types=[QgsProcessing.TypeVectorPolygon], optional=True
        ))
        csv_default = self._default_csv_path()
        self.addParameter(QgsProcessingParameterFile(
            self.P_CSV, self.tr("AR6 CSV"),
            behavior=QgsProcessingParameterFile.File, fileFilter="CSV (*.csv)",
            defaultValue=csv_default
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_SSP, self.tr("Scenario (SSP)"),
            options=self.SSP_OPTIONS, defaultValue=1  # SSP1-2.6
        ))
        years = self._read_years_from_csv(csv_default) or [str(y) for y in range(2020,2151,10)]
        self._year_options = years
        self.addParameter(QgsProcessingParameterEnum(
            self.P_YEAR, self.tr("Year"),
            options=years, defaultValue=years.index("2100") if "2100" in years else 0
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_PCTL, self.tr("Percentile"),
            options=self.PCTL_OPTIONS, defaultValue=0  # p50
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.P_VLM, self.tr("Vertical offset (m, optional)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.O_RASTER, self.tr("Flooded raster (GeoTIFF)")
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_AOI, self.tr("AOI with flooded statistics")
        ))

    # ---------- main ----------
    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        # Inputs
        dem_layer = self.parameterAsRasterLayer(parameters, self.P_DEM, context)
        if dem_layer is None:
            raise QgsProcessingException("DEM is required.")

        # Handle AOI layer with robust validation
        aoi_layer = self.parameterAsVectorLayer(parameters, self.P_AOI, context)
        if aoi_layer:
            # If it's a memory layer, ensure features are properly copied
            if aoi_layer.dataProvider().name() == 'memory':
                feedback.pushInfo("Memory layer detected, ensuring features are properly copied...")
                # Create a new memory layer and copy features
                mem_layer = QgsVectorLayer(f"MultiPolygon?crs={aoi_layer.crs().authid()}", "aoi_copy", "memory")
                mem_provider = mem_layer.dataProvider()
                
                # Copy fields
                mem_provider.addAttributes(aoi_layer.fields())
                mem_layer.updateFields()
                
                # Copy features
                features = []
                for feat in aoi_layer.getFeatures():
                    new_feat = QgsFeature(mem_layer.fields())
                    new_feat.setGeometry(feat.geometry())
                    new_feat.setAttributes(feat.attributes())
                    features.append(new_feat)
                
                if features:
                    mem_provider.addFeatures(features)
                    feedback.pushInfo(f"Successfully copied {len(features)} features to memory layer")
                    aoi_layer = mem_layer
                else:
                    feedback.pushWarning("Source layer appears to have no features to copy")

        csv_path = self.parameterAsFile(parameters, self.P_CSV, context) or self._default_csv_path()
        if not os.path.isabs(csv_path):
            plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            csv_path = os.path.normpath(os.path.join(plugin_root, csv_path))

        ssp_ui  = self.SSP_OPTIONS[self.parameterAsEnum(parameters, self.P_SSP, context)]
        year_str = self._year_options[self.parameterAsEnum(parameters, self.P_YEAR, context)]
        pctl_ui = self.PCTL_OPTIONS[self.parameterAsEnum(parameters, self.P_PCTL, context)]
        vlm     = self.parameterAsDouble(parameters, self.P_VLM, context)

        # Water level
        level_csv = self._level_from_csv(csv_path, ssp_ui, year_str, pctl_ui)
        level_m = level_csv + float(vlm)
        feedback.pushInfo(f"AR6 total SLR: {ssp_ui} {year_str} {pctl_ui} = {level_csv:.3f} m; "
                          f"offset {vlm:.3f} m → using {level_m:.3f} m")

        out_raster = self.parameterAsOutputLayer(parameters, self.O_RASTER, context)

        # Reproject DEM if not in metres
        dem_for_calc = dem_layer
        if (not dem_layer.crs().isValid()) or (dem_layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters):
            target_crs = aoi_layer.crs() if (aoi_layer and aoi_layer.isValid()) else QgsCoordinateReferenceSystem.fromEpsgId(3857)
            warp = processing.run(
                "gdal:warpreproject",
                {
                    "INPUT": dem_layer.source(),
                    "SOURCE_CRS": dem_layer.crs(),
                    "TARGET_CRS": target_crs,
                    "RESAMPLING": 0,  # nearest
                    "NODATA": dem_layer.dataProvider().sourceNoDataValue(1),
                    "TARGET_RESOLUTION": None,
                    "OPTIONS": "TILED=YES|COMPRESS=DEFLATE",
                    "DATA_TYPE": 6,  # Float32
                    "MULTITHREADING": True,
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context, feedback=feedback
            )
            dem_for_calc = warp["OUTPUT"]

        # Flood mask via GDAL rastercalculator (pass creation options via EXTRA)
        dem_src = dem_for_calc if isinstance(dem_for_calc, str) else dem_for_calc.source()
        calc = processing.run(
            "gdal:rastercalculator",
            {
                "INPUT_A": dem_src,
                "BAND_A": 1,
                "FORMULA": f"(A <= {level_m}) * 1",
                "NO_DATA": 0,
                "RTYPE": 0,  # Byte
                "EXTRA": "--creation-option TILED=YES --creation-option COMPRESS=DEFLATE --creation-option PREDICTOR=2",
                "OPTIONS": "",
                "OUTPUT": out_raster,
            },
            context=context, feedback=feedback
        )
        flooded_path = calc.get("OUTPUT")
        if not flooded_path:
            raise QgsProcessingException("Raster calculator failed to produce output.")

        # Load flooded raster
        flooded_rlayer = QgsProcessingUtils.mapLayerFromString(flooded_path, context)
        if flooded_rlayer is None:
            flooded_rlayer = QgsRasterLayer(flooded_path, "flooded_mask", "gdal")
            if not flooded_rlayer.isValid():
                raise QgsProcessingException("Failed to load flooded raster output.")

        # AOI stats (optional)
                # AOI stats (optional, streaming to sink — no in-place edits)
                # AOI stats (streamed; three outputs: flooded, flood_pct, flood_m2)
        aoi_out = None
        if aoi_layer and aoi_layer.isValid():
            if aoi_layer.featureCount() == 0:
                feedback.pushWarning("AOI layer is empty (no features), skipping AOI processing")
                return {self.O_RASTER: flooded_path, self.O_AOI: None}

            if not aoi_layer.extent().intersects(flooded_rlayer.extent()):
                feedback.pushWarning("AOI does not overlap with raster extent, skipping AOI processing")
                return {self.O_RASTER: flooded_path, self.O_AOI: None}

            feedback.pushInfo(f"Processing AOI layer with {aoi_layer.featureCount()} features")

            # Ensure same CRS as raster for correct pixel size usage
            if aoi_layer.crs() != flooded_rlayer.crs():
                aoi_reproj = processing.run(
                    "native:reprojectlayer",
                    {"INPUT": aoi_layer, "TARGET_CRS": flooded_rlayer.crs(),
                     "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                    context=context, feedback=feedback
                )["OUTPUT"]
            else:
                aoi_reproj = aoi_layer

            # Fast Zonal Stats: ask for COUNT and MEAN (indices are stable in QGIS 3.30)
            zs = processing.run(
                "native:zonalstatisticsfb",
                {
                    "INPUT": aoi_reproj,
                    "INPUT_RASTER": flooded_rlayer,
                    "RASTER_BAND": 1,
                    "COLUMN_PREFIX": "f_",
                    "STATISTICS": [0, 2],  # 0=COUNT, 2=MEAN (yields f_count, f_mean)
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context, feedback=feedback
            )
            zs_out = zs.get("OUTPUT")
            if isinstance(zs_out, QgsVectorLayer):
                stats_layer = zs_out
            else:
                stats_layer = QgsProcessingUtils.mapLayerFromString(zs_out, context)

            if stats_layer is None or not stats_layer.isValid():
                raise QgsProcessingException("Failed to obtain zonal statistics output layer.")

            # Prepare output fields: original + flooded, flood_pct, flood_m2
            fields_out = QgsFields()
            for f in stats_layer.fields():
                fields_out.append(f)
            fields_out.append(QgsField("flooded", QVariant.Double))   # fraction in [0,1]
            fields_out.append(QgsField("flood_pct", QVariant.Double)) # %
            fields_out.append(QgsField("flood_m2", QVariant.Double))  # m²

            sink, aoi_out = self.parameterAsSink(
                parameters, self.O_AOI, context,
                fields_out, stats_layer.wkbType(), stats_layer.crs()
            )
            if sink is None:
                raise QgsProcessingException("Could not initialise output sink for AOI stats.")

            # Indices and constants
            idx_mean  = stats_layer.fields().lookupField("f_mean")
            idx_count = stats_layer.fields().lookupField("f_count")
            # Optional fallbacks
            if idx_mean == -1:
                idx_mean = stats_layer.fields().lookupField("f_MEAN")
            if idx_count == -1:
                idx_count = stats_layer.fields().lookupField("f_COUNT")

            px = abs(flooded_rlayer.rasterUnitsPerPixelX())
            py = abs(flooded_rlayer.rasterUnitsPerPixelY())
            pix_area = float(px * py) if px and py else 0.0

            total = max(1, stats_layer.featureCount())
            for i, feat in enumerate(stats_layer.getFeatures()):
                if feedback.isCanceled():
                    break

                attrs = feat.attributes()
                geom = feat.geometry()
                flooded_frac = 0.0
                sampled_area_m2 = 0.0

                # Prefer mean directly; it's the cleanest fraction on a binary mask
                if idx_mean != -1:
                    val_mean = feat[idx_mean]
                    if val_mean is not None:
                        # Clamp for safety against numeric noise
                        flooded_frac = max(0.0, min(1.0, float(val_mean)))

                # Compute sampled area from count if available; otherwise fall back to polygon area
                if idx_count != -1:
                    val_count = feat[idx_count]
                    if val_count is not None and pix_area > 0.0:
                        sampled_area_m2 = float(val_count) * pix_area

                if sampled_area_m2 == 0.0 and geom and not geom.isEmpty():
                    # Fallback: use polygon planar area (may include gaps/NoData)
                    sampled_area_m2 = float(geom.area())

                poly_area_m2 = geom.area() if (geom and not geom.isEmpty()) else 0.0

                # Cap the raster-sampled area to the polygon area to avoid >100% due to centre-in pixels
                effective_sample_area = min(sampled_area_m2, poly_area_m2) if poly_area_m2 > 0 else sampled_area_m2

                flood_m2 = flooded_frac * effective_sample_area
                flood_pct = (flood_m2 / poly_area_m2) * 100.0 if poly_area_m2 > 0 else 0.0

                out_feat = QgsFeature(fields_out)
                out_feat.setGeometry(geom)
                out_feat.setAttributes(attrs + [flooded_frac, flood_pct, flood_m2])
                sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

                if i % 1000 == 0 or i == total - 1:
                    feedback.setProgress(80 + int(20 * (i + 1) / total))

        # Generate dynamic names for outputs
        ssp_short = ssp_ui.replace("SSP", "").replace("-", "").replace(".", "")  # "245" from "SSP2-4.5"
        pctl_short = pctl_ui.split()[0]  # "p50" from "p50 (median)"

        # Dynamic name format: "Flood_SSP245_2050_p50"
        dynamic_name_raster = f"Flood_{ssp_short}_{year_str}_{pctl_short}"
        dynamic_name_aoi = f"AOI_Stats_{ssp_short}_{year_str}_{pctl_short}"

        # Set layer names for better identification
        try:
            flooded_layer = QgsProcessingUtils.mapLayerFromString(flooded_path, context)
            if flooded_layer:
                flooded_layer.setName(dynamic_name_raster)
                feedback.pushInfo(f"✓ Output raster named: {dynamic_name_raster}")
        except Exception as e:
            feedback.pushDebugInfo(f"Could not set raster layer name: {str(e)}")

        if aoi_out:
            try:
                aoi_layer = QgsProcessingUtils.mapLayerFromString(aoi_out, context)
                if aoi_layer:
                    aoi_layer.setName(dynamic_name_aoi)
                    feedback.pushInfo(f"✓ Output AOI named: {dynamic_name_aoi}")
            except Exception as e:
                feedback.pushDebugInfo(f"Could not set AOI layer name: {str(e)}")

        return {self.O_RASTER: flooded_path, self.O_AOI: aoi_out}

