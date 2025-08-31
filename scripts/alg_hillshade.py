# -*- coding: utf-8 -*-
from qgis.core import (QgsProcessing, QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination)
from qgis.PyQt.QtCore import QCoreApplication
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
        result = processing.run("gdal:hillshade", {
            "INPUT": self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context).source(),
            "BAND": 1,
            "AZIMUTH": self.parameterAsDouble(parameters, "AZIMUTH", context),
            "ALTITUDE": self.parameterAsDouble(parameters, "ALTITUDE", context),
            "Z_FACTOR": 1.0,
            "OUTPUT": parameters[self.OUTPUT_HILLSHADE],
        }, context=context, feedback=feedback)
        return {self.OUTPUT_HILLSHADE: result["OUTPUT"]}

    def name(self): return "hillshade_analysis"
    def displayName(self): return self.tr("Hillshade Analysis (DEM)")
    def group(self): return self.tr("Terrain Analysis")
    def groupId(self): return "terrain_analysis"
    def shortHelpString(self): return self.tr("Compute hillshade raster from DEM.")
    def createInstance(self): return AlgHillshade()
    def tr(self, msg): return QCoreApplication.translate("AlgHillshade", msg)
