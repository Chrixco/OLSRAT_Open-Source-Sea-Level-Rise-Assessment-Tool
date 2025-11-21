# -*- coding: utf-8 -*-
"""
Modern GUI for OSLRAT
with category buttons and styled drop-down menus
Cross-platform compatible (macOS, Windows, Linux)
"""

from functools import partial
import platform
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMenu,
    QLabel, QWidget, QFrame
)
from qgis.PyQt.QtGui import QIcon, QPixmap, QColor
from qgis.PyQt.QtCore import Qt, QSize, QPoint, QEvent
import processing
from qgis.core import QgsMessageLog, Qgis
from .slr_vm_viz_redesigned import SlrVmVisualizationDialog

# Detect platform for platform-specific adjustments
IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'


# --- Central colour theme ---
def rgba_50(hex_color: str) -> str:
    """Convert hex to 50% transparent RGBA string for QSS."""
    qcolor = QColor(hex_color)
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, 128)"  # 128 = 50% opacity


CATEGORY_COLORS = {
    "data": {"fill": "#3498db", "outline": "#2980b9"},
    "flood": {"fill": "#e74c3c", "outline": "#c0392b"},
    "social": {"fill": "#2ecc71", "outline": "#27ae60"},
    "terrain": {"fill": "#9b59b6", "outline": "#8e44ad"},
    "visualization": {"fill": "#e91e63", "outline": "#c2185b"},  # Pink/Magenta for visualization
}

for key, vals in CATEGORY_COLORS.items():
    vals["highlight"] = rgba_50(vals["fill"])


