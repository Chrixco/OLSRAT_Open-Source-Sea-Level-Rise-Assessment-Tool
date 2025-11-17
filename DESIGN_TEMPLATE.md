# QGIS Plugin Design Template
## SLR Vulnerability Mapper Style Guide

**Version:** 1.0
**Last Updated:** 2025-10-03
**Purpose:** Standardized design system for creating consistent QGIS plugin interfaces

---

## 1. COLOR PALETTE

### Primary Colors
```
Blue (Primary):     #3498db  // Main actions, selected tabs, primary buttons
Blue Dark:          #2980b9  // Hover states for blue elements
```

### Secondary Colors
```
Orange (Accent):    #f39c12  // Population/optional features, secondary emphasis
Orange Dark:        #e67e22  // Hover states for orange elements
Orange Light:       #fff8e1  // Background highlight for orange-themed sections
```

### Alert Colors
```
Red:                #e74c3c  // Danger, inundated/affected areas
Green:              #2ecc71  // Success, safe/non-affected areas
Green Dark:         #27ae60  // Hover states for green elements
```

### Neutral Colors
```
Dark Text:          #2c3e50  // Primary text, headings
Gray Text:          #7f8c8d  // Secondary text, help text, labels
Light Gray:         #ecf0f1  // Disabled backgrounds, subtle backgrounds
Medium Gray:        #bdc3c7  // Borders, disabled states
Dark Gray:          #95a5a6  // Disabled text, cancel buttons
Very Dark Gray:     #7f8c8d  // Dimmed elements

Background White:   #ffffff  // Card backgrounds, input backgrounds
Background Light:   #f5f6fa  // Page background
Border Gray:        #e0e0e0  // Standard borders
```

### Chart Colors
```
Chart Blue:         #3498db  // Total/primary data
Chart Red:          #e74c3c  // Inundated/affected data
Chart Green:        #2ecc71  // Safe/non-affected data
Chart Yellow:       #ffe5b4  // Legend/stats box backgrounds
```

---

## 2. TYPOGRAPHY

### Font Specifications
```
Font Family:        System Default (Qt inherits from OS)
                    - Windows: Segoe UI
                    - macOS: SF Pro
                    - Linux: Ubuntu/Liberation Sans
```

### Font Sizes
```
Extra Large:        14px   // Main action buttons
Large:              13px   // Dialog headers, important labels
Standard:           12px   // ALL chart text (titles, labels, axes, legends)
                           // Body text, form labels, input fields
Medium:             11px   // Help text, secondary labels, search boxes
Small:              10px   // Fine print, supplementary information
```

### Font Weights
```
Bold:               font-weight: bold;    // Headings, labels, important data
Normal:             font-weight: normal;  // Body text, help text
```

### Font Colors by Context
```
Headings:           #2c3e50
Body Text:          #2c3e50
Help Text:          #7f8c8d
Disabled Text:      #95a5a6
Button Text:        white (on colored backgrounds)
Chart Text:         #000000 (default matplotlib black)
```

---

## 3. SPACING & LAYOUT

### Margins (External Spacing)
```
Large:              20px    // Major sections
Standard:           15px    // Panel content
Medium:             10px    // Between related elements
Small:              5px     // Compact groupings
Tiny:               0px     // Tight elements
```

### Padding (Internal Spacing)
```
Large:              12px    // Main action buttons
Standard:           8px     // Input fields, regular buttons
Medium:             6px     // Compact buttons, checkboxes
Small:              4px     // Tight UI elements
Extra Small:        2px     // Minimal padding
```

### Element Spacing
```
Vertical Spacing:   15px    // Between major UI groups
Form Spacing:       10px    // Between form elements
Tight Spacing:      5px     // Related items within a group
```

### Chart Margins
```
Top Margin:         0.88    // 88% of figure height (12% reserved for title)
Bottom Margin:      0.22    // 22% reserved for x-axis labels + legend boxes
Left Margin:        0.10-0.12  // 10-12% for y-axis labels
Right Margin:       0.95-0.96  // 5-4% right edge buffer
Subplot Spacing:    0.5     // wspace for multi-panel charts

Title Padding:      15px    // Space between title and chart
Legend Y-Position:  0.08    // Vertical position for bottom legends (fig.text)
```

---

## 4. BUTTONS

### Primary Action Button
```css
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px;
    font-weight: bold;
    font-size: 14px;
    min-height: 50px;  // For main CTA buttons
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:disabled {
    background-color: #bdc3c7;
    color: white;
}
```

### Secondary Action Button (Success/Green)
```css
QPushButton {
    background-color: #2ecc71;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #27ae60;
}
```

### Tertiary Action Button (Orange/Warning)
```css
QPushButton {
    background-color: #e67e22;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #d35400;
}
```

### Cancel/Neutral Button
```css
QPushButton {
    background-color: #95a5a6;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: bold;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #7f8c8d;
}
```

### Standard Action Button (Apply/OK)
```css
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 12px;
    font-weight: bold;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #2980b9;
}
```

---

## 5. INPUT FIELDS

### ComboBox (Dropdown) - Blue Theme
```css
QComboBox {
    border: 2px solid #3498db;
    border-radius: 6px;
    padding: 6px;
    background-color: white;
    font-size: 12px;
    font-weight: bold;
    color: #2c3e50;
    min-height: 35px;
}
QComboBox:hover {
    border: 2px solid #2980b9;
    background-color: #e3f2fd;
}
QComboBox:disabled {
    background-color: #ecf0f1;
    color: #95a5a6;
    border: 2px solid #bdc3c7;
}
QComboBox::drop-down {
    border: none;
    width: 25px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #3498db;
    margin-right: 6px;
}
QComboBox::down-arrow:disabled {
    border-top: 6px solid #bdc3c7;
}
QComboBox QAbstractItemView {
    border: 2px solid #3498db;
    border-radius: 6px;
    background-color: white;
    selection-background-color: #3498db;
    selection-color: white;
    font-size: 12px;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 6px;
    border-radius: 3px;
    min-height: 25px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #e3f2fd;
    color: #2c3e50;
}
```

### ComboBox - Orange Theme (Population Fields)
```css
QComboBox {
    border: 2px solid #f39c12;
    border-radius: 6px;
    padding: 6px;
    background-color: white;
    font-size: 12px;
    font-weight: bold;
    color: #2c3e50;
}
QComboBox:hover {
    border: 2px solid #e67e22;
    background-color: #fff8e1;
}
QComboBox::down-arrow {
    border-top: 6px solid #f39c12;
}
QComboBox QAbstractItemView {
    border: 2px solid #f39c12;
    selection-background-color: #f39c12;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #fff8e1;
}
```

### SpinBox (Number Input) - Orange Theme
```css
QSpinBox {
    border: 2px solid #f39c12;
    border-radius: 6px;
    padding: 6px;
    background-color: white;
    font-size: 13px;
    font-weight: bold;
    color: #2c3e50;
    min-height: 35px;
}
QSpinBox:hover {
    border: 2px solid #e67e22;
    background-color: #fff8e1;
}
QSpinBox:disabled {
    background-color: #ecf0f1;
    color: #95a5a6;
    border: 2px solid #bdc3c7;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
    border-left: 1px solid #f39c12;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #fff8e1;
}
```

### Text Edit (Search Box)
```css
QTextEdit {
    border: 2px solid #3498db;
    border-radius: 4px;
    padding: 4px;
    font-size: 11px;
    max-height: 30px;
    background-color: white;
}
QTextEdit:focus {
    border: 2px solid #2980b9;
}
```

---

## 6. CHECKBOXES & RADIO BUTTONS

### Checkbox - Blue Theme (Data Preparation)
```css
QCheckBox {
    font-weight: normal;
    color: #2c3e50;
    spacing: 10px;
    padding: 6px;
}
QCheckBox:hover {
    background-color: #e3f2fd;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 3px solid #3498db;
    border-radius: 4px;
    background-color: white;
}
QCheckBox::indicator:checked {
    background-color: #3498db;
    border: 3px solid #3498db;
}
QCheckBox::indicator:hover {
    border: 3px solid #2980b9;
    background-color: #e3f2fd;
}
QCheckBox::indicator:checked:hover {
    background-color: #2980b9;
}
```

### Checkbox - Red Theme (Flood Exposure)
```css
QCheckBox::indicator {
    border: 3px solid #e74c3c;
}
QCheckBox::indicator:checked {
    background-color: #e74c3c;
    border: 3px solid #e74c3c;
}
QCheckBox::indicator:hover {
    border: 3px solid #c0392b;
    background-color: #fadbd8;
}
```

### Checkbox - Green Theme (Terrain Analysis)
```css
QCheckBox::indicator {
    border: 3px solid #2ecc71;
}
QCheckBox::indicator:checked {
    background-color: #2ecc71;
    border: 3px solid #2ecc71;
}
QCheckBox::indicator:hover {
    border: 3px solid #27ae60;
    background-color: #d5f4e6;
}
```

