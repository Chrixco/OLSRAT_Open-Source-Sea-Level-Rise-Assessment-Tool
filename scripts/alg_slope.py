# -*- coding: utf-8 -*-
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination, QgsProcessingUtils)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
import processing

class AlgSlope(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_SLOPE = "OUTPUT_SLOPE"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM, self.tr("DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_SLOPE, self.tr("Slope (degrees)")))

    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        result = processing.run("gdal:slope", {
            "INPUT": dem.source(),
            "BAND": 1,
            "SCALE": 1.0,
            "OUTPUT": parameters[self.OUTPUT_SLOPE],
            "COMPUTE_EDGES": True,
            "SLOPE_FORMAT": 1
        }, context=context, feedback=feedback)

        # Generate dynamic name for output
        input_name = dem.name()
        clean_name = input_name.replace('.tif', '').replace('.tiff', '').replace('_DEM', '').replace('DEM', '')
        dynamic_name = f"{clean_name}_slope"

        # Set layer name
        try:
            output_layer = QgsProcessingUtils.mapLayerFromString(result["OUTPUT"], context)
            if output_layer:
                output_layer.setName(dynamic_name)
                feedback.pushInfo(f"✓ Output named: {dynamic_name}")
        except Exception as e:
            feedback.pushDebugInfo(f"Could not set output layer name: {str(e)}")

        return {self.OUTPUT_SLOPE: result["OUTPUT"]}

    def name(self): return "slope_analysis"
    def displayName(self): return self.tr("Slope Analysis (DEM)")
    def group(self): return self.tr("Terrain Analysis")
    def groupId(self): return "terrain_analysis"
    def shortHelpString(self): return self.tr("Compute slope in degrees from a DEM raster.")
    def createInstance(self): return AlgSlope()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Terrain_Analysis_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))
    def tr(self, msg): return QCoreApplication.translate("AlgSlope", msg)
