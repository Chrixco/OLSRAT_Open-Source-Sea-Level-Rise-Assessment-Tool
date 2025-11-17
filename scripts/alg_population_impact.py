# -*- coding: utf-8 -*-
"""
Population Impact Analysis Algorithm
Analyzes population affected by inundation with optional population distribution
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterVectorLayer, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterField, QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFileDestination,
    QgsField, QgsFields, QgsFeature, QgsFeatureSink,
    QgsProcessingContext
)
from qgis import processing
import os


class AlgPopulationImpact(QgsProcessingAlgorithm):
    P_PLOTS = "PLOTS"
    P_FLOOD_RASTER = "FLOOD_RASTER"
    P_POP_FIELD = "POP_FIELD"
    P_DISTRIBUTE = "DISTRIBUTE"
    O_OUTPUT = "OUTPUT"
    O_REPORT = "REPORT"

    def tr(self, s):
        return QCoreApplication.translate("AlgPopulationImpact", s)

    def name(self):
        return "population_impact_analysis"

    def displayName(self):
        return self.tr("Population Impact Analysis")

    def group(self):
        return self.tr("Visualization & Analysis")

    def groupId(self):
        return "visualization_analysis"

    def shortHelpString(self):
        return self.tr(
            "Analyzes population affected by inundation with optional proportional distribution.\n\n"
            "This algorithm:\n"
            "1. Reads population data from plot features\n"
            "2. Calculates inundation percentage for each plot\n"
            "3. Optionally distributes population proportionally by area\n"
            "4. Computes affected vs non-affected population\n"
            "5. Generates detailed impact statistics and reports\n\n"
            "Distribution Options:\n"
            "- Simple Mode: Uses plot-level population as-is\n"
            "- Distributed Mode: Allocates population proportionally based on inundated area\n\n"
            "Output fields include:\n"
            "- pop_total: Total population in plot\n"
            "- pop_affected: Population in inundated areas\n"
            "- pop_safe: Population in non-inundated areas\n"
            "- pop_affected_pct: Percentage affected\n"
            "- pop_density: Population per m²\n\n"
            "Perfect for social vulnerability assessment and emergency planning."
        )

    def createInstance(self):
        return AlgPopulationImpact()

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
        self.addParameter(QgsProcessingParameterField(
            self.P_POP_FIELD,
            self.tr("Population Field"),
            parentLayerParameterName=self.P_PLOTS,
            type=QgsProcessingParameterField.Numeric,
            optional=True
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.P_DISTRIBUTE,
            self.tr("Distribute population proportionally by area"),
            defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.O_OUTPUT,
            self.tr("Output with Population Impact")
        ))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.O_REPORT,
            self.tr("Population Impact Report (CSV)"),
            fileFilter="CSV files (*.csv)"
        ))

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        plots_layer = self.parameterAsVectorLayer(parameters, self.P_PLOTS, context)
        flood_raster = self.parameterAsRasterLayer(parameters, self.P_FLOOD_RASTER, context)
        pop_field = self.parameterAsString(parameters, self.P_POP_FIELD, context)
        distribute = self.parameterAsBoolean(parameters, self.P_DISTRIBUTE, context)
        report_path = self.parameterAsFileOutput(parameters, self.O_REPORT, context)

        if not plots_layer or not flood_raster:
            raise QgsProcessingException("Both plot layer and flood raster are required.")

        # Validate population field
        has_pop_field = False
        if pop_field and pop_field in plots_layer.fields().names():
            has_pop_field = True
            feedback.pushInfo(f"Using population field: {pop_field}")
        else:
            feedback.pushWarning("No population field specified. Will use default population of 1 per feature for demonstration.")
            pop_field = None

        feedback.pushInfo(f"Distribution mode: {'Proportional by area' if distribute else 'Simple (plot-level)'}")
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

        feedback.pushInfo("Step 3/4: Computing population impacts...")

        # Output fields
        fields_out = QgsFields()
        for f in stats_layer.fields():
            fields_out.append(f)
        fields_out.append(QgsField("inund_pct", QVariant.Double))
        fields_out.append(QgsField("inund_m2", QVariant.Double))
        fields_out.append(QgsField("total_m2", QVariant.Double))
        fields_out.append(QgsField("pop_total", QVariant.Double))
        fields_out.append(QgsField("pop_affected", QVariant.Double))
        fields_out.append(QgsField("pop_safe", QVariant.Double))
        fields_out.append(QgsField("pop_affected_pct", QVariant.Double))
        fields_out.append(QgsField("pop_density", QVariant.Double))

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
        total_pop = 0.0
        total_affected = 0.0
        total_safe = 0.0
        total_plots = 0
        plots_with_impact = 0

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

            # Get population
            if has_pop_field:
                pop_total = float(feat[pop_field]) if feat[pop_field] is not None else 0.0
            else:
                pop_total = 1.0  # Default for demonstration

            # Calculate affected population
            if distribute:
                # Proportional distribution by area
                pop_affected = pop_total * (inund_m2 / total_area) if total_area > 0 else 0.0
            else:
                # Simple: if any inundation, consider entire plot population affected
                pop_affected = pop_total if inund_pct > 0 else 0.0

            pop_safe = pop_total - pop_affected
            pop_affected_pct = (pop_affected / pop_total * 100.0) if pop_total > 0 else 0.0
            pop_density = pop_total / total_area if total_area > 0 else 0.0

            # Accumulate stats
            total_plots += 1
            total_pop += pop_total
            total_affected += pop_affected
            total_safe += pop_safe
            if pop_affected > 0:
                plots_with_impact += 1

            out_feat = QgsFeature(fields_out)
            out_feat.setGeometry(geom)
            out_feat.setAttributes(attrs + [inund_pct, inund_m2, total_area, pop_total, pop_affected, pop_safe, pop_affected_pct, pop_density])
            sink.addFeature(out_feat, QgsFeatureSink.FastInsert)

            if i % 100 == 0:
                feedback.setProgress(int(60 + (i / total_features * 30)))

        feedback.pushInfo("Step 4/4: Writing population impact report...")

        # Write CSV report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Population Impact Analysis Report\n")
            f.write("="*60 + "\n\n")
            f.write(f"Distribution Method: {'Proportional by Area' if distribute else 'Simple (Plot-level)'}\n")
            f.write(f"Population Field: {pop_field if pop_field else 'Default (1 per feature)'}\n\n")

            f.write("Overall Statistics\n")
            f.write("-"*60 + "\n")
            f.write(f"Total Plots Analyzed,{total_plots}\n")
            f.write(f"Plots with Population Impact,{plots_with_impact}\n")
            f.write(f"Total Population,{total_pop:.0f}\n")
            f.write(f"Affected Population,{total_affected:.0f}\n")
            f.write(f"Safe Population,{total_safe:.0f}\n")
            f.write(f"Percentage Affected,{(total_affected/total_pop*100 if total_pop > 0 else 0):.2f}%\n")
            f.write(f"Percentage Safe,{(total_safe/total_pop*100 if total_pop > 0 else 0):.2f}%\n\n")

            f.write("Averages per Plot\n")
            f.write("-"*60 + "\n")
            f.write(f"Avg Population per Plot,{(total_pop/total_plots if total_plots > 0 else 0):.2f}\n")
            f.write(f"Avg Affected per Plot,{(total_affected/total_plots if total_plots > 0 else 0):.2f}\n")
            f.write(f"Avg Safe per Plot,{(total_safe/total_plots if total_plots > 0 else 0):.2f}\n")

        feedback.pushInfo(f"Population Impact Summary:")
        feedback.pushInfo(f"  Total Population: {total_pop:.0f}")
        feedback.pushInfo(f"  Affected: {total_affected:.0f} ({(total_affected/total_pop*100 if total_pop > 0 else 0):.1f}%)")
        feedback.pushInfo(f"  Safe: {total_safe:.0f} ({(total_safe/total_pop*100 if total_pop > 0 else 0):.1f}%)")
        feedback.pushInfo(f"Report saved to: {report_path}")

        feedback.setProgress(100)
        return {self.O_OUTPUT: dest_id, self.O_REPORT: report_path}