### Checkbox - Orange Theme (Population/Optional)
```css
QCheckBox::indicator {
    border: 3px solid #f39c12;
}
QCheckBox::indicator:checked {
    background-color: #f39c12;
    border: 3px solid #f39c12;
}
QCheckBox::indicator:hover {
    border: 3px solid #e67e22;
    background-color: #fff8e1;
}
```

### Radio Button - Orange Theme
```css
QRadioButton {
    font-weight: normal;
    color: #2c3e50;
    spacing: 10px;
    padding: 6px;
}
QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border: 3px solid #f39c12;
    border-radius: 4px;  // Note: square, not circular
    background-color: white;
}
QRadioButton::indicator:checked {
    background-color: #f39c12;
    border: 3px solid #f39c12;
}
QRadioButton::indicator:hover {
    border: 3px solid #e67e22;
    background-color: #fff8e1;
}
```

---

## 7. GROUP BOXES & CONTAINERS

### Group Box - Blue Theme (Standard)
```css
QGroupBox {
    border: 2px solid #3498db;
    border-radius: 10px;
    margin-top: 12px;
    padding: 15px;
    background-color: white;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 10px;
    color: #3498db;
    font-size: 13px;
}
```

### Group Box - Red Theme (Flood Exposure)
```css
QGroupBox {
    border: 2px solid #e74c3c;
}
QGroupBox::title {
    color: #e74c3c;
}
```

### Group Box - Green Theme (Terrain)
```css
QGroupBox {
    border: 2px solid #2ecc71;
}
QGroupBox::title {
    color: #2ecc71;
}
```

### Group Box - Orange Theme (Population)
```css
QGroupBox {
    border: 2px solid #f39c12;
}
QGroupBox::title {
    color: #f39c12;
}
```

### Panel Container (White Card)
```css
QWidget {
    background-color: white;
    border-radius: 12px;
}
```

### Panel Container (Light Background)
```css
QWidget {
    background-color: #f5f6fa;
    border-radius: 12px;
}
```

---

## 8. TABLES

### Table Widget
```css
QTableWidget {
    border: 1px solid #e0e0e0;
    border-radius: 5px;
    alternate-background-color: #f5f6fa;
    background-color: white;
}
QHeaderView::section {
    background-color: #3498db;
    color: white;
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
    border: none;
}
QTableWidget::item {
    padding: 8px;
    font-size: 12px;
}
QTableWidget::item:selected {
    background-color: #e3f2fd;
    color: #2c3e50;
}
```

---

## 9. TABS

### Tab Widget
```css
QTabWidget::pane {
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    top: -1px;
    background-color: white;
}
QTabBar::tab {
    background: #ecf0f1;
    color: #2c3e50;
    padding: 10px 20px;
    margin-right: 5px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: bold;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #3498db;
    color: white;
}
QTabBar::tab:hover {
    background: #d4e6f1;
}
```

---

## 10. PROGRESS BAR

### Progress Bar
```css
QProgressBar {
    border: 2px solid #bdc3c7;
    border-radius: 5px;
    text-align: center;
    height: 25px;
    background-color: #ecf0f1;
    font-size: 12px;
    font-weight: bold;
    color: #2c3e50;
}
QProgressBar::chunk {
    background-color: #3498db;
    border-radius: 3px;
}
```

---

## 11. SCROLL AREAS

### Scroll Area
```css
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    border: none;
    background: #ecf0f1;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #bdc3c7;
    border-radius: 6px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #95a5a6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
```

---

## 12. CHARTS & VISUALIZATIONS

