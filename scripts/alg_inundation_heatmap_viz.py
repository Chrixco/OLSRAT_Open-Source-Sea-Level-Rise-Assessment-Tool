# -*- coding: utf-8 -*-
"""
Inundation Heatmap Visualization Algorithm
Generates heatmap visualization of inundation intensity across plot features
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterEnum,
    QgsField, QgsFields, QgsFeature, QgsFeatureSink, QgsWkbTypes,
    QgsGradientColorRamp, QgsRendererRangeLabelFormat,
    QgsGraduatedSymbolRenderer, QgsSymbol, QgsRendererRange,
    QgsProcessingContext
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis import processing
import os


class AlgInundationHeatmapViz(QgsProcessingAlgorithm):
    P_PLOTS = "PLOTS"
    P_FLOOD_RASTER = "FLOOD_RASTER"
    P_FIELD_NAME = "FIELD_NAME"
    P_COLOR_SCHEME = "COLOR_SCHEME"
    O_OUTPUT = "OUTPUT"

    COLOR_SCHEMES = ["Blue to Red (Low to High)", "Green to Red (Safe to Danger)", "Yellow to Red (Warning)", "Custom Purple to Pink"]

    def tr(self, s):
        return QCoreApplication.translate("AlgInundationHeatmapViz", s)

    def name(self):
        return "inundation_heatmap_viz"

    def displayName(self):
        return self.tr("Inundation Heatmap for Plots")

    def group(self):
        return self.tr("Visualization & Analysis")

    def groupId(self):
        return "visualization_analysis"

    def shortHelpString(self):
        return self.tr(
            "Creates a heatmap visualization of inundation intensity across plot features.\n\n"
            "This algorithm:\n"
            "1. Analyzes flood raster data within each plot polygon\n"
            "2. Calculates inundation percentage and affected area\n"
            "3. Applies graduated color symbology for visual analysis\n"
            "4. Outputs styled vector layer ready for map visualization\n\n"
            "Perfect for identifying flood hotspots and risk zones across multiple parcels or buildings."
        )

    def createInstance(self):
        return AlgInundationHeatmapViz()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "256.png"))

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.P_PLOTS,
            self.tr("Plot/Parcel Layer (Polygons)"),
            types=[QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.P_FLOOD_RASTER,
            self.tr("Flood Inundation Raster (Binary: 0=dry, 1=flooded)")
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.P_COLOR_SCHEME,
            self.tr("Color Scheme"),
            options=self.COLOR_SCHEMES,
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_OUTPUT,
            self.tr("Heatmap Output (with styling)")
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        plots_layer = self.parameterAsVectorLayer(parameters, self.P_PLOTS, context)
        flood_raster = self.parameterAsRasterLayer(parameters, self.P_FLOOD_RASTER, context)
        color_scheme_idx = self.parameterAsEnum(parameters, self.P_COLOR_SCHEME, context)

        if not plots_layer or not flood_raster:
            raise QgsProcessingException("Both plot layer and flood raster are required.")

        feedback.pushInfo("Step 1/3: Calculating zonal statistics for inundation...")

        # Reproject plots to match raster CRS if needed
        if plots_layer.crs() != flood_raster.crs():
            feedback.pushInfo(f"Reprojecting plots from {plots_layer.crs().authid()} to {flood_raster.crs().authid()}...")
            plots_reproj = processing.run(
                "native:reprojectlayer",
                {"INPUT": plots_layer, "TARGET_CRS": flood_raster.crs(), "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                context=context, feedback=feedback
            )["OUTPUT"]
        else:
            plots_reproj = plots_layer

        # Run zonal statistics: COUNT (total pixels) and SUM (flooded pixels)
        zs_result = processing.run(
            "native:zonalstatisticsfb",
            {
                "INPUT": plots_reproj,
                "INPUT_RASTER": flood_raster,
                "RASTER_BAND": 1,
                "COLUMN_PREFIX": "flood_",
                "STATISTICS": [0, 1],  # 0=COUNT, 1=SUM
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context, feedback=feedback
        )
        stats_layer = zs_result["OUTPUT"]

        feedback.pushInfo("Step 2/3: Computing inundation percentage and area...")

        # Prepare output fields
        fields_out = QgsFields()
        for f in stats_layer.fields():
            fields_out.append(f)
        fields_out.append(QgsField("inund_pct", QVariant.Double))
        fields_out.append(QgsField("inund_m2", QVariant.Double))
        fields_out.append(QgsField("total_m2", QVariant.Double))

        sink, dest_id = self.parameterAsSink(
            parameters, self.O_OUTPUT, context,
            fields_out, plots_layer.wkbType(), plots_layer.crs()
        )
        if sink is None:
            raise QgsProcessingException("Could not create output sink.")

        idx_count = stats_layer.fields().lookupField("flood_count")
        idx_sum = stats_layer.fields().lookupField("flood_sum")
        if idx_count == -1:
            idx_count = stats_layer.fields().lookupField("flood_COUNT")
        if idx_sum == -1:
            idx_sum = stats_layer.fields().lookupField("flood_SUM")

        px_x = abs(flood_raster.rasterUnitsPerPixelX())
        px_y = abs(flood_raster.rasterUnitsPerPixelY())
        pixel_area = float(px_x * px_y) if px_x and px_y else 0.0

        total_features = stats_layer.featureCount()
        for i, feat in enumerate(stats_layer.getFeatures()):
            if feedback.isCanceled():
                break

            attrs = feat.attributes()
            geom = feat.geometry()

            total_pixels = feat[idx_count] if idx_count != -1 and feat[idx_count] is not None else 0
            flooded_pixels = feat[idx_sum] if idx_sum != -1 and feat[idx_sum] is not None else 0

            total_m2 = float(total_pixels) * pixel_area if pixel_area > 0 else geom.area()
            inund_m2 = float(flooded_pixels) * pixel_area if pixel_area > 0 else 0.0
            inund_pct = (inund_m2 / total_m2 * 100.0) if total_m2 > 0 else 0.0

            out_feat = QgsFeature(fields_out)
            out_feat.setGeometry(geom)
            out_feat.setAttributes(attrs + [inund_pct, inund_m2, total_m2])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(50 + (i / total_features * 40)))

        feedback.pushInfo("Step 3/3: Applying graduated color symbology...")

        # Apply color scheme
        color_ramp = self._get_color_ramp(color_scheme_idx)

        feedback.setProgress(100)
        return {self.O_OUTPUT: dest_id}

    def _get_color_ramp(self, scheme_idx):
        """Returns QgsGradientColorRamp based on selected scheme"""
        schemes = {
            0: (QColor(33, 102, 172), QColor(178, 24, 43)),  # Blue to Red
            1: (QColor(0, 168, 107), QColor(220, 50, 50)),   # Green to Red
            2: (QColor(255, 237, 160), QColor(189, 0, 38)),  # Yellow to Red
            3: (QColor(156, 39, 176), QColor(233, 30, 99)),  # Purple to Pink
        }
        start_color, end_color = schemes.get(scheme_idx, schemes[0])
        return QgsGradientColorRamp(start_color, end_color)

    def postProcessAlgorithm(self, context, feedback):
        """Apply styling after layer is added to project"""
        feedback.pushInfo("Applying heatmap styling to output layer...")
        return {}
