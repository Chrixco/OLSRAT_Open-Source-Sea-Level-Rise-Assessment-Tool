# Dynamic Output Naming Guide
## OSLRAT Plugin - Intelligent Layer Naming System

**Implemented:** January 2025
**Status:** ✅ Active in v0.2+

---

## Overview

The OSLRAT plugin now implements **dynamic output naming** across all major algorithms. Instead of generic names like "Output" or "Reprojected", outputs are automatically named based on input parameters, making them instantly identifiable and better organized.

### Before vs. After

**Before (Generic Names):**
```
Output
Output_2
Output_3
Reprojected
Slope
DEM_1
```

**After (Dynamic Names):**
```
Flood_245_2050_p50
Flood_245_2100_p83_RP100
Buildings_3857_reprojected
Miami_slope
DEM_Copernicus90_Lat25p50_Lonm80p20
OSM_Buildings_Lat25p50_Lonm80p20
```

---

## Implementation Status

### ✅ Fully Implemented

| Algorithm Category | Count | Status |
|-------------------|-------|--------|
| **DEM Flood Scenarios** | 2 | ✅ Complete |
| **Terrain Analysis** | 3 | ✅ Complete |
| **Reprojection** | 1 | ✅ Complete |
| **Data Fetching** | 2 | ✅ Complete |
| **Total** | **8** | **✅** |

### 🔄 Remaining (Optional)

| Algorithm Category | Count | Priority |
|-------------------|-------|----------|
| Inundation Tools | 2 | Medium |
| Conversion Tools | 2 | Low |
| Comparison Tools | 3 | Medium |
| SVI/Population | 2 | Medium |
| **Total** | **9** | - |

---

## Naming Conventions by Algorithm

### 1. DEM Flood Scenario (AR6) ✅

**Format:** `Flood_{SSP}_{Year}_{Percentile}`

**Components:**
- `SSP`: Scenario code without "SSP" and punctuation (e.g., "245" from "SSP2-4.5")
- `Year`: 4-digit year (e.g., "2050")
- `Percentile`: Shorthand (e.g., "p50" from "p50 (median)")

**Examples:**
```
Flood_119_2030_p17  → SSP1-1.9, year 2030, p17 (likely lower)
Flood_245_2050_p50  → SSP2-4.5, year 2050, p50 (median)
Flood_585_2100_p95  → SSP5-8.5, year 2100, p95 (high)
```

**Implementation:**
```python
ssp_short = ssp_ui.replace("SSP", "").replace("-", "").replace(".", "")
pctl_short = pctl_ui.split()[0]
dynamic_name = f"Flood_{ssp_short}_{year_str}_{pctl_short}"
```

---

### 2. DEM Flood Scenario + CODEC ✅

**Format:** `Flood_{SSP}_{Year}_{Percentile}_{ReturnPeriod}`

**Additional Component:**
- `ReturnPeriod`: "RP" + year or "SLRonly" (e.g., "RP100" from "SLR + 100-yr")

**Examples:**
```
Flood_245_2050_p50_SLRonly  → SLR only, no return period
Flood_245_2050_p50_RP10     → SLR + 10-year return period
Flood_245_2050_p50_RP1000   → SLR + 1000-year return period
```

**Implementation:**
```python
rp_short = primary_label_fixed.replace("SLR + ", "RP").replace("-yr", "")
if rp_short == "SLR only":
    rp_short = "SLRonly"
dynamic_name = f"Flood_{ssp_short}_{year_str}_{pctl_short}_{rp_short}"
```

---

### 3. Vector Reprojection ✅

**Format:** `{LayerName}_{TargetCRS}_reprojected`

**Components:**
- `LayerName`: Cleaned input layer name (extensions removed)
- `TargetCRS`: EPSG code without "EPSG:" prefix

**Examples:**
```
Buildings_3857_reprojected     → Buildings to EPSG:3857
Parcels_4326_reprojected       → Parcels to WGS84
RoadNetwork_32618_reprojected  → Roads to UTM Zone 18N
```

**Implementation:**
```python
clean_name = input_name.replace('.shp', '').replace('.gpkg', '').replace('.geojson', '')
crs_code = tgt_crs.authid().replace("EPSG:", "").replace(":", "_")
dynamic_name = f"{clean_name}_{crs_code}_reprojected"
```

---

### 4. Terrain Analysis (Slope/Aspect/Hillshade) ✅

