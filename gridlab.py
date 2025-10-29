#!/usr/bin/env python3
"""
Grid Transformation Application
PyQt6 GUI for transforming grid data from one coordinate system to another
"""

import sys
import os
import pandas as pd
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTreeWidget, QTreeWidgetItem, QTextEdit, QPushButton, QFileDialog,
                              QSplitter, QMenuBar, QMessageBox, QProgressBar, QStatusBar,
                              QLabel, QFrame, QDialog, QLineEdit, QListWidget, QListWidgetItem,
                              QGroupBox, QCheckBox, QComboBox, QHBoxLayout, QTabWidget, QTableWidget,
                              QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont
from gridfile import GridFile


class CRSSelectionDialog(QDialog):
    """Dialog for selecting coordinate reference systems"""

    def __init__(self, parent=None, title="Select CRS"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.selected_crs = None
        self.selected_name = None

        # Get available CRS from pyproj
        self.available_crs = self.get_available_crs()

        self.init_ui()

    def get_available_crs(self):
        """Get list of available CRS from pyproj"""
        try:
            from pyproj import CRS
            crs_list = []

            # Try to load a comprehensive list of EPSG codes
            # Common ranges for projected coordinate systems
            epsg_ranges = [
                range(2000, 4000),  # Various projected systems
                range(32000, 32500),  # NAD27 state plane
                range(32100, 32600),  # NAD83 state plane
                range(26900, 27000),  # UTM NAD83
                range(32600, 32800),  # UTM WGS84
                range(3850, 3860),   # Web Mercator
            ]

            # Add specific important ones
            important_epsg = [4326, 4269, 4267, 3857, 3785]

            all_epsg = set()
            for r in epsg_ranges:
                all_epsg.update(r)
            all_epsg.update(important_epsg)

            for epsg in sorted(all_epsg):
                try:
                    crs = CRS.from_epsg(epsg)
                    crs_list.append({
                        'epsg': epsg,
                        'name': crs.name,
                        'area': 'Various'  # Simplified for performance
                    })
                except:
                    continue

            return crs_list

        except Exception as e:
            print(f"Failed to load CRS definitions: {e}")
            # Fallback hardcoded list
            crs_list = [
                {'epsg': 4326, 'name': 'WGS84', 'area': 'World'},
                {'epsg': 32025, 'name': 'NAD27 Oklahoma South', 'area': 'Oklahoma'},
                {'epsg': 32104, 'name': 'NAD83 Oklahoma South', 'area': 'Oklahoma'},
                {'epsg': 2268, 'name': 'NAD83', 'area': 'Various regions'},
                {'epsg': 26913, 'name': 'UTM Zone 13N NAD83', 'area': 'North America'},
                {'epsg': 26914, 'name': 'UTM Zone 14N NAD83', 'area': 'North America'},
                {'epsg': 32613, 'name': 'UTM Zone 13N WGS84', 'area': 'World'},
                {'epsg': 32614, 'name': 'UTM Zone 14N WGS84', 'area': 'World'},
                {'epsg': 3857, 'name': 'Web Mercator', 'area': 'World'},
            ]
            return crs_list

    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)

        # Search bar
        search_label = QLabel("Search CRS:")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter EPSG code or CRS name...")
        self.search_input.textChanged.connect(self.filter_crs)
        self.search_input.returnPressed.connect(self.filter_crs)  # Also filter on Enter key
        layout.addWidget(self.search_input)

        # CRS list
        self.crs_list = QListWidget()
        self.populate_crs_list()
        layout.addWidget(self.crs_list)

        # Buttons
        button_layout = QHBoxLayout()

        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.select_crs)
        button_layout.addWidget(select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setMinimumSize(500, 400)

    def populate_crs_list(self):
        """Populate the CRS list widget"""
        self.crs_list.clear()
        for crs in self.available_crs:
            item_text = f"EPSG:{crs['epsg']} - {crs['name']}"
            if crs['area'] != 'Unknown':
                item_text += f" ({crs['area']})"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, crs)
            self.crs_list.addItem(item)

    def filter_crs(self, text=None):
        """Filter CRS list based on search text"""
        if text is None:
            text = self.search_input.text()
        text = text.lower().strip()

        for i in range(self.crs_list.count()):
            item = self.crs_list.item(i)
            crs_data = item.data(Qt.ItemDataRole.UserRole)

            # Show all items if search is empty
            if not text:
                item.setHidden(False)
            else:
                visible = (text in str(crs_data['epsg']).lower() or
                          text in crs_data['name'].lower() or
                          text in crs_data['area'].lower())
                item.setHidden(not visible)

    def select_crs(self):
        """Handle CRS selection"""
        current_item = self.crs_list.currentItem()
        if current_item:
            crs_data = current_item.data(Qt.ItemDataRole.UserRole)
            self.selected_crs = f"EPSG:{crs_data['epsg']}"
            self.selected_name = crs_data['name']
            self.accept()

# Remove the old TransformationWorker class as it's no longer needed
# The GridFile class handles all transformation and writing logic now

