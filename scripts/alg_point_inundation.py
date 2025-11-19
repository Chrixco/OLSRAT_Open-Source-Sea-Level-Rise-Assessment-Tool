# -*- coding: utf-8 -*-
"""
Point-based Flooding from DEM
Generates a regular grid of points over DEM extent, sampling elevation and
classifying flooded points based on user-defined SLR level.
Also generates a separate 3D point layer (PointZ).
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
    QgsPoint,
    QgsPointXY,
    QgsGeometry,
    QgsWkbTypes,
    QgsRasterShader,
    QgsColorRampShader,
    QgsSingleBandPseudoColorRenderer,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsSymbol,
    QgsRasterLayer,
    QgsRaster,
    QgsStyle,
    QgsRasterBandStats
)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsProject



class AlgPointFlooding(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    SPACING = "SPACING"
    SLR_LEVEL = "SLR_LEVEL"
    OUTPUT_POINTS = "OUTPUT_POINTS"
    OUTPUT_POINTS_3D = "OUTPUT_POINTS_3D"

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
            defaultValue=500.0,
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

        # Output 2D points
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_POINTS,
            self.tr("Flooding Points (2D)")
        ))

        # Output 3D points
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_POINTS_3D,
            self.tr("Flooding Points (3D)")
        ))

    def processAlgorithm(self, parameters, context, feedback):
        dem_layer = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        spacing = self.parameterAsDouble(parameters, self.SPACING, context)
        slr_value = self.parameterAsDouble(parameters, self.SLR_LEVEL, context)

        crs = dem_layer.crs()

        # Info about units
        if crs.isGeographic():
            feedback.pushInfo("⚠ DEM is in geographic coordinates (degrees). "
                              "Spacing is in degrees, not meters.")
        else:
            feedback.pushInfo("✅ DEM is in projected coordinates (meters). "
                              "Spacing is correctly interpreted in meters.")

        provider = dem_layer.dataProvider()
        extent = dem_layer.extent()

        # Define fields (common)
        fields = QgsFields()
        fields.append(QgsField("id", QVariant.Int))
        fields.append(QgsField("x", QVariant.Double))
        fields.append(QgsField("y", QVariant.Double))
        fields.append(QgsField("elev", QVariant.Double))
        fields.append(QgsField("flooded", QVariant.Int))

        # Dynamic layer names
        layer_name_2d = f"Flooding Points 2D (SLR={slr_value}m, spacing={spacing}m)"
        layer_name_3d = f"Flooding Points 3D (SLR={slr_value}m, spacing={spacing}m)"
        dem_copy_name = f"DEM (Spectral Inverted, SLR={slr_value}m)"

        # Create sinks
        sink2d, sink_id2d = self.parameterAsSink(
            parameters,
            self.OUTPUT_POINTS,
            context,
            fields,
            QgsWkbTypes.Point,
            crs
        )
        sink3d, sink_id3d = self.parameterAsSink(
            parameters,
            self.OUTPUT_POINTS_3D,
            context,
            fields,
            QgsWkbTypes.PointZ,
            crs
        )

        # Rename output layers
        if context.willLoadLayerOnCompletion(sink_id2d):
            context.layerToLoadOnCompletionDetails(sink_id2d).name = layer_name_2d
        if context.willLoadLayerOnCompletion(sink_id3d):
            context.layerToLoadOnCompletionDetails(sink_id3d).name = layer_name_3d

        # Generate points
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
                        if elev is not None and elev > -1e20:
                            flooded = 1 if elev <= slr_value else 0
                        else:
                            elev, flooded = None, -1
                    else:
                        elev, flooded = None, -1
                else:
                    elev, flooded = None, -1

                # 2D feature
                f2d = QgsFeature(fields)
                f2d.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
                f2d.setAttributes([point_id, x, y, elev if elev is not None else -9999, flooded])
                sink2d.addFeature(f2d)

                # 3D feature (PointZ)
                f3d = QgsFeature(fields)
                zval = elev if elev is not None else -9999
                point3d = QgsPoint(x, y, zval)
                f3d.setGeometry(QgsGeometry(point3d))
                f3d.setAttributes([point_id, x, y, zval, flooded])
                sink3d.addFeature(f3d)

                point_id += 1
                x += spacing
            y += spacing

        feedback.pushInfo(f"Generated {point_id} points (2D + 3D).")

        # Apply symbology to 2D points
        if context.willLoadLayerOnCompletion(sink_id2d):
            point_layer = context.getMapLayer(sink_id2d)
            if point_layer:
                categories = []
                symbol_flooded = QgsSymbol.defaultSymbol(point_layer.geometryType())
                symbol_flooded.setColor(QColor("#0199ff"))  # flooded = blue
                categories.append(QgsRendererCategory(1, symbol_flooded, "Flooded"))

                symbol_safe = QgsSymbol.defaultSymbol(point_layer.geometryType())
                symbol_safe.setColor(QColor("#e3fcee"))  # safe = greenish
                categories.append(QgsRendererCategory(0, symbol_safe, "Safe"))

                symbol_nodata = QgsSymbol.defaultSymbol(point_layer.geometryType())
                symbol_nodata.setColor(QColor("lightgray"))
                categories.append(QgsRendererCategory(-1, symbol_nodata, "No Data"))

                renderer = QgsCategorizedSymbolRenderer("flooded", categories)
                point_layer.setRenderer(renderer)
                feedback.pushInfo("Applied 2D symbology: blue=flooded, green=safe, gray=nodata.")

        # Apply DEM symbology copy with QGIS built-in "Spectral" ramp
        # Apply DEM symbology copy with custom pastel ramp
        dem_copy = QgsRasterLayer(dem_layer.source(), dem_copy_name, "gdal")
        if dem_copy.isValid():
            stats = dem_copy.dataProvider().bandStatistics(1, QgsRasterBandStats.All)
            min_val, max_val = stats.minimumValue, stats.maximumValue

            # Define custom pastel ramp (hex colors are pastel shades)
            pastel_colors = [
                (min_val, QColor("#4685a7"), "Blue (low)"),       # pastel blue
                (min_val + (max_val-min_val)*0.2, QColor("#b2df8a"), "Light Green"),
                (min_val + (max_val-min_val)*0.4, QColor("#33a02c"), "Green"),
                (min_val + (max_val-min_val)*0.6, QColor("#ffff99"), "Yellow"),
                (min_val + (max_val-min_val)*0.8, QColor("#fb9a99"), "Orange"),
                (max_val, QColor("#e31a1c"), "Red (high)"),       # pastel red
            ]

            shader = QgsRasterShader()
            color_ramp = QgsColorRampShader()
            color_ramp.setColorRampType(QgsColorRampShader.Interpolated)

            # Build ramp with custom pastel items
            ramp_items = [QgsColorRampShader.ColorRampItem(v, c, lbl) for v, c, lbl in pastel_colors]
            color_ramp.setColorRampItemList(ramp_items)
            shader.setRasterShaderFunction(color_ramp)

            # Apply renderer
            renderer = QgsSingleBandPseudoColorRenderer(dem_copy.dataProvider(), 1, shader)
            dem_copy.setRenderer(renderer)

            # ✅ Force refresh and bring to front
            QgsProject.instance().addMapLayer(dem_copy, addToLegend=True)
            root = QgsProject.instance().layerTreeRoot()
            node = root.findLayer(dem_copy.id())
            if node:
                node.setItemVisibilityChecked(True)
                root.insertChildNode(0, node.clone())
                root.removeChildNode(node)

            feedback.pushInfo("Added DEM copy with custom pastel symbology.")




        return {
            self.OUTPUT_POINTS_3D: sink_id3d,
             "DEM_COPY": dem_copy.id(),
             self.OUTPUT_POINTS: sink_id2d, 
            
            }

    def name(self): 
        return "point_flooding"

    def displayName(self): 
        return self.tr("Point-based Flooding from DEM")

    def group(self): 
        return self.tr("Flood Exposure")

    def groupId(self): 
        return "flood_exposure"

    def shortHelpString(self):
        return self.tr(
            "<h2>Point-based Flooding from DEM</h2>"
            "<p>This algorithm generates a regular grid of points from a DEM and classifies them "
            "as flooded or safe based on a user-defined Sea Level Rise (SLR) threshold.</p>"
            "<h3>Outputs:</h3>"
            "<ul>"
            "<li><b>Flooding Points 2D</b>: styled by flooded status (blue=flooded, green=safe).</li>"
            "<li><b>Flooding Points 3D</b>: with Z values for use in the QGIS 3D Scene.</li>"
            "<li><b>DEM Copy</b>: styled with Spectral Inverted color ramp.</li>"
            "</ul>"
            "<h3><font color='red'><b>⚠ Notes:</b></font></h3>"
            "<p><font color='red'>If your DEM is in geographic coordinates (degrees), it will be "
            "treated as such, but projected DEMs in meters are recommended.</font></p>"
        )

    def createInstance(self):
        return AlgPointFlooding()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "SLR_Alg_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def tr(self, message): 
        return QCoreApplication.translate("AlgPointFlooding", message)