### Chart Configuration (Matplotlib)
```python
# All chart fonts: 12pt
title_font = 12
label_font = 12
tick_font = 12
annotation_font = 12
legend_font = 12

# Chart margins
fig.subplots_adjust(
    left=0.10,      # Y-axis labels
    right=0.96,     # Right edge buffer
    top=0.88,       # Title space (12% from top)
    bottom=0.22     # X-axis + legend boxes (22% from bottom)
)

# For multi-panel charts
gs = fig.add_gridspec(
    1, 2,
    wspace=0.5,     # 50% width spacing between panels
    left=0.10,
    right=0.96,
    top=0.88,
    bottom=0.22
)

# Title styling
ax.set_title('Title Text',
    fontweight='bold',
    fontsize=12,
    pad=15
)

# Main title (suptitle)
fig.suptitle('Main Title\n(subtitle)',
    fontweight='bold',
    fontsize=12,
    y=0.96
)

# Axis labels
ax.set_xlabel('Label', fontweight='bold', fontsize=12)
ax.set_ylabel('Label', fontweight='bold', fontsize=12)

# Tick labels
ax.tick_params(axis='both', labelsize=12)

# Legend boxes below chart
fig.text(
    0.5, 0.08,              # x=center, y=8% from bottom
    'Legend Text',
    ha='center',
    fontsize=12,
    fontweight='bold',
    bbox=dict(
        boxstyle='round,pad=0.7',
        facecolor='#ffe5b4',
        alpha=0.95,
        edgecolor='black',
        linewidth=2
    )
)

# Bar value labels (2% above bars)
ax.text(
    x_pos,
    height * 1.02,
    f'{value:,.0f}',
    ha='center',
    va='bottom',
    fontweight='bold',
    fontsize=12
)

# Y-axis headroom (15% extra space for labels)
ax.set_ylim(0, max(values) * 1.15)

# Grid
ax.grid(axis='y', alpha=0.3, linestyle='--')
```

### Chart Color Schemes
```python
# Area comparison
colors = ['#3498db', '#e74c3c', '#2ecc71']  # Total, Inundated, Dry

# Population comparison
colors = ['#3498db', '#e74c3c', '#2ecc71']  # Total, Affected, Safe

# Feature comparison
colors = ['#e74c3c', '#2ecc71']  # Inundated, Non-Inundated

# Distribution histogram
base_color = '#3498db'
colormap = 'RdYlGn_r'  # Red (high) to Green (low)

# Legend/Stats boxes
background = '#ffe5b4'  # Soft yellow
border = 'black'
linewidth = 2
alpha = 0.95
```

---

## 13. DIALOG WINDOWS

### Main Dialog Window
```python
self.setWindowTitle("Window Title")
self.setMinimumWidth(1400)
self.setMinimumHeight(900)
self.setWindowModality(Qt.NonModal)  # Allow interaction with other windows
```

### Value Selector Dialog
```python
self.setWindowTitle(f"Select Values from '{field_name}'")
self.setMinimumWidth(450)
self.setMinimumHeight(500)
self.setWindowModality(Qt.ApplicationModal)  # Block parent until closed
```

---

## 14. LAYOUT SYSTEM

### Splitter Proportions
```python
splitter = QSplitter(Qt.Horizontal)
splitter.addWidget(left_panel)
splitter.addWidget(right_panel)
splitter.setStretchFactor(0, 2)  # Left panel: 40%
splitter.setStretchFactor(1, 3)  # Right panel: 60%
```

### Layout Margins & Spacing
```python
# Main layout
layout.setContentsMargins(20, 20, 20, 20)
layout.setSpacing(15)

# Panel layout
layout.setContentsMargins(15, 15, 15, 15)
layout.setSpacing(15)

# Form layout
layout.setContentsMargins(10, 10, 10, 10)
layout.setSpacing(10)

# Compact layout
layout.setContentsMargins(5, 5, 5, 5)
layout.setSpacing(5)
```

---

## 15. ICONS & EMOJIS

### Standard Emoji Usage
```
🏠  Home / Main GUI
🚀  Generate / Launch / Execute
📈  Charts / Visualization
📋  List / Browse / Select
🔍  Search
✓   Success / Select All
✗   Cancel / Select None
⇄   Invert / Toggle
📊  Statistics / Data
💾  Save / Export
🔄  Refresh / Reload
⚠️  Warning
❌  Error / Delete
```

---

## 16. HELP TEXT & LABELS

### Help Text Styling
```css
QLabel {
    color: #7f8c8d;
    font-size: 11px;
    font-weight: normal;
    font-style: italic;  // Optional
}
```

### Field Labels
```css
QLabel {
    font-weight: bold;
    color: #2c3e50;
    font-size: 12px;
}
```

### Info Boxes
```css
QLabel {
    color: #7f8c8d;
    font-size: 11px;
    font-weight: normal;
    padding: 8px;
    background-color: #fff8e1;  // Light yellow
    border-radius: 4px;
    border: 1px solid #f39c12;  // Orange border
}
```

---

## 17. BORDER RADIUS STANDARDS

```
Large Panels:       12px
Medium Containers:  10px
Standard Elements:  8px
Small Elements:     6px
Buttons:            4-8px (depending on size)
Input Fields:       6px
Checkboxes:         4px
```

---

## 18. OPACITY/ALPHA VALUES

```
Legend Boxes:       0.95
Chart Elements:     0.85 (bars)
                    0.75 (histograms)
Hover States:       Solid (1.0)
Backgrounds:        0.9-0.95
```

---

## 19. SHADOW & ELEVATION

**Note:** Qt StyleSheets have limited shadow support. Use borders and backgrounds for depth.

```css
/* Subtle elevation effect */
border: 2px solid #e0e0e0;
background-color: white;

/* Active/Selected state */
border: 2px solid #3498db;
background-color: #e3f2fd;
```

---

## 20. RESPONSIVE BEHAVIOR

### Minimum Sizes
```python
# Main windows
setMinimumWidth(1400)
setMinimumHeight(900)

# Dialogs
setMinimumWidth(450)
setMinimumHeight(500)

# Input fields
setMinimumHeight(35)

# Buttons
setMinimumHeight(50)  # Primary CTA
setMinimumWidth(80)   # Standard buttons
```

### Stretch Factors
```python
layout.addStretch()  # Push elements up/left
layout.addWidget(widget, stretch=1)  # Proportional sizing
```

---

## 21. ACCESSIBILITY CONSIDERATIONS

- **Contrast Ratio:** All text meets WCAG AA standards (4.5:1 minimum)
- **Font Size:** Minimum 10px for fine print, 12px standard
- **Touch Targets:** Minimum 35px height for interactive elements
- **Color Independence:** Don't rely solely on color (use icons, text, patterns)
- **Hover States:** Clear visual feedback on all interactive elements
- **Disabled States:** Clear visual distinction with reduced opacity/gray tones

---

## 22. IMPLEMENTATION EXAMPLES

### Complete Button Set
```python
# Primary Action
primary_btn = QPushButton("🚀 Execute")
primary_btn.setMinimumHeight(50)
primary_btn.setStyleSheet("""
    QPushButton {
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 12px;
        font-weight: bold;
        font-size: 14px;
    }
    QPushButton:hover { background-color: #2980b9; }
    QPushButton:disabled { background-color: #bdc3c7; }
""")

# Secondary Action
secondary_btn = QPushButton("✓ Apply")
secondary_btn.setStyleSheet("""
    QPushButton {
        background-color: #2ecc71;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 11px;
        font-weight: bold;
    }
    QPushButton:hover { background-color: #27ae60; }
""")

# Cancel Button
cancel_btn = QPushButton("Cancel")
cancel_btn.setStyleSheet("""
    QPushButton {
        background-color: #95a5a6;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 8px 20px;
        font-size: 12px;
        font-weight: bold;
        min-width: 80px;
    }
    QPushButton:hover { background-color: #7f8c8d; }
""")
```

### Complete Checkbox Set (Color-Coded)
```python
# Blue checkbox (Data Preparation)
blue_check = QCheckBox("Data Option")
blue_check.setStyleSheet("""
    QCheckBox {
        font-weight: normal;
        color: #2c3e50;
        spacing: 10px;
        padding: 6px;
    }
    QCheckBox:hover { background-color: #e3f2fd; }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border: 3px solid #3498db;
        border-radius: 4px;
        background-color: white;
    }
    QCheckBox::indicator:checked {
        background-color: #3498db;
        border: 3px solid #3498db;
    }
    QCheckBox::indicator:hover {
        border: 3px solid #2980b9;
        background-color: #e3f2fd;
    }
""")

# Red checkbox (Flood Exposure)
red_check = QCheckBox("Flood Option")
red_check.setStyleSheet("""
    QCheckBox::indicator { border: 3px solid #e74c3c; }
    QCheckBox::indicator:checked {
        background-color: #e74c3c;
        border: 3px solid #e74c3c;
    }
    QCheckBox::indicator:hover {
        border: 3px solid #c0392b;
        background-color: #fadbd8;
    }
""")

# Green checkbox (Terrain)
green_check = QCheckBox("Terrain Option")
green_check.setStyleSheet("""
    QCheckBox::indicator { border: 3px solid #2ecc71; }
    QCheckBox::indicator:checked {
        background-color: #2ecc71;
        border: 3px solid #2ecc71;
    }
    QCheckBox::indicator:hover {
        border: 3px solid #27ae60;
        background-color: #d5f4e6;
    }
""")

# Orange checkbox (Population)
orange_check = QCheckBox("Population Option")
orange_check.setStyleSheet("""
    QCheckBox::indicator { border: 3px solid #f39c12; }
    QCheckBox::indicator:checked {
        background-color: #f39c12;
        border: 3px solid #f39c12;
    }
    QCheckBox::indicator:hover {
        border: 3px solid #e67e22;
        background-color: #fff8e1;
    }
""")
```

