# -*- coding: utf-8 -*-
"""
Fetch OpenStreetMap Data for Flood Vulnerability Assessment
Uses Overpass API to extract buildings, streets, and infrastructure
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterExtent, QgsProcessingParameterEnum,
    QgsProcessingParameterVectorDestination, QgsProcessingParameterBoolean,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields,
    QgsWkbTypes, QgsProject, QgsPointXY
)
from qgis import processing
import requests
import json
import os


class AlgFetchOSMData(QgsProcessingAlgorithm):
    """
    Fetch OpenStreetMap data for flood vulnerability assessment including:
    - Buildings (with type, height, levels, function)
    - Streets (with type, surface, bridge status)
    - Infrastructure (bridges, critical facilities)
    """

    # Parameter keys
    EXTENT = "EXTENT"
    DATA_TYPE = "DATA_TYPE"
    INCLUDE_ATTRIBUTES = "INCLUDE_ATTRIBUTES"
    OUTPUT = "OUTPUT"

    # Data type options
    DATA_TYPES = [
        "Buildings (all)",
        "Buildings (residential only)",
        "Buildings (commercial/industrial)",
        "Streets and Roads (all)",
        "Streets (major roads only)",
        "Bridges and Overpasses",
        "Critical Infrastructure (hospitals, schools, fire stations)",
        "All Data (comprehensive)"
    ]

    def name(self):
        return "fetch_osm_data"

    def displayName(self):
        return "Fetch OpenStreetMap Data"

    def group(self):
        return "Data Preparation"

    def groupId(self):
        return "data_preparation"

    def shortHelpString(self):
        return """
        <p><b>Fetch OpenStreetMap data for flood vulnerability assessment</b></p>

        <p>This algorithm uses the <b>Overpass API</b> to download OpenStreetMap data
        including buildings, streets, and infrastructure within your area of interest.</p>

        <h3>Features:</h3>
        <ul>
            <li><b>Buildings:</b> Includes type, height, levels, function, material</li>
            <li><b>Streets:</b> Includes road type, surface, width, bridge status</li>
            <li><b>Infrastructure:</b> Hospitals, schools, fire stations, bridges</li>
        </ul>

        <h3>Building Attributes:</h3>
        <ul>
            <li>building:type (residential, commercial, industrial, etc.)</li>
            <li>building:height (meters)</li>
            <li>building:levels (number of floors)</li>
            <li>building:material (brick, concrete, wood, etc.)</li>
            <li>amenity/shop (function)</li>
        </ul>

        <h3>Street Attributes:</h3>
        <ul>
            <li>highway type (motorway, primary, residential, etc.)</li>
            <li>surface (asphalt, concrete, unpaved, etc.)</li>
            <li>bridge (yes/no)</li>
            <li>width (meters)</li>
            <li>lanes (number)</li>
        </ul>

        <p><b>Note:</b> Large areas may take time to download. Consider splitting
        large regions into smaller chunks.</p>

        <p><b>API:</b> Uses Overpass API (https://overpass-api.de/)</p>
        """

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "Icons", "Data_Prep_Logo", "Assets.xcassets",
                                  "AppIcon.appiconset", "_", "32.png"))

    def createInstance(self):
        return AlgFetchOSMData()

    def initAlgorithm(self, config=None):
        """Define inputs and outputs"""

        # Extent parameter
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT,
            "Area of Interest (draw rectangle or use layer extent)",
            optional=False
        ))

        # Data type selection
        self.addParameter(QgsProcessingParameterEnum(
            self.DATA_TYPE,
            "Data Type to Fetch",
            options=self.DATA_TYPES,
            defaultValue=0
        ))

        # Detailed attributes
        self.addParameter(QgsProcessingParameterBoolean(
            self.INCLUDE_ATTRIBUTES,
            "Include all detailed attributes (height, levels, surface, etc.)",
            defaultValue=True
        ))

        # Output layer
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT,
            "Output Layer"
        ))

    def processAlgorithm(self, parameters, context, feedback):
        """Execute the algorithm"""

        # Get parameters
        extent = self.parameterAsExtent(parameters, self.EXTENT, context)
        data_type_idx = self.parameterAsEnum(parameters, self.DATA_TYPE, context)
        include_attributes = self.parameterAsBoolean(parameters, self.INCLUDE_ATTRIBUTES, context)

        # Validate extent is provided and not empty
        if extent is None or extent.isEmpty() or extent.isNull():
            raise QgsProcessingException(
                "Area of Interest is required.\n\n"
                "Please define an extent by:\n"
                "1. Drawing a rectangle on the map canvas, OR\n"
                "2. Using 'Calculate from Layer' to use a layer's extent, OR\n"
                "3. Entering coordinates manually\n\n"
                "The extent cannot be empty."
            )

        # Check for NaN/infinity values in extent (happens when extent is not properly set)
        # Note: Don't check geographic bounds here since input could be in any CRS
        import math
        try:
            coords = [extent.xMinimum(), extent.xMaximum(), extent.yMinimum(), extent.yMaximum()]
            if any(math.isnan(c) or math.isinf(c) for c in coords):
                raise ValueError("NaN or infinity in coordinates")
        except (ValueError, TypeError):
            raise QgsProcessingException(
                "Invalid extent coordinates detected.\n\n"
                "The extent appears to be empty or invalid. "
                "Please draw a rectangle on the map or select a valid extent."
            )

        # Transform extent to WGS84 (required by Overpass API)
        extent_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

        try:
            if extent_crs != wgs84:
                transform = QgsCoordinateTransform(extent_crs, wgs84, context.transformContext())
                extent_wgs84 = transform.transformBoundingBox(extent)
            else:
                extent_wgs84 = extent
        except Exception as e:
            raise QgsProcessingException(
                f"Failed to transform extent to WGS84: {str(e)}\n\n"
                "This usually happens when:\n"
                "1. No extent was selected (please draw a rectangle on the map)\n"
                "2. The extent coordinates are invalid or outside the valid range\n"
                "3. The source CRS cannot be transformed to WGS84\n\n"
                "Please ensure you have drawn a valid extent on the map canvas."
            )

        # Get bounding box coordinates with validation
        try:
            south = float(extent_wgs84.yMinimum())
            west = float(extent_wgs84.xMinimum())
            north = float(extent_wgs84.yMaximum())
            east = float(extent_wgs84.xMaximum())
        except (ValueError, TypeError) as e:
            raise QgsProcessingException(f"Invalid extent coordinates: {e}")

        # Validate coordinate ranges
        if not (-90 <= south <= 90 and -90 <= north <= 90):
            raise QgsProcessingException(f"Latitude out of range: south={south}, north={north}")
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            raise QgsProcessingException(f"Longitude out of range: west={west}, east={east}")

        # Validate extent is not inverted
        if south >= north or west >= east:
            raise QgsProcessingException("Invalid extent: coordinates appear inverted")

        # Limit area size to prevent API abuse (max 0.5 degrees square)
        area = (north - south) * (east - west)
        MAX_AREA = 0.5
        if area > MAX_AREA:
            raise QgsProcessingException(
                f"Area too large ({area:.4f}°²). Maximum: {MAX_AREA}°². "
                "Please use a smaller extent to avoid overloading the Overpass API."
            )

        feedback.pushInfo(f"Fetching OSM data for bbox: {south:.6f},{west:.6f},{north:.6f},{east:.6f}")
        feedback.pushInfo(f"Data type: {self.DATA_TYPES[data_type_idx]}")

        # Build Overpass query based on data type
        query = self._build_overpass_query(south, west, north, east, data_type_idx, feedback)

        # Fetch data from Overpass API
        feedback.pushInfo("Querying Overpass API...")
        osm_data = self._query_overpass(query, feedback)

        if not osm_data:
            raise QgsProcessingException("No data returned from Overpass API")

        # Convert OSM data to QGIS layer
        feedback.pushInfo("Converting OSM data to vector layer...")
        layer = self._create_vector_layer(
            osm_data,
            data_type_idx,
            include_attributes,
            extent_crs,
            feedback
        )

        if layer.featureCount() == 0:
            feedback.reportError("Warning: No features found in the specified area")

        feedback.pushInfo(f"Successfully fetched {layer.featureCount()} features")

        # Generate dynamic name for output
        data_type_short = self.DATA_TYPES[data_type_idx].replace(" (all)", "").replace(" (", "_").replace(")", "").replace(" ", "_")
        # Create area identifier from coordinates
        center_lat = (north + south) / 2
        center_lon = (east + west) / 2
        area_name = f"Lat{center_lat:.2f}_Lon{center_lon:.2f}".replace(".", "p").replace("-", "m")

        # Dynamic name format: "OSM_Buildings_Lat25p5_Lonm80p2"
        dynamic_name = f"OSM_{data_type_short}_{area_name}"

        # Set layer name
        try:
            layer.setName(dynamic_name)
            feedback.pushInfo(f"✓ Output layer named: {dynamic_name}")
        except:
            pass

        # Return the layer
        return {self.OUTPUT: layer.id()}

    def _build_overpass_query(self, south, west, north, east, data_type_idx, feedback):
        """Build Overpass QL query based on data type"""

        bbox = f"{south},{west},{north},{east}"
        data_type = self.DATA_TYPES[data_type_idx]

        # Base query structure
        query_parts = ["[out:json][timeout:90];", f"("]

        if data_type == "Buildings (all)":
            query_parts.append(f'  way["building"]({bbox});')
            query_parts.append(f'  relation["building"]({bbox});')

        elif data_type == "Buildings (residential only)":
            query_parts.append(f'  way["building"="residential"]({bbox});')
            query_parts.append(f'  way["building"="house"]({bbox});')
            query_parts.append(f'  way["building"="apartments"]({bbox});')
            query_parts.append(f'  relation["building"="residential"]({bbox});')

        elif data_type == "Buildings (commercial/industrial)":
            query_parts.append(f'  way["building"="commercial"]({bbox});')
            query_parts.append(f'  way["building"="retail"]({bbox});')
            query_parts.append(f'  way["building"="industrial"]({bbox});')
            query_parts.append(f'  way["building"="warehouse"]({bbox});')
            query_parts.append(f'  relation["building"="commercial"]({bbox});')
            query_parts.append(f'  relation["building"="industrial"]({bbox});')

        elif data_type == "Streets and Roads (all)":
            query_parts.append(f'  way["highway"]({bbox});')

        elif data_type == "Streets (major roads only)":
            query_parts.append(f'  way["highway"="motorway"]({bbox});')
            query_parts.append(f'  way["highway"="trunk"]({bbox});')
            query_parts.append(f'  way["highway"="primary"]({bbox});')
            query_parts.append(f'  way["highway"="secondary"]({bbox});')

        elif data_type == "Bridges and Overpasses":
            query_parts.append(f'  way["bridge"="yes"]({bbox});')
            query_parts.append(f'  way["man_made"="bridge"]({bbox});')

        elif data_type == "Critical Infrastructure (hospitals, schools, fire stations)":
            query_parts.append(f'  node["amenity"="hospital"]({bbox});')
            query_parts.append(f'  way["amenity"="hospital"]({bbox});')
            query_parts.append(f'  node["amenity"="school"]({bbox});')
            query_parts.append(f'  way["amenity"="school"]({bbox});')
            query_parts.append(f'  node["amenity"="fire_station"]({bbox});')
            query_parts.append(f'  way["amenity"="fire_station"]({bbox});')
            query_parts.append(f'  node["amenity"="police"]({bbox});')
            query_parts.append(f'  way["amenity"="police"]({bbox});')

        elif data_type == "All Data (comprehensive)":
            # Buildings
            query_parts.append(f'  way["building"]({bbox});')
            # Streets
            query_parts.append(f'  way["highway"]({bbox});')
            # Bridges
            query_parts.append(f'  way["bridge"="yes"]({bbox});')
            # Critical infrastructure
            query_parts.append(f'  node["amenity"~"hospital|school|fire_station|police"]({bbox});')
            query_parts.append(f'  way["amenity"~"hospital|school|fire_station|police"]({bbox});')

        query_parts.append(");")
        query_parts.append("out body;")
        query_parts.append(">;")
        query_parts.append("out skel qt;")

        query = "\n".join(query_parts)
        feedback.pushDebugInfo(f"Overpass query:\n{query}")
        return query

    def _query_overpass(self, query, feedback):
        """Query Overpass API and return JSON data"""

        overpass_url = "https://overpass-api.de/api/interpreter"

        # Add proper headers for identification and security
        headers = {
            'User-Agent': 'OSLRAT/0.2 (QGIS Plugin; +https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool)',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            feedback.pushInfo("Sending request to Overpass API...")
            response = requests.post(
                overpass_url,
                data={"data": query},
                headers=headers,
                timeout=120
            )
            response.raise_for_status()

            # Validate response content type
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                raise QgsProcessingException(
                    f"Unexpected response type: {content_type}. Expected JSON."
                )

            data = response.json()

            # Validate response structure
            if not isinstance(data, dict):
                raise QgsProcessingException("Invalid response structure from Overpass API")

            elements = data.get('elements', [])
            feedback.pushInfo(f"Received {len(elements)} elements")
            return data

        except requests.exceptions.Timeout:
            raise QgsProcessingException(
                "Request timed out after 120 seconds. Try a smaller area or simpler query."
            )
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            raise QgsProcessingException(
                f"HTTP error {status_code} from Overpass API. The service may be overloaded or temporarily unavailable."
            )
        except requests.exceptions.RequestException as e:
            raise QgsProcessingException(f"Network error querying Overpass API: {str(e)}")
        except json.JSONDecodeError as e:
            raise QgsProcessingException(f"Invalid JSON response from Overpass API: {str(e)}")

    def _create_vector_layer(self, osm_data, data_type_idx, include_attributes, target_crs, feedback):
        """Convert OSM JSON to QGIS vector layer"""

        elements = osm_data.get('elements', [])

        # Create node lookup for way geometry
        nodes = {elem['id']: elem for elem in elements if elem['type'] == 'node'}

        # Determine geometry type
        data_type = self.DATA_TYPES[data_type_idx]
        if "Buildings" in data_type or "Infrastructure" in data_type or "All Data" in data_type:
            geom_type = "Polygon"
        else:  # Streets, bridges
            geom_type = "LineString"

        # Create fields
        fields = QgsFields()
        fields.append(QgsField("osm_id", QVariant.String))
        fields.append(QgsField("osm_type", QVariant.String))
        fields.append(QgsField("name", QVariant.String))

        if include_attributes:
            # Building-specific fields
            if "Building" in data_type or "All Data" in data_type:
                fields.append(QgsField("building", QVariant.String))
                fields.append(QgsField("building_levels", QVariant.Int))
                fields.append(QgsField("height", QVariant.Double))
                fields.append(QgsField("roof_levels", QVariant.Int))
                fields.append(QgsField("building_material", QVariant.String))
                fields.append(QgsField("amenity", QVariant.String))
                fields.append(QgsField("shop", QVariant.String))

            # Street-specific fields
            if "Street" in data_type or "Bridge" in data_type or "All Data" in data_type:
                fields.append(QgsField("highway", QVariant.String))
                fields.append(QgsField("surface", QVariant.String))
                fields.append(QgsField("bridge", QVariant.String))
                fields.append(QgsField("width", QVariant.Double))
                fields.append(QgsField("lanes", QVariant.Int))
                fields.append(QgsField("maxspeed", QVariant.String))

            # Infrastructure fields
            if "Infrastructure" in data_type or "All Data" in data_type:
                fields.append(QgsField("amenity", QVariant.String))
                fields.append(QgsField("emergency", QVariant.String))
                fields.append(QgsField("healthcare", QVariant.String))

        # Create memory layer
        layer = QgsVectorLayer(f"{geom_type}?crs=EPSG:4326", "OSM_Data", "memory")
        provider = layer.dataProvider()
        provider.addAttributes(fields)
        layer.updateFields()

        # Add features
        features = []
        for elem in elements:
            if elem['type'] not in ['way', 'node']:
                continue

            # Skip nodes that are just part of ways (unless we're looking for point features)
            if elem['type'] == 'node' and 'tags' not in elem:
                continue

            feature = QgsFeature(fields)
            feature.setAttribute("osm_id", str(elem['id']))
            feature.setAttribute("osm_type", elem['type'])

            # Get tags
            tags = elem.get('tags', {})
            if 'name' in tags:
                feature.setAttribute("name", tags['name'])

            # Set geometry
            try:
                if elem['type'] == 'way':
                    # Build geometry from nodes
                    node_refs = elem.get('nodes', [])
                    if not node_refs:
                        continue  # Skip ways with no node references

                    points = []
                    for node_id in node_refs:
                        if node_id in nodes:
                            node = nodes[node_id]
                            # Validate node has required coordinates
                            if 'lon' in node and 'lat' in node:
                                try:
                                    points.append(QgsPointXY(float(node['lon']), float(node['lat'])))
                                except (ValueError, TypeError):
                                    feedback.pushWarning(f"Invalid coordinates for node {node_id}")
                                    continue
                        else:
                            # Node reference missing - common with incomplete OSM data
                            pass

                    if len(points) >= 2:
                        if geom_type == "Polygon" and points[0] == points[-1]:
                            # Closed way = polygon
                            feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
                        elif geom_type == "LineString":
                            feature.setGeometry(QgsGeometry.fromPolylineXY(points))

                elif elem['type'] == 'node':
                    # Point feature
                    feature.setGeometry(QgsGeometry.fromPointXY(
                        QgsPointXY(elem['lon'], elem['lat'])
                    ))

            except Exception as e:
                feedback.reportError(f"Error creating geometry for OSM element {elem['id']}: {str(e)}")
                continue

            # Set attributes
            if include_attributes:
                # Get list of available field names to check before setting
                field_names = [field.name() for field in fields]

                # Buildings
                if 'building' in tags and 'building' in field_names:
                    feature.setAttribute("building", tags['building'])
                if 'building:levels' in tags and 'building_levels' in field_names:
                    try:
                        feature.setAttribute("building_levels", int(tags['building:levels']))
                    except:
                        pass
                if 'height' in tags and 'height' in field_names:
                    try:
                        # Remove 'm' suffix if present
                        height_str = tags['height'].replace('m', '').strip()
                        feature.setAttribute("height", float(height_str))
                    except:
                        pass
                if 'roof:levels' in tags and 'roof_levels' in field_names:
                    try:
                        feature.setAttribute("roof_levels", int(tags['roof:levels']))
                    except:
                        pass
                if 'building:material' in tags and 'building_material' in field_names:
                    feature.setAttribute("building_material", tags['building:material'])
                if 'amenity' in tags and 'amenity' in field_names:
                    feature.setAttribute("amenity", tags['amenity'])
                if 'shop' in tags and 'shop' in field_names:
                    feature.setAttribute("shop", tags['shop'])

                # Streets
                if 'highway' in tags and 'highway' in field_names:
                    feature.setAttribute("highway", tags['highway'])
                if 'surface' in tags and 'surface' in field_names:
                    feature.setAttribute("surface", tags['surface'])
                if 'bridge' in tags and 'bridge' in field_names:
                    feature.setAttribute("bridge", tags['bridge'])
                if 'width' in tags and 'width' in field_names:
                    try:
                        width_str = tags['width'].replace('m', '').strip()
                        feature.setAttribute("width", float(width_str))
                    except:
                        pass
                if 'lanes' in tags and 'lanes' in field_names:
                    try:
                        feature.setAttribute("lanes", int(tags['lanes']))
                    except:
                        pass
                if 'maxspeed' in tags and 'maxspeed' in field_names:
                    feature.setAttribute("maxspeed", tags['maxspeed'])

                # Infrastructure
                if 'emergency' in tags and 'emergency' in field_names:
                    feature.setAttribute("emergency", tags['emergency'])
                if 'healthcare' in tags and 'healthcare' in field_names:
                    feature.setAttribute("healthcare", tags['healthcare'])

            if feature.hasGeometry():
                features.append(feature)

        provider.addFeatures(features)

        # Reproject to target CRS if needed
        if target_crs != QgsCoordinateReferenceSystem("EPSG:4326"):
            feedback.pushInfo(f"Reprojecting to {target_crs.authid()}...")
            params = {
                'INPUT': layer,
                'TARGET_CRS': target_crs,
                'OUTPUT': 'memory:'
            }
            result = processing.run("native:reprojectlayer", params, context=None, feedback=feedback)
            layer = result['OUTPUT']

        return layer

    def tr(self, string):
        return QCoreApplication.translate('AlgFetchOSMData', string)