class DataTableViewer(QTableWidget):
    """Table viewer for displaying parsed data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["X Coordinate", "Y Coordinate", "Z Value"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.max_rows = 1000  # Limit for performance

    def display_dataframe(self, df, title="Data"):
        """Display pandas DataFrame in table format"""
        self.clearContents()
        self.setRowCount(0)

        if df is None or df.empty:
            self.insertRow(0)
            self.setItem(0, 0, QTableWidgetItem("No data available"))
            self.setItem(0, 1, QTableWidgetItem(""))
            self.setItem(0, 2, QTableWidgetItem(""))
            return

        # Ensure we have the expected columns
        x_col = 'X' if 'X' in df.columns else df.columns[0]
        y_col = 'Y' if 'Y' in df.columns else df.columns[1] if len(df.columns) > 1 else df.columns[0]
        z_col = 'Z' if 'Z' in df.columns else df.columns[2] if len(df.columns) > 2 else df.columns[0]

        row_count = 0
        for idx, row in df.iterrows():
            try:
                x = float(row[x_col])
                y = float(row[y_col])
                z = float(row[z_col]) if pd.notna(row[z_col]) else 0.0

                self.insertRow(row_count)
                self.setItem(row_count, 0, QTableWidgetItem(f"{x:.5f}"))
                self.setItem(row_count, 1, QTableWidgetItem(f"{y:.5f}"))
                self.setItem(row_count, 2, QTableWidgetItem(f"{z:.4f}"))
                row_count += 1

                if row_count >= self.max_rows:  # Performance limit
                    break

            except (ValueError, KeyError, TypeError):
                continue

        if row_count == 0:
            self.insertRow(0)
            self.setItem(0, 0, QTableWidgetItem("No valid data found"))
            self.setItem(0, 1, QTableWidgetItem(""))
            self.setItem(0, 2, QTableWidgetItem(""))

    def display_parsed_data(self, data_lines, delimiter=",", title="Parsed Data", columns=None):
        """Legacy method for backward compatibility"""
        self.display_dataframe(None, title)

class DataPlotViewer(QWidget):
    """Plot viewer for data visualization"""

    def __init__(self, parent=None):
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)

    def plot_dataframe(self, df, title="Data Plot"):
        """Plot DataFrame data points as scatter plot for irregular grid data"""
        self.axes.clear()

        if df is None or df.empty:
            self.axes.text(0.5, 0.5, 'No data available to plot',
                          transform=self.axes.transAxes, ha='center', va='center')
            self.axes.set_title(title)
            self.canvas.draw()
            return

        # Extract coordinates
        x_col = 'X' if 'X' in df.columns else df.columns[0]
        y_col = 'Y' if 'Y' in df.columns else df.columns[1] if len(df.columns) > 1 else df.columns[0]
        z_col = 'Z' if 'Z' in df.columns else df.columns[2] if len(df.columns) > 2 else df.columns[0]

        try:
            x_coords = pd.to_numeric(df[x_col], errors='coerce').dropna().values
            y_coords = pd.to_numeric(df[y_col], errors='coerce').dropna().values
            z_values = pd.to_numeric(df[z_col], errors='coerce').fillna(0).values

            # Ensure we have matching lengths
            min_len = min(len(x_coords), len(y_coords), len(z_values))
            x_coords = x_coords[:min_len]
            y_coords = y_coords[:min_len]
            z_values = z_values[:min_len]

            if len(x_coords) > 0 and len(y_coords) > 0:
                # For irregular grids, use scatter plot with color mapping
                # Limit points for performance
                max_points = 10000  # Increased limit for better visualization
                if len(x_coords) > max_points:
                    indices = np.random.choice(len(x_coords), max_points, replace=False)
                    x_coords = x_coords[indices]
                    y_coords = y_coords[indices]
                    z_values = z_values[indices]

                # Create scatter plot with Z values as colors
                scatter = self.axes.scatter(x_coords, y_coords, c=z_values,
                                          cmap='viridis', s=1, alpha=0.8, edgecolors='none')

                self.axes.set_xlabel('X Coordinate')
                self.axes.set_ylabel('Y Coordinate')
                self.axes.set_title(title)
                self.axes.grid(True, alpha=0.3)

                # Add colorbar - ensure we only add one
                try:
                    if hasattr(self, '_colorbar'):
                        self._colorbar.remove()
                    self._colorbar = self.figure.colorbar(scatter, ax=self.axes, label='Z Value', shrink=0.8)
                    self._colorbar.ax.tick_params(labelsize=8)
                except Exception:
                    # If colorbar creation fails, continue without it
                    pass

                # Set equal aspect ratio for proper spatial representation
                self.axes.set_aspect('equal', adjustable='box')

            else:
                self.axes.text(0.5, 0.5, 'No valid numeric data to plot',
                              transform=self.axes.transAxes, ha='center', va='center')
                self.axes.set_title(title)

        except Exception as e:
            self.axes.text(0.5, 0.5, f'Error plotting data: {str(e)}',
                          transform=self.axes.transAxes, ha='center', va='center')
            self.axes.set_title(title)

        self.canvas.draw()

    def plot_data(self, data_lines, delimiter=",", title="Data Plot", columns=None):
        """Legacy method for backward compatibility"""
        self.plot_dataframe(None, title)

class OutputTextViewer(QTextEdit):
    """Text viewer for displaying transformed output"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Courier New", 10))
        self.setReadOnly(True)
        self.setPlaceholderText("Transformed output will appear here...")

    def display_transformed_data(self, data_lines, title="Transformed Output"):
        """Display transformed data lines"""
        # Add a header
        header = f"-- {title} --\n\n"
        content = header + ''.join(data_lines[:1000])  # Limit for performance

        if len(data_lines) > 1000:
            content += f"\n\n... ({len(data_lines) - 1000} more lines not shown) ..."

        self.setPlainText(content)

class GridLabApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.grid_files = {}  # Store GridFile objects for each file
        self.input_crs = ""
        self.input_crs_name = "Not selected"
        self.output_crs = ""
        self.output_crs_name = "Not selected"
        self.input_folder = ""
        self.output_folder = ""
        self.output_delimiter = ","  # Default output delimiter
        self.default_delimiter = ","  # Default input delimiter

        # Performance optimization caches
        self.preview_cache = {}  # Cache for preview transformations
        self.file_delimiters = {}  # Store delimiter for each file
        self.file_columns = {}  # Store column indices for each file

        self.setWindowTitle("GridLab")
        self.setGeometry(100, 100, 1400, 900)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create sidebar
        self.create_sidebar()
        main_layout.addWidget(self.sidebar, 1)

        # Create main content area
        self.create_main_content()
        main_layout.addWidget(self.main_content, 3)

        # Initialize folder labels
        self.input_folder_label = QLabel("Input Folder: Not selected")
        self.output_folder_label = QLabel("Output Folder: Not selected")

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Create menu bar
        self.create_menu_bar()

        # Worker thread no longer needed - GridFile handles everything

    def create_sidebar(self):
        """Create the left sidebar with file tree"""
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)

        # CRS Selection Group
        crs_group = QGroupBox("Coordinate Reference Systems")
        crs_layout = QVBoxLayout(crs_group)

        # Input CRS selector
        self.select_input_crs_btn = QPushButton("Select Input CRS")
        self.select_input_crs_btn.clicked.connect(self.select_input_crs)
        crs_layout.addWidget(self.select_input_crs_btn)

        self.input_crs_label = QLabel("Input CRS: Not selected")
        crs_layout.addWidget(self.input_crs_label)

        # Output CRS selector
        self.select_output_crs_btn = QPushButton("Select Output CRS")
        self.select_output_crs_btn.clicked.connect(self.select_output_crs)
        crs_layout.addWidget(self.select_output_crs_btn)

        self.output_crs_label = QLabel("Output CRS: Not selected")
        crs_layout.addWidget(self.output_crs_label)

        sidebar_layout.addWidget(crs_group)

        # File selection buttons
        files_group = QGroupBox("File Management")
        files_layout = QVBoxLayout(files_group)

        # Input folder selection
        self.select_input_folder_btn = QPushButton("Select Input Folder")
        self.select_input_folder_btn.clicked.connect(self.select_input_folder)
        files_layout.addWidget(self.select_input_folder_btn)

        # Output folder selection
        self.select_output_folder_btn = QPushButton("Select Output Folder")
        self.select_output_folder_btn.clicked.connect(self.select_output_folder)
        files_layout.addWidget(self.select_output_folder_btn)

        # Default delimiter selection
        delimiter_layout = QHBoxLayout()
        delimiter_label = QLabel("Default Delimiter:")
        delimiter_layout.addWidget(delimiter_label)

        self.default_delimiter_combo = QComboBox()
        self.default_delimiter_combo.addItems(["Comma (,)", "Space ( )", "Tab (\\t)"])
        self.default_delimiter_combo.currentTextChanged.connect(self.on_default_delimiter_changed)
        delimiter_layout.addWidget(self.default_delimiter_combo)

        files_layout.addLayout(delimiter_layout)

        # Output delimiter selection
        output_delimiter_layout = QHBoxLayout()
        output_delimiter_label = QLabel("Output Delimiter:")
        output_delimiter_layout.addWidget(output_delimiter_label)

        self.output_delimiter_combo = QComboBox()
        self.output_delimiter_combo.addItems(["Comma (,)", "Space ( )", "Tab (\\t)", "Semicolon (;)"])
        self.output_delimiter_combo.setCurrentText("Comma (,)")
        self.output_delimiter_combo.currentTextChanged.connect(self.on_output_delimiter_changed)
        output_delimiter_layout.addWidget(self.output_delimiter_combo)

        files_layout.addLayout(output_delimiter_layout)

        # Include column headers checkbox
        self.include_column_headers_checkbox = QCheckBox("Include column headers (X,Y,Z) in output")
        self.include_column_headers_checkbox.setChecked(False)  # Default to not including headers
        files_layout.addWidget(self.include_column_headers_checkbox)

        # Remove input headers/comments checkbox
        self.remove_input_headers_checkbox = QCheckBox("Remove input headers/comments from output")
        self.remove_input_headers_checkbox.setChecked(True)  # Default to removing input headers
        files_layout.addWidget(self.remove_input_headers_checkbox)

        # Overwrite checkbox
        self.overwrite_checkbox = QCheckBox("Overwrite existing output files")
        self.overwrite_checkbox.setChecked(False)
        files_layout.addWidget(self.overwrite_checkbox)

        sidebar_layout.addWidget(files_group)

        # File tree with delimiter column
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Grid Files", "Delimiter"])
        self.file_tree.setColumnWidth(0, 200)
        self.file_tree.setColumnWidth(1, 80)
        self.file_tree.itemClicked.connect(self.on_file_selected)
        sidebar_layout.addWidget(self.file_tree)

        # Progress bar for transformations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        sidebar_layout.addWidget(self.progress_bar)

    def create_main_content(self):
        """Create the main content area"""
        self.main_content = QWidget()
        main_layout = QVBoxLayout(self.main_content)

        # Create splitter for input and output views
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Input view (top half)
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)

        input_label = QLabel("Input Data:")
        input_layout.addWidget(input_label)

        # File-specific delimiter and column selection
        delimiter_controls = QWidget()
        delimiter_controls_layout = QHBoxLayout(delimiter_controls)

        # Delimiter selection
        delimiter_controls_layout.addWidget(QLabel("File Delimiter:"))
        self.file_delimiter_combo = QComboBox()
        self.file_delimiter_combo.addItems(["Auto", "Comma (,)", "Space ( )", "Tab (\\t)"])
        self.file_delimiter_combo.currentTextChanged.connect(self.on_file_delimiter_changed)
        delimiter_controls_layout.addWidget(self.file_delimiter_combo)

        # Column selection dropdowns
        delimiter_controls_layout.addWidget(QLabel("X Col:"))
        self.x_column_combo = QComboBox()
        self.x_column_combo.setEnabled(False)
        delimiter_controls_layout.addWidget(self.x_column_combo)

        delimiter_controls_layout.addWidget(QLabel("Y Col:"))
        self.y_column_combo = QComboBox()
        self.y_column_combo.setEnabled(False)
        delimiter_controls_layout.addWidget(self.y_column_combo)

        delimiter_controls_layout.addWidget(QLabel("Z Col:"))
        self.z_column_combo = QComboBox()
        self.z_column_combo.setEnabled(False)
        delimiter_controls_layout.addWidget(self.z_column_combo)

        delimiter_controls_layout.addStretch()
        input_layout.addWidget(delimiter_controls)

        # Input tab widget
        self.input_tabs = QTabWidget()

        # Text/Raw tab
        self.input_text_viewer = QTextEdit()
        self.input_text_viewer.setFont(QFont("Courier New", 10))
        self.input_text_viewer.setReadOnly(True)
        self.input_tabs.addTab(self.input_text_viewer, "Text/Raw")

        # Table tab
        self.input_table_viewer = DataTableViewer()
        self.input_tabs.addTab(self.input_table_viewer, "Table")

        # Plot tab
        self.input_plot_viewer = DataPlotViewer()
        self.input_tabs.addTab(self.input_plot_viewer, "Plot")

        input_layout.addWidget(self.input_tabs)
        splitter.addWidget(input_container)

        # Output view (bottom half)
        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)

        output_label = QLabel("Output Preview:")
        output_layout.addWidget(output_label)

        # Output tab widget
        self.output_tabs = QTabWidget()

        # Text/Raw tab
        self.output_text_viewer = OutputTextViewer()
        self.output_tabs.addTab(self.output_text_viewer, "Text/Raw")

        # Table tab
        self.output_table_viewer = DataTableViewer()
        self.output_tabs.addTab(self.output_table_viewer, "Table")

        # Plot tab
        self.output_plot_viewer = DataPlotViewer()
        self.output_tabs.addTab(self.output_plot_viewer, "Plot")

        output_layout.addWidget(self.output_tabs)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_selected_btn = QPushButton("Save Selected Output")
        self.save_selected_btn.clicked.connect(self.save_selected_output)
        self.save_selected_btn.setEnabled(False)
        button_layout.addWidget(self.save_selected_btn)

        self.convert_all_btn = QPushButton("Convert and Save All")
        self.convert_all_btn.clicked.connect(self.convert_all_files)
        self.convert_all_btn.setEnabled(False)
        button_layout.addWidget(self.convert_all_btn)

        output_layout.addLayout(button_layout)
        splitter.addWidget(output_container)

        # Set splitter proportions
        splitter.setSizes([400, 400])

        main_layout.addWidget(splitter)

    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu('File')
        help_menu = menubar.addMenu('Help')

        # File menu actions
        select_action = QAction('Select Input Folder', self)
        select_action.triggered.connect(self.select_input_folder)
        file_menu.addAction(select_action)

        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu actions
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def select_input_crs(self):
        """Select input coordinate reference system"""
        dialog = CRSSelectionDialog(self, "Select Input CRS")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.input_crs = dialog.selected_crs
            self.input_crs_name = dialog.selected_name
            self.input_crs_label.setText(f"Input CRS: {self.input_crs_name}\nEPSG: {self.input_crs.split(':')[1]}")
            self.status_bar.showMessage(f"Input CRS set to {self.input_crs_name} ({self.input_crs})")

            # Update all GridFile objects with new input CRS and clear preview cache
            for grid_file in self.grid_files.values():
                grid_file.input_crs = self.input_crs
                grid_file._recompute_outputs()

            # Clear preview cache since CRS changed
            self.preview_cache.clear()

            # Regenerate preview if a file is currently selected
            current_item = self.file_tree.currentItem()
            if current_item:
                filename = current_item.text(0)
                if filename in self.grid_files:
                    QTimer.singleShot(100, lambda: self.generate_preview(filename))

    def select_output_crs(self):
        """Select output coordinate reference system"""
        dialog = CRSSelectionDialog(self, "Select Output CRS")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.output_crs = dialog.selected_crs
            self.output_crs_name = dialog.selected_name
            self.output_crs_label.setText(f"Output CRS: {self.output_crs_name}\nEPSG: {self.output_crs.split(':')[1]}")
            self.status_bar.showMessage(f"Output CRS set to {self.output_crs_name} ({self.output_crs})")

            # Update all GridFile objects with new output CRS and clear preview cache
            for grid_file in self.grid_files.values():
                grid_file.output_crs = self.output_crs
                grid_file._recompute_outputs()

            # Clear preview cache since CRS changed
            self.preview_cache.clear()

            # Regenerate preview if a file is currently selected
            current_item = self.file_tree.currentItem()
            if current_item:
                filename = current_item.text(0)
                if filename in self.grid_files:
                    QTimer.singleShot(100, lambda: self.generate_preview(filename))

    def select_input_folder(self):
        """Select input folder containing grid files"""
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder Containing Grid Files")
        if folder:
            self.input_folder = folder
            self.load_grid_files(folder)

    def select_output_folder(self):
        """Select output folder for transformed files"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.status_bar.showMessage(f"Output folder set to: {folder}")
    
    def on_default_delimiter_changed(self):
        """Handle default delimiter change"""
        delimiter_text = self.default_delimiter_combo.currentText()
        if delimiter_text == "Comma (,)":
            self.default_delimiter = ","
        elif delimiter_text == "Space ( )":
            self.default_delimiter = " "
        elif delimiter_text == "Tab (\\t)":
            self.default_delimiter = "\t"

        self.status_bar.showMessage(f"Default delimiter set to: {delimiter_text}")

        # Update all GridFile objects with new default delimiter
        for grid_file in self.grid_files.values():
            if grid_file.input_delimiter is None:  # Only update if auto-detected
                grid_file.input_delimiter = self.default_delimiter
                grid_file._recompute_outputs()

    def on_output_delimiter_changed(self):
        """Handle output delimiter change"""
        delimiter_text = self.output_delimiter_combo.currentText()
        if delimiter_text == "Comma (,)":
            self.output_delimiter = ","
        elif delimiter_text == "Space ( )":
            self.output_delimiter = " "
        elif delimiter_text == "Tab (\\t)":
            self.output_delimiter = "\t"
        elif delimiter_text == "Semicolon (;)":
            self.output_delimiter = ";"

        self.status_bar.showMessage(f"Output delimiter set to: {delimiter_text}")

        # Update all GridFile objects with new output delimiter
        for grid_file in self.grid_files.values():
            grid_file.output_delimiter = self.output_delimiter
            grid_file._recompute_outputs()

        # Clear preview cache since output format changed
        self.preview_cache.clear()

        # Regenerate preview if a file is currently selected
        current_item = self.file_tree.currentItem()
        if current_item:
            filename = current_item.text(0)
            if filename in self.grid_files:
                QTimer.singleShot(100, lambda: self.generate_preview(filename))
    
    def on_file_delimiter_changed(self):
        """Handle file-specific delimiter change"""
        current_item = self.file_tree.currentItem()
        if current_item:
            filename = current_item.text(0)
            delimiter_text = self.file_delimiter_combo.currentText()

            if filename in self.grid_files:
                grid_file = self.grid_files[filename]

                # Set the delimiter on the GridFile object
                if delimiter_text == "Auto":
                    # Re-parse with auto-detection
                    grid_file.input_delimiter = None
                    if grid_file.read() and grid_file.parse():
                        delimiter = grid_file.input_delimiter or self.default_delimiter
                    else:
                        delimiter = self.default_delimiter
                elif delimiter_text == "Comma (,)":
                    delimiter = ","
                    grid_file.input_delimiter = delimiter
                elif delimiter_text == "Space ( )":
                    delimiter = " "
                    grid_file.input_delimiter = delimiter
                elif delimiter_text == "Tab (\\t)":
                    delimiter = "\t"
                    grid_file.input_delimiter = delimiter
                else:
                    delimiter = self.default_delimiter
                    grid_file.input_delimiter = delimiter

                # Re-parse the file with new delimiter
                grid_file.parse()

                self.file_delimiters[filename] = delimiter
                current_item.setText(1, delimiter_text)

                # Update column dropdowns based on detected columns
                self.update_column_dropdowns(filename, delimiter)

                # Clear preview cache for this file
                preview_cache_key = f"{filename}_preview"
                if preview_cache_key in self.preview_cache:
                    del self.preview_cache[preview_cache_key]

                # Regenerate preview with new delimiter (use QTimer to prevent blocking)
                QTimer.singleShot(100, lambda: self.generate_preview(filename))

                # Also update the input views immediately to reflect the new delimiter
                self.update_input_views(filename)

    def update_column_dropdowns(self, filename, delimiter):
        """Update column selection dropdowns based on file and delimiter"""
        if filename not in self.grid_files:
            return

        grid_file = self.grid_files[filename]
        if grid_file.input_df is None:
            return

        # Get number of columns from the parsed DataFrame
        max_columns = len(grid_file.input_df.columns)

        # Update dropdowns
        column_options = [f"Col {i+1}" for i in range(max_columns)]
        if not column_options:
            column_options = ["Col 1", "Col 2", "Col 3"]

        self.x_column_combo.clear()
        self.y_column_combo.clear()
        self.z_column_combo.clear()

        self.x_column_combo.addItems(column_options)
        self.y_column_combo.addItems(column_options)
        self.z_column_combo.addItems(column_options)

        # Set defaults (assuming X=1, Y=2, Z=3)
        if len(column_options) >= 3:
            self.x_column_combo.setCurrentIndex(0)  # Col 1 (X)
            self.y_column_combo.setCurrentIndex(1)  # Col 2 (Y)
            self.z_column_combo.setCurrentIndex(2)  # Col 3 (Z)

        # Store column indices for this file
        self.file_columns[filename] = {
            'x_col': 0,  # 0-based index
            'y_col': 1,
            'z_col': 2
        }

        # Enable dropdowns
        self.x_column_combo.setEnabled(True)
        self.y_column_combo.setEnabled(True)
        self.z_column_combo.setEnabled(True)

        # Connect change handlers (only once to avoid duplicates)
        try:
            self.x_column_combo.currentIndexChanged.disconnect()
            self.y_column_combo.currentIndexChanged.disconnect()
            self.z_column_combo.currentIndexChanged.disconnect()
        except:
            pass  # Ignore if not connected

        self.x_column_combo.currentIndexChanged.connect(lambda: self.on_column_changed(filename, 'x'))
        self.y_column_combo.currentIndexChanged.connect(lambda: self.on_column_changed(filename, 'y'))
        self.z_column_combo.currentIndexChanged.connect(lambda: self.on_column_changed(filename, 'z'))

    def on_column_changed(self, filename, column_type):
        """Handle column selection changes"""
        if filename not in self.file_columns:
            self.file_columns[filename] = {'x_col': 0, 'y_col': 1, 'z_col': 2}

        if column_type == 'x':
            self.file_columns[filename]['x_col'] = self.x_column_combo.currentIndex()
        elif column_type == 'y':
            self.file_columns[filename]['y_col'] = self.y_column_combo.currentIndex()
        elif column_type == 'z':
            self.file_columns[filename]['z_col'] = self.z_column_combo.currentIndex()

        # Note: GridFile class doesn't support custom column mapping yet
        # This would require extending GridFile to handle custom column indices
        # For now, we'll keep the column selection UI but it won't affect processing

        # Clear preview cache and regenerate preview with new column selections
        preview_cache_key = f"{filename}_preview"
        if preview_cache_key in self.preview_cache:
            del self.preview_cache[preview_cache_key]

        if filename in self.grid_files:
            # Use QTimer to prevent blocking UI during preview generation
            QTimer.singleShot(200, lambda: self.generate_preview(filename))
    
    def auto_detect_delimiter(self, filename):
        """Auto-detect delimiter for a file using GridFile's method"""
        if filename not in self.grid_files:
            return self.default_delimiter

        grid_file = self.grid_files[filename]
        return grid_file._detect_delimiter()

    def update_input_views(self, filename):
        """Update all input view tabs with current file data"""
        if filename not in self.grid_files:
            return

        grid_file = self.grid_files[filename]

        # Update text view - show raw input data
        if grid_file.input_raw:
            try:
                # Show first 100 lines of raw data
                lines = grid_file.input_raw.split('\n')[:100]
                text_content = f"-- Input: {filename} --\n\n"
                text_content += '\n'.join(lines)
                if len(grid_file.input_raw.split('\n')) > 100:
                    text_content += f"\n\n... ({len(grid_file.input_raw.split('\n')) - 100} more lines) ..."
                self.input_text_viewer.setPlainText(text_content)
            except Exception as e:
                self.input_text_viewer.setPlainText(f"Error displaying text: {str(e)}")

        # Update table view
        if grid_file.input_df is not None:
            try:
                self.input_table_viewer.display_dataframe(grid_file.input_df.head(1000), f"Input: {filename}")
            except Exception as e:
                self.input_table_viewer.display_dataframe(None, f"Input: {filename} (Error: {str(e)})")

        # Update plot view
        if grid_file.input_df is not None:
            try:
                self.input_plot_viewer.plot_dataframe(grid_file.input_df, f"Input: {filename}")
            except Exception as e:
                # Just skip plotting if there's an error
                pass

    def update_output_views(self, grid_file, title):
        """Update all output view tabs with transformed data"""
        # Update text view - show transformed raw data
        if grid_file.output_raw:
            try:
                text_content = f"-- {title} --\n\n"
                lines = grid_file.output_raw.split('\n')[:100]
                text_content += '\n'.join(lines)
                if len(grid_file.output_raw.split('\n')) > 100:
                    text_content += f"\n\n... ({len(grid_file.output_raw.split('\n')) - 100} more lines) ..."
                self.output_text_viewer.setPlainText(text_content)
            except Exception as e:
                self.output_text_viewer.setPlainText(f"Error displaying output text: {str(e)}")

        # Update table view
        if grid_file.output_df is not None:
            try:
                self.output_table_viewer.display_dataframe(grid_file.output_df.head(1000), title)
            except Exception as e:
                self.output_table_viewer.display_dataframe(None, f"{title} (Error: {str(e)})")

        # Update plot view
        if grid_file.output_df is not None:
            try:
                self.output_plot_viewer.plot_dataframe(grid_file.output_df, title)
            except Exception as e:
                # Just skip plotting if there's an error
                pass

    def load_grid_files(self, folder):
        """Load grid files from selected folder"""
        self.file_tree.clear()
        self.grid_files.clear()
        self.preview_cache.clear()
        self.file_delimiters.clear()
        self.file_columns.clear()

        # Look for all files in the selected folder
        all_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

        if not all_files:
            QMessageBox.warning(self, "Warning", f"No files found in {folder}")
            return

        # Create tree items for each file
        loaded_count = 0
        for filename in sorted(all_files):
            file_path = os.path.join(folder, filename)
            item = QTreeWidgetItem([filename, "Loading..."])

            try:
                # Check file size first (limit to 50MB for performance)
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:  # 50MB limit
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setText(1, "File too large")
                    self.file_tree.addTopLevelItem(item)
                    continue

                # Create GridFile object (CRS will be set later by GUI)
                grid_file = GridFile(file_path, output_delimiter=self.output_delimiter)

                # Read and parse the file
                if grid_file.read() and grid_file.parse():
                    self.grid_files[filename] = grid_file

                    # Set delimiter display text
                    delimiter = grid_file.input_delimiter or ','
                    if delimiter == ",":
                        delimiter_display = "Comma (,)"
                    elif delimiter == " ":
                        delimiter_display = "Space ( )"
                    elif delimiter == "\t":
                        delimiter_display = "Tab (\\t)"
                    else:
                        delimiter_display = "Auto"

                    item.setText(1, delimiter_display)
                    item.setCheckState(0, Qt.CheckState.Checked)
                    loaded_count += 1
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setText(1, "Parse failed")

            except Exception as e:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setText(1, f"Error: {str(e)[:20]}")

            self.file_tree.addTopLevelItem(item)

        if loaded_count > 0:
            self.status_bar.showMessage(f"Loaded {loaded_count} files from {folder}")
            self.convert_all_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "Warning", f"Could not load any files from {folder}")

    def on_file_selected(self, item, column):
        """Handle file selection in tree"""
        filename = item.text(0)

        if filename in self.grid_files:
            grid_file = self.grid_files[filename]

            # Update file delimiter combo to match detected delimiter
            delimiter = grid_file.input_delimiter or ','
            if delimiter == ",":
                self.file_delimiter_combo.setCurrentText("Comma (,)")
            elif delimiter == " ":
                self.file_delimiter_combo.setCurrentText("Space ( )")
            elif delimiter == "\t":
                self.file_delimiter_combo.setCurrentText("Tab (\\t)")
            else:
                self.file_delimiter_combo.setCurrentText("Auto")

            # Update column dropdowns for this file
            self.update_column_dropdowns(filename, delimiter)

            # Update input views - wrap in try-catch to prevent crashes
            try:
                self.update_input_views(filename)
            except Exception as e:
                QMessageBox.warning(self, "Display Error", f"Error displaying input data: {str(e)}")

            # Generate preview transformation - wrap in try-catch
            try:
                self.generate_preview(filename)
            except Exception as e:
                QMessageBox.warning(self, "Preview Error", f"Error generating preview: {str(e)}")

            # Enable save button since we have a selected file
            self.save_selected_btn.setEnabled(True)

    def generate_preview(self, filename):
        """Generate preview of transformed data"""
        if filename not in self.grid_files:
            return

        # Always show output preview, even without CRS transformation
        grid_file = self.grid_files[filename]

        # Check cache first (use different cache key for non-transformed vs transformed)
        if self.input_crs and self.output_crs:
            cache_key = f"{filename}_preview_{self.input_crs}_{self.output_crs}_transformed"
            preview_title = f"Preview: {filename} ({self.input_crs_name} → {self.output_crs_name})"
            do_transform = True
        else:
            cache_key = f"{filename}_preview_no_transform"
            preview_title = f"Preview: {filename} (No transformation - CRS not selected)"
            do_transform = False

        if cache_key in self.preview_cache:
            cached_result = self.preview_cache[cache_key]
            try:
                self.update_output_views(cached_result['grid_file'], cached_result['title'])
                self.save_selected_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.warning(self, "Cache Error", f"Error loading cached preview: {str(e)}")
            return

        try:
            # Set CRS from GUI selection (may be empty)
            grid_file.input_crs = self.input_crs
            grid_file.output_crs = self.output_crs

            # Transform the data if CRS are selected, otherwise just prepare output format
            if do_transform:
                success = grid_file.transform()
            else:
                # No transformation - just prepare output with selected delimiter and header settings
                success = True
                grid_file.output_df = grid_file.input_df.copy() if grid_file.input_df is not None else None
                grid_file._generate_output_raw(include_column_headers=self.include_column_headers_checkbox.isChecked(),
                                             remove_input_headers=self.remove_input_headers_checkbox.isChecked())

            if success:
                # Cache the result
                cache_result = {
                    'grid_file': grid_file,
                    'title': preview_title
                }
                self.preview_cache[cache_key] = cache_result

                try:
                    self.update_output_views(grid_file, preview_title)
                    self.save_selected_btn.setEnabled(True)
                except Exception as e:
                    QMessageBox.warning(self, "Display Error", f"Error displaying preview: {str(e)}")
            else:
                QMessageBox.warning(self, "Preview Error", f"Failed to process {filename}")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error generating preview: {str(e)}")

    def save_selected_output(self):
        """Save the currently selected file's transformed output"""
        if not self.output_folder:
            QMessageBox.warning(self, "Warning", "Please select an output folder first")
            return

        current_item = self.file_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "No file selected")
            return

        filename = current_item.text(0)
        if filename not in self.grid_files:
            QMessageBox.warning(self, "Warning", "No data available for selected file")
            return

        try:
            grid_file = self.grid_files[filename]

            # Ensure the file has output data (transformed or not)
            if grid_file.output_df is None and grid_file.output_raw is None:
                if not grid_file.transform():
                    QMessageBox.warning(self, "Error", f"Failed to process {filename}")
                    return

            # Set output generation options
            grid_file._generate_output_raw(include_column_headers=self.include_column_headers_checkbox.isChecked(),
                                          remove_input_headers=self.remove_input_headers_checkbox.isChecked())

            # Write the transformed data
            if grid_file.write(self.output_folder):
                QMessageBox.information(self, "Success",
                                      f"File saved successfully to {grid_file.output_path}\n"
                                      f"Transformed from {self.input_crs_name} to {self.output_crs_name}")
            else:
                QMessageBox.critical(self, "Error", f"Failed to save {filename}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving file: {str(e)}")

    # Remove the old generate_transformation_for_file method as it's no longer needed
    # The GridFile class handles all transformation logic now

    def convert_all_files(self):
        """Convert and save all files"""
        if not self.grid_files:
            QMessageBox.warning(self, "Warning", "No files loaded")
            return

        if not self.output_folder:
            QMessageBox.warning(self, "Warning", "Please select an output folder first")
            return

        # Check for existing files if overwrite is not enabled
        if not self.overwrite_checkbox.isChecked():
            existing_files = []
            for filename in self.grid_files.keys():
                output_path = os.path.join(self.output_folder, filename)
                if os.path.exists(output_path):
                    existing_files.append(filename)

            if existing_files:
                reply = QMessageBox.question(
                    self, "Overwrite Confirmation",
                    f"The following files already exist in the output folder:\n\n" +
                    "\n".join(existing_files[:5]) +  # Show first 5
                    (f"\n... and {len(existing_files) - 5} more" if len(existing_files) > 5 else "") +
                    "\n\nDo you want to overwrite all existing output files?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.No:
                    return

        # Transform and save each file
        success_count = 0
        error_files = []

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        total_files = len(self.grid_files)

        for i, (filename, grid_file) in enumerate(self.grid_files.items()):
            try:
                # Set CRS from GUI selection before transforming
                grid_file.input_crs = self.input_crs
                grid_file.output_crs = self.output_crs

                # Only transform if both CRS are selected
                if self.input_crs and self.output_crs:
                    transform_success = grid_file.transform()
                else:
                    # No transformation - just prepare output with selected delimiter and header settings
                    transform_success = True
                    grid_file.output_df = grid_file.input_df.copy() if grid_file.input_df is not None else None
                    grid_file._generate_output_raw(include_column_headers=self.include_column_headers_checkbox.isChecked(),
                                                  remove_input_headers=self.remove_input_headers_checkbox.isChecked())

                if transform_success:
                    # Write the file
                    if grid_file.write(self.output_folder):
                        success_count += 1
                    else:
                        error_files.append(f"{filename}: Write failed")
                else:
                    error_files.append(f"{filename}: Transform failed")

            except Exception as e:
                error_files.append(f"{filename}: {str(e)}")

            # Update progress
            self.progress_bar.setValue(int((i + 1) / total_files * 100))

        self.progress_bar.setVisible(False)

        # Show results
        if success_count > 0:
            message = f"Successfully transformed and saved {success_count} files to {self.output_folder}"
            if error_files:
                message += f"\n\nErrors occurred with {len(error_files)} files:\n" + "\n".join(error_files[:5])
                if len(error_files) > 5:
                    message += f"\n... and {len(error_files) - 5} more errors"
            QMessageBox.information(self, "Batch Conversion Complete", message)
        else:
            QMessageBox.critical(self, "Batch Conversion Failed",
                                f"Failed to convert any files.\n\nErrors:\n" + "\n".join(error_files[:10]))

    # Remove old worker-related methods as they're no longer needed

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About",
                         "Grid Transformation Tool\n\n"
                         "Transforms grid data from one coordinate system to another.\n\n"
                         "Built with PyQt6 and pyproj.")

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Grid Transformation Tool")
    app.setApplicationVersion("1.0.0")

    # Create and show main window
    window = GridLabApp()
    window.show()

    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()