# -*- coding: utf-8 -*-
"""
Vector to Raster (pixel-count mode)
Data Preparation group

Converts a vector layer to a raster using GDAL Rasterize.
- Burn an attribute (FIELD) or a constant value (BURN).
- If a TEMPLATE raster is provided, its extent and size (cols/rows) are used.
- Otherwise, supply a rectangular EXTENT and a target PIXEL_SIZE (map units);
  pixel counts (WIDTH/HEIGHT) are computed from extent/size and passed in pixel-count mode.
- ALL_TOUCHED controls whether any pixel touched by geometry is burned.

This implementation uses UNITS=0 (pixel counts), so GDAL receives -ts <cols> <rows>,
combined with -te <extent>, which avoids 0×0 datasets in geographic CRSs.
"""

import math
import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterField,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterExtent,
    QgsProcessingParameterNumber, QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean, QgsProcessingParameterRasterDestination,
    QgsProcessingException
)


class AlgVectorToRaster(QgsProcessingAlgorithm):
    # Parameters
    INPUT = "INPUT"
    FIELD = "FIELD"
    BURN = "BURN"
    TEMPLATE = "TEMPLATE"
    EXTENT = "EXTENT"
    PIXEL_SIZE = "PIXEL_SIZE"
    ALL_TOUCHED = "ALL_TOUCHED"
    NODATA = "NODATA"
    DATA_TYPE = "DATA_TYPE"
    OUTPUT = "OUTPUT"

    _DT_OPTS = ["Byte", "UInt16", "Int16", "UInt32", "Int32", "Float32", "Float64"]
    _DT_MAP = {"Byte": 0, "UInt16": 1, "Int16": 2, "UInt32": 3, "Int32": 4, "Float32": 5, "Float64": 6}

    # ---- metadata ----
    def name(self): return "vector_to_raster"
    def displayName(self): return self.tr("Vector to raster (GDAL, pixel-count)")
    def group(self): return self.tr("Data Preparation")
    def groupId(self): return "data_preparation"
    def shortHelpString(self):
        return self.tr(
            "Rasterises a vector using GDAL Rasterize in pixel-count mode (-ts). "
            "If a template raster is provided, its extent and pixel size are used. "
            "Otherwise, the output uses the given rectangular extent and a target pixel size "
            "(map units) to compute the number of columns/rows. "
            "Burn either an attribute (FIELD) or a constant (BURN)."
        )
    def tr(self, m): return QCoreApplication.translate("AlgVectorToRaster", m)
    def createInstance(self): return AlgVectorToRaster()

    # ---- UI ----
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.INPUT, self.tr("Input vector"), types=[QgsProcessing.TypeVectorAnyGeometry]))

        self.addParameter(QgsProcessingParameterField(
            self.FIELD, self.tr("Attribute to burn (optional)"),
            parentLayerParameterName=self.INPUT, optional=True))

        self.addParameter(QgsProcessingParameterNumber(
            self.BURN, self.tr("Constant burn value (used if no FIELD)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.TEMPLATE, self.tr("Template raster (optional: copies extent & size)"),
            optional=True))

        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT, self.tr("Target extent (if no template)"), optional=True))

        self.addParameter(QgsProcessingParameterNumber(
            self.PIXEL_SIZE, self.tr("Target pixel size (map units; if no template)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=10.0, minValue=1e-9))

        self.addParameter(QgsProcessingParameterBoolean(
            self.ALL_TOUCHED, self.tr("All touched pixels"), defaultValue=False))

        self.addParameter(QgsProcessingParameterNumber(
            self.NODATA, self.tr("NODATA value (background)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0))

        self.addParameter(QgsProcessingParameterEnum(
            self.DATA_TYPE, self.tr("Output data type"),
            options=self._DT_OPTS, defaultValue=self._DT_OPTS.index("Float32")))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, self.tr("Output raster")))

    # ---- CORE ----
    def processAlgorithm(self, p, context, feedback):
        v = self.parameterAsVectorLayer(p, self.INPUT, context)
        if v is None or not v.isValid():
            raise QgsProcessingException("Invalid input vector layer.")

        field = (self.parameterAsString(p, self.FIELD, context) or "").strip()
        burn = float(self.parameterAsDouble(p, self.BURN, context))
        tmpl = self.parameterAsRasterLayer(p, self.TEMPLATE, context)
        ext  = self.parameterAsExtent(p, self.EXTENT, context)
        px   = float(self.parameterAsDouble(p, self.PIXEL_SIZE, context))
        touched = self.parameterAsBool(p, self.ALL_TOUCHED, context)
        nodata = float(self.parameterAsDouble(p, self.NODATA, context))
        dtype_idx = self.parameterAsEnum(p, self.DATA_TYPE, context)
        dtype_name = self._DT_OPTS[dtype_idx]
        dtype_code = self._DT_MAP[dtype_name]
        out_path = self.parameterAsOutputLayer(p, self.OUTPUT, context)

        # Decide extent and pixel counts
        if tmpl:
            extent = tmpl.extent()
            width  = max(1, int(tmpl.width()))
            height = max(1, int(tmpl.height()))
            feedback.pushInfo(f"Template used → extent {extent.toString()}, size {width}×{height}")
        else:
            # Use supplied extent if present; else vector extent
            extent = ext if (ext and not ext.isEmpty()) else v.extent()

            if px <= 0:
                raise QgsProcessingException("Pixel size must be > 0.")

            width  = max(1, int(math.ceil(extent.width()  / px)))
            height = max(1, int(math.ceil(extent.height() / px)))
            feedback.pushInfo(f"Computed size → {width}×{height} px from extent and pixel size {px}")

        if width == 0 or height == 0:
            raise QgsProcessingException(
                "Computed raster size is 0 in at least one dimension. "
                "Use a smaller pixel size or a larger extent (or provide a template)."
            )

        # Build GDAL params (pixel-count mode: UNITS=0 => -ts cols rows)
        params = {
            "INPUT": v,
            "FIELD": field if field else None,
            "BURN": burn if not field else None,
            "UNITS": 0,                      # 0 = pixel counts (GDAL -ts)
            "WIDTH": width,                  # columns
            "HEIGHT": height,                # rows
            "EXTENT": extent,                # GDAL -te
            "NODATA": nodata,
            "OPTIONS": "",
            "DATA_TYPE": dtype_code,
            "INIT": nodata,
            "INVERT": False,
            "ALL_TOUCHED": bool(touched),
            "EXTRA": "",
            "OUTPUT": out_path
        }

        # Remove None entries
        params = {k: v for k, v in params.items() if v is not None}

        # Informative logging
        feedback.pushInfo(f"Burn mode: {'FIELD=' + field if field else 'BURN=' + str(burn)}")
        feedback.pushInfo(f"Data type: {dtype_name}, NODATA={nodata}, ALL_TOUCHED={touched}")
        feedback.pushInfo(f"Extent: {extent.toString()} → size {width}×{height} (pixel-count mode)")

        res = processing.run(
            "gdal:rasterize", params,
            context=context, feedback=feedback, is_child_algorithm=True
        )
        return {self.OUTPUT: res["OUTPUT"]}
