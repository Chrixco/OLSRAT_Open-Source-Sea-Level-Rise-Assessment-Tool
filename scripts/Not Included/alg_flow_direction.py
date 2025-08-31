# -*- coding: utf-8 -*-
from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgFlowDirection(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_DIR = "OUTPUT_DIR"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM, self.tr("Input DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_DIR, self.tr("Flow Direction")))

    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT_DIR, context)
        processing.run("saga:flowaccumulation", {
            "ELEVATION": dem,
            "DIRECTION": output
        }, context=context, feedback=feedback)
        return {self.OUTPUT_DIR: output}

    def name(self): return "flow_direction"
    def displayName(self): return self.tr("Flow Direction")
    def group(self): return self.tr("Hydrological Analysis")
    def groupId(self): return "hydrology"
    def shortHelpString(self): return self.tr("Compute flow direction grid from DEM.")
    def createInstance(self): return AlgFlowDirection()
    def tr(self, msg): return QCoreApplication.translate("AlgFlowDirection", msg)
