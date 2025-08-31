from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterCrs, QgsProcessingParameterNumber, QgsProcessingParameterExtent,
    QgsProcessingParameterEnum, QgsProcessingParameterBoolean, QgsProcessingParameterRasterDestination,
    QgsProcessingException, QgsCoordinateReferenceSystem
)
from qgis import processing
import requests, tempfile, os

class AlgFetchDEM(QgsProcessingAlgorithm):
    INPUT_SOURCE = "INPUT_SOURCE"   # Local DEM or OT
    INPUT_DEM    = "INPUT_DEM"
    TARGET_CRS   = "TARGET_CRS"
    PIXEL_SIZE   = "PIXEL_SIZE"
    EXTENT       = "EXTENT"
    RESAMPLING   = "RESAMPLING"
    CLIP         = "CLIP"
    OUTPUT       = "OUTPUT"

    DEM_SOURCE_OPTS = ["Local DEM", "Copernicus 90m (OpenTopography)", "Copernicus 30m (OpenTopography)"]
    RESAMPLING_OPTS = ["Nearest", "Bilinear", "Cubic"]

    def name(self): return "fetch_dem_prep"
    def displayName(self): return "Fetch & Prepare DEM (local or OpenTopography)"
    def group(self): return "Data Preparation"
    def groupId(self): return "data_preparation"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.INPUT_SOURCE, "DEM source", options=self.DEM_SOURCE_OPTS, defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT_DEM, "Input DEM (if local)", optional=True
        ))
        self.addParameter(QgsProcessingParameterCrs(
            self.TARGET_CRS, "Target CRS", defaultValue=QgsCoordinateReferenceSystem("EPSG:3857")
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.PIXEL_SIZE, "Target pixel size",
            type=QgsProcessingParameterNumber.Double, defaultValue=10.0, minValue=0.0001
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.RESAMPLING, "Resampling", options=self.RESAMPLING_OPTS, defaultValue=1
        ))
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT, "Area of interest / Clip extent", optional=True
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.CLIP, "Clip to extent", defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Output DEM (prepped)"
        ))

    def processAlgorithm(self, p, context, feedback):
        source_choice = self.parameterAsEnum(p, self.INPUT_SOURCE, context)
        crs = self.parameterAsCrs(p, self.TARGET_CRS, context)
        px  = self.parameterAsDouble(p, self.PIXEL_SIZE, context)
        res = {0:0, 1:1, 2:2}[self.parameterAsEnum(p, self.RESAMPLING, context)]
        ext = self.parameterAsExtent(p, self.EXTENT, context)
        clip= self.parameterAsBoolean(p, self.CLIP, context)

        # --- Fetch DEM depending on source ---
        if source_choice == 0:  # Local DEM
            dem = self.parameterAsRasterLayer(p, self.INPUT_DEM, context)
            if dem is None:
                raise QgsProcessingException("No DEM provided.")
            dem_path = dem.source()

        else:  # OpenTopography fetch
            if ext is None or ext.isEmpty():
                raise QgsProcessingException("Extent is required when fetching from OpenTopography.")

            # Choose DEM type
            demtype = "COP90" if source_choice == 1 else "COP30"

            url = (
                f"https://portal.opentopography.org/API/globaldem?"
                f"demtype={demtype}&west={ext.xMinimum()}&south={ext.yMinimum()}&"
                f"east={ext.xMaximum()}&north={ext.yMaximum()}&outputFormat=GTiff"
            )
            feedback.pushInfo(f"Requesting DEM from OpenTopography: {url}")

            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            tmpfile.close()

            r = requests.get(url, stream=True)
            if r.status_code != 200:
                raise QgsProcessingException(f"Failed to fetch DEM from OpenTopography: {r.text}")

            with open(tmpfile.name, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            dem_path = tmpfile.name

        # --- Reproject and resample ---
        warp = processing.run("gdal:warpreproject", {
            "INPUT": dem_path, "SOURCE_CRS": None, "TARGET_CRS": crs, "RESAMPLING": res,
            "NODATA": None, "TARGET_RESOLUTION": px, "OPTIONS": "", "DATA_TYPE": 0,
            "TARGET_EXTENT": None, "TARGET_EXTENT_CRS": None, "MULTITHREADING": True,
            "OUTPUT": "TEMPORARY_OUTPUT"
        }, context=context, feedback=feedback, is_child_algorithm=True)
        out = warp["OUTPUT"]

        # --- Clip if requested ---
        if clip and ext and not ext.isEmpty():
            res = processing.run("gdal:cliprasterbyextent", {
                "INPUT": out, "PROJWIN": ext, "NODATA": None, "OPTIONS": "", "DATA_TYPE": 0,
                "OUTPUT": p[self.OUTPUT]
            }, context=context, feedback=feedback, is_child_algorithm=True)
            return {self.OUTPUT: res["OUTPUT"]}

        # --- Otherwise just save ---
        res = processing.run("gdal:translate", {
            "INPUT": out, "TARGET_CRS": crs, "OUTPUT": p[self.OUTPUT]
        }, context=context, feedback=feedback, is_child_algorithm=True)
        return {self.OUTPUT: res["OUTPUT"]}

    def createInstance(self): 
        return AlgFetchDEM()

    def shortHelpString(self): 
        return (
            "Fetch and prepare a DEM.\n"
            "- Source: Local DEM or Copernicus 90m/30m via OpenTopography API.\n"
            "- Reproject and resample to the chosen CRS and pixel size.\n"
            "- Optionally clip to a rectangular AOI (extent).\n"
            "Note: For OpenTopography, you must provide an AOI extent."
        )
