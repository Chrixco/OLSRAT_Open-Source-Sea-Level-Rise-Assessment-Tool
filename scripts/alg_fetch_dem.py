from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterCrs, QgsProcessingParameterNumber, QgsProcessingParameterExtent,
    QgsProcessingParameterEnum, QgsProcessingParameterBoolean, QgsProcessingParameterRasterDestination,
    QgsProcessingException, QgsCoordinateReferenceSystem, QgsProcessingParameterString,
    QgsCoordinateTransform, QgsRectangle, QgsProcessingUtils
)
from qgis.PyQt.QtGui import QIcon
from qgis import processing
import requests, tempfile, os

# Constants for coordinate conversions and limits
METERS_PER_DEGREE_AT_EQUATOR = 111320.0  # Approximate meters per degree latitude at equator
MAX_AREA_DEGREES_SQUARED = 5.0  # Maximum area for DEM downloads (degrees²)
WARNING_AREA_DEGREES_SQUARED = 0.5  # Threshold for large area warning
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB maximum download size
DOWNLOAD_TIMEOUT_SECONDS = 60  # HTTP request timeout
DOWNLOAD_CHUNK_SIZE = 8192  # Bytes to download per iteration

class AlgFetchDEM(QgsProcessingAlgorithm):
    DEM_TYPE     = "DEM_TYPE"
    EXTENT       = "EXTENT"
    TARGET_CRS   = "TARGET_CRS"
    PIXEL_SIZE   = "PIXEL_SIZE"
    RESAMPLING   = "RESAMPLING"
    CLIP         = "CLIP"
    API_KEY      = "API_KEY"
    OUTPUT       = "OUTPUT"

    DEM_TYPE_OPTS = ["Copernicus 90m (OpenTopography)", "Copernicus 30m (OpenTopography)"]
    RESAMPLING_OPTS = ["Nearest", "Bilinear", "Cubic"]

    def name(self): return "fetch_dem_prep"
    def displayName(self): return "Fetch DEM from OpenTopography"
    def group(self): return "Data Preparation"
    def groupId(self): return "data_preparation"

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Data_Prep_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.DEM_TYPE, "DEM Resolution", options=self.DEM_TYPE_OPTS, defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT, "Area of Interest (required - draw rectangle or enter coordinates)"
        ))
        self.addParameter(QgsProcessingParameterCrs(
            self.TARGET_CRS, "Target CRS", defaultValue=QgsCoordinateReferenceSystem("EPSG:3857")
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.PIXEL_SIZE, "Target pixel size (meters)",
            type=QgsProcessingParameterNumber.Double, defaultValue=30.0, minValue=0.0001
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.RESAMPLING, "Resampling method", options=self.RESAMPLING_OPTS, defaultValue=1
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.CLIP, "Clip to exact extent", defaultValue=True
        ))
        self.addParameter(QgsProcessingParameterString(
            self.API_KEY, "OpenTopography API Key (optional - get from opentopography.org)",
            optional=True, defaultValue=""
        ))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT, "Output DEM"
        ))

    def processAlgorithm(self, p, context, feedback):
        dem_type_choice = self.parameterAsEnum(p, self.DEM_TYPE, context)
        ext = self.parameterAsExtent(p, self.EXTENT, context)
        crs = self.parameterAsCrs(p, self.TARGET_CRS, context)
        px  = self.parameterAsDouble(p, self.PIXEL_SIZE, context)
        res = {0:0, 1:1, 2:2}[self.parameterAsEnum(p, self.RESAMPLING, context)]
        clip= self.parameterAsBoolean(p, self.CLIP, context)
        api_key = self.parameterAsString(p, self.API_KEY, context)

        # Convert pixel size to degrees if target CRS is geographic
        if crs.isGeographic():
            # User specified meters, convert to degrees using standard approximation
            px_degrees = px / METERS_PER_DEGREE_AT_EQUATOR
            feedback.pushWarning(
                f"Target CRS is geographic (degrees). Converting pixel size from {px}m to {px_degrees:.8f}°"
            )
            px = px_degrees

        # --- Validate extent is provided ---
        if ext is None or ext.isEmpty():
            raise QgsProcessingException(
                "Area of Interest is required. "
                "Please define an extent by drawing a rectangle on the map or entering coordinates."
            )

        # Transform extent to WGS84 (EPSG:4326) for OpenTopography API
        # The API requires lat/lon coordinates in degrees
        extent_crs = self.parameterAsExtentCrs(p, self.EXTENT, context)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

        if extent_crs != wgs84:
            try:
                transform = QgsCoordinateTransform(extent_crs, wgs84, context.transformContext())
                # Transform the extent to WGS84
                ext_wgs84 = transform.transformBoundingBox(ext)
            except Exception as e:
                raise QgsProcessingException(f"Failed to transform extent to WGS84: {str(e)}")
        else:
            ext_wgs84 = ext

        # Validate extent coordinates are valid numbers
        try:
            west = float(ext_wgs84.xMinimum())
            south = float(ext_wgs84.yMinimum())
            east = float(ext_wgs84.xMaximum())
            north = float(ext_wgs84.yMaximum())
        except (ValueError, TypeError):
            raise QgsProcessingException("Invalid extent coordinates.")

        # Validate extent is reasonable (not inverted or zero-size)
        if west >= east or south >= north:
            raise QgsProcessingException(
                "Invalid extent: coordinates appear inverted. "
                "Ensure west < east and south < north."
            )

        # Validate lat/lon bounds (OpenTopography global coverage)
        if west < -180 or east > 180 or south < -90 or north > 90:
            raise QgsProcessingException(
                f"Extent coordinates out of valid range.\n"
                f"Longitude must be -180 to 180, Latitude must be -90 to 90.\n"
                f"Got: west={west:.2f}, east={east:.2f}, south={south:.2f}, north={north:.2f}"
            )

        # Validate area size (hard limit for safety) - now in degrees
        width = east - west
        height = north - south
        area_deg = width * height

        # Check against maximum area limit
        if area_deg > MAX_AREA_DEGREES_SQUARED:
            raise QgsProcessingException(
                f"Area too large ({area_deg:.2f}°²). Maximum allowed: {MAX_AREA_DEGREES_SQUARED}°². "
                "Please use a smaller extent. For large areas, download tiles separately."
            )

        # Warn if moderately large
        if area_deg > WARNING_AREA_DEGREES_SQUARED:
            feedback.pushWarning(
                f"⚠ Large area requested ({area_deg:.2f}°²). Download may take several minutes."
            )

        feedback.pushInfo(f"Extent in WGS84: {west:.6f}, {south:.6f} to {east:.6f}, {north:.6f} ({area_deg:.4f}°²)")

        # Choose DEM type: 0=COP90, 1=COP30
        demtype = "COP90" if dem_type_choice == 0 else "COP30"

        # Sanitize API key (remove any whitespace, limit length)
        sanitized_api_key = ""
        if api_key and api_key.strip():
            sanitized_api_key = api_key.strip()[:100]  # Max 100 chars for safety
            # Basic validation: API keys are typically alphanumeric
            if not sanitized_api_key.replace('-', '').replace('_', '').isalnum():
                feedback.pushWarning(
                    "⚠ API key contains unusual characters. If download fails, "
                    "verify your API key from opentopography.org"
                )
            feedback.pushInfo("Using provided OpenTopography API key.")
        else:
            feedback.pushInfo(
                "No API key provided. Using free tier (limited to small areas, "
                "may have rate limits). Get a key at opentopography.org for larger areas."
            )

        # Build URL with sanitized coordinates
        base_url = "https://portal.opentopography.org/API/globaldem"
        params = {
            'demtype': demtype,
            'west': f"{west:.6f}",
            'south': f"{south:.6f}",
            'east': f"{east:.6f}",
            'north': f"{north:.6f}",
            'outputFormat': 'GTiff'
        }
        if sanitized_api_key:
            params['API_Key'] = sanitized_api_key

        # Use requests params for proper URL encoding
        feedback.pushInfo(f"Requesting DEM from OpenTopography ({demtype})...")
        feedback.setProgress(10)

        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
        tmpfile.close()

        try:
            # Add proper headers for identification
            headers = {
                'User-Agent': 'OSLRAT/0.2 (QGIS Plugin; +https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool)'
            }
            r = requests.get(base_url, params=params, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)

            if r.status_code == 429:
                raise QgsProcessingException(
                    "Rate limit exceeded. Please wait and try again, or provide an API key "
                    "from opentopography.org for higher limits."
                )
            elif r.status_code == 403:
                raise QgsProcessingException(
                    "Access denied. Area may be too large for free tier. "
                    "Try a smaller extent or use an API key from opentopography.org."
                )
            elif r.status_code != 200:
                raise QgsProcessingException(
                    f"Failed to fetch DEM from OpenTopography (HTTP {r.status_code}): {r.text[:200]}"
                )

            # Download with progress and size limits
            feedback.pushInfo("Downloading DEM...")
            feedback.setProgress(30)
            total_size = int(r.headers.get('content-length', 0))

            # Safety check: max file size
            if total_size > MAX_FILE_SIZE_BYTES:
                raise QgsProcessingException(
                    f"File too large ({total_size / 1024 / 1024:.1f} MB). "
                    f"Maximum allowed: {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB. "
                    "Please use a smaller extent."
                )

            downloaded = 0
            with open(tmpfile.name, "wb") as f:
                for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if feedback.isCanceled():
                        raise QgsProcessingException("Download canceled by user.")
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Secondary check during download
                    if downloaded > MAX_FILE_SIZE_BYTES:
                        raise QgsProcessingException(
                            "Download exceeded maximum file size. Operation aborted."
                        )

                    if total_size > 0:
                        progress = 30 + int((downloaded / total_size) * 40)
                        feedback.setProgress(min(progress, 70))

            feedback.pushInfo(f"✓ Downloaded DEM ({downloaded / 1024 / 1024:.2f} MB)")
            feedback.setProgress(75)

        except requests.exceptions.Timeout:
            raise QgsProcessingException(
                "Download timed out. Try a smaller extent or check your internet connection."
            )
        except requests.exceptions.RequestException as e:
            raise QgsProcessingException(f"Network error: {str(e)}")

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
            # Transform extent to target CRS for clipping
            extent_crs = self.parameterAsExtentCrs(p, self.EXTENT, context)
            if extent_crs != crs:
                transform = QgsCoordinateTransform(extent_crs, crs, context.transformContext())
                ext_target = transform.transformBoundingBox(ext)
            else:
                ext_target = ext

            res = processing.run("gdal:cliprasterbyextent", {
                "INPUT": out, "PROJWIN": ext_target, "NODATA": None, "OPTIONS": "", "DATA_TYPE": 0,
                "OUTPUT": p[self.OUTPUT]
            }, context=context, feedback=feedback, is_child_algorithm=True)

            # Generate dynamic name for clipped output
            dem_type_name = demtype.replace("COP", "Copernicus")
            center_lat = (north + south) / 2
            center_lon = (east + west) / 2
            area_name = f"Lat{center_lat:.2f}_Lon{center_lon:.2f}".replace(".", "p").replace("-", "m")
            dynamic_name = f"DEM_{dem_type_name}_{area_name}"

            # Set layer name
            try:
                output_layer = QgsProcessingUtils.mapLayerFromString(res["OUTPUT"], context)
                if output_layer:
                    output_layer.setName(dynamic_name)
                    feedback.pushInfo(f"✓ Output DEM named: {dynamic_name}")
            except Exception as e:
                feedback.pushDebugInfo(f"Could not set output layer name: {str(e)}")

            return {self.OUTPUT: res["OUTPUT"]}

        # --- Otherwise just save ---
        res = processing.run("gdal:translate", {
            "INPUT": out, "TARGET_CRS": crs, "OUTPUT": p[self.OUTPUT]
        }, context=context, feedback=feedback, is_child_algorithm=True)

        # Generate dynamic name for output
        dem_type_name = demtype.replace("COP", "Copernicus")  # "Copernicus90" or "Copernicus30"
        # Create area identifier from coordinates (center point)
        center_lat = (north + south) / 2
        center_lon = (east + west) / 2
        area_name = f"Lat{center_lat:.2f}_Lon{center_lon:.2f}".replace(".", "p").replace("-", "m")

        # Dynamic name format: "DEM_Copernicus90_Lat25p5_Lonm80p2"
        dynamic_name = f"DEM_{dem_type_name}_{area_name}"

        # Set layer name
        try:
            output_layer = QgsProcessingUtils.mapLayerFromString(res["OUTPUT"], context)
            if output_layer:
                output_layer.setName(dynamic_name)
                feedback.pushInfo(f"✓ Output DEM named: {dynamic_name}")
        except Exception as e:
            feedback.pushDebugInfo(f"Could not set output layer name: {str(e)}")

        return {self.OUTPUT: res["OUTPUT"]}

    def createInstance(self): 
        return AlgFetchDEM()

    def shortHelpString(self):
        return (
            "<h2>Fetch DEM from OpenTopography</h2>"
            "<p>Download global Digital Elevation Models directly from OpenTopography and prepare them for flood analysis.</p>"
            "<h3>DEM Options:</h3>"
            "<ul>"
            "<li><b>Copernicus 90m:</b> Global coverage at ~90m resolution</li>"
            "<li><b>Copernicus 30m:</b> Global coverage at ~30m resolution (larger file sizes)</li>"
            "</ul>"
            "<h3>Usage:</h3>"
            "<ol>"
            "<li>Select DEM resolution (90m or 30m)</li>"
            "<li>Draw or enter Area of Interest (AOI) - <b>required</b></li>"
            "<li>Choose target CRS and pixel size for output</li>"
            "<li>Optionally provide API key for larger areas</li>"
            "</ol>"
            "<h3>API Key (Optional):</h3>"
            "<p>Free tier allows small areas without API key but has rate limits. For larger areas:</p>"
            "<ol>"
            "<li>Register at <a href='https://opentopography.org'>opentopography.org</a></li>"
            "<li>Generate API key from your account settings</li>"
            "<li>Enter key in the API Key field</li>"
            "</ol>"
            "<h3>Limits:</h3>"
            "<ul>"
            "<li>Maximum area: 5°² (~555km × 555km at equator)</li>"
            "<li>Maximum file size: 500 MB</li>"
            "<li>For larger regions, download multiple tiles separately</li>"
            "</ul>"
            "<p><b>Data Source:</b> Copernicus DEM GLO-90/GLO-30 distributed by OpenTopography "
            "(<a href='https://doi.org/10.5069/G9028PQB'>doi:10.5069/G9028PQB</a>)</p>"
            "<p><b>Note:</b> Downloaded DEM is automatically reprojected and resampled to your specified settings.</p>"
        )