class SlrVmNewGui(QDialog):
    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self._viz_dialog = None  # Track visualization dialog
        self.setWindowTitle("OSLRAT - Open-Source Sea-Level Rise Assessment Tool")
        self.resize(1300, 750)

        QgsMessageLog.logMessage("Initialising OSLRAT Toolkit GUI", "OSLRAT", Qgis.Info)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Professional gradient header with logo and description
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db,
                    stop:0.3 #5b74b3,
                    stop:0.6 #8e5ba8,
                    stop:0.85 #b94398,
                    stop:1 #e91e63
                );
                border-radius: 0px;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(40, 25, 40, 25)
        header_layout.setSpacing(25)

        # Logo on the left
        try:
            logo_pixmap = QPixmap(":/slr_vm/Icons/256.png")
            logo_label = QLabel()
            logo_label.setPixmap(
                logo_pixmap.scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            logo_label.setFixedSize(110, 110)
            header_layout.addWidget(logo_label, alignment=Qt.AlignVCenter)
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to load header logo: {e}", "SLR Mapper", Qgis.Warning)

        # Title and description on the right
        text_container = QWidget()
        text_container.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_container)
        text_layout.setSpacing(10)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("<h1 style='color: white; margin: 0; font-size: 32px; font-weight: bold; letter-spacing: 1px;'>OSLRAT</h1>")
        title_label.setStyleSheet("background: transparent;")
        text_layout.addWidget(title_label)

        subtitle_label = QLabel("<p style='color: rgba(255, 255, 255, 0.98); margin: 0; font-size: 15px; font-weight: 600; letter-spacing: 0.5px;'>Open-Source Sea-Level Rise Assessment Tool</p>")
        subtitle_label.setStyleSheet("background: transparent;")
        text_layout.addWidget(subtitle_label)

        description_label = QLabel(
            "<p style='color: rgba(255, 255, 255, 0.93); margin: 0; font-size: 13px; line-height: 1.6;'>"
            "Assess and visualize sea-level rise & flood exposure using <b>IPCC AR6 projections</b>, "
            "<b>CODEC extreme datasets</b>, and advanced spatial analysis. Designed for urban planners, "
            "researchers, emergency managers, and decision-makers building climate-resilient communities. "
            "Analyze flood scenarios, assess social vulnerability, and generate professional reports."
            "</p>"
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("background: transparent;")
        text_layout.addWidget(description_label)

        header_layout.addWidget(text_container, stretch=1)
        main_layout.addWidget(header_widget)

        # Content area with padding
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f5f6fa;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        # Instructions section
        instructions = QLabel(
            "<h3 style='color: #2c3e50; margin: 0 0 10px 0; font-size: 18px;'>📍 Select Your Analysis Tool</h3>"
            "<p style='color: #555; margin: 0; font-size: 13px; line-height: 1.5;'>"
            "Choose from <b>Data Preparation</b> (DEM fetching, reprojection), <b>Flood Mapping</b> (AR6 scenarios, inundation), "
            "<b>Social Analysis</b> (vulnerability indices), <b>Terrain Analysis</b> (slope, aspect, hillshade), or "
            "<b>Data Visualization</b> (interactive charts and comparisons)."
            "</p>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "QLabel { padding: 20px; background-color: white; border-radius: 10px; border: 2px solid #e0e0e0; }"
        )
        content_layout.addWidget(instructions)

        # Categories container - single horizontal row
        button_container = QWidget()
        button_container.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(18)
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Algorithm IDs (use algorithm name() method, not class names!)
        categories = [
            {
                "name": "Data Preparation",
                "icon_path": ":/slr_vm/Icons/Data_Prep_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:fetch_dem_prep", "name": "Fetch DEM (OpenTopography)"},
                    {"id": f"{self.provider.id()}:fetch_osm_data", "name": "🏘️ Fetch OSM Buildings & Streets"},
                    {"id": f"{self.provider.id()}:reproject_vector", "name": "Reproject Vector"},
                    {"id": f"{self.provider.id()}:vector_to_raster", "name": "Vector to Raster"},
                    {"id": f"{self.provider.id()}:raster_to_vector", "name": "Raster to Vector"},
                ],
                "colors": CATEGORY_COLORS["data"],
            },
            {
                "name": "Flood Mapping",
                "icon_path": ":/slr_vm/Icons/SLR_Alg_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:dem_flood_scenario", "name": "DEM Flood Scenario (AR6)"},
                    {"id": f"{self.provider.id()}:dem_flood_scenario_codec", "name": "DEM Flood + Return Period (CODEC)"},
                    {"id": f"{self.provider.id()}:inundation", "name": "Inundation Mapping"},
                    {"id": f"{self.provider.id()}:point_flooding", "name": "Point Flooding"},
                    {"id": f"{self.provider.id()}:point_flood_heatmap", "name": "Flood Heatmap"},
                    {"id": f"{self.provider.id()}:ipcc_flood_scenarios_polygon_fast", "name": "IPCC Flood Scenarios (Fast)"},
                ],
                "colors": CATEGORY_COLORS["flood"],
            },
            {
                "name": "Social Analysis",
                "icon_path": ":/slr_vm/Icons/Social_Analysis_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:svi_index", "name": "Social Vulnerability Index"},
                ],
                "colors": CATEGORY_COLORS["social"],
            },
            {
                "name": "Terrain Analysis",
                "icon_path": ":/slr_vm/Icons/Terrain_Analysis_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:slope_analysis", "name": "Slope"},
                    {"id": f"{self.provider.id()}:aspect_analysis", "name": "Aspect"},
                    {"id": f"{self.provider.id()}:hillshade_analysis", "name": "Hillshade"},
                ],
                "colors": CATEGORY_COLORS["terrain"],
            },
            {
                "name": "Data Visualization",
                "icon_path": ":/slr_vm/Icons/256.png",  # Use main program logo
                "algorithms": [
                    {"id": "interactive_viz", "name": "📊 Interactive Data Visualization Dashboard", "special": True},
                ],
                "colors": CATEGORY_COLORS["visualization"],
            },
        ]

        # Add all category buttons to horizontal layout
        for category in categories:
            btn = self.create_category_button(category)
            button_layout.addWidget(btn)

        content_layout.addWidget(button_container)
        content_layout.addStretch()

        # Footer with Close, Donate, Contact buttons
        footer_widget = QWidget()
        footer_widget.setStyleSheet("background: transparent;")
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setSpacing(12)
        footer_layout.setContentsMargins(0, 10, 0, 0)

        footer_layout.addStretch()

        # Contact button
        contact_btn = QPushButton("✉ Contact")
        contact_btn.setMinimumWidth(120)
        contact_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        contact_btn.clicked.connect(self.open_contact)
        footer_layout.addWidget(contact_btn)

        # Donate button
        donate_btn = QPushButton("❤ Donate")
        donate_btn.setMinimumWidth(120)
        donate_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        donate_btn.clicked.connect(self.open_donate)
        footer_layout.addWidget(donate_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(120)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        content_layout.addWidget(footer_widget)

        main_layout.addWidget(content_widget)

    def open_contact(self):
        """Open contact information dialog"""
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Contact Information",
            "<h3>Get in Touch</h3>"
            "<p><b>Author:</b> Christian Xavier Corral Burau</p>"
            "<p><b>Email:</b> <a href='mailto:christianxcorral@gmail.com'>christianxcorral@gmail.com</a></p>"
            "<p><b>GitHub:</b> <a href='https://github.com/Chrixco'>@Chrixco</a></p>"
            "<br>"
            "<p>For bug reports, feature requests, or collaboration inquiries, please visit:</p>"
            "<p><a href='https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool/issues'>GitHub Issues</a></p>"
        )

    def open_donate(self):
        """Open donation information dialog"""
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Support This Project",
            "<h3>❤ Support Open-Source Climate Science</h3>"
            "<p>This plugin is <b>free and open-source</b>, developed to help communities "
            "build resilience against sea-level rise and coastal flooding.</p>"
            "<br>"
            "<p>If you find this tool valuable, please consider:</p>"
            "<ul>"
            "<li>⭐ Starring the project on <a href='https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool'>GitHub</a></li>"
            "<li>📢 Sharing it with colleagues and organizations</li>"
            "<li>💬 Providing feedback and suggestions</li>"
            "<li>🤝 Contributing code or documentation</li>"
            "</ul>"
            "<br>"
            "<p>For custom development, training, or consulting services, please contact:<br>"
            "<a href='mailto:christianxcorral@gmail.com'>christianxcorral@gmail.com</a></p>"
        )

    def create_category_button(self, category):
        QgsMessageLog.logMessage(f"Creating category button for {category['name']}", "OSLRAT", Qgis.Info)
        colors = category["colors"]
        fill, outline, highlight = colors["fill"], colors["outline"], colors["highlight"]

        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(0)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 3px solid {outline};
                border-radius: 15px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        icon = QIcon(category["icon_path"]) if category.get("icon_path") else QIcon(":/slr_vm/Icons/64.png")
        btn = QPushButton(category["name"])
        btn.setIcon(icon)
        btn.setIconSize(QSize(64, 64))
        btn.setMinimumSize(220, 180)
        btn.setMaximumSize(240, 200)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {fill};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 25px 15px;
                font-weight: bold;
                font-size: 13px;
                text-align: center;
            }}
            QPushButton::menu-indicator {{ image: none; }}
            QPushButton:hover {{
                background-color: {outline};
                transform: scale(1.02);
            }}
            QPushButton:pressed {{
                background-color: {outline};
            }}
        """)

        # Menu with enhanced styling - parent to self (dialog) for proper z-order
        # Important: Parent to dialog (not button) to ensure menu stays on top
        menu = QMenu(self)

        # Set window flags to ensure menu appears on top
        menu.setWindowFlags(menu.windowFlags() | Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground, False)

        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #ffffff;
                border: 2px solid {outline};
                border-radius: 10px;
                padding: 8px;
            }}
            QMenu::item {{
                padding: 10px 25px;
                border-radius: 6px;
                color: #2c3e50;
                font-size: 12px;
                margin: 2px 0px;
            }}
            QMenu::item:selected {{
                background-color: {fill};
                color: white;
                font-weight: bold;
            }}
            QMenu::separator {{
                height: 1px;
                background: #e0e0e0;
                margin: 4px 10px;
            }}
        """)

        for alg in category["algorithms"]:
            # Handle special items (separator, interactive viz)
            if alg.get("special"):
                if alg["name"] == "separator":
                    menu.addSeparator()
                    continue
                elif alg["id"] == "interactive_viz":
                    QgsMessageLog.logMessage(f"Adding special interactive viz action", "OSLRAT", Qgis.Info)
                    action = menu.addAction(alg["name"])
                    action.triggered.connect(self.open_interactive_visualization)
                    continue

            QgsMessageLog.logMessage(f"Adding menu action for {alg['name']} with ID {alg['id']}", "OSLRAT", Qgis.Info)
            action = menu.addAction(alg["name"])
            action.triggered.connect(partial(self._run_algorithm_with_debug, alg["id"], alg["name"]))

        def show_menu():
            QgsMessageLog.logMessage(
                f"Button clicked for {category['name']} on {platform.system()}, showing menu with {len(category['algorithms'])} items",
                "OSLRAT", Qgis.Info
            )
            try:
                menu.setMinimumWidth(btn.width())

                # Platform-specific menu positioning
                # macOS: bottomLeft works well
                # Windows: May need slight Y offset to avoid overlap
                # Linux: Similar to Windows
                pos = btn.mapToGlobal(btn.rect().bottomLeft())

                # Add small Y offset on Windows to prevent menu from overlapping button
                if IS_WINDOWS:
                    pos = QPoint(pos.x(), pos.y() + 2)

                QgsMessageLog.logMessage(f"Menu position: {pos.x()}, {pos.y()} (Platform: {platform.system()})", "OSLRAT", Qgis.Info)

                # Ensure the menu is activated and raised to front
                menu.activateWindow()
                menu.raise_()

                # Show the menu at the calculated position
                # exec_() is synchronous and blocks until menu is closed
                selected_action = menu.exec_(pos)

                if selected_action:
                    QgsMessageLog.logMessage(f"Menu item selected: {selected_action.text()}", "OSLRAT", Qgis.Info)
                else:
                    QgsMessageLog.logMessage(f"Menu closed without selection", "OSLRAT", Qgis.Info)

            except Exception as e:
                QgsMessageLog.logMessage(f"Error showing menu for {category['name']}: {str(e)}", "OSLRAT", Qgis.Critical)
                import traceback
                QgsMessageLog.logMessage(f"Traceback: {traceback.format_exc()}", "OSLRAT", Qgis.Critical)

        btn.clicked.connect(show_menu)
        layout.addWidget(btn)
        return frame

    def open_interactive_visualization(self):
        """Open the interactive visualization dashboard"""
        QgsMessageLog.logMessage("Opening Interactive Data Visualization Dashboard", "OSLRAT", Qgis.Info)
        try:
            # Check if already open (with proper Qt state check)
            if self._viz_dialog is not None:
                # Verify the dialog still exists (Qt may have deleted it)
                try:
                    self._viz_dialog.isVisible()  # Will raise if deleted
                    self._viz_dialog.show()
                    self._viz_dialog.raise_()
                    self._viz_dialog.activateWindow()
                    QgsMessageLog.logMessage("Reusing existing visualization dialog", "OSLRAT", Qgis.Info)
                    return
                except (RuntimeError, AttributeError):
                    # Dialog was deleted, clear reference and create new
                    self._viz_dialog = None

            # Prevent race condition by setting placeholder immediately
            # (will be replaced with actual dialog below, or None if creation fails)
            self._viz_dialog = object()  # Placeholder to prevent concurrent creation

            # Create new dialog
            dialog = SlrVmVisualizationDialog(self)

            # Replace placeholder with actual dialog
            self._viz_dialog = dialog

            # Cleanup reference when destroyed
            dialog.destroyed.connect(
                lambda: setattr(self, '_viz_dialog', None)
            )

            # Show non-modally (allows interaction with main GUI and map)
            dialog.show()

            QgsMessageLog.logMessage("Created new visualization dialog", "OSLRAT", Qgis.Info)

        except Exception as e:
            # Clear placeholder on error
            self._viz_dialog = None

            QgsMessageLog.logMessage(
                f"Error opening visualization dashboard: {str(e)}",
                "OSLRAT", level=Qgis.Critical
            )
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Visualization Error",
                f"Failed to open Interactive Visualization Dashboard:\n\n{str(e)}\n\n"
                f"Please ensure matplotlib is installed:\npip install matplotlib"
            )

    def _run_algorithm_with_debug(self, alg_id, alg_name):
        QgsMessageLog.logMessage(f"Opening Processing dialog for {alg_name} (ID={alg_id})", "OSLRAT", Qgis.Info)
        try:
            # Open the Processing dialog
            # Note: execAlgorithmDialog returns results dict if run, or None/False if user cancels
            result = processing.execAlgorithmDialog(alg_id)

            # result is None/False when user closes dialog without running - this is NORMAL, not an error
            if result:
                QgsMessageLog.logMessage(f"Algorithm '{alg_name}' completed successfully", "OSLRAT", Qgis.Info)
            else:
                QgsMessageLog.logMessage(f"Algorithm dialog closed without running (user canceled)", "OSLRAT", Qgis.Info)

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error running algorithm {alg_id}: {str(e)}",
                "OSLRAT", level=Qgis.Critical
            )
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open algorithm '{alg_name}':\n\n{str(e)}"
            )

    def closeEvent(self, event):
        """Cleanup resources when dialog closes"""
        QgsMessageLog.logMessage("Closing main GUI dialog", "OSLRAT", Qgis.Info)

        # Close child visualization dialog if open
        if self._viz_dialog is not None:
            try:
                self._viz_dialog.close()
            except (RuntimeError, AttributeError):
                # Dialog may already be deleted by Qt
                pass
            self._viz_dialog = None

        # Accept the close event
        super().closeEvent(event)

