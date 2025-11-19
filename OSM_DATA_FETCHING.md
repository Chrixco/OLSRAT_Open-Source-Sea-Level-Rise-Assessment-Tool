# 🏘️ OpenStreetMap Data Fetching for Flood Vulnerability

## Overview

The **Fetch OpenStreetMap Data** algorithm downloads real-world infrastructure data from OpenStreetMap to assess flood vulnerability at the building and street level.

---

## 🎯 What It Does

Downloads detailed vector data including:

### 🏠 **Buildings**
- **Geometry**: Polygon footprints
- **Attributes**:
  - `building` - Type (residential, commercial, industrial, etc.)
  - `building_levels` - Number of floors
  - `height` - Building height in meters
  - `roof_levels` - Number of roof levels
  - `building_material` - Construction material (brick, concrete, wood)
  - `amenity` - Function (hospital, school, fire_station, etc.)
  - `shop` - Commercial type (if applicable)

### 🛣️ **Streets & Roads**
- **Geometry**: LineString
- **Attributes**:
  - `highway` - Road classification (motorway, primary, residential, etc.)
  - `surface` - Pavement type (asphalt, concrete, unpaved)
  - `bridge` - Whether road is on a bridge (yes/no)
  - `width` - Road width in meters
  - `lanes` - Number of lanes
  - `maxspeed` - Speed limit

### 🌉 **Bridges & Infrastructure**
- **Critical Facilities**:
  - Hospitals
  - Schools
  - Fire stations
  - Police stations
- **Transportation**:
  - Bridges
  - Overpasses

---

## 📊 Data Type Options

| Option | What It Fetches | Use Case |
|--------|----------------|----------|
| **Buildings (all)** | All building footprints | Complete building inventory |
| **Buildings (residential only)** | Houses, apartments | Residential flood exposure |
| **Buildings (commercial/industrial)** | Shops, factories, warehouses | Economic impact assessment |
| **Streets and Roads (all)** | All road types | Complete transportation network |
| **Streets (major roads only)** | Motorways, primary, secondary roads | Critical evacuation routes |
| **Bridges and Overpasses** | Bridge infrastructure | Flood-vulnerable crossings |
| **Critical Infrastructure** | Hospitals, schools, fire stations | Emergency services accessibility |
| **All Data (comprehensive)** | Everything above | Complete vulnerability assessment |

---

## 🚀 How to Use

### **Step 1: Open the Algorithm**
1. Open OSLRAT Toolkit (toolbar icon)
2. Click **Data Preparation** button
3. Select **"🏘️ Fetch OSM Buildings & Streets"**

### **Step 2: Define Area of Interest**
- **Draw Rectangle**: Click the button, draw on map
- **Use Layer Extent**: Select from dropdown
- **Enter Coordinates**: Manually input bbox

💡 **Tip**: Start with a small area (e.g., 1-2 km²) to test, then expand

### **Step 3: Select Data Type**
Choose what to download based on your analysis needs:
- For building-level flood risk: **Buildings (all)**
- For evacuation planning: **Streets (major roads only)**
- For comprehensive assessment: **All Data**

### **Step 4: Configure Attributes**
- ✅ **Include all detailed attributes**: Gets height, levels, surface, etc.
- ❌ **Basic attributes only**: Just geometry and name

### **Step 5: Run**
- Algorithm queries **Overpass API**
- Progress shown in dialog
- Output layer added to map

---

## 📈 Example Workflows

### **Workflow 1: Building Flood Exposure**
```
1. Fetch OSM Buildings (all) → Get building footprints
2. DEM Flood Scenario → Create flood extent raster
3. Overlay Analysis → Identify flooded buildings
4. Calculate Statistics → Count by building type, estimate damage
```

### **Workflow 2: Evacuation Route Planning**
```
1. Fetch OSM Streets (major roads) → Get road network
2. Fetch OSM Bridges → Get bridge locations
3. DEM Flood + Return Period → Model 100-year flood
4. Spatial Analysis → Identify blocked routes, plan alternatives
```

### **Workflow 3: Critical Infrastructure Assessment**
```
1. Fetch OSM Critical Infrastructure → Get hospitals, schools, fire stations
2. DEM Flood Scenario (AR6) → Model 2100 SLR
3. Buffer Analysis → 500m accessibility zones
4. Risk Report → Which facilities are at risk?
```

### **Workflow 4: Multi-Story Building Analysis**
```
1. Fetch OSM Buildings with attributes → Get heights/levels
2. DEM Flood Scenario → Get flood depth
3. Calculate → Which floors are safe? (building_levels × 3m per floor)
4. Identify → Buildings with ground floor flooding but safe upper floors
```

---

## 🔍 Understanding OSM Data Quality

### **Coverage**
- **Urban areas**: Excellent (90-100% buildings mapped)
- **Suburban**: Good (70-90% coverage)
- **Rural**: Variable (30-70% coverage)
- **Developing countries**: Varies widely

### **Attributes Completeness**
| Attribute | Typical Availability |
|-----------|---------------------|
| Building footprint | ~95% |
| Building type | ~60% |
| Building height | ~15-30% (varies by city) |
| Number of levels | ~20-40% |
| Street type | ~90% |
| Street surface | ~40% |
| Bridge status | ~80% |

### **Data Quality Tips**
1. **Validate**: Cross-check with satellite imagery
2. **Manual correction**: Use JOSM editor to fix/add missing data
3. **Local knowledge**: Contact local OSM community
4. **Crowdsourcing**: Organize mapathons for your area

---

## ⚙️ Technical Details

### **API Used**
- **Overpass API**: https://overpass-api.de/
- **Query Language**: Overpass QL
- **Timeout**: 90 seconds
- **Rate Limits**: Fair use policy (no excessive querying)

