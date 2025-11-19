# 🖥️ OSLRAT Cross-Platform Testing Guide

## Platform Support Status

| Platform | Status | Tested Version | Notes |
|----------|--------|----------------|-------|
| **macOS** | ✅ Working | Sonoma 14.x+ | Primary development platform |
| **Windows** | ⚠️ Needs Testing | 10/11 | Menu positioning adjusted |
| **Linux** | ⚠️ Needs Testing | Ubuntu 20.04+ | Should work like macOS |

---

## 🔍 Platform-Specific Considerations

### **macOS**
- **Menu Positioning**: Uses `bottomLeft()` positioning
- **File Paths**: Forward slashes `/` (native)
- **Qt Styling**: Native macOS look-and-feel
- **QGIS Location**: `/Applications/QGIS.app/Contents/MacOS/`
- **Plugin Directory**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

**Known Issues:**
- None reported

### **Windows**
- **Menu Positioning**: Added +2px Y offset to prevent overlap
- **File Paths**: Backslashes `\` (handled by `os.path.join`)
- **Qt Styling**: Native Windows look-and-feel
- **QGIS Location**: `C:\Program Files\QGIS 3.x\`
- **Plugin Directory**: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`

**Potential Issues:**
- Menu positioning may need fine-tuning
- File dialog filters syntax
- Icon loading from resources

### **Linux**
- **Menu Positioning**: Same as macOS (bottomLeft)
- **File Paths**: Forward slashes `/` (native)
- **Qt Styling**: Varies by desktop environment
- **QGIS Location**: `/usr/bin/qgis` or `/usr/local/bin/qgis`
- **Plugin Directory**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

**Potential Issues:**
- Different desktop environments (KDE, GNOME, XFCE) may render differently
- Qt theme consistency

---

## ✅ Testing Checklist

### **Installation & Loading**

- [ ] Plugin installs without errors
- [ ] Plugin appears in Plugin Manager
- [ ] Plugin checkbox stays checked after closing Plugin Manager
- [ ] No Python errors in QGIS Message Log during load
- [ ] Processing provider "OSLRAT" appears in Processing Toolbox

### **GUI Functionality**

- [ ] **Main Toolbar**
  - [ ] OSLRAT icon appears in toolbar
  - [ ] Clicking icon opens GUI window
  - [ ] Icon displays correctly (not broken/placeholder)

- [ ] **Plugin Window**
  - [ ] Window opens centered on screen
  - [ ] Gradient header displays correctly
  - [ ] Logo/icon displays in header
  - [ ] All text is readable (no overflow)
  - [ ] Window is resizable
  - [ ] Close button works

- [ ] **Category Buttons**
  - [ ] All 5 category buttons visible
  - [ ] Icons display correctly on each button
  - [ ] Button hover effect works
  - [ ] Button colors match theme

- [ ] **Dropdown Menus**
  - [ ] Click button → menu appears below button
  - [ ] Menu items are readable and styled correctly
  - [ ] Hovering over menu items highlights them
  - [ ] Clicking menu item opens Processing dialog
  - [ ] Menu closes properly after selection
  - [ ] Menu closes when clicking outside

### **Algorithm Execution**

Test at least one algorithm from each category:

#### Data Preparation
- [ ] **Fetch DEM**
  - [ ] Dialog opens
  - [ ] Extent selector works (draw rectangle on map)
  - [ ] API key field accepts input
  - [ ] File save dialog works (cross-platform paths)
  - [ ] Algorithm runs without errors

- [ ] **Reproject Vector**
  - [ ] Input layer dropdown works
  - [ ] CRS selector works
  - [ ] Output path selector works

#### Flood Mapping
- [ ] **DEM Flood Scenario (AR6)**
  - [ ] DEM input selector works
  - [ ] AOI polygon selector works
  - [ ] Scenario dropdown works (SSP1-1.9, etc.)
  - [ ] Year selector works (2020-2150)
  - [ ] Percentile selector works (p50, p17, etc.)
  - [ ] Algorithm finds CSV file in `Data/` folder
  - [ ] Output raster and AOI stats generated

#### Social Analysis
- [ ] **Social Vulnerability Index**
  - [ ] Dialog opens
  - [ ] Field selectors work

#### Terrain Analysis
- [ ] **Slope/Aspect/Hillshade**
  - [ ] Dialog opens
  - [ ] Algorithm runs on sample DEM

#### Visualization
- [ ] **Interactive Dashboard**
  - [ ] Dashboard opens (if matplotlib installed)
  - [ ] Charts display correctly
  - [ ] Interactive elements work

### **File I/O Operations**

