# -*- coding: utf-8 -*-
"""
Inundation mapping from DEM with user-defined water level

Thresholds a DEM by a user-provided water level (metres),
produces a binary flood raster, and computes flooded
area statistics per AOI polygon.
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterVectorLayer,
    QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination,
    QgsProcessingParameterFeatureSink, QgsProcessingContext,
    QgsProcessingUtils, QgsFeature, QgsFields, QgsField,
    QgsVectorLayer, QgsRasterLayer, QgsFeatureSink
)
from qgis import processing


class AlgInundation(QgsProcessingAlgorithm):
    # parameter keys
    P_DEM = "DEM"
    P_AOI = "AOI"
    P_LEVEL = "WATER_LEVEL"
    O_RASTER = "FLOODED_RASTER"
    O_AOI = "AOI_WITH_STATS"

    def tr(self, s): 
        return QCoreApplication.translate("AlgInundation", s)

    def name(self): 
        return "inundation"

    def displayName(self): 
        return self.tr("DEM → Flooded extent + AOI stats (User level)")

    def group(self):
        return self.tr("Flood Exposure")

    def groupId(self):
        return "flood_exposure"

    def shortHelpString(self):
        return self.tr(
            "Thresholds a DEM using a user-provided water level (metres), "
            "outputs a binary flood raster, and computes flooded area statistics "
            "per AOI polygon (if provided)."
        )

    def createInstance(self):
        return AlgInundation()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    # ---------- parameters ----------
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.P_DEM, self.tr("DEM (m)")
        ))
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.P_AOI, self.tr("AOI polygons (optional)"),
            types=[QgsProcessing.TypeVectorPolygon], optional=True
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.P_LEVEL, self.tr("Water level (m)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.O_RASTER, self.tr("Flooded raster (GeoTIFF)")
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_AOI, self.tr("AOI with flooded statistics")
        ))

    # ---------- main ----------
    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        dem_layer = self.parameterAsRasterLayer(parameters, self.P_DEM, context)
        if dem_layer is None:
            raise QgsProcessingException("DEM is required.")

        aoi_layer = self.parameterAsVectorLayer(parameters, self.P_AOI, context)
        level_m = self.parameterAsDouble(parameters, self.P_LEVEL, context)

        feedback.pushInfo(f"Using user-defined water level = {level_m:.3f} m")

        out_raster = self.parameterAsOutputLayer(parameters, self.O_RASTER, context)

        # Flood mask via raster calculator
        calc = processing.run(
            "gdal:rastercalculator",
            {
                "INPUT_A": dem_layer.source(),
                "BAND_A": 1,
                "FORMULA": f"(A <= {level_m}) * 1",
                "NO_DATA": 0,
                "RTYPE": 0,  # Byte
                "OUTPUT": out_raster,
                "EXTRA": "--creation-option TILED=YES --creation-option COMPRESS=DEFLATE"
            },
            context=context, feedback=feedback
        )
        flooded_path = calc.get("OUTPUT")

        flooded_rlayer = QgsProcessingUtils.mapLayerFromString(flooded_path, context)
        if flooded_rlayer is None or not flooded_rlayer.isValid():
            flooded_rlayer = QgsRasterLayer(flooded_path, "flooded_mask", "gdal")
            if not flooded_rlayer.isValid():
                raise QgsProcessingException("Failed to load flooded raster output.")

        aoi_out = None
        if aoi_layer and aoi_layer.isValid():
            feedback.pushInfo(f"Computing stats for {aoi_layer.featureCount()} AOI polygons")

            zs = processing.run(
                "native:zonalstatisticsfb",
                {
                    "INPUT": aoi_layer,
                    "INPUT_RASTER": flooded_rlayer,
                    "RASTER_BAND": 1,
                    "COLUMN_PREFIX": "f_",
                    "STATISTICS": [0, 2],  # COUNT, MEAN
                    "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT,
                },
                context=context, feedback=feedback
            )
            stats_layer = QgsProcessingUtils.mapLayerFromString(zs.get("OUTPUT"), context)

            fields_out = QgsFields()
            for f in stats_layer.fields():
                fields_out.append(f)
            fields_out.append(QgsField("flooded", QVariant.Double))
            fields_out.append(QgsField("flood_pct", QVariant.Double))
            fields_out.append(QgsField("flood_m2", QVariant.Double))

            sink, aoi_out = self.parameterAsSink(
                parameters, self.O_AOI, context,
                fields_out, stats_layer.wkbType(), stats_layer.crs()
            )

            px = abs(flooded_rlayer.rasterUnitsPerPixelX())
            py = abs(flooded_rlayer.rasterUnitsPerPixelY())
            pix_area = float(px * py) if px and py else 0.0

            idx_mean = stats_layer.fields().lookupField("f_mean")
            idx_count = stats_layer.fields().lookupField("f_count")

            for feat in stats_layer.getFeatures():
                geom = feat.geometry()
                flooded_frac = feat[idx_mean] if idx_mean != -1 else 0.0
                flooded_frac = max(0.0, min(1.0, float(flooded_frac or 0.0)))

                sampled_area_m2 = 0.0
                if idx_count != -1:
                    val_count = feat[idx_count]
                    if val_count and pix_area > 0.0:
                        sampled_area_m2 = float(val_count) * pix_area

                poly_area_m2 = geom.area() if geom else 0.0
                flood_m2 = flooded_frac * sampled_area_m2
                flood_pct = (flood_m2 / poly_area_m2) * 100.0 if poly_area_m2 > 0 else 0.0

                out_feat = QgsFeature(fields_out)
                out_feat.setGeometry(geom)
                out_feat.setAttributes(feat.attributes() + [flooded_frac, flood_pct, flood_m2])
                sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

        return {self.O_RASTER: flooded_path, self.O_AOI: aoi_out}
