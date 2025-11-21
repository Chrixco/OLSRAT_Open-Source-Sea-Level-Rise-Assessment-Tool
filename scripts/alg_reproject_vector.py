# -*- coding: utf-8 -*-
"""
Reproject Vector (Data Preparation)
Reprojects a vector layer to a target CRS, preserving attributes and geometry type.
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterCrs,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsProcessingContext,
    QgsFeature,
    QgsFields,
    QgsCoordinateTransform,
    QgsWkbTypes,
)

class AlgReprojectVector(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    TARGET_CRS = "TARGET_CRS"
    OUTPUT = "OUTPUT"

    # ----- UI / registration -----
    def name(self):
        # Internal, machine-safe id (no spaces)
        return "reproject_vector"

    def displayName(self):
        # Text shown in the toolbox
        return self.tr("Reproject vector")

    def group(self):
        # Group name shown in the toolbox
        return self.tr("Data Preparation")

    def groupId(self):
        # Stable, lower-case group id
        return "data_preparation"

    def shortHelpString(self):
        return self.tr(
            "Reprojects a vector layer into a target CRS, preserving fields and geometry type. "
            "Geometries are transformed using a coordinate transform based on the project’s "
            "transform context. The output layer uses the target CRS."
        )

    def createInstance(self):
        return AlgReprojectVector()

    def icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Data_Prep_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def tr(self, message):
        return QCoreApplication.translate("AlgReprojectVector", message)

    # ----- Parameters -----
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr("Input vector layer"),
                types=[QgsProcessing.TypeVectorAnyGeometry],
            )
        )

        self.addParameter(
            QgsProcessingParameterCrs(
                self.TARGET_CRS,
                self.tr("Target CRS")
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr("Reprojected vector")
            )
        )

    # ----- Core logic -----
    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        # Get inputs
        vlayer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if vlayer is None or not vlayer.isValid():
            raise QgsProcessingException("Invalid input vector layer.")

        src_crs = vlayer.crs()
        tgt_crs = self.parameterAsCrs(parameters, self.TARGET_CRS, context)
        if not tgt_crs.isValid():
            raise QgsProcessingException("Invalid target CRS.")

        if src_crs.isValid():
            feedback.pushInfo(f"Source CRS: {src_crs.authid()}")
        else:
            feedback.reportError("Source layer has no valid CRS; proceeding with raw coordinates.")

        feedback.pushInfo(f"Target CRS: {tgt_crs.authid()}")

        fields: QgsFields = vlayer.fields()
        wkb = vlayer.wkbType()

        # Create sink with target CRS
        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, wkb, tgt_crs
        )
        if sink is None:
            raise QgsProcessingException("Failed to create output sink.")

        # Coordinate transform (project's transform context controls datum/grid shifts)
        ct = QgsCoordinateTransform(src_crs, tgt_crs, context.transformContext())

        total = vlayer.featureCount() or 0
        step = 100.0 / total if total else 0.0

        transformed = 0
        skipped = 0

        for i, feat in enumerate(vlayer.getFeatures(), start=1):
            if feedback.isCanceled():
                break

            geom = feat.geometry()
            if not geom.isEmpty() and src_crs.isValid() and tgt_crs.isValid():
                try:
                    geom.transform(ct)
                except Exception as e:
                    skipped += 1
                    feedback.reportError(f"Feature {feat.id()} transform failed: {e}")
                    if step:
                        feedback.setProgress(int(i * step))
                    continue

            out_f = QgsFeature(fields)
            out_f.setAttributes(feat.attributes())
            out_f.setGeometry(geom)
            sink.addFeature(out_f)
            transformed += 1

            if step:
                feedback.setProgress(int(i * step))

        feedback.pushInfo(f"✓ Features written: {transformed}")
        if skipped:
            feedback.reportError(f"✗ Features skipped (transform errors): {skipped}")

        # Generate dynamic name for output
        input_name = vlayer.name()
        # Clean input name (remove file extensions and special chars)
        clean_name = input_name.replace('.shp', '').replace('.gpkg', '').replace('.geojson', '')
        # Get CRS code (e.g., "EPSG:3857" -> "3857")
        crs_code = tgt_crs.authid().replace("EPSG:", "").replace(":", "_")

        # Dynamic name format: "LayerName_CRS_reprojected"
        dynamic_name = f"{clean_name}_{crs_code}_reprojected"

        # Set layer name for better identification
        try:
            output_layer = QgsProcessingUtils.mapLayerFromString(dest_id, context)
            if output_layer:
                output_layer.setName(dynamic_name)
                feedback.pushInfo(f"✓ Output layer named: {dynamic_name}")
        except Exception as e:
            feedback.pushDebugInfo(f"Could not set output layer name: {str(e)}")

        return {self.OUTPUT: dest_id}