- [ ] **File Open Dialogs**
  - [ ] Browse button opens native file dialog
  - [ ] File filters work (e.g., "*.tif" for rasters)
  - [ ] Selected files load correctly
  - [ ] Paths with spaces work
  - [ ] Non-ASCII characters in paths work (if applicable)

- [ ] **File Save Dialogs**
  - [ ] Browse button opens save dialog
  - [ ] Default filename appears
  - [ ] Extension added automatically
  - [ ] Overwrite confirmation works
  - [ ] Files save to correct location

### **Data Access**

- [ ] **CSV Data Files**
  - [ ] `Data/slr_ipcc_ar6_sea_level_projection_global_total.csv` readable
  - [ ] CODEC CSV files readable
  - [ ] No path encoding issues

- [ ] **NetCDF Files**
  - [ ] CODEC NetCDF file opens without errors

### **Error Handling**

- [ ] **Missing Inputs**
  - [ ] Algorithm shows error if required input missing
  - [ ] Error message is clear and helpful

- [ ] **Invalid Inputs**
  - [ ] Algorithm validates CRS compatibility
  - [ ] Algorithm validates extent bounds
  - [ ] Error messages displayed properly

- [ ] **Missing Dependencies**
  - [ ] Clear error if matplotlib not installed (visualization)
  - [ ] Clear error if requests not installed (DEM fetch)

---

## 🐛 How to Report Issues

If you encounter issues on **Windows** or **Linux**, please report with:

### Required Information
1. **Platform Details**
   - OS: Windows 10/11, Ubuntu 22.04, etc.
   - Architecture: 64-bit / ARM
   - QGIS Version: e.g., 3.34.1
   - Python Version: (in QGIS Python Console: `import sys; print(sys.version)`)

2. **Issue Description**
   - What were you trying to do?
   - What happened?
   - What did you expect to happen?

3. **QGIS Message Log**
   - View → Panels → Log Messages
   - Select "OSLRAT" tab
   - Copy all messages
   - Include in report

4. **Screenshots** (if GUI issue)
   - Screenshot of the problem
   - Screenshot of QGIS Message Log

### Where to Report
- **GitHub Issues**: https://github.com/Chrixco/OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool/issues
- **Email**: christianxcorral@gmail.com (for sensitive issues)

---

## 🔧 Platform-Specific Fixes Applied

### Menu Interaction (All Platforms)
- ✅ Menu now parented to button widget: `QMenu(btn)`
- ✅ Comprehensive error handling with try-except
- ✅ Detailed logging for diagnostics
- ✅ Platform detection: macOS, Windows, Linux

### Windows-Specific
- ✅ Added +2px Y offset for menu positioning
- ✅ File paths use `os.path.join()` (handles backslashes)
- ✅ Platform logged in messages for debugging

### macOS-Specific
- ✅ Uses standard `bottomLeft()` positioning
- ✅ Native menu styling

### Linux-Specific
- ✅ Same positioning as macOS
- ✅ Should work across different desktop environments

---

## 📝 Testing Commands

### Check Platform Detection
```python
# Run in QGIS Python Console
import platform
print(f"System: {platform.system()}")
print(f"Release: {platform.release()}")
print(f"Machine: {platform.machine()}")
```

### Check Plugin Loading
```python
# Run in QGIS Python Console
from qgis.core import QgsApplication
reg = QgsApplication.processingRegistry()
provider = reg.providerById('slr_vulnerability')
print(f"Provider loaded: {provider is not None}")
if provider:
    print(f"Algorithms: {len(list(provider.algorithms()))}")
```

### Check File Paths
```python
# Run in QGIS Python Console
import os
plugin_dir = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Roaming", "QGIS", "QGIS3", "profiles", "default", "python", "plugins", "OSLRAT"
)  # Windows

# Or for macOS:
plugin_dir = os.path.expanduser("~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/OSLRAT")

print(f"Plugin dir exists: {os.path.exists(plugin_dir)}")
print(f"metadata.txt exists: {os.path.exists(os.path.join(plugin_dir, 'metadata.txt'))}")
```

---

## ✨ Version History

- **v0.1** - Initial release (tested on macOS)
- **v0.1.1** - Added Windows menu positioning fix
- **v0.1.2** - Enhanced cross-platform logging

---

## 🤝 Volunteer Testers Wanted!

If you have access to **Windows** or **Linux** and can help test this plugin:

1. Install QGIS 3.30+
2. Install the plugin
3. Run through the testing checklist
4. Report results (working ✅ or issues ❌)

**Your help ensures this tool works for everyone!** 🌍