**Format:** `{DEMName}_{AnalysisType}`

**Components:**
- `DEMName`: Cleaned DEM layer name
- `AnalysisType`: "slope", "aspect", or "hillshade"

**Examples:**
```
Miami_slope      → Slope analysis of Miami DEM
NYC_aspect       → Aspect analysis of NYC DEM
Coastal_hillshade → Hillshade of Coastal DEM
```

**Implementation:**
```python
clean_name = input_name.replace('.tif', '').replace('.tiff', '').replace('_DEM', '').replace('DEM', '')
dynamic_name = f"{clean_name}_{analysis_type}"
```

---

### 5. Fetch DEM from OpenTopography ✅

**Format:** `DEM_{Resolution}_{Location}`

**Components:**
- `Resolution`: "Copernicus90" or "Copernicus30"
- `Location`: Lat/Lon of bbox center

**Coordinate Format:**
- Positive: `Lat25p50` (25.50°)
- Negative: `Lonm80p20` (-80.20°)
- Decimal point: "p"
- Negative sign: "m"

**Examples:**
```
DEM_Copernicus90_Lat25p50_Lonm80p20  → 90m DEM, Miami area
DEM_Copernicus30_Lat40p75_Lonm73p98  → 30m DEM, NYC area
DEM_Copernicus90_Latm34p05_Lon151p21 → 90m DEM, Sydney area
```

**Implementation:**
```python
dem_type_name = demtype.replace("COP", "Copernicus")
center_lat = (north + south) / 2
center_lon = (east + west) / 2
area_name = f"Lat{center_lat:.2f}_Lon{center_lon:.2f}".replace(".", "p").replace("-", "m")
dynamic_name = f"DEM_{dem_type_name}_{area_name}"
```

---

### 6. Fetch OSM Data ✅

**Format:** `OSM_{DataType}_{Location}`

**Components:**
- `DataType`: Simplified data type selection
- `Location`: Same as DEM fetch

**Examples:**
```
OSM_Buildings_Lat25p50_Lonm80p20
OSM_Streets_and_Roads_Lat40p75_Lonm73p98
OSM_Critical_Infrastructure_Lat34p05_Lonm118p25
```

**Implementation:**
```python
data_type_short = self.DATA_TYPES[data_type_idx].replace(" (all)", "").replace(" (", "_").replace(")", "").replace(" ", "_")
center_lat = (north + south) / 2
center_lon = (east + west) / 2
area_name = f"Lat{center_lat:.2f}_Lon{center_lon:.2f}".replace(".", "p").replace("-", "m")
dynamic_name = f"OSM_{data_type_short}_{area_name}"
```

---

## Implementation Pattern

All dynamic naming implementations follow this standard pattern:

### 1. Add Required Import

```python
from qgis.core import (..., QgsProcessingUtils)
```

### 2. Generate Dynamic Name

```python
# At the end of processAlgorithm(), before return statement
# Generate dynamic name based on input parameters
dynamic_name = f"OutputType_{param1}_{param2}"
```

### 3. Set Layer Name

```python
# For vector/raster outputs from processing.run()
try:
    output_layer = QgsProcessingUtils.mapLayerFromString(result["OUTPUT"], context)
    if output_layer:
        output_layer.setName(dynamic_name)
        feedback.pushInfo(f"✓ Output named: {dynamic_name}")
except:
    pass  # Naming is optional, don't fail algorithm

# For direct layer creation (memory layers, etc.)
try:
    layer.setName(dynamic_name)
    feedback.pushInfo(f"✓ Output named: {dynamic_name}")
except:
    pass
```

### 4. Return Output

```python
return {self.OUTPUT: output_id}
```

---

## Template for Remaining Algorithms

### Example: Inundation Algorithm

```python
def processAlgorithm(self, parameters, context, feedback):
    # ... existing algorithm code ...

    result = processing.run("some:algorithm", {...}, context=context, feedback=feedback)

    # Generate dynamic name
    dem_name = self.parameterAsRasterLayer(parameters, self.DEM, context).name()
    water_level = self.parameterAsDouble(parameters, self.WATER_LEVEL, context)
    clean_name = dem_name.replace('.tif', '').replace('_DEM', '')
    dynamic_name = f"{clean_name}_inundation_{water_level}m"

    # Set layer name
    try:
        output_layer = QgsProcessingUtils.mapLayerFromString(result["OUTPUT"], context)
        if output_layer:
            output_layer.setName(dynamic_name)
            feedback.pushInfo(f"✓ Output named: {dynamic_name}")
    except:
        pass

    return {self.OUTPUT: result["OUTPUT"]}
```

