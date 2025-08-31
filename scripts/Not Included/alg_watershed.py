# -*- coding: utf-8 -*-
from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgWatershed(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_BASINS = "OUTPUT_BASINS"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM, self.tr("Input DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_BASINS, self.tr("Watershed Basins")))

    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT_BASINS, context)
        processing.run("saga:watershedbasins", {
            "ELEVATION": dem,
            "BASINS": output
        }, context=context, feedback=feedback)
        return {self.OUTPUT_BASINS: output}

    def name(self): return "watershed_delineation"
    def displayName(self): return self.tr("Watershed Delineation")
    def group(self): return self.tr("Hydrological Analysis")
    def groupId(self): return "hydrology"
    def shortHelpString(self): return self.tr("Delineates watershed basins from DEM.")
    def createInstance(self): return AlgWatershed()
    def tr(self, msg): return QCoreApplication.translate("AlgWatershed", msg)
