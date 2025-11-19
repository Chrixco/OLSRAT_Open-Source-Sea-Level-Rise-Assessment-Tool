# -*- coding: utf-8 -*-
"""
Raster to Vector (Data Preparation)
Polygonizes a raster band to polygons, writing cell values into an attribute.
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterNumber,
    QgsProcessingParameterString, QgsProcessingParameterBoolean,
    QgsProcessingParameterVectorDestination, QgsProcessingException
)
import processing

class AlgRasterToVector(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    FIELD_NAME = "FIELD_NAME"
    EIGHT_CONNECTED = "EIGHT_CONNECTED"
    OUTPUT = "OUTPUT"

    def name(self): return "raster_to_vector"
    def displayName(self): return self.tr("Raster to vector (polygonize)")
    def group(self): return self.tr("Data Preparation")
    def groupId(self): return "data_preparation"
    def shortHelpString(self):
        return self.tr(
            "Converts a raster band to polygons using GDAL Polygonize. "
            "Cell values are stored in the specified attribute field."
        )
    def tr(self, m): return QCoreApplication.translate("AlgRasterToVector", m)
    def createInstance(self): return AlgRasterToVector()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Data_Prep_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT, self.tr("Input raster")))
        self.addParameter(QgsProcessingParameterNumber(
            self.BAND, self.tr("Band index"), type=QgsProcessingParameterNumber.Integer,
            defaultValue=1, minValue=1))
        self.addParameter(QgsProcessingParameterString(
            self.FIELD_NAME, self.tr("Output field name for value (e.g. DN)"),
            defaultValue="DN"))
        self.addParameter(QgsProcessingParameterBoolean(
            self.EIGHT_CONNECTED, self.tr("8-connectedness"), defaultValue=False))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT, self.tr("Output polygons")))

    def processAlgorithm(self, p, context, feedback):
        r = self.parameterAsRasterLayer(p, self.INPUT, context)
        if r is None or not r.isValid():
            raise QgsProcessingException("Invalid input raster.")

        band = int(self.parameterAsInt(p, self.BAND, context))
        field = self.parameterAsString(p, self.FIELD_NAME, context) or "DN"
        eight = self.parameterAsBool(p, self.EIGHT_CONNECTED, context)
        out   = self.parameterAsOutputLayer(p, self.OUTPUT, context)

        params = {
            "INPUT": r,
            "BAND": band,
            "FIELD": field,
            "EIGHT_CONNECTEDNESS": bool(eight),
            "EXTRA": "",
            "OUTPUT": out
        }

        res = processing.run(
            "gdal:polygonize", params,
            context=context, feedback=feedback, is_child_algorithm=True
        )
        return { self.OUTPUT: res["OUTPUT"] }
