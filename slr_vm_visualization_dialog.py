# -*- coding: utf-8 -*-
"""
Interactive Data Visualization Dialog for OSLRAT
Displays charts, statistics, and analysis within the UI with export capabilities
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QWidget, QProgressBar, QCheckBox, QDoubleSpinBox, QSpinBox,
    QMessageBox, QFileDialog, QTextEdit, QSplitter, QScrollArea
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap, QColor
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsMessageLog,
    Qgis, QgsProcessingContext, QgsProcessingFeedback
)
from qgis import processing
import os

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class AnalysisWorker(QThread):
    """Background worker for heavy computations"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, analysis_type, plots_layer, flood_layer, params):
        super().__init__()
        self.analysis_type = analysis_type
        self.plots_layer = plots_layer
        self.flood_layer = flood_layer
        self.params = params
        self.results = {}

    def run(self):
        try:
            if self.analysis_type == "area_comparison":
                self.results = self.calculate_area_comparison()
            elif self.analysis_type == "feature_comparison":
                self.results = self.calculate_feature_comparison()
            elif self.analysis_type == "population_impact":
                self.results = self.calculate_population_impact()
            elif self.analysis_type == "heatmap":
                self.results = self.calculate_heatmap_data()

            self.finished.emit(self.results)
        except Exception as e:
            self.error.emit(str(e))

    def calculate_area_comparison(self):
        """Calculate total area vs inundation statistics"""
        self.status.emit("Reprojecting layers...")
        self.progress.emit(10)

        # Reproject if needed
        if self.plots_layer.crs() != self.flood_layer.crs():
            result = processing.run(
                "native:reprojectlayer",
                {"INPUT": self.plots_layer, "TARGET_CRS": self.flood_layer.crs(),
                 "OUTPUT": "memory:"},
                feedback=QgsProcessingFeedback()
            )
            plots_reproj = result["OUTPUT"]
        else:
            plots_reproj = self.plots_layer

        self.status.emit("Running zonal statistics...")
        self.progress.emit(30)

        # Zonal statistics
        zs_result = processing.run(
            "native:zonalstatisticsfb",
            {
                "INPUT": plots_reproj,
                "INPUT_RASTER": self.flood_layer,
                "RASTER_BAND": 1,
                "COLUMN_PREFIX": "zs_",
                "STATISTICS": [0, 1],  # COUNT, SUM
                "OUTPUT": "memory:"
            },
            feedback=QgsProcessingFeedback()
        )
        stats_layer = zs_result["OUTPUT"]

        self.status.emit("Computing area statistics...")
        self.progress.emit(60)

        # Calculate statistics
        idx_count = stats_layer.fields().lookupField("zs_count")
        idx_sum = stats_layer.fields().lookupField("zs_sum")
        if idx_count == -1:
            idx_count = stats_layer.fields().lookupField("zs_COUNT")
        if idx_sum == -1:
            idx_sum = stats_layer.fields().lookupField("zs_SUM")

        px_x = abs(self.flood_layer.rasterUnitsPerPixelX())
        px_y = abs(self.flood_layer.rasterUnitsPerPixelY())
        pixel_area = float(px_x * px_y) if px_x and px_y else 0.0

        total_area = 0.0
        inund_area = 0.0
        feature_data = []

        for feat in stats_layer.getFeatures():
            total_pixels = feat[idx_count] if idx_count != -1 and feat[idx_count] is not None else 0
            flooded_pixels = feat[idx_sum] if idx_sum != -1 and feat[idx_sum] is not None else 0

            area = float(total_pixels) * pixel_area if pixel_area > 0 else feat.geometry().area()
            inund = float(flooded_pixels) * pixel_area if pixel_area > 0 else 0.0

            total_area += area
            inund_area += inund

            feature_data.append({
                'total_area': area,
                'inund_area': inund,
                'inund_pct': (inund / area * 100) if area > 0 else 0
            })

        self.progress.emit(100)

        return {
            'total_area': total_area,
            'inund_area': inund_area,
            'dry_area': total_area - inund_area,
            'inund_pct': (inund_area / total_area * 100) if total_area > 0 else 0,
            'feature_count': len(feature_data),
            'feature_data': feature_data
        }

    def calculate_feature_comparison(self):
        """Calculate inundated vs non-inundated feature counts"""
        self.status.emit("Classifying features...")
        self.progress.emit(20)

        threshold = self.params.get('threshold', 10.0)

        # Reuse area comparison logic
        area_results = self.calculate_area_comparison()
        feature_data = area_results['feature_data']

        self.status.emit("Counting classifications...")
        self.progress.emit(70)

        counts = {"Non-Inundated": 0, "Partially Inundated": 0, "Fully Inundated": 0}
        areas = {"Non-Inundated": 0.0, "Partially Inundated": 0.0, "Fully Inundated": 0.0}

        for feat_data in feature_data:
            pct = feat_data['inund_pct']
            if pct < threshold:
                cat = "Non-Inundated"
            elif pct >= 90.0:
                cat = "Fully Inundated"
            else:
                cat = "Partially Inundated"

            counts[cat] += 1
            areas[cat] += feat_data['total_area']

        self.progress.emit(100)

        return {
            'counts': counts,
            'areas': areas,
            'threshold': threshold,
            'total_features': len(feature_data)
        }

    def calculate_population_impact(self):
        """Calculate population affected vs safe"""
        self.status.emit("Analyzing population impact...")
        self.progress.emit(20)

        pop_field = self.params.get('pop_field', None)
        distribute = self.params.get('distribute', True)

        # Get area data first
        area_results = self.calculate_area_comparison()
        feature_data = area_results['feature_data']

        self.status.emit("Computing population distribution...")
        self.progress.emit(60)

        total_pop = 0.0
        affected_pop = 0.0

        # Get population data
        if pop_field and pop_field in self.plots_layer.fields().names():
            idx = 0
            for feat in self.plots_layer.getFeatures():
                if idx < len(feature_data):
                    pop = float(feat[pop_field]) if feat[pop_field] is not None else 0.0
                    inund_pct = feature_data[idx]['inund_pct']

                    if distribute:
                        # Proportional distribution
                        affected = pop * (inund_pct / 100.0)
                    else:
                        # Simple: all or nothing
                        affected = pop if inund_pct > 0 else 0.0

                    total_pop += pop
                    affected_pop += affected
                    feature_data[idx]['pop_total'] = pop
                    feature_data[idx]['pop_affected'] = affected
                    idx += 1
        else:
            # Default: 1 person per feature
            for feat_data in feature_data:
                pop = 1.0
                inund_pct = feat_data['inund_pct']
                if distribute:
                    affected = pop * (inund_pct / 100.0)
                else:
                    affected = 1.0 if inund_pct > 0 else 0.0

                total_pop += pop
                affected_pop += affected
                feat_data['pop_total'] = pop
                feat_data['pop_affected'] = affected

        self.progress.emit(100)

        return {
            'total_population': total_pop,
            'affected_population': affected_pop,
            'safe_population': total_pop - affected_pop,
            'affected_pct': (affected_pop / total_pop * 100) if total_pop > 0 else 0,
            'feature_count': len(feature_data),
            'has_pop_field': pop_field is not None
        }

    def calculate_heatmap_data(self):
        """Get data for heatmap visualization"""
        return self.calculate_area_comparison()