---

## Benefits

### For Users

✅ **Instant Identification** - Know what each layer is at a glance
✅ **Better Organization** - Easy to find specific scenarios/parameters
✅ **Professional Output** - Publication-ready naming conventions
✅ **Time Saving** - No manual renaming needed
✅ **Clear Workflow** - Parameters visible in layer name

### For Developers

✅ **Consistent Pattern** - Same approach across all algorithms
✅ **Easy to Implement** - Copy-paste template with parameter changes
✅ **Fail-Safe** - Naming errors don't crash algorithm
✅ **User Feedback** - Success message confirms naming
✅ **Maintainable** - Clear, self-documenting code

---

## Testing Checklist

When implementing dynamic naming for a new algorithm:

- [ ] Import `QgsProcessingUtils` added
- [ ] Dynamic name generated from input parameters
- [ ] Name cleaning implemented (remove extensions, special chars)
- [ ] Layer name set using `setName()`
- [ ] Try-except wraps naming code
- [ ] Success feedback message added
- [ ] Tested with various parameter combinations
- [ ] Verified name appears correctly in QGIS Layers Panel
- [ ] Checked name doesn't exceed reasonable length (~100 chars)
- [ ] Confirmed naming failure doesn't crash algorithm

---

## Best Practices

### Naming Format

1. **Use underscores** (`_`) for separators, not spaces or dashes
2. **Keep it concise** - Essential parameters only
3. **Use abbreviations** - "p50" not "percentile_50"
4. **Clean inputs** - Remove file extensions and redundant text
5. **Consistent order** - Same parameter order across similar algorithms

### Code Style

1. **Comment the format** - Show example in comment
2. **Use f-strings** - Modern, readable formatting
3. **Fail gracefully** - Bare `except:` for naming code only
4. **Provide feedback** - Use `feedback.pushInfo()` for success
5. **Keep it at the end** - Just before return statement

### Parameter Cleaning

```python
# Good practices for cleaning parameter values
ssp = "SSP2-4.5" → "245"  # Remove prefix, punctuation
crs = "EPSG:3857" → "3857"  # Extract code only
name = "layer.shp" → "layer"  # Remove extension
coord = -80.25 → "m80p25"  # Handle negative and decimal
```

---

## Future Enhancements

### Planned

- [ ] User preference for naming format (short vs. verbose)
- [ ] Custom naming templates in settings
- [ ] Automatic layer styling based on name pattern
- [ ] Layer grouping by name prefix

### Ideas

- Smart truncation for very long names
- Name collision detection and auto-numbering
- Export naming scheme to metadata
- Integration with project naming conventions

---

## Troubleshooting

### Issue: Output layer not named

**Cause:** Layer string not found by `QgsProcessingUtils.mapLayerFromString()`

**Solution:** Check output is being added to project. For temporary outputs, may need different approach.

### Issue: Name too long

**Cause:** Too many parameters or verbose naming

**Solution:** Use abbreviations, limit precision of floats, drop less important parameters

### Issue: Invalid characters in name

**Cause:** Special characters from input names

**Solution:** Add more `.replace()` calls to clean input names

### Issue: Name collision

**Cause:** Multiple outputs with same parameters

**Solution:** Add timestamp or sequence number: `f"{dynamic_name}_{int(time.time())}"`

---

## Examples in Practice

### Research Project Workflow

```
Study Area: Miami Beach, FL
Analysis: SLR flooding under various scenarios

Outputs:
├── DEM_Copernicus90_Lat25p79_Lonm80p13
├── OSM_Buildings_Lat25p79_Lonm80p13
├── Flood_245_2050_p50
├── Flood_245_2050_p83
├── Flood_245_2100_p50
├── Flood_245_2100_p83
├── Flood_585_2050_p50
├── Flood_585_2100_p50
├── Miami_slope
├── Miami_aspect
└── Miami_hillshade
```

Clear, organized, immediately understandable! 🎯

---

## Support

For questions or issues with dynamic naming:
- GitHub Issues: https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool/issues
- Documentation: See this guide

---

**Last Updated:** January 2025
**Version:** 0.2+
**Status:** Active Development
