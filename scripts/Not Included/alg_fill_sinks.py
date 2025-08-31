# -*- coding: utf-8 -*-
"""
Fill Sinks (DEM)
Fills depressions in a DEM using QGIS native algorithm if available,
or falls back to SAGA if installed.
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterRasterDestination,
    QgsProcessingException,
    QgsApplication
)
import processing
from qgis.PyQt.QtCore import QCoreApplication


class AlgFillSinks(QgsProcessingAlgorithm):
    INPUT_DEM = "INPUT_DEM"
    OUTPUT_DEM = "OUTPUT_DEM"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM,
            self.tr("Input DEM")  # 🟡 This requires `self.tr()` to be defined
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT_DEM,
            self.tr("Filled DEM")
        ))

    def processAlgorithm(self, parameters, context, feedback):
        # Use native:fillsinks
        from qgis import processing
        result = processing.run("native:fillsinks", {
            "INPUT": parameters[self.INPUT_DEM],
            "OUTPUT": parameters[self.OUTPUT_DEM]
        }, context=context, feedback=feedback)
        return {self.OUTPUT_DEM: result["OUTPUT"]}

    def name(self):
        return "fillsinks"

    def displayName(self):
        return self.tr("Fill Sinks (DEM)")

    def group(self):
        return self.tr("Hydrological Analysis")

    def groupId(self):
        return "hydrological_analysis"

    def shortHelpString(self):
        return self.tr("Fills small depressions (sinks) in a DEM using QGIS native algorithm.")

    def createInstance(self):
        return AlgFillSinks()

    def tr(self, message):  # ✅ This must exist if you're using self.tr(...)
        return QCoreApplication.translate("AlgFillSinks", message)
