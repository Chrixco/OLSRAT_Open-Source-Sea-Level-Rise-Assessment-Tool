# -*- coding: utf-8 -*-
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination)
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgSlope(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_SLOPE = "OUTPUT_SLOPE"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM, self.tr("DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_SLOPE, self.tr("Slope (degrees)")))

    def processAlgorithm(self, parameters, context, feedback):
        result = processing.run("gdal:slope", {
            "INPUT": self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context).source(),
            "BAND": 1,
            "SCALE": 1.0,
            "OUTPUT": parameters[self.OUTPUT_SLOPE],
            "COMPUTE_EDGES": True,
            "SLOPE_FORMAT": 1
        }, context=context, feedback=feedback)
        return {self.OUTPUT_SLOPE: result["OUTPUT"]}

    def name(self): return "slope_analysis"
    def displayName(self): return self.tr("Slope Analysis (DEM)")
    def group(self): return self.tr("Terrain Analysis")
    def groupId(self): return "terrain_analysis"
    def shortHelpString(self): return self.tr("Compute slope in degrees from a DEM raster.")
    def createInstance(self): return AlgSlope()
    def tr(self, msg): return QCoreApplication.translate("AlgSlope", msg)
