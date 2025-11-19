# -*- coding: utf-8 -*-
"""
GUI Launcher Algorithm - Opens the OSLRAT Main GUI
"""

from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingContext
)
from qgis.PyQt.QtCore import QCoreApplication
import os


class AlgOpenGui(QgsProcessingAlgorithm):
    """
    Algorithm to launch the main GUI from the processing toolbox
    """

    def tr(self, s):
        return QCoreApplication.translate("AlgOpenGui", s)

    def name(self):
        return "open_main_gui"

    def displayName(self):
        return self.tr("🏠 Open Main GUI (Recommended)")

    def group(self):
        return self.tr("Quick Access")

    def groupId(self):
        return "quick_access"

    def shortHelpString(self):
        return self.tr(
            "<b>Launch the OSLRAT Main Interface</b><br><br>"
            "This opens the main graphical user interface with organized access to all toolkit features:<br><br>"
            "• <b>Data Preparation</b> - Download DEM, reproject layers, convert formats<br>"
            "• <b>Flood Exposure Analysis</b> - Generate inundation scenarios, analyze flooding<br>"
            "• <b>Social Vulnerability</b> - Calculate SVI, assess population impacts<br>"
            "• <b>Terrain Analysis</b> - Slope, hillshade, aspect calculations<br>"
            "• <b>Data Visualization</b> - Interactive charts, comparisons, and reports<br><br>"
            "<b>🌟 Recommended for most users!</b><br>"
            "The GUI provides an easier, more intuitive way to use the toolkit compared to running individual algorithms."
        )

    def createInstance(self):
        return AlgOpenGui()

    def icon(self):
        """Return the plugin icon"""
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Icons", "256.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return QIcon()

    def initAlgorithm(self, config=None):
        """No parameters needed - this just opens the GUI"""
        pass

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback):
        """Open the main GUI"""
        try:
            # Import the main GUI class
            from ..slr_vm_new_gui import SlrVulnerabilityMapperDialog

            # Create and show the GUI (non-modal)
            dialog = SlrVulnerabilityMapperDialog()
            dialog.setWindowModality(0)  # Non-modal
            dialog.show()

            feedback.pushInfo("✓ Main GUI opened successfully!")
            feedback.pushInfo("The toolkit window should now be visible.")
            feedback.pushInfo("You can continue working in QGIS while the GUI is open.")

            return {}

        except Exception as e:
            feedback.reportError(f"Failed to open GUI: {str(e)}", fatalError=False)
            return {}

    def flags(self):
        """Make this algorithm not cancellable since it just opens a window"""
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading
