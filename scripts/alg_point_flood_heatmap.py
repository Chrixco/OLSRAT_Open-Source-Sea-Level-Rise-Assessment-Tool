# -*- coding: utf-8 -*-
"""
Point-based Flooding with Heatmap
Generates a regular grid of points over DEM extent, keeps only flooded ones,
and applies a heatmap renderer using the Magma ramp.
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsPointXY,
    QgsGeometry,
    QgsWkbTypes,
    QgsHeatmapRenderer,
    QgsStyle,
    QgsRaster,
)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
from qgis.PyQt.QtGui import QIcon


class AlgPointFloodHeatmap(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    SPACING = "SPACING"
    SLR_LEVEL = "SLR_LEVEL"
    OUTPUT_POINTS = "OUTPUT_POINTS"

    def initAlgorithm(self, config=None):
        # DEM input
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM,
            self.tr("Digital Elevation Model (DEM)")
        ))

        # Point spacing
        self.addParameter(QgsProcessingParameterNumber(
            self.SPACING,
            self.tr("Point Spacing (meters)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=200.0,
            minValue=1.0
        ))

        # Sea Level Rise (threshold)
        self.addParameter(QgsProcessingParameterNumber(
            self.SLR_LEVEL,
            self.tr("Sea Level Rise (m)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=2.0,
            minValue=0.0
        ))

        # Output flooded points (for heatmap)
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_POINTS,
            self.tr("Flooding Heatmap Points")
        ))

    def processAlgorithm(self, parameters, context, feedback):
        dem_layer = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        spacing = self.parameterAsDouble(parameters, self.SPACING, context)
        slr_value = self.parameterAsDouble(parameters, self.SLR_LEVEL, context)

        crs = dem_layer.crs()
        provider = dem_layer.dataProvider()
        extent = dem_layer.extent()

        # Define fields
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("x", QVariant.Double))
        fields.append(QgsField("y", QVariant.Double))
        fields.append(QgsField("elev", QVariant.Double))
        fields.append(QgsField("weight", QVariant.Double))

        # Create sink for flooded points
        sink, sink_id = self.parameterAsSink(
            parameters,
            self.OUTPUT_POINTS,
            context,
            fields,
            QgsWkbTypes.Point,
            crs
        )

        # Generate only flooded points
        point_id = 0
        y = extent.yMinimum()
        while y <= extent.yMaximum():
            x = extent.xMinimum()
            while x <= extent.xMaximum():
                pt = QgsPointXY(x, y)

                # Sample DEM
                ident = provider.identify(pt, QgsRaster.IdentifyFormatValue)
                if ident.isValid():
                    results = ident.results()
                    if results:
                        elev = list(results.values())[0]
                        if elev is not None and elev <= slr_value:
                            # Only add flooded points
                            f = QgsFeature(fields)
                            f.setGeometry(QgsGeometry.fromPointXY(pt))
                            f.setAttributes([point_id, x, y, elev, 1.0])  # weight=1
                            sink.addFeature(f)
                            point_id += 1
                x += spacing
            y += spacing

        feedback.pushInfo(f"Generated {point_id} flooded points.")

        # Apply heatmap renderer directly
        point_layer = context.getMapLayer(sink_id)
        if point_layer:
            style = QgsStyle().defaultStyle()
            magma_ramp = style.colorRamp("Magma")
            if magma_ramp:
                heat_renderer = QgsHeatmapRenderer()
                heat_renderer.setWeightExpression("weight")
                heat_renderer.setColorRamp(magma_ramp)
                heat_renderer.setRadius(spacing * 2)
                point_layer.setRenderer(heat_renderer)
                feedback.pushInfo("Applied heatmap renderer using Magma ramp (only flooded points).")

        return {self.OUTPUT_POINTS: sink_id}

    def name(self):
        return "point_flood_heatmap"

    def displayName(self):
        return self.tr("Point-based Flooding with Heatmap")

    def group(self):
        return self.tr("Flood Exposure")

    def groupId(self):
        return "flood_exposure"

    def shortHelpString(self):
        return self.tr(
            "<h2>Point-based Flooding with Heatmap</h2>"
            "<p>This algorithm generates a regular grid of points from a DEM, "
            "keeps only the flooded points (<= SLR threshold), and applies a Magma heatmap renderer.</p>"
            "<h3>Output:</h3>"
            "<ul><li><b>Flooding Heatmap Points</b>: Only flooded points, styled as a heatmap.</li></ul>"
        )

    def createInstance(self):
        return AlgPointFloodHeatmap()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def tr(self, message):
        return QCoreApplication.translate("AlgPointFloodHeatmap", message)
