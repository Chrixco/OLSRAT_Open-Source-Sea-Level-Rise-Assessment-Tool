# -*- coding: utf-8 -*-
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterRasterDestination)
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgAspect(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_ASPECT = "OUTPUT_ASPECT"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM, self.tr("DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT_ASPECT, self.tr("Aspect (0-360)")))

    def processAlgorithm(self, parameters, context, feedback):
        result = processing.run("gdal:aspect", {
            "INPUT": self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context).source(),
            "BAND": 1,
            "TRIG_ANGLE": False,
            "ZERO_FLAT": False,
            "OUTPUT": parameters[self.OUTPUT_ASPECT],
        }, context=context, feedback=feedback)
        return {self.OUTPUT_ASPECT: result["OUTPUT"]}

    def name(self): return "aspect_analysis"
    def displayName(self): return self.tr("Aspect Analysis (DEM)")
    def group(self): return self.tr("Terrain Analysis")
    def groupId(self): return "terrain_analysis"
    def shortHelpString(self): return self.tr("Compute aspect (0-360°) from a DEM raster.")
    def createInstance(self): return AlgAspect()
    def tr(self, msg): return QCoreApplication.translate("AlgAspect", msg)
