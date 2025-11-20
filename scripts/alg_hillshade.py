# -*- coding: utf-8 -*-
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination, QgsProcessingUtils)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
import processing

class AlgHillshade(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_HILLSHADE = "OUTPUT_HILLSHADE"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM, self.tr("DEM")))
        self.addParameter(QgsProcessingParameterNumber("AZIMUTH", self.tr("Azimuth"), type=QgsProcessingParameterNumber.Double, defaultValue=315.0))
        self.addParameter(QgsProcessingParameterNumber("ALTITUDE", self.tr("Altitude"), type=QgsProcessingParameterNumber.Double, defaultValue=45.0))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_HILLSHADE, self.tr("Hillshade")))

    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        result = processing.run("gdal:hillshade", {
            "INPUT": dem.source(),
            "BAND": 1,
            "AZIMUTH": self.parameterAsDouble(parameters, "AZIMUTH", context),
            "ALTITUDE": self.parameterAsDouble(parameters, "ALTITUDE", context),
            "Z_FACTOR": 1.0,
            "OUTPUT": parameters[self.OUTPUT_HILLSHADE],
        }, context=context, feedback=feedback)

        # Generate dynamic name for output
        input_name = dem.name()
        clean_name = input_name.replace('.tif', '').replace('.tiff', '').replace('_DEM', '').replace('DEM', '')
        dynamic_name = f"{clean_name}_hillshade"

        # Set layer name
        try:
            output_layer = QgsProcessingUtils.mapLayerFromString(result["OUTPUT"], context)
            if output_layer:
                output_layer.setName(dynamic_name)
                feedback.pushInfo(f"✓ Output named: {dynamic_name}")
        except:
            pass

        return {self.OUTPUT_HILLSHADE: result["OUTPUT"]}

    def name(self): return "hillshade_analysis"
    def displayName(self): return self.tr("Hillshade Analysis (DEM)")
    def group(self): return self.tr("Terrain Analysis")
    def groupId(self): return "terrain_analysis"
    def shortHelpString(self): return self.tr("Compute hillshade raster from DEM.")
    def createInstance(self): return AlgHillshade()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Terrain_Analysis_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))
    def tr(self, msg): return QCoreApplication.translate("AlgHillshade", msg)
