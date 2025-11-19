# 🌊 OLSRAT_Open-Source-Sea-Level-Rise-Assessment-Tool

[![QGIS](https://img.shields.io/badge/QGIS-3.30+-green.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)

A professional QGIS plugin for mapping **sea-level rise (SLR) vulnerability** and **flood exposure** in coastal and delta regions. Integrates cutting-edge climate science with spatial analysis for evidence-based adaptation planning.

![SLR Vulnerability Mapper](https://via.placeholder.com/800x400?text=Add+Screenshot+Here)

---

## 🎯 Features

### 🌍 Climate Science Integration
- **IPCC AR6 (2021)** global mean sea-level projections
- **FACTS Framework (2023)** for parametric & structural uncertainty
- **CODEC** return period datasets for storm surge & tide extremes
- Scenarios: SSP1-1.9, SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5

### 🗺️ Spatial Analysis Tools
- **DEM-based inundation mapping** with customizable water levels
- **Polygon-based flood exposure** analysis (parcel/building-level)
- **Point-based flood mapping** with 2D/3D visualization
- **Heatmap generation** for flood risk hotspots

### 📊 Vulnerability Assessment
- **Social Vulnerability Index (SVI)** calculator
- Integration with census and demographic data
- Multi-indicator composite scoring

### 🛠️ Data Preparation
- **OpenTopography DEM fetching** (Copernicus 30m/90m)
- Vector ↔ Raster conversion tools
- Automated CRS reprojection
- Terrain analysis (slope, aspect, hillshade)

---

## 📥 Installation

### From QGIS Plugin Repository (Recommended)
1. Open QGIS
2. Go to **Plugins → Manage and Install Plugins**
3. Search for "SLR Vulnerability Mapper"
4. Click **Install Plugin**

### Manual Installation
1. Download the latest release from [GitHub Releases](https://github.com/christianxcorral/slr_vulnerability_mapper/releases)
2. Extract the ZIP file to your QGIS plugins directory:
   - **Windows:** `C:\Users\<YourName>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS
4. Enable the plugin in **Plugins → Manage and Install Plugins**

---

## 🚀 Quick Start

### Option 1: Use the Toolkit GUI
1. Click the **SLR Vulnerability Mapper** icon in the toolbar
2. Choose a category: **Data Preparation**, **Flood Mapping**, **Social Analysis**, or **Terrain Analysis**
3. Select an algorithm from the dropdown menu
4. Configure parameters and run

### Option 2: Use Processing Toolbox
1. Open **Processing → Toolbox**
2. Find **SLR Vulnerability** provider
3. Expand to see all algorithms organized by category
4. Double-click to open algorithm dialog

---

## 📖 Example Workflows

### Workflow 1: Basic Flood Exposure Mapping
```
1. Fetch DEM → Select OpenTopography Copernicus 90m for your region
2. DEM Flood Scenario (AR6) → Choose SSP2-4.5, year 2100, median (p50)
3. Inundation Mapping → Apply custom water level if needed
4. Visualize results → Binary flood raster + AOI statistics
```

### Workflow 2: Advanced Vulnerability Assessment
```
1. Fetch DEM + Prepare AOI polygons (census tracts/parcels)
2. DEM Flood + Return Period (CODEC) → Combine SLR + storm surge
3. Social Vulnerability Index → Calculate SVI from demographic data
4. Overlay Analysis → Identify high-risk, high-vulnerability areas
```

### Workflow 3: Point-Based Visualization
```
1. Fetch DEM for coastal area
2. Point Flooding → Generate regular grid of flood points
3. Flood Heatmap → Visualize spatial density of flood risk
4. Export to 3D → Use Point Z output in QGIS 3D view
```

---

## 📚 Data Sources & Citations

### Sea-Level Rise Projections
- **IPCC AR6 (2021)** - Sixth Assessment Report, Working Group I
  - Citation: *IPCC, 2021: Climate Change 2021: The Physical Science Basis*
  - [Download Report](https://www.ipcc.ch/report/ar6/wg1/)

- **FACTS Framework (2023)** - Framework for Assessing Changes To Sea-level
  - Citation: *Kopp et al., 2023, Earth's Future*
  - [Project Website](https://github.com/radical-collaboration/facts)

### Extreme Sea Levels
- **CODEC** - Coastal Dataset for Evaluating Extremes
  - Citation: *Dullaart et al., 2020, Journal of Marine Science and Engineering*
  - Return periods: 1-yr, 10-yr, 50-yr, 100-yr, 1000-yr
  - [Dataset Portal](https://data.4tu.nl/collections/CODEC_dataset/5171187)

### Elevation Data
- **Copernicus DEM** - 30m and 90m global coverage
  - Via OpenTopography API
  - [OpenTopography](https://opentopography.org/)

---

## 🛠️ Technical Details

### Requirements
- **QGIS:** 3.30 or higher
- **Python:** 3.9+
- **Dependencies:** NumPy, Pandas, GDAL (included with QGIS)
- **Optional:** Internet connection for DEM fetching

### Processing Algorithms (14 total)

#### Data Preparation (4)
- Fetch DEM (OpenTopography)
- Reproject Vector
- Vector to Raster
- Raster to Vector

#### Flood Exposure (6)
- DEM Flood Scenario (AR6 projections)
- DEM Flood + Return Period (CODEC integration)
- Inundation Mapping (custom water level)
- Point Flooding (grid-based)
- Flood Heatmap
- IPCC Flood Scenarios (batch polygon processing)

#### Social Analysis (1)
- Social Vulnerability Index (SVI)

#### Terrain Analysis (3)
- Slope Analysis
- Aspect Analysis
- Hillshade

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
git clone https://github.com/christianxcorral/slr_vulnerability_mapper.git
cd slr_vulnerability_mapper
# Symlink to QGIS plugins directory for testing
```

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

### Commercial Use
While this plugin is free and open-source under GPL v3, commercial support, custom development, and training services are available. Contact: [christianxcorral@gmail.com](mailto:christianxcorral@gmail.com)

---

## 👤 Author

**Christian Xavier Corral Burau**
- Email: christianxcorral@gmail.com
- GitHub: [@christianxcorral](https://github.com/christianxcorral)

---

## 🙏 Acknowledgments

- IPCC Working Group I for AR6 sea-level projections
- FACTS Framework contributors
- CODEC dataset developers
- OpenTopography facility
- QGIS Development Team

---

## 📮 Support

- **Documentation:** [Plugin Help](help/build/html/index.html)
- **Issues:** [GitHub Issues](https://github.com/christianxcorral/slr_vulnerability_mapper/issues)
- **Discussions:** [GitHub Discussions](https://github.com/christianxcorral/slr_vulnerability_mapper/discussions)

---

## 🗺️ Use Cases

This plugin is designed for:
- **Urban planners** assessing climate adaptation strategies
- **Emergency managers** planning evacuation routes
- **Researchers** studying coastal vulnerability
- **Policy makers** evaluating infrastructure investments
- **Environmental consultants** conducting impact assessments
- **NGOs** working on community resilience

---

## 📊 Sample Results

*Add screenshots of:*
- Flood inundation map with AOI statistics
- Social vulnerability heatmap
- 3D point visualization
- CODEC return period comparison

---

## 🔮 Roadmap

### v0.2 (Planned)
- [ ] Automated report generation
- [ ] Time series animation support
- [ ] Multi-scenario comparison tools
- [ ] Integration with more DEM sources

### v1.0 (Future)
- [ ] Web-based version
- [ ] Real-time data integration
- [ ] Machine learning flood prediction

---


**⭐ If you find this plugin useful, please star the repository!**
