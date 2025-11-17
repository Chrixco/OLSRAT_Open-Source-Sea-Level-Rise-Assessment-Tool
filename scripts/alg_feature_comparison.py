# -*- coding: utf-8 -*-
"""
Feature Comparison Analysis Algorithm
Classifies and compares inundated vs non-inundated features
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsField, QgsFields, QgsFeature, QgsFeatureSink,
    QgsProcessingContext
)
from qgis import processing
import os


class AlgFeatureComparison(QgsProcessingAlgorithm):
    P_PLOTS = "PLOTS"
    P_FLOOD_RASTER = "FLOOD_RASTER"
    P_THRESHOLD = "THRESHOLD"
    O_OUTPUT = "OUTPUT"
    O_REPORT = "REPORT"

    def tr(self, s):
        return QCoreApplication.translate("AlgFeatureComparison", s)

    def name(self):
        return "feature_comparison_analysis"

    def displayName(self):
        return self.tr("Inundated vs Non-Inundated Features")

    def group(self):
        return self.tr("Visualization & Analysis")

    def groupId(self):
        return "visualization_analysis"

    def shortHelpString(self):
        return self.tr(
            "Classifies features as inundated or non-inundated based on a threshold.\n\n"
            "This algorithm:\n"
            "1. Calculates inundation percentage for each feature\n"
            "2. Classifies features using a threshold (default: 10%)\n"
            "3. Generates statistics for both groups\n"
            "4. Creates comparative report with counts, areas, and percentages\n"
            "5. Adds classification field for mapping and filtering\n\n"
            "Classification Logic:\n"
            "- 'Non-Inundated': < threshold %\n"
            "- 'Partially Inundated': >= threshold % and < 90%\n"
            "- 'Fully Inundated': >= 90%\n\n"
            "Perfect for risk assessment and prioritizing adaptation measures."
        )

    def createInstance(self):
        return AlgFeatureComparison()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "256.png"))

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(
            self.P_PLOTS,
            self.tr("Plot/Parcel Layer (Polygons)"),
            types=[QgsProcessing.TypeVectorPolygon]
        ))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.P_FLOOD_RASTER,
            self.tr("Flood Inundation Raster (Binary: 0=dry, 1=flooded)")
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.P_THRESHOLD,
            self.tr("Inundation Threshold (%) for Classification"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=10.0,
            minValue=0.1,
            maxValue=100.0
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_OUTPUT,
            self.tr("Output with Classification")
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.O_REPORT,
            self.tr("Comparison Report (CSV)"),
            fileFilter="CSV files (*.csv)"
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        plots_layer = self.parameterAsVectorLayer(parameters, self.P_PLOTS, context)
        flood_raster = self.parameterAsRasterLayer(parameters, self.P_FLOOD_RASTER, context)
        threshold = self.parameterAsDouble(parameters, self.P_THRESHOLD, context)
        report_path = self.parameterAsFileOutput(parameters, self.O_REPORT, context)

        if not plots_layer or not flood_raster:
            raise QgsProcessingException("Both plot layer and flood raster are required.")

        feedback.pushInfo(f"Using classification threshold: {threshold}%")
        feedback.pushInfo("Step 1/4: Reprojecting layers...")

        # Reproject if needed
        if plots_layer.crs() != flood_raster.crs():
            plots_reproj = processing.run(
                "native:reprojectlayer",
                {"INPUT": plots_layer, "TARGET_CRS": flood_raster.crs(), "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT},
                context=context, feedback=feedback
            )["OUTPUT"]
        else:
            plots_reproj = plots_layer

        feedback.pushInfo("Step 2/4: Running zonal statistics...")

        # Zonal statistics
        zs_result = processing.run(
            "native:zonalstatisticsfb",
            {
                "INPUT": plots_reproj,
                "INPUT_RASTER": flood_raster,
                "RASTER_BAND": 1,
                "COLUMN_PREFIX": "zs_",
                "STATISTICS": [0, 1],  # COUNT, SUM
                "OUTPUT": QgsProcessing.TEMPORARY_OUTPUT
            },
            context=context, feedback=feedback
        )
        stats_layer = zs_result["OUTPUT"]

        feedback.pushInfo("Step 3/4: Classifying features...")

        # Output fields
        fields_out = QgsFields()
        for f in stats_layer.fields():
            fields_out.append(f)
        fields_out.append(QgsField("inund_pct", QVariant.Double))
        fields_out.append(QgsField("inund_m2", QVariant.Double))
        fields_out.append(QgsField("classification", QVariant.String))
        fields_out.append(QgsField("class_code", QVariant.Int))  # 0=Non, 1=Partial, 2=Full

        sink, dest_id = self.parameterAsSink(
            parameters, self.O_OUTPUT, context,
            fields_out, plots_layer.wkbType(), plots_layer.crs()
        )
        if sink is None:
            raise QgsProcessingException("Could not create output sink.")

        idx_count = stats_layer.fields().lookupField("zs_count")
        idx_sum = stats_layer.fields().lookupField("zs_sum")
        if idx_count == -1:
            idx_count = stats_layer.fields().lookupField("zs_COUNT")
        if idx_sum == -1:
            idx_sum = stats_layer.fields().lookupField("zs_SUM")

        px_x = abs(flood_raster.rasterUnitsPerPixelX())
        px_y = abs(flood_raster.rasterUnitsPerPixelY())
        pixel_area = float(px_x * px_y) if px_x and px_y else 0.0

        # Statistics accumulators
        counts = {"Non-Inundated": 0, "Partially Inundated": 0, "Fully Inundated": 0}
        areas = {"Non-Inundated": 0.0, "Partially Inundated": 0.0, "Fully Inundated": 0.0}
        inund_areas = {"Non-Inundated": 0.0, "Partially Inundated": 0.0, "Fully Inundated": 0.0}

        total_features = stats_layer.featureCount()
        for i, feat in enumerate(stats_layer.getFeatures()):
            if feedback.isCanceled():
                break

            attrs = feat.attributes()
            geom = feat.geometry()

            total_pixels = feat[idx_count] if idx_count != -1 and feat[idx_count] is not None else 0
            flooded_pixels = feat[idx_sum] if idx_sum != -1 and feat[idx_sum] is not None else 0

            total_area = float(total_pixels) * pixel_area if pixel_area > 0 else geom.area()
            inund_m2 = float(flooded_pixels) * pixel_area if pixel_area > 0 else 0.0
            inund_pct = (inund_m2 / total_area * 100.0) if total_area > 0 else 0.0

            # Classify
            if inund_pct < threshold:
                classification = "Non-Inundated"
                class_code = 0
            elif inund_pct >= 90.0:
                classification = "Fully Inundated"
                class_code = 2
            else:
                classification = "Partially Inundated"
                class_code = 1

            # Accumulate stats
            counts[classification] += 1
            areas[classification] += total_area
            inund_areas[classification] += inund_m2

            out_feat = QgsFeature(fields_out)
            out_feat.setGeometry(geom)
            out_feat.setAttributes(attrs + [inund_pct, inund_m2, classification, class_code])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(60 + (i / total_features * 30)))

        feedback.pushInfo("Step 4/4: Writing comparison report...")

        # Write CSV report
        total_count = sum(counts.values())
        total_area = sum(areas.values())
        total_inund = sum(inund_areas.values())

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Feature Classification Comparison Report\n")
            f.write("="*60 + "\n\n")
            f.write(f"Threshold Used: {threshold}%\n")
            f.write(f"Total Features: {total_count}\n\n")

            f.write("Classification Summary\n")
            f.write("-"*60 + "\n")
            f.write("Category,Count,% of Total,Total Area (m²),Inundated Area (m²),Avg Inundation %\n")

            for cat in ["Non-Inundated", "Partially Inundated", "Fully Inundated"]:
                count = counts[cat]
                area = areas[cat]
                inund = inund_areas[cat]
                pct_count = (count / total_count * 100) if total_count > 0 else 0
                avg_inund_pct = (inund / area * 100) if area > 0 else 0
                f.write(f"{cat},{count},{pct_count:.1f},{area:.2f},{inund:.2f},{avg_inund_pct:.1f}\n")

            f.write("\n" + "="*60 + "\n")
            f.write(f"TOTALS,{total_count},100.0,{total_area:.2f},{total_inund:.2f},{(total_inund/total_area*100 if total_area > 0 else 0):.1f}\n")

        feedback.pushInfo(f"Classification complete:")
        feedback.pushInfo(f"  Non-Inundated: {counts['Non-Inundated']} features")
        feedback.pushInfo(f"  Partially Inundated: {counts['Partially Inundated']} features")
        feedback.pushInfo(f"  Fully Inundated: {counts['Fully Inundated']} features")
        feedback.pushInfo(f"Report saved to: {report_path}")

        feedback.setProgress(100)
        return {self.O_OUTPUT: dest_id, self.O_REPORT: report_path}