class ChartWidget(QWidget):
    """Custom widget for displaying matplotlib charts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(8, 6), facecolor='white')
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)


class SlrVmVisualizationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OSLRAT - Data Visualization & Analysis")
        self.resize(1200, 800)

        self.current_results = None
        self.worker = None

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QLabel("<h2>📊 Interactive Data Visualization & Analysis</h2>")
        header.setStyleSheet("color: #2c3e50; padding: 10px;")
        main_layout.addWidget(header)

        # Splitter for left panel and right panel
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Configuration
        left_panel = self.create_config_panel()
        splitter.addWidget(left_panel)

        # Right panel - Visualization
        right_panel = self.create_visualization_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)

        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)

        main_layout.addLayout(button_layout)

    def create_config_panel(self):
        """Create left configuration panel"""
        panel = QWidget()
        panel.setStyleSheet("QWidget { background-color: #f8f9fa; border-radius: 8px; }")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title = QLabel("<b>Configuration</b>")
        title.setStyleSheet("font-size: 14px; color: #2c3e50;")
        layout.addWidget(title)

        # Analysis Type
        type_group = QGroupBox("Analysis Type")
        type_layout = QVBoxLayout()
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems([
            "Area Comparison (Total vs Inundated)",
            "Feature Classification (Inundated vs Non-Inundated)",
            "Population Impact Analysis",
            "Inundation Heatmap Data"
        ])
        self.analysis_combo.currentIndexChanged.connect(self.on_analysis_type_changed)
        type_layout.addWidget(self.analysis_combo)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)

        # Layer Selection
        layer_group = QGroupBox("Layer Selection")
        layer_layout = QVBoxLayout()

        layer_layout.addWidget(QLabel("Plot/Parcel Layer:"))
        self.plots_combo = QComboBox()
        self.populate_vector_layers()
        layer_layout.addWidget(self.plots_combo)

        layer_layout.addWidget(QLabel("Flood Raster Layer:"))
        self.flood_combo = QComboBox()
        self.populate_raster_layers()
        layer_layout.addWidget(self.flood_combo)

        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)

        # Parameters (dynamic based on analysis type)
        self.params_group = QGroupBox("Parameters")
        self.params_layout = QVBoxLayout()
        self.params_group.setLayout(self.params_layout)
        layout.addWidget(self.params_group)
        self.update_parameters_ui()

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Generate Button
        self.generate_btn = QPushButton("🔄 Calculate & Generate Chart")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)
        self.generate_btn.clicked.connect(self.generate_analysis)
        layout.addWidget(self.generate_btn)

        layout.addStretch()

        return panel

    def create_visualization_panel(self):
        """Create right visualization panel"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Tabs for different views
        self.tabs = QTabWidget()

        # Chart tab
        self.chart_widget = ChartWidget() if MATPLOTLIB_AVAILABLE else QLabel("Matplotlib not available")
        self.tabs.addTab(self.chart_widget, "📈 Chart")

        # Statistics table tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_table = QTableWidget()
        self.stats_table.setAlternatingRowColors(True)
        stats_layout.addWidget(self.stats_table)
        self.tabs.addTab(stats_widget, "📊 Statistics")

        # Raw data tab
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setFont(self.data_text.font())
        data_layout.addWidget(self.data_text)
        self.tabs.addTab(data_widget, "📋 Raw Data")

        layout.addWidget(self.tabs)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_png_btn = QPushButton("Export Chart as PNG")
        self.export_png_btn.clicked.connect(lambda: self.export_chart('png'))
        self.export_png_btn.setEnabled(False)

        self.export_pdf_btn = QPushButton("Export Chart as PDF")
        self.export_pdf_btn.clicked.connect(lambda: self.export_chart('pdf'))
        self.export_pdf_btn.setEnabled(False)

        self.export_csv_btn = QPushButton("Export Data as CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.export_csv_btn.setEnabled(False)

        if PANDAS_AVAILABLE:
            self.export_excel_btn = QPushButton("Export Data as Excel")
            self.export_excel_btn.clicked.connect(self.export_excel)
            self.export_excel_btn.setEnabled(False)
            export_layout.addWidget(self.export_excel_btn)

        export_layout.addWidget(self.export_png_btn)
        export_layout.addWidget(self.export_pdf_btn)
        export_layout.addWidget(self.export_csv_btn)
        export_layout.addStretch()

        layout.addLayout(export_layout)

        return panel

    def populate_vector_layers(self):
        """Populate combo with vector polygon layers"""
        self.plots_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 2:  # Polygon
                self.plots_combo.addItem(layer.name(), layer)

    def populate_raster_layers(self):
        """Populate combo with raster layers"""
        self.flood_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.flood_combo.addItem(layer.name(), layer)

    def on_analysis_type_changed(self):
        """Update parameters when analysis type changes"""
        self.update_parameters_ui()

    def update_parameters_ui(self):
        """Dynamically update parameters based on analysis type"""
        # Clear existing widgets
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        analysis_idx = self.analysis_combo.currentIndex()

        if analysis_idx == 1:  # Feature Classification
            self.params_layout.addWidget(QLabel("Classification Threshold (%):"))
            self.threshold_spin = QDoubleSpinBox()
            self.threshold_spin.setRange(0.1, 100.0)
            self.threshold_spin.setValue(10.0)
            self.threshold_spin.setSuffix(" %")
            self.params_layout.addWidget(self.threshold_spin)

        elif analysis_idx == 2:  # Population Impact
            self.params_layout.addWidget(QLabel("Population Field (optional):"))
            self.pop_field_combo = QComboBox()
            self.pop_field_combo.addItem("(None - use default)")
            # Will be populated when plots layer is selected
            self.update_population_fields()
            self.params_layout.addWidget(self.pop_field_combo)

            self.distribute_check = QCheckBox("Distribute population proportionally by area")
            self.distribute_check.setChecked(True)
            self.params_layout.addWidget(self.distribute_check)

        self.params_layout.addStretch()

    def update_population_fields(self):
        """Update population field combo with numeric fields"""
        if hasattr(self, 'pop_field_combo'):
            self.pop_field_combo.clear()
            self.pop_field_combo.addItem("(None - use default)", None)

            plots_layer = self.plots_combo.currentData()
            if plots_layer:
                for field in plots_layer.fields():
                    if field.isNumeric():
                        self.pop_field_combo.addItem(field.name(), field.name())

    def generate_analysis(self):
        """Start analysis calculation"""
        # Get selected layers
        plots_layer = self.plots_combo.currentData()
        flood_layer = self.flood_combo.currentData()

        if not plots_layer or not flood_layer:
            QMessageBox.warning(self, "Missing Data",
                              "Please select both plot layer and flood raster layer.")
            return

        # Determine analysis type
        analysis_idx = self.analysis_combo.currentIndex()
        analysis_types = ['area_comparison', 'feature_comparison', 'population_impact', 'heatmap']
        analysis_type = analysis_types[analysis_idx]

        # Gather parameters
        params = {}
        if analysis_idx == 1:  # Feature Classification
            params['threshold'] = self.threshold_spin.value()
        elif analysis_idx == 2:  # Population Impact
            params['pop_field'] = self.pop_field_combo.currentData()
            params['distribute'] = self.distribute_check.isChecked()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting analysis...")
        self.generate_btn.setEnabled(False)

        # Start worker thread
        self.worker = AnalysisWorker(analysis_type, plots_layer, flood_layer, params)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()

    def on_analysis_finished(self, results):
        """Handle completed analysis"""
        self.current_results = results
        self.progress_bar.setVisible(False)
        self.status_label.setText("✓ Analysis complete")
        self.generate_btn.setEnabled(True)

        # Update visualizations
        self.update_chart(results)
        self.update_statistics_table(results)
        self.update_raw_data(results)

        # Enable export buttons
        self.export_png_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)
        self.export_csv_btn.setEnabled(True)
        if PANDAS_AVAILABLE and hasattr(self, 'export_excel_btn'):
            self.export_excel_btn.setEnabled(True)

    def on_analysis_error(self, error_msg):
        """Handle analysis error"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("✗ Error occurred")
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Analysis Error", f"An error occurred:\n\n{error_msg}")

    def update_chart(self, results):
        """Generate matplotlib chart based on results"""
        if not MATPLOTLIB_AVAILABLE:
            return

        self.chart_widget.figure.clear()

        analysis_idx = self.analysis_combo.currentIndex()

        if analysis_idx == 0:  # Area Comparison
            self.create_area_comparison_chart(results)
        elif analysis_idx == 1:  # Feature Classification
            self.create_feature_classification_chart(results)
        elif analysis_idx == 2:  # Population Impact
            self.create_population_impact_chart(results)
        elif analysis_idx == 3:  # Heatmap
            self.create_heatmap_chart(results)

        self.chart_widget.canvas.draw()

    def create_area_comparison_chart(self, results):
        """Create area comparison bar chart"""
        ax = self.chart_widget.figure.add_subplot(111)

        categories = ['Total Area', 'Inundated Area', 'Dry Area']
        values = [
            results['total_area'],
            results['inund_area'],
            results['dry_area']
        ]
        colors = ['#3498db', '#e74c3c', '#2ecc71']

        bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:,.0f} m²',
                   ha='center', va='bottom', fontweight='bold')

        ax.set_ylabel('Area (m²)', fontweight='bold', fontsize=11)
        ax.set_title(f'Total Area vs Inundation Comparison\n({results["feature_count"]} features analyzed)',
                    fontweight='bold', fontsize=13, pad=15)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Add percentage annotation
        ax.text(0.02, 0.98, f'Inundation: {results["inund_pct"]:.1f}%',
               transform=ax.transAxes, fontsize=12, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        self.chart_widget.figure.tight_layout()

    def create_feature_classification_chart(self, results):
        """Create pie chart for feature classification"""
        ax = self.chart_widget.figure.add_subplot(111)

        counts = results['counts']
        labels = list(counts.keys())
        values = list(counts.values())
        colors = ['#2ecc71', '#f39c12', '#e74c3c']
        explode = (0.05, 0.05, 0.1)

        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                           colors=colors, explode=explode,
                                           startangle=90, textprops={'fontweight': 'bold', 'fontsize': 11})

        # Add count labels
        for i, (label, val) in enumerate(zip(labels, values)):
            texts[i].set_text(f'{label}\n({val} features)')

        ax.set_title(f'Feature Classification\n(Threshold: {results["threshold"]}%, Total: {results["total_features"]} features)',
                    fontweight='bold', fontsize=13, pad=15)

        self.chart_widget.figure.tight_layout()

    def create_population_impact_chart(self, results):
        """Create population impact comparison chart"""
        fig = self.chart_widget.figure
        gs = fig.add_gridspec(1, 2, wspace=0.3)

        # Pie chart
        ax1 = fig.add_subplot(gs[0, 0])
        labels = ['Affected', 'Safe']
        values = [results['affected_population'], results['safe_population']]
        colors = ['#e74c3c', '#2ecc71']
        explode = (0.1, 0)

        wedges, texts, autotexts = ax1.pie(values, labels=labels, autopct='%1.1f%%',
                                            colors=colors, explode=explode,
                                            startangle=90, textprops={'fontweight': 'bold', 'fontsize': 11})
        ax1.set_title('Population Distribution', fontweight='bold', fontsize=12)

        # Bar chart
        ax2 = fig.add_subplot(gs[0, 1])
        categories = ['Total\nPopulation', 'Affected\nPopulation', 'Safe\nPopulation']
        values2 = [results['total_population'], results['affected_population'], results['safe_population']]
        colors2 = ['#3498db', '#e74c3c', '#2ecc71']

        bars = ax2.bar(categories, values2, color=colors2, alpha=0.8, edgecolor='black', linewidth=1.5)

        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:,.0f}',
                    ha='center', va='bottom', fontweight='bold', fontsize=10)

        ax2.set_ylabel('Population Count', fontweight='bold', fontsize=11)
        ax2.set_title('Population Statistics', fontweight='bold', fontsize=12)
        ax2.grid(axis='y', alpha=0.3, linestyle='--')

        fig.suptitle(f'Population Impact Analysis\n({results["feature_count"]} features analyzed)',
                    fontweight='bold', fontsize=14, y=0.98)

        fig.tight_layout()

    def create_heatmap_chart(self, results):
        """Create histogram of inundation percentages"""
        ax = self.chart_widget.figure.add_subplot(111)

        percentages = [f['inund_pct'] for f in results['feature_data']]

        n, bins, patches = ax.hist(percentages, bins=20, color='#3498db',
                                   alpha=0.7, edgecolor='black', linewidth=1.2)

        # Color bars by intensity
        cm = plt.cm.get_cmap('RdYlGn_r')
        for i, patch in enumerate(patches):
            patch.set_facecolor(cm(i / len(patches)))

        ax.set_xlabel('Inundation Percentage (%)', fontweight='bold', fontsize=11)
        ax.set_ylabel('Number of Features', fontweight='bold', fontsize=11)
        ax.set_title(f'Inundation Distribution Histogram\n({results["feature_count"]} features)',
                    fontweight='bold', fontsize=13, pad=15)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Add statistics
        stats_text = f'Mean: {sum(percentages)/len(percentages):.1f}%\nMedian: {sorted(percentages)[len(percentages)//2]:.1f}%'
        ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
               fontsize=11, verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        self.chart_widget.figure.tight_layout()

    def update_statistics_table(self, results):
        """Update statistics table"""
        self.stats_table.clear()

        analysis_idx = self.analysis_combo.currentIndex()

        if analysis_idx == 0:  # Area Comparison
            self.stats_table.setRowCount(5)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

            data = [
                ('Total Area (m²)', f"{results['total_area']:,.2f}"),
                ('Inundated Area (m²)', f"{results['inund_area']:,.2f}"),
                ('Dry Area (m²)', f"{results['dry_area']:,.2f}"),
                ('Inundation Percentage', f"{results['inund_pct']:.2f}%"),
                ('Features Analyzed', str(results['feature_count']))
            ]

        elif analysis_idx == 1:  # Feature Classification
            self.stats_table.setRowCount(5)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Category', 'Count'])

            counts = results['counts']
            data = [
                ('Non-Inundated Features', str(counts['Non-Inundated'])),
                ('Partially Inundated Features', str(counts['Partially Inundated'])),
                ('Fully Inundated Features', str(counts['Fully Inundated'])),
                ('Total Features', str(results['total_features'])),
                ('Classification Threshold', f"{results['threshold']}%")
            ]

        elif analysis_idx == 2:  # Population Impact
            self.stats_table.setRowCount(5)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

            data = [
                ('Total Population', f"{results['total_population']:,.0f}"),
                ('Affected Population', f"{results['affected_population']:,.0f}"),
                ('Safe Population', f"{results['safe_population']:,.0f}"),
                ('Affected Percentage', f"{results['affected_pct']:.2f}%"),
                ('Features Analyzed', str(results['feature_count']))
            ]

        else:  # Heatmap
            self.stats_table.setRowCount(3)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

            percentages = [f['inund_pct'] for f in results['feature_data']]
            data = [
                ('Mean Inundation %', f"{sum(percentages)/len(percentages):.2f}%"),
                ('Median Inundation %', f"{sorted(percentages)[len(percentages)//2]:.2f}%"),
                ('Features Analyzed', str(results['feature_count']))
            ]

        for row, (label, value) in enumerate(data):
            self.stats_table.setItem(row, 0, QTableWidgetItem(label))
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stats_table.setItem(row, 1, value_item)

        self.stats_table.resizeColumnsToContents()
        self.stats_table.horizontalHeader().setStretchLastSection(True)

    def update_raw_data(self, results):
        """Update raw data text view"""
        import json

        # Create readable JSON
        display_results = dict(results)
        if 'feature_data' in display_results:
            # Limit feature data display
            display_results['feature_data'] = f"[{len(results['feature_data'])} features - see CSV export for details]"

        formatted_json = json.dumps(display_results, indent=2)
        self.data_text.setText(formatted_json)

    def export_chart(self, format_type):
        """Export chart as PNG or PDF"""
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please generate a chart first.")
            return

        file_filter = "PNG Image (*.png)" if format_type == 'png' else "PDF Document (*.pdf)"
        file_path, _ = QFileDialog.getSaveFileName(self, f"Export Chart as {format_type.upper()}",
                                                   "", file_filter)

        if file_path:
            try:
                self.chart_widget.figure.savefig(file_path, dpi=300, bbox_inches='tight',
                                                facecolor='white', edgecolor='none')
                QMessageBox.information(self, "Success", f"Chart exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export chart:\n{str(e)}")

    def export_csv(self):
        """Export data as CSV"""
        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please generate analysis first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data as CSV", "", "CSV Files (*.csv)")

        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    analysis_idx = self.analysis_combo.currentIndex()

                    if analysis_idx == 0 or analysis_idx == 3:  # Area or Heatmap
                        writer.writerow(['Feature_ID', 'Total_Area_m2', 'Inundated_Area_m2', 'Inundation_Pct'])
                        for i, feat in enumerate(self.current_results['feature_data']):
                            writer.writerow([i+1, feat['total_area'], feat['inund_area'], feat['inund_pct']])

                    elif analysis_idx == 1:  # Feature Classification
                        writer.writerow(['Category', 'Count', 'Total_Area_m2'])
                        for cat, count in self.current_results['counts'].items():
                            writer.writerow([cat, count, self.current_results['areas'][cat]])

                    elif analysis_idx == 2:  # Population
                        writer.writerow(['Summary', 'Value'])
                        writer.writerow(['Total Population', self.current_results['total_population']])
                        writer.writerow(['Affected Population', self.current_results['affected_population']])
                        writer.writerow(['Safe Population', self.current_results['safe_population']])

                QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export CSV:\n{str(e)}")

    def export_excel(self):
        """Export data as Excel"""
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Pandas Required",
                              "Pandas library is required for Excel export.")
            return

        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please generate analysis first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data as Excel", "", "Excel Files (*.xlsx)")

        if file_path:
            try:
                analysis_idx = self.analysis_combo.currentIndex()

                if analysis_idx == 0 or analysis_idx == 3:  # Area or Heatmap
                    df = pd.DataFrame(self.current_results['feature_data'])
                    df.to_excel(file_path, index_label='Feature_ID')

                elif analysis_idx == 1:  # Feature Classification
                    df = pd.DataFrame({
                        'Category': list(self.current_results['counts'].keys()),
                        'Count': list(self.current_results['counts'].values()),
                        'Area_m2': list(self.current_results['areas'].values())
                    })
                    df.to_excel(file_path, index=False)

                elif analysis_idx == 2:  # Population
                    df = pd.DataFrame({
                        'Metric': ['Total Population', 'Affected Population', 'Safe Population'],
                        'Value': [self.current_results['total_population'],
                                 self.current_results['affected_population'],
                                 self.current_results['safe_population']]
                    })
                    df.to_excel(file_path, index=False)

                QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export Excel:\n{str(e)}")
