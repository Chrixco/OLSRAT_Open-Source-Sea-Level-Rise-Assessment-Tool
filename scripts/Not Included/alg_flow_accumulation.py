# -*- coding: utf-8 -*-
from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgFlowAccumulation(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_ACC = "OUTPUT_ACC"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM, self.tr("Input DEM")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_ACC, self.tr("Flow Accumulation")))

    def processAlgorithm(self, parameters, context, feedback):
        dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT_ACC, context)
        processing.run("saga:flowaccumulation", {
            "ELEVATION": dem,
            "FLOW": output
        }, context=context, feedback=feedback)
        return {self.OUTPUT_ACC: output}

    def name(self): return "flow_accumulation"
    def displayName(self): return self.tr("Flow Accumulation")
    def group(self): return self.tr("Hydrological Analysis")
    def groupId(self): return "hydrology"
    def shortHelpString(self): return self.tr("Compute flow accumulation raster from DEM.")
    def createInstance(self): return AlgFlowAccumulation()
    def tr(self, msg): return QCoreApplication.translate("AlgFlowAccumulation", msg)
