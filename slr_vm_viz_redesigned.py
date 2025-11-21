# -*- coding: utf-8 -*-
"""
Redesigned Interactive Data Visualization Dashboard
Professional UI with proper layer selection workflow for inundation analysis
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QWidget, QProgressBar, QMessageBox, QFileDialog, QTextEdit, QSplitter,
    QRadioButton, QButtonGroup, QScrollArea, QFrame, QCheckBox, QSpinBox, QGridLayout
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QMutex, QMutexLocker
from qgis.PyQt.QtGui import QIcon, QColor, QFont
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsMessageLog, Qgis
)
from qgis import processing

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


class ValueSelectorDialog(QDialog):
    """Dialog for selecting field values with checkboxes"""
    def __init__(self, field_name, unique_values, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.unique_values = sorted(unique_values)
        self.selected_values = []
        self.checkboxes = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"Select Values from '{self.field_name}'")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel(f"<b>Select values to include:</b>")
        header.setStyleSheet("font-size: 13px; color: #2c3e50; padding: 5px;")
        layout.addWidget(header)

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Search:")
        search_label.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        search_layout.addWidget(search_label)

        self.search_box = QTextEdit()
        self.search_box.setMaximumHeight(30)
        self.search_box.setPlaceholderText("Type to filter values...")
        self.search_box.textChanged.connect(self.filter_checkboxes)
        self.search_box.setStyleSheet("""
            QTextEdit {
                border: 2px solid #3498db;
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }
        """)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        # Selection buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("✓ Select All")
        select_all_btn.clicked.connect(self.select_all)
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        button_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("✗ Select None")
        select_none_btn.clicked.connect(self.select_none)
        select_none_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        button_layout.addWidget(select_none_btn)

        invert_btn = QPushButton("⇄ Invert Selection")
        invert_btn.clicked.connect(self.invert_selection)
        invert_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        button_layout.addWidget(invert_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Count label
        self.count_label = QLabel()
        self.count_label.setStyleSheet("font-size: 11px; color: #7f8c8d; padding: 5px;")
        layout.addWidget(self.count_label)

        # Scrollable checkbox area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 2px solid #3498db;
                border-radius: 6px;
                background-color: white;
            }
        """)

        checkbox_widget = QWidget()
        self.checkbox_layout = QVBoxLayout(checkbox_widget)
        self.checkbox_layout.setSpacing(8)
        self.checkbox_layout.setContentsMargins(10, 10, 10, 10)

        # Create checkboxes
        for value in self.unique_values:
            cb = QCheckBox(str(value))
            cb.setChecked(True)  # Default: all selected
            cb.stateChanged.connect(self.update_count)
            cb.setStyleSheet("""
                QCheckBox {
                    font-size: 12px;
                    color: #2c3e50;
                    spacing: 10px;
                    padding: 8px;
                    background-color: transparent;
                    border-radius: 4px;
                }
                QCheckBox:hover {
                    background-color: #e3f2fd;
                }
                QCheckBox::indicator {
                    width: 22px;
                    height: 22px;
                    border: 3px solid #3498db;
                    border-radius: 5px;
                    background-color: white;
                }
                QCheckBox::indicator:checked {
                    background-color: #3498db;
                    border: 3px solid #3498db;
                }
                QCheckBox::indicator:hover {
                    border: 3px solid #2980b9;
                    background-color: #e3f2fd;
                }
                QCheckBox::indicator:checked:hover {
                    background-color: #2980b9;
                    border: 3px solid #2980b9;
                }
            """)
            self.checkbox_layout.addWidget(cb)
            self.checkboxes.append(cb)

        self.checkbox_layout.addStretch()
        scroll.setWidget(checkbox_widget)
        layout.addWidget(scroll)

        # Update count
        self.update_count()

        # Dialog buttons
        button_box_layout = QHBoxLayout()
        button_box_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_box_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Apply Selection")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        button_box_layout.addWidget(ok_btn)

        layout.addLayout(button_box_layout)

    def filter_checkboxes(self):
        """Filter checkboxes based on search text"""
        search_text = self.search_box.toPlainText().lower()
        for cb in self.checkboxes:
            if search_text in cb.text().lower():
                cb.setVisible(True)
            else:
                cb.setVisible(False)

    def select_all(self):
        """Select all visible checkboxes"""
        for cb in self.checkboxes:
            if cb.isVisible():
                cb.setChecked(True)

    def select_none(self):
        """Deselect all visible checkboxes"""
        for cb in self.checkboxes:
            if cb.isVisible():
                cb.setChecked(False)

    def invert_selection(self):
        """Invert selection of visible checkboxes"""
        for cb in self.checkboxes:
            if cb.isVisible():
                cb.setChecked(not cb.isChecked())

    def update_count(self):
        """Update the count label"""
        selected_count = sum(1 for cb in self.checkboxes if cb.isChecked())
        total_count = len(self.checkboxes)
        self.count_label.setText(f"Selected: <b>{selected_count}</b> of {total_count} values")

    def get_selected_values(self):
        """Return list of selected values"""
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]


