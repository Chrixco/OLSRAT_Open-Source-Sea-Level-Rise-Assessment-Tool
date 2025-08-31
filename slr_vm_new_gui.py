# -*- coding: utf-8 -*-
"""
Modern GUI for SLR Vulnerability Mapper
with category buttons and styled drop-down menus
"""

import os
import sys
from functools import partial
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMenu,
    QLabel, QWidget, QFrame
)
from qgis.PyQt.QtGui import QIcon, QPixmap, QColor
from qgis.PyQt.QtCore import Qt, QSize
import processing
from qgis.core import QgsMessageLog


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
}

for key, vals in CATEGORY_COLORS.items():
    vals["highlight"] = rgba_50(vals["fill"])


class SlrVmNewGui(QDialog):
    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.setWindowTitle("SLR Vulnerability Mapper - Toolkit")
        self.resize(900, 600)

        print("DEBUG: Initialising SLR Vulnerability Toolkit GUI")

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        try:
            logo_pixmap = QPixmap(":/slr_vm/Icons/256.png")
            logo_label = QLabel()
            logo_label.setPixmap(
                logo_pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            header_layout.addWidget(logo_label)
        except Exception as e:
            print(f"DEBUG: Failed to load header logo: {e}")

        title_label = QLabel("<h1>SLR Vulnerability Mapper</h1>")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        main_layout.addWidget(header_widget)

        # Instructions
        instructions = QLabel(
            "<h3>Select a category to access vulnerability mapping tools:</h3>"
            "<p>Choose from data preparation, flood mapping, social analysis, or terrain tools.</p>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "QLabel { padding: 10px; background-color: #f8f9fa; border-radius: 5px; }"
        )
        main_layout.addWidget(instructions)

        # Categories container
        button_grid = QWidget()
        grid_layout = QHBoxLayout(button_grid)
        grid_layout.setSpacing(20)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        # Algorithm IDs (lowercase from provider)
        categories = [
            {
                "name": "Data Preparation",
                "icon_path": ":/slr_vm/Icons/Data_Prep_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:AlgFetchDEM", "name": "Fetch DEM"},
                    {"id": f"{self.provider.id()}:AlgReprojectVector", "name": "Reproject Vector"},
                    {"id": f"{self.provider.id()}:AlgVectorToRaster", "name": "Vector to Raster"},
                    {"id": f"{self.provider.id()}:AlgRasterToVector", "name": "Raster to Vector"},
                ],
                "colors": CATEGORY_COLORS["data"],
            },
            {
                "name": "Flood Mapping",
                "icon_path": ":/slr_vm/Icons/SLR_Alg_Logo/Assets.xcassets/AppIcon.appiconset/_/64.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:DemFloodScenarioAlgorithm", "name": "DEM Flood Scenario"},
                    {"id": f"{self.provider.id()}:DemFloodScenarioAlgorithmWithReturnPeriod", "name": "DEM Flood + Return Period"},
                    {"id": f"{self.provider.id()}:AlgInundation", "name": "Inundation Mapping"},
                    {"id": f"{self.provider.id()}:AlgPointFlooding", "name": "Point Flooding"},
                    {"id": f"{self.provider.id()}:AlgPointFloodHeatmap", "name": "Flood Heatmap"},
                    {"id": f"{self.provider.id()}:AlgIPCCScenarios", "name": "IPCC Scenarios"},
                ],
                "colors": CATEGORY_COLORS["flood"],
            },
            {
                "name": "Social Analysis",
                "icon_path": ":/slr_vm/Icons/Social_Analysis_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:AlgSVI", "name": "Social Vulnerability Index"},
                ],
                "colors": CATEGORY_COLORS["social"],
            },
            {
                "name": "Terrain Analysis",
                "icon_path": ":/slr_vm/Icons/Terrain_Analysis_Logo/Assets.xcassets/AppIcon.appiconset/_/32.png",
                "algorithms": [
                    {"id": f"{self.provider.id()}:AlgSlope", "name": "Slope"},
                    {"id": f"{self.provider.id()}:AlgAspect", "name": "Aspect"},
                    {"id": f"{self.provider.id()}:AlgHillshade", "name": "Hillshade"},
                ],
                "colors": CATEGORY_COLORS["terrain"],
            },
        ]

        # Add category buttons
        for category in categories:
            btn = self.create_category_button(category)
            grid_layout.addWidget(btn)

        main_layout.addWidget(button_grid)
        main_layout.addSpacing(20)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

    def create_category_button(self, category):
        print(f"DEBUG: Creating category button for {category['name']}")
        colors = category["colors"]
        fill, outline, highlight = colors["fill"], colors["outline"], colors["highlight"]

        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet(f"QFrame {{ border: 2px solid {outline}; border-radius: 10px; }}")

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        icon = QIcon(category["icon_path"]) if category.get("icon_path") else QIcon(":/slr_vm/Icons/64.png")
        btn = QPushButton(category["name"])
        btn.setIcon(icon)
        btn.setIconSize(QSize(48, 48))
        btn.setMinimumSize(180, 100)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {fill};
                color: white;
                border: none;
                border-radius: 12px;
                padding: 15px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton::menu-indicator {{ image: none; }}
            QPushButton:hover {{ background-color: {highlight}; }}
        """)

        # Menu
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #ffffff;
                border: 1px solid {outline};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                border-radius: 6px;
                color: #2c3e50;
                qproperty-alignment: AlignCenter;
            }}
            QMenu::item:selected {{
                background-color: {highlight};
                color: white;
            }}
        """)

        for alg in category["algorithms"]:
            print(f"DEBUG: Adding menu action for {alg['name']} with ID {alg['id']}")
            action = menu.addAction(alg["name"])
            action.triggered.connect(partial(self._run_algorithm_with_debug, alg["id"], alg["name"]))

        def show_menu():
            print(f"DEBUG: Showing menu for {category['name']}")
            menu.setFixedWidth(btn.width())
            button_pos = btn.mapToGlobal(btn.rect().center())
            menu_x = button_pos.x() - menu.width() // 2
            menu_y = button_pos.y() + btn.height() // 2
            menu.move(menu_x, menu_y)
            menu.exec_()
            print(f"DEBUG: Menu closed for {category['name']}")

        btn.clicked.connect(show_menu)
        layout.addWidget(btn)
        return frame

    def _run_algorithm_with_debug(self, alg_id, alg_name):
        print(f"DEBUG: Attempting to open Processing dialog for {alg_name} (ID={alg_id})")
        try:
            # Close Toolkit first
            self.close()   # or self.accept()

            # Then open the Processing dialog
            processing.execAlgorithmDialog(alg_id)
            print(f"DEBUG: Dialog for {alg_name} should now be visible in QGIS")

        except Exception as e:
            print(f"ERROR: Failed to open algorithm {alg_name} (ID={alg_id}): {e}")
            QgsMessageLog.logMessage(
                f"Error running algorithm {alg_id}: {str(e)}",
                "SLR Vulnerability Mapper", level=QgsMessageLog.CRITICAL
            )

