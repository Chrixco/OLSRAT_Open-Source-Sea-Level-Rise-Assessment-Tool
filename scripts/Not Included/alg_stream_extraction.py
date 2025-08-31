# -*- coding: utf-8 -*-
from qgis.core import *
from qgis.PyQt.QtCore import QCoreApplication
import processing

class AlgStreamExtraction(QgsProcessingAlgorithm):
    INPUT_ACC = "INPUT_ACC"
    THRESHOLD = "THRESHOLD"
    OUTPUT_STREAMS = "OUTPUT_STREAMS"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_ACC, self.tr("Flow Accumulation Raster")))
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, self.tr("Threshold Area"), type=QgsProcessingParameterNumber.Double, defaultValue=1000.0))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_STREAMS, self.tr("Stream Raster")))

    def processAlgorithm(self, parameters, context, feedback):
        acc = self.parameterAsRasterLayer(parameters, self.INPUT_ACC, context)
        threshold = self.parameterAsDouble(parameters, self.THRESHOLD, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT_STREAMS, context)
        processing.run("saga:channelnetwork", {
            "ELEVATION": acc,
            "INIT_GRID": threshold,
            "CHANNELS": output
        }, context=context, feedback=feedback)
        return {self.OUTPUT_STREAMS: output}

    def name(self): return "stream_extraction"
    def displayName(self): return self.tr("Stream Extraction")
    def group(self): return self.tr("Hydrological Analysis")
    def groupId(self): return "hydrology"
    def shortHelpString(self): return self.tr("Extract stream network from flow accumulation raster.")
    def createInstance(self): return AlgStreamExtraction()
    def tr(self, msg): return QCoreApplication.translate("AlgStreamExtraction", msg)