class AnalysisWorker(QThread):
    """Background worker for analysis calculations"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, analysis_type, inundated_layer, comparison_layer, inund_field, pop_field=None, proportional=True):
        super().__init__()
        self.analysis_type = analysis_type
        self.inundated_layer = inundated_layer
        self.comparison_layer = comparison_layer
        self.inund_field = inund_field
        self.pop_field = pop_field
        self.proportional = proportional
        self.results = {}
        self._abort = False  # Flag for aborting analysis
        self._mutex = QMutex()  # Thread-safe access to abort flag

    def request_abort(self):
        """Thread-safe method to request worker abort"""
        with QMutexLocker(self._mutex):
            self._abort = True

    def is_aborted(self):
        """Thread-safe method to check if abort was requested"""
        with QMutexLocker(self._mutex):
            return self._abort

    def run(self):
        try:
            # Check abort before starting
            if self.is_aborted():
                return

            self.status.emit("Analyzing data...")
            self.progress.emit(20)

            if self.is_aborted():
                self.status.emit("Analysis aborted")
                return

            if self.analysis_type == "area_comparison":
                self.results = self.calculate_area_comparison()
            elif self.analysis_type == "feature_comparison":
                self.results = self.calculate_feature_comparison()
            elif self.analysis_type == "distribution":
                self.results = self.calculate_distribution()

            if not self.is_aborted():
                self.finished.emit(self.results)
            else:
                self.status.emit("Analysis aborted")

        except Exception as e:
            if not self.is_aborted():
                self.error.emit(str(e))

    def calculate_area_comparison(self):
        """Compare total area vs inundated area from single layer"""
        self.status.emit("Calculating area statistics...")
        self.progress.emit(40)

        total_area = 0.0
        inund_area = 0.0
        feature_data = []

        inund_idx = self.inundated_layer.fields().lookupField(self.inund_field)
        if inund_idx == -1:
            raise Exception(f"Field '{self.inund_field}' not found in layer")

        for feat in self.inundated_layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area = geom.area()
            inund_val = float(feat[inund_idx]) if feat[inund_idx] is not None else 0.0

            # Handle different field types: fraction (0-1) or percentage (0-100) or area (m²)
            # Assuming field is percentage or area in m²
            if self.inund_field in ['flood_pct', 'inund_pct']:
                # It's a percentage
                inund = area * (inund_val / 100.0)
            elif self.inund_field in ['flood_m2', 'inund_m2']:
                # It's already area
                inund = inund_val
            elif self.inund_field in ['flooded']:
                # It's a fraction (0-1)
                inund = area * inund_val
            else:
                # Guess: if value > 1, assume m², else fraction
                if inund_val > 1:
                    inund = inund_val
                else:
                    inund = area * inund_val

            total_area += area
            inund_area += inund

            feat_dict = {
                'total_area': area,
                'inund_area': inund,
                'inund_pct': (inund / area * 100) if area > 0 else 0
            }

            feature_data.append(feat_dict)

        # Handle population after collecting all features
        if self.pop_field:
            # Check if pop_field is a dict (manual entry) or string (field name)
            if isinstance(self.pop_field, dict):
                # Manual entry with optional filtering
                total_pop = self.pop_field['value']
                filter_field = self.pop_field.get('filter_field')
                filter_values = self.pop_field.get('filter_values', [])

                # Identify which features to distribute to
                if filter_field and filter_values:
                    # Filter features by field values
                    filter_idx = self.inundated_layer.fields().lookupField(filter_field)
                    if filter_idx != -1:
                        feat_idx = 0
                        eligible_indices = []
                        eligible_areas = []

                        for feat in self.inundated_layer.getFeatures():
                            if feat_idx >= len(feature_data):
                                break

                            filter_val = str(feat[filter_idx]) if feat[filter_idx] is not None else ""
                            if filter_val in filter_values:
                                eligible_indices.append(feat_idx)
                                eligible_areas.append(feature_data[feat_idx]['total_area'])

                            feat_idx += 1

                        # Distribute population proportionally by area to eligible features
                        total_eligible_area = sum(eligible_areas)
                        for idx, area in zip(eligible_indices, eligible_areas):
                            if total_eligible_area > 0:
                                pop_per_feature = total_pop * (area / total_eligible_area)
                            else:
                                pop_per_feature = total_pop / len(eligible_indices) if eligible_indices else 0.0

                            feature_data[idx]['population'] = pop_per_feature

                            # Calculate affected population
                            if self.proportional:
                                affected = pop_per_feature * (feature_data[idx]['inund_pct'] / 100.0)
                            else:
                                affected = pop_per_feature if feature_data[idx]['inund_pct'] > 0 else 0.0

                            feature_data[idx]['pop_affected'] = affected
                            feature_data[idx]['pop_safe'] = pop_per_feature - affected

                        # Set non-eligible features to 0 population
                        for idx in range(len(feature_data)):
                            if idx not in eligible_indices:
                                feature_data[idx]['population'] = 0.0
                                feature_data[idx]['pop_affected'] = 0.0
                                feature_data[idx]['pop_safe'] = 0.0
                else:
                    # Distribute to all features proportionally by area
                    total_area_all = sum(f['total_area'] for f in feature_data)
                    for feat_dict in feature_data:
                        if total_area_all > 0:
                            pop_per_feature = total_pop * (feat_dict['total_area'] / total_area_all)
                        else:
                            pop_per_feature = total_pop / len(feature_data) if feature_data else 0.0

                        feat_dict['population'] = pop_per_feature

                        # Calculate affected population
                        if self.proportional:
                            affected = pop_per_feature * (feat_dict['inund_pct'] / 100.0)
                        else:
                            affected = pop_per_feature if feat_dict['inund_pct'] > 0 else 0.0

                        feat_dict['pop_affected'] = affected
                        feat_dict['pop_safe'] = pop_per_feature - affected

            elif isinstance(self.pop_field, int):
                # Legacy: simple integer (distribute equally)
                total_features = len(feature_data)
                pop_per_feature = self.pop_field / total_features if total_features > 0 else 0.0

                for feat_dict in feature_data:
                    feat_dict['population'] = pop_per_feature

                    # Calculate affected population
                    if self.proportional:
                        affected = pop_per_feature * (feat_dict['inund_pct'] / 100.0)
                    else:
                        affected = pop_per_feature if feat_dict['inund_pct'] > 0 else 0.0

                    feat_dict['pop_affected'] = affected
                    feat_dict['pop_safe'] = pop_per_feature - affected
            else:
                # Field name: get population from layer attribute
                pop_idx = self.inundated_layer.fields().lookupField(self.pop_field)
                if pop_idx != -1:
                    feat_idx = 0
                    for feat in self.inundated_layer.getFeatures():
                        if feat_idx >= len(feature_data):
                            break

                        pop = float(feat[pop_idx]) if feat[pop_idx] is not None else 0.0
                        feature_data[feat_idx]['population'] = pop

                        # Calculate affected population
                        if self.proportional:
                            affected = pop * (feature_data[feat_idx]['inund_pct'] / 100.0)
                        else:
                            affected = pop if feature_data[feat_idx]['inund_pct'] > 0 else 0.0

                        feature_data[feat_idx]['pop_affected'] = affected
                        feature_data[feat_idx]['pop_safe'] = pop - affected
                        feat_idx += 1

        self.progress.emit(80)

        # Calculate population totals
        total_pop = 0.0
        affected_pop = 0.0
        safe_pop = 0.0

        if self.pop_field:
            for feat_data in feature_data:
                if 'population' in feat_data:
                    total_pop += feat_data['population']
                    affected_pop += feat_data.get('pop_affected', 0.0)
                    safe_pop += feat_data.get('pop_safe', 0.0)

        self.progress.emit(100)

        result = {
            'total_area': total_area,
            'inund_area': inund_area,
            'dry_area': total_area - inund_area,
            'inund_pct': (inund_area / total_area * 100) if total_area > 0 else 0,
            'feature_count': len(feature_data),
            'feature_data': feature_data
        }

        # Add population results if enabled
        if self.pop_field and total_pop > 0:
            result['has_population'] = True
            result['total_population'] = total_pop
            result['affected_population'] = affected_pop
            result['safe_population'] = safe_pop
            result['affected_pop_pct'] = (affected_pop / total_pop * 100) if total_pop > 0 else 0
        else:
            result['has_population'] = False

        return result

    def calculate_feature_comparison(self):
        """Compare inundated layer features vs comparison layer features"""
        self.status.emit("Comparing feature sets...")
        self.progress.emit(40)

        # Get counts
        inundated_count = self.inundated_layer.featureCount()
        comparison_count = self.comparison_layer.featureCount() if self.comparison_layer else 0

        # Calculate total areas
        inundated_total_area = sum(f.geometry().area() for f in self.inundated_layer.getFeatures() if f.geometry() and not f.geometry().isEmpty())
        comparison_total_area = 0.0
        if self.comparison_layer:
            comparison_total_area = sum(f.geometry().area() for f in self.comparison_layer.getFeatures() if f.geometry() and not f.geometry().isEmpty())

        self.progress.emit(70)

        # Get inundation from inundated layer
        inund_idx = self.inundated_layer.fields().lookupField(self.inund_field)
        total_inund_area = 0.0

        if inund_idx != -1:
            for feat in self.inundated_layer.getFeatures():
                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    continue
                area = geom.area()
                inund_val = float(feat[inund_idx]) if feat[inund_idx] is not None else 0.0

                if self.inund_field in ['flood_pct', 'inund_pct']:
                    inund = area * (inund_val / 100.0)
                elif self.inund_field in ['flood_m2', 'inund_m2']:
                    inund = inund_val
                elif self.inund_field in ['flooded']:
                    inund = area * inund_val
                else:
                    if inund_val > 1:
                        inund = inund_val
                    else:
                        inund = area * inund_val

                total_inund_area += inund

        self.progress.emit(100)

        return {
            'inundated_count': inundated_count,
            'comparison_count': comparison_count,
            'total_count': inundated_count + comparison_count,
            'inundated_total_area': inundated_total_area,
            'comparison_total_area': comparison_total_area,
            'total_inund_area': total_inund_area,
            'inund_pct_of_all': (inundated_count / (inundated_count + comparison_count) * 100) if (inundated_count + comparison_count) > 0 else 0
        }

    def calculate_distribution(self):
        """Calculate inundation distribution across features"""
        self.status.emit("Calculating distribution...")
        self.progress.emit(40)

        inund_idx = self.inundated_layer.fields().lookupField(self.inund_field)
        if inund_idx == -1:
            raise Exception(f"Field '{self.inund_field}' not found")

        percentages = []

        for feat in self.inundated_layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            area = geom.area()
            inund_val = float(feat[inund_idx]) if feat[inund_idx] is not None else 0.0

            # Calculate percentage
            if self.inund_field in ['flood_pct', 'inund_pct']:
                pct = inund_val
            elif self.inund_field in ['flood_m2', 'inund_m2']:
                pct = (inund_val / area * 100) if area > 0 else 0
            elif self.inund_field in ['flooded']:
                pct = inund_val * 100
            else:
                if inund_val > 1:
                    pct = (inund_val / area * 100) if area > 0 else 0
                else:
                    pct = inund_val * 100

            percentages.append(pct)

        self.progress.emit(100)

        percentages.sort()
        n = len(percentages)

        return {
            'percentages': percentages,
            'count': n,
            'mean': sum(percentages) / n if n > 0 else 0,
            'median': percentages[n // 2] if n > 0 else 0,
            'min': percentages[0] if n > 0 else 0,
            'max': percentages[-1] if n > 0 else 0
        }


class ChartWidget(QWidget):
    """Custom widget for matplotlib charts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(10, 7), facecolor='white')
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)


class SlrVmVisualizationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OSLRAT - Data Visualization Dashboard")
        self.resize(1400, 850)
        # Note: Don't set WindowModality here - let show() handle it (non-modal by default)

        self.current_results = None
        self.worker = None
        self._abort_analysis = False

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Professional header
        header = self.create_header()
        main_layout.addWidget(header)

        # Content area
        content = QWidget()
        content.setStyleSheet("background-color: #f5f6fa;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(20)

        # Splitter for panels
        splitter = QSplitter(Qt.Horizontal)

        left_panel = self.create_config_panel()
        right_panel = self.create_visualization_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        content_layout.addWidget(splitter)

        # Footer
        footer = self.create_footer()
        content_layout.addWidget(footer)

        main_layout.addWidget(content)

    def create_header(self):
        """Create professional gradient header"""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db,
                    stop:0.5 #8e5ba8,
                    stop:1 #e91e63
                );
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(30, 20, 30, 20)

        title = QLabel("<h1 style='color: white; margin: 0; font-size: 28px; font-weight: bold;'>📊 Interactive Data Visualization Dashboard</h1>")
        title.setStyleSheet("background: transparent;")

        subtitle = QLabel(
            "<p style='color: rgba(255, 255, 255, 0.95); margin: 5px 0 0 0; font-size: 14px;'>"
            "Analyze flood exposure data with professional charts, statistics, and export capabilities"
            "</p>"
        )
        subtitle.setStyleSheet("background: transparent;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        return header

    def create_config_panel(self):
        """Create left configuration panel with scroll area"""
        # Main panel container
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 12px;
            }
        """)
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #ecf0f1;
                width: 10px;
                margin: 0px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #2980b9;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget inside scroll area
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        # Title
        title = QLabel("<b>Configuration</b>")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2c3e50;")
        layout.addWidget(title)

        # Step 1: Layer with inundation data
        step1_group = QGroupBox("Step 1: Select Layer with Inundation Data")
        step1_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                color: #3498db;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        step1_layout = QVBoxLayout()

        step1_help = QLabel("Choose the layer that contains flood analysis results\n(with fields like: flooded, flood_pct, flood_m2)")
        step1_help.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal;")
        step1_help.setWordWrap(True)
        step1_layout.addWidget(step1_help)

        self.inundated_combo = QComboBox()
        self.inundated_combo.setMinimumHeight(40)
        self.inundated_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #3498db;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
                font-weight: bold;
                color: #2c3e50;
            }
            QComboBox:hover {
                border: 2px solid #2980b9;
                background-color: #ecf9ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #3498db;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #3498db;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
                font-size: 13px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: #2c3e50;
            }
        """)
        self.populate_vector_layers(self.inundated_combo)
        self.inundated_combo.currentIndexChanged.connect(self.on_inundated_layer_changed)
        step1_layout.addWidget(self.inundated_combo)

        field_label = QLabel("Inundation Field:")
        field_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 8px;")
        step1_layout.addWidget(field_label)

        self.inund_field_combo = QComboBox()
        self.inund_field_combo.setMinimumHeight(40)
        self.inund_field_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #3498db;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
                font-weight: bold;
                color: #2c3e50;
            }
            QComboBox:hover {
                border: 2px solid #2980b9;
                background-color: #ecf9ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #3498db;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #3498db;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #3498db;
                selection-color: white;
                font-size: 13px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #e3f2fd;
                color: #2c3e50;
            }
        """)
        step1_layout.addWidget(self.inund_field_combo)

        step1_group.setLayout(step1_layout)
        layout.addWidget(step1_group)

        # Step 2: Analysis type
        step2_group = QGroupBox("Step 2: Choose Analysis Type")
        step2_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9b59b6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                color: #9b59b6;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        step2_layout = QVBoxLayout()

        self.analysis_group = QButtonGroup()

        self.radio_area = QRadioButton("Compare Total Area vs Inundated Area\n   → Shows how much area is flooded vs dry")
        self.radio_area.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                spacing: 10px;
                padding: 8px;
            }
            QRadioButton::indicator {
                width: 22px;
                height: 22px;
                border: 3px solid #9b59b6;
                border-radius: 5px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #9b59b6;
                border: 3px solid #9b59b6;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #8e44ad;
                background-color: #f4ecf7;
            }
        """)
        self.radio_area.setChecked(True)
        self.analysis_group.addButton(self.radio_area, 0)
        step2_layout.addWidget(self.radio_area)

        self.radio_feature = QRadioButton("Compare Flooded vs Non-Flooded Features\n   → Counts features with flooding vs without flooding")
        self.radio_feature.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                spacing: 10px;
                padding: 8px;
            }
            QRadioButton::indicator {
                width: 22px;
                height: 22px;
                border: 3px solid #9b59b6;
                border-radius: 5px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #9b59b6;
                border: 3px solid #9b59b6;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #8e44ad;
                background-color: #f4ecf7;
            }
        """)
        self.analysis_group.addButton(self.radio_feature, 1)
        step2_layout.addWidget(self.radio_feature)

        self.radio_distribution = QRadioButton("Show Flooding Distribution Across Features\n   → Histogram showing how flooding varies")
        self.radio_distribution.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                spacing: 10px;
                padding: 8px;
            }
            QRadioButton::indicator {
                width: 22px;
                height: 22px;
                border: 3px solid #9b59b6;
                border-radius: 5px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #9b59b6;
                border: 3px solid #9b59b6;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #8e44ad;
                background-color: #f4ecf7;
            }
        """)
        self.analysis_group.addButton(self.radio_distribution, 2)
        step2_layout.addWidget(self.radio_distribution)

        # Connect to update UI
        self.analysis_group.buttonClicked.connect(self.on_analysis_type_changed)

        step2_group.setLayout(step2_layout)
        layout.addWidget(step2_group)

        # Step 3: Optional comparison layer
        self.step3_group = QGroupBox("Step 3: Select Comparison Layer (Optional)")
        self.step3_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e74c3c;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                color: #e74c3c;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        step3_layout = QVBoxLayout()

        step3_help = QLabel("Select a layer WITHOUT inundation data for comparison\n(e.g., all parcels vs only flooded parcels)")
        step3_help.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal;")
        step3_help.setWordWrap(True)
        step3_layout.addWidget(step3_help)

        self.comparison_combo = QComboBox()
        self.comparison_combo.addItem("(None - not needed)", None)
        self.comparison_combo.setMinimumHeight(40)
        self.comparison_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #e74c3c;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
                font-weight: bold;
                color: #2c3e50;
            }
            QComboBox:hover {
                border: 2px solid #c0392b;
                background-color: #ffebee;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #e74c3c;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #e74c3c;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #e74c3c;
                selection-color: white;
                font-size: 13px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px;
                border-radius: 4px;
                min-height: 30px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #ffebee;
                color: #2c3e50;
            }
        """)
        self.populate_vector_layers(self.comparison_combo, include_none=False)
        step3_layout.addWidget(self.comparison_combo)

        self.step3_group.setLayout(step3_layout)
        self.step3_group.setVisible(False)  # Hidden by default
        layout.addWidget(self.step3_group)

        # Step 4: Population Analysis (Optional)
        step4_group = QGroupBox("Step 4: Population Analysis (Optional)")
        step4_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #f39c12;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                color: #f39c12;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        step4_layout = QVBoxLayout()

        step4_help = QLabel("Add population data to calculate affected vs non-affected people")
        step4_help.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal;")
        step4_help.setWordWrap(True)
        step4_layout.addWidget(step4_help)

        # Enable population analysis checkbox
        self.enable_population_check = QCheckBox("Enable Population Analysis")
        self.enable_population_check.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #2c3e50;
                font-size: 13px;
                spacing: 10px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 24px;
                height: 24px;
                border: 3px solid #f39c12;
                border-radius: 6px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #f39c12;
                border: 3px solid #f39c12;
                image: url(none);
            }
            QCheckBox::indicator:hover {
                border: 3px solid #e67e22;
                background-color: #fff8e1;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #e67e22;
                border: 3px solid #e67e22;
            }
        """)
        self.enable_population_check.stateChanged.connect(self.on_population_check_changed)
        step4_layout.addWidget(self.enable_population_check)

        # Population source selection
        pop_source_label = QLabel("Population Data Source:")
        pop_source_label.setStyleSheet("font-weight: bold; color: #2c3e50; margin-top: 8px;")
        self.pop_source_label = pop_source_label
        step4_layout.addWidget(pop_source_label)

        self.pop_source_group = QButtonGroup()

        self.radio_manual_pop = QRadioButton("Enter Total Population Number")
        self.radio_manual_pop.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                spacing: 10px;
                padding: 6px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 3px solid #f39c12;
                border-radius: 4px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #f39c12;
                border: 3px solid #f39c12;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #e67e22;
                background-color: #fff8e1;
            }
        """)
        self.radio_manual_pop.setChecked(True)
        self.radio_manual_pop.setEnabled(False)
        self.pop_source_group.addButton(self.radio_manual_pop, 0)
        self.radio_manual_pop.toggled.connect(self.on_pop_source_changed)
        step4_layout.addWidget(self.radio_manual_pop)

        # Manual entry field
        manual_entry_container = QWidget()
        manual_entry_layout = QHBoxLayout(manual_entry_container)
        manual_entry_layout.setContentsMargins(20, 0, 0, 0)
        manual_entry_layout.setSpacing(10)

        manual_label = QLabel("Total Population:")
        manual_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal;")
        manual_entry_layout.addWidget(manual_label)

        self.manual_pop_spinbox = QSpinBox()
        self.manual_pop_spinbox.setMinimum(0)
        self.manual_pop_spinbox.setMaximum(999999999)
        self.manual_pop_spinbox.setValue(10000)
        self.manual_pop_spinbox.setMinimumHeight(35)
        self.manual_pop_spinbox.setEnabled(False)
        self.manual_pop_spinbox.setStyleSheet("""
            QSpinBox {
                border: 2px solid #f39c12;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                font-size: 13px;
                font-weight: bold;
                color: #2c3e50;
            }
            QSpinBox:hover {
                border: 2px solid #e67e22;
                background-color: #fff8e1;
            }
            QSpinBox:disabled {
                background-color: #ecf0f1;
                color: #95a5a6;
                border: 2px solid #bdc3c7;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 20px;
                border-left: 1px solid #f39c12;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #fff8e1;
            }
        """)
        manual_entry_layout.addWidget(self.manual_pop_spinbox)
        manual_entry_layout.addStretch()

        step4_layout.addWidget(manual_entry_container)
        self.manual_entry_container = manual_entry_container

        # Manual entry distribution options
        manual_distrib_container = QWidget()
        manual_distrib_layout = QVBoxLayout(manual_distrib_container)
        manual_distrib_layout.setContentsMargins(40, 5, 0, 0)
        manual_distrib_layout.setSpacing(5)

        manual_distrib_label = QLabel("Distribute to:")
        manual_distrib_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: bold;")
        manual_distrib_layout.addWidget(manual_distrib_label)

        self.manual_distrib_group = QButtonGroup()

        self.radio_all_features = QRadioButton("All Features (split proportionally by area)")
        self.radio_all_features.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                font-size: 11px;
                spacing: 8px;
                padding: 5px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 3px solid #f39c12;
                border-radius: 4px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #f39c12;
                border: 3px solid #f39c12;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #e67e22;
                background-color: #fff8e1;
            }
        """)
        self.radio_all_features.setChecked(True)
        self.radio_all_features.setEnabled(False)
        self.radio_all_features.toggled.connect(self.on_manual_distrib_changed)
        self.manual_distrib_group.addButton(self.radio_all_features, 0)
        manual_distrib_layout.addWidget(self.radio_all_features)

        self.radio_selected_features = QRadioButton("Selected Features Only (filter by field)")
        self.radio_selected_features.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                font-size: 11px;
                spacing: 8px;
                padding: 5px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 3px solid #f39c12;
                border-radius: 4px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #f39c12;
                border: 3px solid #f39c12;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #e67e22;
                background-color: #fff8e1;
            }
        """)
        self.radio_selected_features.setEnabled(False)
        self.radio_selected_features.toggled.connect(self.on_manual_distrib_changed)
        self.manual_distrib_group.addButton(self.radio_selected_features, 1)
        manual_distrib_layout.addWidget(self.radio_selected_features)

        # Feature filter options (shown when "Selected Features Only" is chosen)
        filter_container = QWidget()
        filter_layout = QGridLayout(filter_container)
        filter_layout.setContentsMargins(20, 5, 0, 0)
        filter_layout.setSpacing(8)

        filter_label = QLabel("Filter by field:")
        filter_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        filter_layout.addWidget(filter_label, 0, 0)

        self.filter_field_combo = QComboBox()
        self.filter_field_combo.setMinimumHeight(30)
        self.filter_field_combo.setEnabled(False)
        self.filter_field_combo.currentIndexChanged.connect(self.on_filter_field_changed)
        self.filter_field_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #f39c12;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
                font-size: 11px;
                color: #2c3e50;
            }
            QComboBox:disabled {
                background-color: #ecf0f1;
                color: #95a5a6;
                border: 2px solid #bdc3c7;
            }
        """)
        filter_layout.addWidget(self.filter_field_combo, 0, 1)

        values_label = QLabel("Enter values (comma-separated):")
        values_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        filter_layout.addWidget(values_label, 1, 0, 1, 2)

        # Text input for comma-separated values
        self.filter_values_text = QTextEdit()
        self.filter_values_text.setMaximumHeight(80)
        self.filter_values_text.setEnabled(False)
        self.filter_values_text.setPlaceholderText("e.g., value1, value2, value3")
        self.filter_values_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #f39c12;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
                font-size: 11px;
                color: #2c3e50;
                font-family: Consolas, Monaco, monospace;
            }
            QTextEdit:disabled {
                background-color: #ecf0f1;
                color: #95a5a6;
                border: 2px solid #bdc3c7;
            }
            QTextEdit:focus {
                border: 2px solid #e67e22;
            }
        """)
        filter_layout.addWidget(self.filter_values_text, 2, 0, 1, 2)

        # Helper buttons
        helper_layout = QHBoxLayout()

        self.show_unique_btn = QPushButton("📋 Browse & Select Values")
        self.show_unique_btn.setEnabled(False)
        self.show_unique_btn.clicked.connect(self.show_value_selector_dialog)
        self.show_unique_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        helper_layout.addWidget(self.show_unique_btn)

        self.clear_values_btn = QPushButton("🗑 Clear")
        self.clear_values_btn.setEnabled(False)
        self.clear_values_btn.clicked.connect(lambda: self.filter_values_text.clear())
        self.clear_values_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        helper_layout.addWidget(self.clear_values_btn)
        helper_layout.addStretch()

        filter_layout.addLayout(helper_layout, 3, 0, 1, 2)

        manual_distrib_layout.addWidget(filter_container)
        self.filter_container = filter_container
        self.filter_container.setVisible(False)

        step4_layout.addWidget(manual_distrib_container)
        self.manual_distrib_container = manual_distrib_container

        # Field selection option
        self.radio_field_pop = QRadioButton("Use Population Field from Layer Data")
        self.radio_field_pop.setStyleSheet("""
            QRadioButton {
                font-weight: normal;
                color: #2c3e50;
                spacing: 10px;
                padding: 6px;
                margin-top: 5px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 3px solid #f39c12;
                border-radius: 4px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background-color: #f39c12;
                border: 3px solid #f39c12;
            }
            QRadioButton::indicator:hover {
                border: 3px solid #e67e22;
                background-color: #fff8e1;
            }
        """)
        self.radio_field_pop.setEnabled(False)
        self.pop_source_group.addButton(self.radio_field_pop, 1)
        self.radio_field_pop.toggled.connect(self.on_pop_source_changed)
        step4_layout.addWidget(self.radio_field_pop)

        # Population field selector
        field_container = QWidget()
        field_layout = QHBoxLayout(field_container)
        field_layout.setContentsMargins(20, 0, 0, 0)
        field_layout.setSpacing(10)

        pop_field_label = QLabel("Population Field:")
        pop_field_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal;")
        field_layout.addWidget(pop_field_label)

        self.pop_field_combo = QComboBox()
        self.pop_field_combo.setMinimumHeight(35)
        self.pop_field_combo.setEnabled(False)
        self.pop_field_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #f39c12;
                border-radius: 6px;
                padding: 6px;
                background-color: white;
                font-size: 12px;
                font-weight: bold;
                color: #2c3e50;
            }
            QComboBox:hover {
                border: 2px solid #e67e22;
                background-color: #fff8e1;
            }
            QComboBox:disabled {
                background-color: #ecf0f1;
                color: #95a5a6;
                border: 2px solid #bdc3c7;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #f39c12;
                margin-right: 6px;
            }
            QComboBox::down-arrow:disabled {
                border-top: 6px solid #bdc3c7;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #f39c12;
                border-radius: 6px;
                background-color: white;
                selection-background-color: #f39c12;
                selection-color: white;
                font-size: 12px;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px;
                border-radius: 3px;
                min-height: 25px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #fff8e1;
                color: #2c3e50;
            }
        """)
        field_layout.addWidget(self.pop_field_combo, stretch=1)

        step4_layout.addWidget(field_container)
        self.field_container = field_container

        field_help = QLabel("   → Population values taken from selected field per feature")
        field_help.setStyleSheet("color: #7f8c8d; font-size: 10px; font-weight: normal; margin-left: 20px;")
        step4_layout.addWidget(field_help)
        self.field_help = field_help

        # Distribution method (simplified - always proportional)
        distrib_info = QLabel("Population Distribution:\n   → Proportional by flooded area percentage (affected pop = total pop × flood %)")
        distrib_info.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: normal; margin-top: 8px; padding: 8px; background-color: #fff8e1; border-radius: 4px; border: 1px solid #f39c12;")
        distrib_info.setWordWrap(True)
        step4_layout.addWidget(distrib_info)

        step4_group.setLayout(step4_layout)
        layout.addWidget(step4_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f8c8d; font-style: italic; font-weight: normal;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Generate button
        self.generate_btn = QPushButton("🚀 Generate Visualization")
        self.generate_btn.setMinimumHeight(50)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_analysis)
        layout.addWidget(self.generate_btn)

        layout.addStretch()

        # Set content widget to scroll area
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        return panel

    def create_visualization_panel(self):
        """Create right visualization panel"""
        panel = QWidget()
        panel.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                background: #ecf0f1;
                color: #2c3e50;
                padding: 10px 20px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)

        # Chart tab
        self.chart_widget = ChartWidget() if MATPLOTLIB_AVAILABLE else QLabel("Matplotlib not available.\nPlease install: pip install matplotlib")
        self.tabs.addTab(self.chart_widget, "📈 Chart")

        # Statistics tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        self.stats_table = QTableWidget()
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
            }
            QHeaderView::section {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
            }
        """)
        stats_layout.addWidget(self.stats_table)
        self.tabs.addTab(stats_widget, "📊 Statistics")

        # Raw data tab
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        self.data_text = QTextEdit()
        self.data_text.setReadOnly(True)
        self.data_text.setStyleSheet("border: 1px solid #e0e0e0; border-radius: 5px; padding: 10px;")
        data_layout.addWidget(self.data_text)
        self.tabs.addTab(data_widget, "📋 Raw Data")

        layout.addWidget(self.tabs)

        # Export buttons
        export_layout = QHBoxLayout()

        self.export_png_btn = QPushButton("💾 Export Chart (PNG)")
        self.export_png_btn.clicked.connect(lambda: self.export_chart('png'))
        self.export_png_btn.setEnabled(False)
        self.export_png_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)

        self.export_pdf_btn = QPushButton("📄 Export Chart (PDF)")
        self.export_pdf_btn.clicked.connect(lambda: self.export_chart('pdf'))
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)

        self.export_csv_btn = QPushButton("📊 Export Data (CSV)")
        self.export_csv_btn.clicked.connect(self.export_csv)
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #229954; }
            QPushButton:disabled { background-color: #bdc3c7; }
        """)

        export_layout.addWidget(self.export_png_btn)
        export_layout.addWidget(self.export_pdf_btn)
        export_layout.addWidget(self.export_csv_btn)

        if PANDAS_AVAILABLE:
            self.export_excel_btn = QPushButton("📑 Export Data (Excel)")
            self.export_excel_btn.clicked.connect(self.export_excel)
            self.export_excel_btn.setEnabled(False)
            self.export_excel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 15px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #229954; }
                QPushButton:disabled { background-color: #bdc3c7; }
            """)
            export_layout.addWidget(self.export_excel_btn)

        export_layout.addStretch()

        layout.addLayout(export_layout)

        return panel

    def create_footer(self):
        """Create footer with back and close buttons"""
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 10, 0, 0)

        footer_layout.addStretch()

        # Back to main GUI button
        back_btn = QPushButton("← Back to Main GUI")
        back_btn.setMinimumWidth(150)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        back_btn.clicked.connect(self.back_to_main_gui)
        footer_layout.addWidget(back_btn)

        close_btn = QPushButton("Close Dashboard")
        close_btn.setMinimumWidth(150)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        return footer

    def back_to_main_gui(self):
        """Close this dialog and show parent GUI"""
        if self.parent_gui:
            self.parent_gui.show()
            self.parent_gui.raise_()
            self.parent_gui.activateWindow()
        self.close()

    def populate_vector_layers(self, combo, include_none=True):
        """Populate combo with vector polygon layers"""
        if include_none:
            combo.addItem("(Select a layer)", None)

        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == 2:
                combo.addItem(layer.name(), layer)

    def on_inundated_layer_changed(self):
        """Update field combos when layer selection changes"""
        self.inund_field_combo.clear()
        self.pop_field_combo.clear()
        self.filter_field_combo.clear()

        layer = self.inundated_combo.currentData()
        if not layer:
            return

        # Look for common inundation field names
        priority_fields = ['flood_pct', 'inund_pct', 'flooded', 'flood_m2', 'inund_m2']

        for field_name in priority_fields:
            idx = layer.fields().lookupField(field_name)
            if idx != -1:
                self.inund_field_combo.addItem(field_name, field_name)

        # Add all numeric fields to inundation combo
        for field in layer.fields():
            if field.isNumeric() and field.name() not in priority_fields:
                self.inund_field_combo.addItem(field.name(), field.name())

        # Populate population field combo
        self.pop_field_combo.addItem("(None - will use default)", None)

        # Look for common population field names
        pop_priority = ['population', 'pop', 'people', 'residents', 'inhabitants']

        for field_name in pop_priority:
            for field in layer.fields():
                if field.name().lower() == field_name and field.isNumeric():
                    self.pop_field_combo.addItem(field.name(), field.name())
                    break

        # Add remaining numeric fields
        for field in layer.fields():
            if field.isNumeric() and field.name() not in priority_fields:
                if field.name() not in [self.pop_field_combo.itemText(i) for i in range(self.pop_field_combo.count())]:
                    self.pop_field_combo.addItem(field.name(), field.name())

        # Populate filter field combo (all fields, not just numeric)
        self.filter_field_combo.addItem("(Select a field)", None)
        for field in layer.fields():
            self.filter_field_combo.addItem(field.name(), field.name())

    def on_population_check_changed(self, state):
        """Enable/disable population fields based on checkbox"""
        enabled = (state == 2)  # Qt.Checked
        self.radio_manual_pop.setEnabled(enabled)
        self.radio_field_pop.setEnabled(enabled)

        # Enable appropriate controls based on current selection
        if enabled:
            self.on_pop_source_changed()
        else:
            self.manual_pop_spinbox.setEnabled(False)
            self.pop_field_combo.setEnabled(False)

    def on_pop_source_changed(self):
        """Update visibility based on population source selection"""
        if self.radio_manual_pop.isChecked():
            # Enable manual entry controls, disable field
            self.manual_pop_spinbox.setEnabled(True)
            self.manual_distrib_container.setVisible(True)
            self.radio_all_features.setEnabled(True)
            self.radio_selected_features.setEnabled(True)
            self.pop_field_combo.setEnabled(False)
            self.field_container.setVisible(True)
        else:
            # Disable manual entry controls, enable field
            self.manual_pop_spinbox.setEnabled(False)
            self.manual_distrib_container.setVisible(False)
            self.pop_field_combo.setEnabled(True)
            self.field_container.setVisible(True)

    def on_analysis_type_changed(self):
        """Show/hide comparison layer based on analysis type"""
        if self.radio_feature.isChecked():
            self.step3_group.setVisible(True)
        else:
            self.step3_group.setVisible(False)

    def on_manual_distrib_changed(self):
        """Show/hide filter options based on distribution selection"""
        if self.radio_selected_features.isChecked():
            self.filter_container.setVisible(True)
            self.filter_field_combo.setEnabled(True)
            self.filter_values_text.setEnabled(True)
            self.show_unique_btn.setEnabled(True)
            self.clear_values_btn.setEnabled(True)
        else:
            self.filter_container.setVisible(False)

    def on_filter_field_changed(self):
        """Clear text when field changes"""
        self.filter_values_text.clear()

    def show_value_selector_dialog(self):
        """Show dialog for selecting field values with checkboxes"""
        field_name = self.filter_field_combo.currentData()
        if not field_name:
            QMessageBox.warning(self, "No Field Selected", "Please select a field first.")
            return

        layer = self.inundated_combo.currentData()
        if not layer:
            return

        # Get unique values from field
        field_idx = layer.fields().lookupField(field_name)
        if field_idx == -1:
            return

        unique_values = set()
        for feat in layer.getFeatures():
            val = feat[field_idx]
            if val is not None:
                unique_values.add(str(val))

        if not unique_values:
            QMessageBox.information(self, "No Values", "No values found in this field.")
            return

        # Show dialog
        dialog = ValueSelectorDialog(field_name, unique_values, self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_values()
            if selected:
                # Write comma-separated values to text field
                self.filter_values_text.setPlainText(", ".join(selected))

    def generate_analysis(self):
        """Start analysis"""
        inundated_layer = self.inundated_combo.currentData()
        inund_field = self.inund_field_combo.currentData()

        if not inundated_layer or not inund_field:
            QMessageBox.warning(self, "Missing Data",
                              "Please select both a layer and an inundation field.")
            return

        # Determine analysis type
        if self.radio_area.isChecked():
            analysis_type = "area_comparison"
            comparison_layer = None
        elif self.radio_feature.isChecked():
            analysis_type = "feature_comparison"
            comparison_layer = self.comparison_combo.currentData()
            if not comparison_layer:
                QMessageBox.warning(self, "Missing Comparison Layer",
                                  "Please select a comparison layer for this analysis type.")
                return
        else:
            analysis_type = "distribution"
            comparison_layer = None

        # Get population settings
        pop_field = None
        proportional = True
        filter_field = None
        filter_values = []

        if self.enable_population_check.isChecked():
            if self.radio_manual_pop.isChecked():
                # Use manual entry (pass as dict with value and filter info)
                pop_value = self.manual_pop_spinbox.value()

                # Check if filtering to selected features
                if self.radio_selected_features.isChecked():
                    filter_field = self.filter_field_combo.currentData()
                    if filter_field:
                        # Parse comma-separated values from text input
                        values_text = self.filter_values_text.toPlainText().strip()
                        if values_text:
                            # Split by comma and strip whitespace from each value
                            filter_values = [v.strip() for v in values_text.split(',') if v.strip()]
                        else:
                            filter_values = []

                        if not filter_values:
                            QMessageBox.warning(self, "No Values Entered",
                                              "Please enter at least one value (comma-separated) to filter features.")
                            return

                # Pass as dict to distinguish from field name
                pop_field = {
                    'type': 'manual',
                    'value': pop_value,
                    'filter_field': filter_field,
                    'filter_values': filter_values
                }
            else:
                # Use field from layer (pass as string)
                pop_field = self.pop_field_combo.currentData()
            proportional = True  # Always use proportional distribution

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setVisible(True)
        self.status_label.setText("Starting analysis...")
        self.generate_btn.setEnabled(False)

        # Stop any existing worker
        self.stop_worker()

        # Create and start new worker
        self.worker = AnalysisWorker(analysis_type, inundated_layer, comparison_layer, inund_field, pop_field, proportional)

        # Connect signals with Qt.QueuedConnection for thread safety
        self.worker.progress.connect(self.progress_bar.setValue, Qt.QueuedConnection)
        self.worker.status.connect(self.status_label.setText, Qt.QueuedConnection)
        self.worker.finished.connect(self.on_analysis_finished, Qt.QueuedConnection)
        self.worker.error.connect(self.on_analysis_error, Qt.QueuedConnection)

        # Auto-cleanup when finished
        self.worker.finished.connect(self.cleanup_worker, Qt.QueuedConnection)

        self.worker.start()

    def on_analysis_finished(self, results):
        """Handle completed analysis"""
        self.current_results = results
        self.progress_bar.setVisible(False)
        self.status_label.setText("✓ Analysis complete!")
        self.generate_btn.setEnabled(True)

        # Update visualizations
        self.update_chart(results)
        self.update_statistics_table(results)
        self.update_raw_data(results)

        # Enable export
        self.export_png_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)
        self.export_csv_btn.setEnabled(True)
        if PANDAS_AVAILABLE and hasattr(self, 'export_excel_btn'):
            self.export_excel_btn.setEnabled(True)

    def on_analysis_error(self, error_msg):
        """Handle error"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("✗ Error occurred")
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Analysis Error", f"An error occurred:\n\n{error_msg}")

    def update_chart(self, results):
        """Generate chart"""
        if not MATPLOTLIB_AVAILABLE:
            return

        self.chart_widget.figure.clear()

        if self.radio_area.isChecked():
            self.create_area_chart(results)
        elif self.radio_feature.isChecked():
            self.create_feature_chart(results)
        else:
            self.create_distribution_chart(results)

        self.chart_widget.canvas.draw()

    def create_area_chart(self, results):
        """Area comparison bar chart with optional population"""
        fig = self.chart_widget.figure

        if results.get('has_population'):
            # Create two subplots: area and population with MORE SPACING
            gs = fig.add_gridspec(1, 2, wspace=0.5, left=0.10, right=0.96, top=0.88, bottom=0.22)

            # Area chart (left)
            ax1 = fig.add_subplot(gs[0, 0])
            categories = ['Total\nArea', 'Inundated\nArea', 'Dry\nArea']
            values = [results['total_area'], results['inund_area'], results['dry_area']]
            colors = ['#3498db', '#e74c3c', '#2ecc71']

            bars = ax1.bar(categories, values, color=colors, alpha=0.85, edgecolor='black', linewidth=2)

            # Add value labels on bars with offset
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height * 1.02,  # 2% above bar
                       f'{height:,.0f} m²',
                       ha='center', va='bottom', fontweight='bold', fontsize=12)

            ax1.set_ylabel('Area (m²)', fontweight='bold', fontsize=12)
            ax1.set_title('Area Analysis', fontweight='bold', fontsize=12, pad=15)
            ax1.tick_params(axis='both', labelsize=12)
            ax1.grid(axis='y', alpha=0.3, linestyle='--')
            ax1.set_ylim(0, max(values) * 1.15)  # Add 15% headroom for labels

            # Population chart (right)
            ax2 = fig.add_subplot(gs[0, 1])
            pop_cats = ['Total\nPopulation', 'Affected\nPopulation', 'Safe\nPopulation']
            pop_vals = [results['total_population'], results['affected_population'], results['safe_population']]
            pop_colors = ['#3498db', '#e74c3c', '#2ecc71']

            bars2 = ax2.bar(pop_cats, pop_vals, color=pop_colors, alpha=0.85, edgecolor='black', linewidth=2)

            # Add value labels on bars with offset
            for bar in bars2:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height * 1.02,  # 2% above bar
                       f'{height:,.0f}',
                       ha='center', va='bottom', fontweight='bold', fontsize=12)

            ax2.set_ylabel('Population Count', fontweight='bold', fontsize=12)
            ax2.set_title('Population Impact', fontweight='bold', fontsize=12, pad=15)
            ax2.tick_params(axis='both', labelsize=12)
            ax2.grid(axis='y', alpha=0.3, linestyle='--')
            ax2.set_ylim(0, max(pop_vals) * 1.15)  # Add 15% headroom for labels

            # Main title
            fig.suptitle(f'Area & Population Analysis\n({results["feature_count"]} features analyzed)',
                        fontweight='bold', fontsize=12, y=0.96)

            # Legend boxes below charts
            fig.text(0.30, 0.08, f'Flood: {results["inund_pct"]:.1f}%',
                    ha='center', fontsize=12, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.6', facecolor='#ffe5b4', alpha=0.95, edgecolor='black', linewidth=2))
            fig.text(0.73, 0.08, f'Affected: {results["affected_pop_pct"]:.1f}%',
                    ha='center', fontsize=12, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.6', facecolor='#ffe5b4', alpha=0.95, edgecolor='black', linewidth=2))

        else:
            # Original area-only chart
            ax = fig.add_subplot(111)
            fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.22)

            categories = ['Total Area', 'Inundated Area', 'Dry Area']
            values = [results['total_area'], results['inund_area'], results['dry_area']]
            colors = ['#3498db', '#e74c3c', '#2ecc71']

            bars = ax.bar(categories, values, color=colors, alpha=0.85, edgecolor='black', linewidth=2)

            # Add value labels with offset to avoid overlap
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height * 1.02,  # 2% above bar
                       f'{height:,.0f} m²',
                       ha='center', va='bottom', fontweight='bold', fontsize=12)

            ax.set_ylabel('Area (m²)', fontweight='bold', fontsize=12)
            ax.set_title(f'Total Area vs Inundation Comparison\n({results["feature_count"]} features analyzed)',
                        fontweight='bold', fontsize=12, pad=15)
            ax.tick_params(axis='both', labelsize=12)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            ax.set_ylim(0, max(values) * 1.15)  # Add 15% headroom for value labels

            # Legend box below chart
            fig.text(0.5, 0.08, f'Inundation: {results["inund_pct"]:.1f}%',
                    ha='center', fontsize=12, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.7', facecolor='#ffe5b4', alpha=0.95, edgecolor='black', linewidth=2))

    def create_feature_chart(self, results):
        """Feature comparison pie + bar"""
        fig = self.chart_widget.figure

        gs = fig.add_gridspec(1, 2, wspace=0.5, left=0.10, right=0.96, top=0.88, bottom=0.22)

        # Pie chart
        ax1 = fig.add_subplot(gs[0, 0])
        labels = ['Inundated Features', 'Non-Inundated Features']
        values = [results['inundated_count'], results['comparison_count']]
        colors = ['#e74c3c', '#2ecc71']
        explode = (0.1, 0)

        wedges, texts, autotexts = ax1.pie(values, labels=labels, autopct='%1.1f%%',
                                            colors=colors, explode=explode, startangle=90,
                                            textprops={'fontweight': 'bold', 'fontsize': 12})
        for autotext in autotexts:
            autotext.set_fontsize(12)
        ax1.set_title('Feature Count Distribution', fontweight='bold', fontsize=12, pad=15)

        # Bar chart
        ax2 = fig.add_subplot(gs[0, 1])
        cats = ['Inundated\nFeatures', 'Non-Inundated\nFeatures']
        vals = [results['inundated_count'], results['comparison_count']]
        colors2 = ['#e74c3c', '#2ecc71']

        bars = ax2.bar(cats, vals, color=colors2, alpha=0.85, edgecolor='black', linewidth=2)

        # Add value labels with offset
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height * 1.02,
                    f'{int(height)}',
                    ha='center', va='bottom', fontweight='bold', fontsize=12)

        ax2.set_ylabel('Feature Count', fontweight='bold', fontsize=12)
        ax2.set_title('Feature Comparison', fontweight='bold', fontsize=12, pad=15)
        ax2.tick_params(axis='both', labelsize=12)
        ax2.grid(axis='y', alpha=0.3, linestyle='--')
        ax2.set_ylim(0, max(vals) * 1.15)  # Add 15% headroom for labels

        # Main title
        fig.suptitle(f'Inundated vs Non-Inundated Features Analysis\n(Total: {results["total_count"]} features)',
                    fontweight='bold', fontsize=12, y=0.96)

    def create_distribution_chart(self, results):
        """Distribution histogram"""
        fig = self.chart_widget.figure

        ax = fig.add_subplot(111)
        fig.subplots_adjust(left=0.12, right=0.95, top=0.88, bottom=0.22)

        n, bins, patches = ax.hist(results['percentages'], bins=25, color='#3498db',
                                   alpha=0.75, edgecolor='black', linewidth=1.3)

        cm = plt.cm.get_cmap('RdYlGn_r')
        for i, patch in enumerate(patches):
            patch.set_facecolor(cm(i / len(patches)))

        ax.set_xlabel('Inundation Percentage (%)', fontweight='bold', fontsize=12)
        ax.set_ylabel('Number of Features', fontweight='bold', fontsize=12)
        ax.set_title(f'Inundation Distribution Histogram\n({results["count"]} features)',
                    fontweight='bold', fontsize=12, pad=15)
        ax.tick_params(axis='both', labelsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Stats box below chart
        stats_text = f'Mean: {results["mean"]:.1f}%\nMedian: {results["median"]:.1f}%\nMin: {results["min"]:.1f}%\nMax: {results["max"]:.1f}%'
        fig.text(0.5, 0.08, stats_text, ha='center', fontsize=12, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.7', facecolor='#ffe5b4', alpha=0.95, edgecolor='black', linewidth=2))

    def update_statistics_table(self, results):
        """Update statistics table"""
        self.stats_table.clear()

        if self.radio_area.isChecked():
            # Include population if available
            if results.get('has_population'):
                self.stats_table.setRowCount(10)
                self.stats_table.setColumnCount(2)
                self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

                data = [
                    ('Total Area (m²)', f"{results['total_area']:,.2f}"),
                    ('Inundated Area (m²)', f"{results['inund_area']:,.2f}"),
                    ('Dry Area (m²)', f"{results['dry_area']:,.2f}"),
                    ('Inundation Percentage', f"{results['inund_pct']:.2f}%"),
                    ('Features Analyzed', str(results['feature_count'])),
                    ('━━━━━━━━━━━━━━━━━━━━', '━━━━━━━━━━━━━━━━━━'),
                    ('Total Population', f"{results['total_population']:,.0f}"),
                    ('Affected Population', f"{results['affected_population']:,.0f}"),
                    ('Safe Population', f"{results['safe_population']:,.0f}"),
                    ('Population Affected %', f"{results['affected_pop_pct']:.2f}%")
                ]
            else:
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

        elif self.radio_feature.isChecked():
            self.stats_table.setRowCount(4)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

            data = [
                ('Inundated Features', str(results['inundated_count'])),
                ('Non-Inundated Features', str(results['comparison_count'])),
                ('Total Features', str(results['total_count'])),
                ('Inundated Percentage', f"{results['inund_pct_of_all']:.2f}%")
            ]

        else:
            self.stats_table.setRowCount(5)
            self.stats_table.setColumnCount(2)
            self.stats_table.setHorizontalHeaderLabels(['Metric', 'Value'])

            data = [
                ('Mean Inundation %', f"{results['mean']:.2f}%"),
                ('Median Inundation %', f"{results['median']:.2f}%"),
                ('Min Inundation %', f"{results['min']:.2f}%"),
                ('Max Inundation %', f"{results['max']:.2f}%"),
                ('Features Analyzed', str(results['count']))
            ]

        for row, (label, value) in enumerate(data):
            self.stats_table.setItem(row, 0, QTableWidgetItem(label))
            value_item = QTableWidgetItem(value)
            value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stats_table.setItem(row, 1, value_item)

        self.stats_table.resizeColumnsToContents()
        self.stats_table.horizontalHeader().setStretchLastSection(True)

    def update_raw_data(self, results):
        """Update raw data view"""
        import json
        display_results = dict(results)
        if 'feature_data' in display_results:
            display_results['feature_data'] = f"[{len(results['feature_data'])} features]"
        if 'percentages' in display_results:
            display_results['percentages'] = f"[{len(results['percentages'])} values]"
        self.data_text.setText(json.dumps(display_results, indent=2))

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
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

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

                    if self.radio_area.isChecked():
                        # Check if population data exists
                        if self.current_results.get('has_population'):
                            writer.writerow(['Feature_ID', 'Total_Area_m2', 'Inundated_Area_m2', 'Inundation_Pct',
                                           'Population', 'Pop_Affected', 'Pop_Safe'])
                            for i, feat in enumerate(self.current_results['feature_data']):
                                writer.writerow([i+1, feat['total_area'], feat['inund_area'], feat['inund_pct'],
                                               feat.get('population', 0), feat.get('pop_affected', 0), feat.get('pop_safe', 0)])
                        else:
                            writer.writerow(['Feature_ID', 'Total_Area_m2', 'Inundated_Area_m2', 'Inundation_Pct'])
                            for i, feat in enumerate(self.current_results['feature_data']):
                                writer.writerow([i+1, feat['total_area'], feat['inund_area'], feat['inund_pct']])
                    elif self.radio_feature.isChecked():
                        writer.writerow(['Category', 'Count'])
                        writer.writerow(['Inundated Features', self.current_results['inundated_count']])
                        writer.writerow(['Non-Inundated Features', self.current_results['comparison_count']])
                    else:
                        writer.writerow(['Inundation_Percentage'])
                        for pct in self.current_results['percentages']:
                            writer.writerow([pct])

                QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def export_excel(self):
        """Export data as Excel"""
        if not PANDAS_AVAILABLE:
            QMessageBox.warning(self, "Pandas Required", "Pandas library required for Excel export.")
            return

        if not self.current_results:
            QMessageBox.warning(self, "No Data", "Please generate analysis first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data as Excel", "", "Excel Files (*.xlsx)")

        if file_path:
            try:
                if self.radio_area.isChecked():
                    df = pd.DataFrame(self.current_results['feature_data'])
                    df.to_excel(file_path, index_label='Feature_ID')
                elif self.radio_feature.isChecked():
                    df = pd.DataFrame({
                        'Category': ['Inundated Features', 'Non-Inundated Features'],
                        'Count': [self.current_results['inundated_count'], self.current_results['comparison_count']]
                    })
                    df.to_excel(file_path, index=False)
                else:
                    df = pd.DataFrame({'Inundation_Percentage': self.current_results['percentages']})
                    df.to_excel(file_path, index=False)

                QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def stop_worker(self):
        """Safely stop worker thread"""
        if self.worker is not None:
            if self.worker.isRunning():
                QgsMessageLog.logMessage(
                    "Stopping analysis worker...",
                    "OSLRAT",
                    Qgis.Info
                )

                # Set abort flag using thread-safe method
                self._abort_analysis = True
                self.worker.request_abort()

                # Wait for graceful shutdown
                if not self.worker.wait(3000):  # 3 second timeout
                    QgsMessageLog.logMessage(
                        "Worker did not stop gracefully, terminating...",
                        "OSLRAT",
                        Qgis.Warning
                    )
                    self.worker.terminate()
                    self.worker.wait()

            self.cleanup_worker()

    def cleanup_worker(self):
        """Cleanup worker object and connections"""
        if self.worker is not None:
            try:
                # Disconnect all signals
                self.worker.progress.disconnect()
                self.worker.status.disconnect()
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except (TypeError, RuntimeError):
                pass  # Already disconnected or deleted

            # Schedule for deletion
            self.worker.deleteLater()
            self.worker = None

            self._abort_analysis = False

    def cleanup_matplotlib(self):
        """Cleanup matplotlib resources"""
        try:
            if hasattr(self, 'chart_widget') and self.chart_widget is not None:
                if hasattr(self.chart_widget, 'figure') and self.chart_widget.figure is not None:
                    self.chart_widget.figure.clear()
                    if MATPLOTLIB_AVAILABLE:
                        plt.close(self.chart_widget.figure)
                    self.chart_widget.figure = None
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error cleaning up matplotlib: {e}",
                "OSLRAT",
                Qgis.Warning
            )

    def closeEvent(self, event):
        """Cleanup all resources before closing"""
        QgsMessageLog.logMessage(
            "Closing visualization dialog, cleaning up resources...",
            "OSLRAT",
            Qgis.Info
        )

        # Stop worker thread
        self.stop_worker()

        # Cleanup matplotlib
        self.cleanup_matplotlib()

        # Clear results
        self.current_results = None

        # Accept close event
        super().closeEvent(event)