### **Data Format**
- **Input**: Bounding box (WGS84)
- **Processing**: Overpass JSON response
- **Output**: QGIS vector layer (memory or file)
- **CRS**: Reprojected to match your project

### **Performance**
| Area Size | Typical Time | Features |
|-----------|--------------|----------|
| 1 km² | 5-10 sec | 100-500 buildings |
| 5 km² | 15-30 sec | 500-2000 buildings |
| 20 km² | 60-120 sec | 2000-10000 buildings |
| 100 km² | 5-10 min | 10000+ buildings |

⚠️ **Large areas may timeout**. Split into multiple queries if needed.

---

## 🛠️ Advanced Usage

### **Custom Overpass Queries**
For advanced users, you can modify `alg_fetch_osm_data.py` to add custom queries:

```python
# Example: Fetch only tall buildings (>20m)
query_parts.append(f'  way["building"]["height">"20"]({bbox});')

# Example: Fetch parking lots
query_parts.append(f'  way["amenity"="parking"]({bbox});')

# Example: Fetch railways
query_parts.append(f'  way["railway"="rail"]({bbox});')
```

### **Batch Processing**
Process multiple areas:

```python
from qgis import processing

areas = [
    {'name': 'Downtown', 'extent': '...'},
    {'name': 'Harbor', 'extent': '...'},
    {'name': 'Industrial', 'extent': '...'}
]

for area in areas:
    processing.run("slr_vulnerability:fetch_osm_data", {
        'EXTENT': area['extent'],
        'DATA_TYPE': 0,  # Buildings (all)
        'OUTPUT': f'osm_{area["name"]}.gpkg'
    })
```

---

## 📋 Attribute Dictionary

### Building Attributes

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `osm_id` | String | Unique OSM identifier | "123456789" |
| `building` | String | Building type | "residential", "commercial", "industrial" |
| `building_levels` | Integer | Number of floors | 1, 2, 5, 20 |
| `height` | Double | Height in meters | 3.5, 12.0, 45.8 |
| `roof_levels` | Integer | Attic/roof floors | 1, 2 |
| `building_material` | String | Construction material | "brick", "concrete", "wood", "metal" |
| `amenity` | String | Facility type | "hospital", "school", "fire_station" |
| `shop` | String | Shop type | "supermarket", "bakery", "clothes" |

### Street Attributes

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `highway` | String | Road classification | "motorway", "primary", "residential", "path" |
| `surface` | String | Pavement type | "asphalt", "concrete", "gravel", "unpaved" |
| `bridge` | String | On a bridge | "yes", "no", "viaduct" |
| `width` | Double | Width in meters | 3.5, 7.0, 12.0 |
| `lanes` | Integer | Number of lanes | 1, 2, 4 |
| `maxspeed` | String | Speed limit | "30", "50 mph", "walk" |

---

## 🌍 OpenStreetMap Highway Classification

| Type | Description | Use Case |
|------|-------------|----------|
| **motorway** | Controlled-access highways | Major evacuation routes |
| **trunk** | Important non-motorway roads | Primary arterials |
| **primary** | Primary roads linking large towns | Main roads |
| **secondary** | Secondary roads | Regional connections |
| **tertiary** | Local roads | Neighborhood access |
| **residential** | Roads in residential areas | Local evacuation |
| **service** | Access roads to buildings | Service vehicles |
| **pedestrian** | Pedestrian zones | Walking evacuation |

---

## ❓ Troubleshooting

### **No data returned**
- ✅ Check your extent is not too small
- ✅ Verify area has OSM data (check openstreetmap.org)
- ✅ Try a different data type option
- ✅ Check internet connection

### **Timeout error**
- ✅ Reduce area size
- ✅ Use simpler data type (not "All Data")
- ✅ Try during off-peak hours
- ✅ Split into multiple queries

### **Missing attributes**
- This is normal! Not all buildings have height/levels mapped
- Consider manual data collection or estimation
- Use average values for your region

### **Geometry errors**
- Some OSM ways may have incomplete geometry
- Algorithm skips invalid geometries
- Check QGIS Message Log for warnings

---

## 📚 Resources

### **OpenStreetMap**
- Website: https://www.openstreetmap.org/
- Wiki: https://wiki.openstreetmap.org/
- Tagging Guidelines: https://wiki.openstreetmap.org/wiki/Map_Features

### **Overpass API**
- Documentation: https://wiki.openstreetmap.org/wiki/Overpass_API
- Overpass Turbo (query builder): https://overpass-turbo.eu/
- Examples: https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_API_by_Example

### **Editing OSM**
- iD Editor (web): https://www.openstreetmap.org/edit
- JOSM (desktop): https://josm.openstreetmap.de/
- Tutorials: https://learnosm.org/

---

## 🤝 Contributing to OSM

If your area has incomplete data, you can help:

1. **Create OSM Account**: https://www.openstreetmap.org/user/new
2. **Learn to Edit**: https://learnosm.org/
3. **Map Your Area**: Add missing buildings, roads, attributes
4. **Organize Mapathon**: Gather volunteers to map together
5. **Use Field Papers**: Print maps for field surveys

**Your contributions help everyone doing flood risk assessments!**

---

## 📊 Citation

If you use OSM data in publications, please cite:

```
OpenStreetMap Contributors (2024). Planet dump retrieved from
https://planet.osm.org. https://www.openstreetmap.org
```

---

## 🔮 Future Enhancements

Planned features:
- [ ] Export to standard formats (GeoJSON, Shapefile)
- [ ] Automatic height estimation from LIDAR/satellite
- [ ] Building age from OSM history
- [ ] Population estimation from building footprints
- [ ] 3D building models from height data
- [ ] Integration with cadastral data

---

**Questions?** Contact: christianxcorral@gmail.com