### Complete ComboBox
```python
combo = QComboBox()
combo.setMinimumHeight(35)
combo.setStyleSheet("""
    QComboBox {
        border: 2px solid #3498db;
        border-radius: 6px;
        padding: 6px;
        background-color: white;
        font-size: 12px;
        font-weight: bold;
        color: #2c3e50;
    }
    QComboBox:hover {
        border: 2px solid #2980b9;
        background-color: #e3f2fd;
    }
    QComboBox:disabled {
        background-color: #ecf0f1;
        color: #95a5a6;
        border: 2px solid #bdc3c7;
    }
    QComboBox::drop-down {
        border: none;
        width: 25px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #3498db;
        margin-right: 6px;
    }
    QComboBox::down-arrow:disabled {
        border-top: 6px solid #bdc3c7;
    }
    QComboBox QAbstractItemView {
        border: 2px solid #3498db;
        border-radius: 6px;
        background-color: white;
        selection-background-color: #3498db;
        selection-color: white;
        font-size: 12px;
        padding: 4px;
    }
    QComboBox QAbstractItemView::item {
        padding: 6px;
        border-radius: 3px;
        min-height: 25px;
    }
    QComboBox QAbstractItemView::item:hover {
        background-color: #e3f2fd;
        color: #2c3e50;
    }
""")
```

---

## 23. FILE NAMING CONVENTIONS

```
Main GUI:               plugin_name_gui.py
Visualization Module:   plugin_name_viz.py
Processing Provider:    plugin_name_provider.py
Algorithm Files:        alg_feature_name.py
Icons:                  Icons/256.png, Icons/128.png
Resources:              resources.qrc, resources_rc.py
Metadata:               metadata.txt
```

---

## 24. QUICK REFERENCE: COLOR THEME BY CATEGORY

| Category | Primary Color | Border Color | Hover Background | Example Use |
|----------|--------------|--------------|------------------|-------------|
| **Data Preparation** | #3498db (Blue) | #3498db | #e3f2fd | Layer selection, data tools |
| **Flood Exposure** | #e74c3c (Red) | #e74c3c | #fadbd8 | Inundation analysis, flood data |
| **Social Analysis** | #f39c12 (Orange) | #f39c12 | #fff8e1 | Population, vulnerability |
| **Terrain Analysis** | #2ecc71 (Green) | #2ecc71 | #d5f4e6 | Slope, hillshade, aspect |
| **Visualization** | #3498db (Blue) | #3498db | #e3f2fd | Charts, reports, output |
| **Actions** | #3498db (Blue) | none | #2980b9 | Primary buttons, execute |
| **Success** | #2ecc71 (Green) | none | #27ae60 | Confirmation, safe areas |
| **Warning/Alert** | #f39c12 (Orange) | #f39c12 | #fff8e1 | Optional features, caution |
| **Danger/Affected** | #e74c3c (Red) | none | #c0392b | Inundated areas, critical |
| **Neutral** | #95a5a6 (Gray) | #bdc3c7 | #7f8c8d | Cancel, disabled, secondary |

---

## 25. USAGE GUIDELINES

### When to Use Each Color:
- **Blue (#3498db):** Default choice for primary actions, standard UI elements, data preparation
- **Red (#e74c3c):** Inundated/affected areas, flood-related features, danger states
- **Green (#2ecc71):** Safe/non-affected areas, terrain analysis, success states
- **Orange (#f39c12):** Population features, optional settings, social analysis, warnings
- **Gray (#95a5a6):** Cancel actions, disabled states, neutral elements

### Consistency Rules:
1. Always use 12pt font for ALL chart text (no dynamic scaling)
2. Place legend boxes below charts at y=0.08
3. Use 3px borders for checkbox/radio button indicators
4. Set minimum 35px height for input fields
5. Use border-radius: 6px for input fields, 8px for primary buttons
6. Always provide hover states for interactive elements
7. Use bold font for labels and headings, normal for body text
8. Match checkbox/radio button colors to their thematic category
9. Use emoji icons consistently (🚀 for execute, 📈 for charts, etc.)
10. Maintain 2:3 ratio for left:right panel split (40%:60%)

---

**END OF DESIGN TEMPLATE**

This template should be provided to any developer/AI system creating plugins in this style. All values are production-tested and ensure visual consistency across QGIS plugin interfaces.
