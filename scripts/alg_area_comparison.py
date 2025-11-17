# -*- coding: utf-8 -*-
"""
Area Comparison Analysis Algorithm
Compares total feature area with inundated area and generates statistics
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFileDestination,
    QgsField, QgsFields, QgsFeature, QgsFeatureSink,
    QgsProcessingContext
)
from qgis import processing
import os


class AlgAreaComparison(QgsProcessingAlgorithm):
    P_PLOTS = "PLOTS"
    P_FLOOD_RASTER = "FLOOD_RASTER"
    O_OUTPUT = "OUTPUT"
    O_REPORT = "REPORT"

    def tr(self, s):
        return QCoreApplication.translate("AlgAreaComparison", s)

    def name(self):
        return "area_comparison_analysis"

    def displayName(self):
        return self.tr("Total Area vs Inundation Comparison")

    def group(self):
        return self.tr("Visualization & Analysis")

    def groupId(self):
        return "visualization_analysis"

    def shortHelpString(self):
        return self.tr(
            "Compares total plot area with inundated area for each feature.\n\n"
            "This algorithm:\n"
            "1. Calculates total area for each plot/parcel\n"
            "2. Computes inundated area from flood raster\n"
            "3. Generates comparison statistics (%, m², ratios)\n"
            "4. Creates summary report with aggregate statistics\n"
            "5. Outputs enhanced vector layer with all metrics\n\n"
            "Output fields include:\n"
            "- total_area_m2: Total feature area\n"
            "- inund_area_m2: Inundated area\n"
            "- dry_area_m2: Non-inundated area\n"
            "- inund_pct: Percentage inundated\n"
            "- dry_pct: Percentage dry\n"
            "- inund_ratio: Ratio of inundated to total area"
        )

    def createInstance(self):
        return AlgAreaComparison()

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
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_OUTPUT,
            self.tr("Output with Area Statistics")
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.O_REPORT,
            self.tr("Summary Report (CSV)"),
            fileFilter="CSV files (*.csv)"
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        plots_layer = self.parameterAsVectorLayer(parameters, self.P_PLOTS, context)
        flood_raster = self.parameterAsRasterLayer(parameters, self.P_FLOOD_RASTER, context)
        report_path = self.parameterAsFileOutput(parameters, self.O_REPORT, context)

        if not plots_layer or not flood_raster:
            raise QgsProcessingException("Both plot layer and flood raster are required.")

        feedback.pushInfo("Step 1/4: Reprojecting layers to match CRS...")

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

        feedback.pushInfo("Step 3/4: Computing area comparisons...")

        # Output fields
        fields_out = QgsFields()
        for f in stats_layer.fields():
            fields_out.append(f)
        fields_out.append(QgsField("total_area_m2", QVariant.Double))
        fields_out.append(QgsField("inund_area_m2", QVariant.Double))
        fields_out.append(QgsField("dry_area_m2", QVariant.Double))
        fields_out.append(QgsField("inund_pct", QVariant.Double))
        fields_out.append(QgsField("dry_pct", QVariant.Double))
        fields_out.append(QgsField("inund_ratio", QVariant.Double))

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
        total_plots = 0
        total_area_sum = 0.0
        total_inund_sum = 0.0
        total_dry_sum = 0.0

        total_features = stats_layer.featureCount()
        for i, feat in enumerate(stats_layer.getFeatures()):
            if feedback.isCanceled():
                break

            attrs = feat.attributes()
            geom = feat.geometry()

            total_pixels = feat[idx_count] if idx_count != -1 and feat[idx_count] is not None else 0
            flooded_pixels = feat[idx_sum] if idx_sum != -1 and feat[idx_sum] is not None else 0

            total_area = float(total_pixels) * pixel_area if pixel_area > 0 else geom.area()
            inund_area = float(flooded_pixels) * pixel_area if pixel_area > 0 else 0.0
            dry_area = total_area - inund_area

            inund_pct = (inund_area / total_area * 100.0) if total_area > 0 else 0.0
            dry_pct = 100.0 - inund_pct
            inund_ratio = inund_area / total_area if total_area > 0 else 0.0

            # Accumulate for summary
            total_plots += 1
            total_area_sum += total_area
            total_inund_sum += inund_area
            total_dry_sum += dry_area

            out_feat = QgsFeature(fields_out)
            out_feat.setGeometry(geom)
            out_feat.setAttributes(attrs + [total_area, inund_area, dry_area, inund_pct, dry_pct, inund_ratio])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(60 + (i / total_features * 30)))

        feedback.pushInfo("Step 4/4: Writing summary report...")

        # Write CSV report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Area Comparison Summary Report\n")
            f.write("="*50 + "\n\n")
            f.write(f"Total Plots Analyzed,{total_plots}\n")
            f.write(f"Total Area (m²),{total_area_sum:.2f}\n")
            f.write(f"Inundated Area (m²),{total_inund_sum:.2f}\n")
            f.write(f"Dry Area (m²),{total_dry_sum:.2f}\n")
            f.write(f"Inundation Percentage (%),{(total_inund_sum/total_area_sum*100.0 if total_area_sum > 0 else 0):.2f}\n")
            f.write(f"Dry Percentage (%),{(total_dry_sum/total_area_sum*100.0 if total_area_sum > 0 else 0):.2f}\n")
            f.write(f"\nAverage Inundation per Plot (m²),{(total_inund_sum/total_plots if total_plots > 0 else 0):.2f}\n")
            f.write(f"Average Dry Area per Plot (m²),{(total_dry_sum/total_plots if total_plots > 0 else 0):.2f}\n")

        feedback.pushInfo(f"Summary report written to: {report_path}")
        feedback.pushInfo(f"Total plots: {total_plots}, Total inundation: {total_inund_sum:.2f} m² ({(total_inund_sum/total_area_sum*100 if total_area_sum > 0 else 0):.1f}%)")

        feedback.setProgress(100)
        return {self.O_OUTPUT: dest_id, self.O_REPORT: report_path}
