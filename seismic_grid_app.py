#!/usr/bin/env python3
"""
Seismic Grid Transformation Application
PyQt6 GUI for transforming seismic grid data from NAD27 to NAD83
"""

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTreeWidget, QTreeWidgetItem, QTextEdit, QPushButton, QFileDialog,
                             QSplitter, QMenuBar, QMessageBox, QProgressBar, QStatusBar,
                             QLabel, QFrame, QDialog, QLineEdit, QListWidget, QListWidgetItem,
                             QGroupBox, QCheckBox, QComboBox, QHBoxLayout, QTabWidget, QTableWidget,
                             QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont

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

            print(f"Loaded {len(crs_list)} CRS definitions")
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
        print(f"Populating CRS list with {len(self.available_crs)} items")  # Debug print
        for crs in self.available_crs:
            item_text = f"EPSG:{crs['epsg']} - {crs['name']}"
            if crs['area'] != 'Unknown':
                item_text += f" ({crs['area']})"

            print(f"Adding item: {item_text}")  # Debug print
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, crs)
            self.crs_list.addItem(item)

        print(f"CRS list now has {self.crs_list.count()} items")  # Debug print

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

class TransformationWorker(QThread):
    """Worker thread for coordinate transformations"""
    progress_updated = pyqtSignal(int)
    transformation_complete = pyqtSignal(str, object)  # filename, transformed_data
    error_occurred = pyqtSignal(str)

    def __init__(self, files_to_transform, input_crs="EPSG:4326", output_crs="EPSG:4326", remove_headers=True):
        super().__init__()
        self.files_to_transform = files_to_transform
        self.input_crs = input_crs
        self.output_crs = output_crs
        self.remove_headers = remove_headers

    def run(self):
        """Run the transformation process"""
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)
        except Exception as e:
            self.error_occurred.emit(f"Failed to create coordinate transformation: {e}\nPlease ensure pyproj is properly installed and the selected CRS codes are valid.")
            return

        total_files = len(self.files_to_transform)

        for i, (input_file, output_file) in enumerate(self.files_to_transform):
            try:
                # Transform and save the file directly
                self.transform_and_save_file(input_file, output_file, transformer)
                self.transformation_complete.emit(output_file, [])  # Empty data since file is already saved
                self.progress_updated.emit(int((i + 1) / total_files * 100))
            except Exception as e:
                self.error_occurred.emit(f"Error transforming {input_file}: {e}")

    def transform_and_save_file(self, input_file, output_file, transformer):
        """Transform a single file and save it directly"""
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        filename = os.path.basename(input_file)
        delimiter = self.file_delimiters.get(filename, self.default_delimiter)
        columns = self.file_columns.get(filename, {'x_col': 0, 'y_col': 1, 'z_col': 2})
        remove_headers = self.remove_headers_checkbox.isChecked()

        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line_num, line in enumerate(infile, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    # Skip header/comment lines if remove_headers is enabled
                    if remove_headers and (line.startswith('!') or line.startswith('@')):
                        continue

                    # Handle fault files (fixed-width format)
                    if input_file.endswith('Faults.dat'):
                        if len(line) >= 41:
                            x_str = line[0:12].strip()
                            y_str = line[12:24].strip()
                            z_str = line[24:36].strip()

                            x = float(x_str)
                            y = float(y_str)
                            z = float(z_str) if z_str != '1e+030' else 9999999.0

                            # Transform coordinates using pyproj
                            x_new, y_new = transformer.transform(x, y)

                            outfile.write(f"{x_new:12.2f}{y_new:12.2f}{z:12.6f}     1    \n")
                        else:
                            outfile.write(line + '\n')
                    else:
                        # Handle delimited format
                        parts = line.split(delimiter)
                        if len(parts) > max(columns['x_col'], columns['y_col'], columns['z_col']):
                            try:
                                x = float(parts[columns['x_col']])
                                y = float(parts[columns['y_col']])
                                z = float(parts[columns['z_col']])

                                # Transform coordinates using pyproj
                                x_new, y_new = transformer.transform(x, y)

                                outfile.write(f"{x_new:.5f}{delimiter}{y_new:.5f}{delimiter}{z:.4f}\n")
                            except (ValueError, IndexError):
                                outfile.write(line + '\n')
                        else:
                            outfile.write(line + '\n')

                except Exception as e:
                    raise Exception(f"Failed to transform line {line_num}: {e}")

class DataTableViewer(QTableWidget):
    """Table viewer for displaying parsed data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["X Coordinate", "Y Coordinate", "Z Value"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setAlternatingRowColors(True)
        self.max_rows = 1000  # Limit for performance

    def display_parsed_data(self, data_lines, delimiter=",", title="Parsed Data", columns=None):
        """Display parsed data in table format"""
        self.clearContents()
        self.setRowCount(0)

        if columns is None:
            columns = {'x_col': 0, 'y_col': 1, 'z_col': 2}

        row_count = 0
        for line in data_lines:
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('@'):
                continue

            try:
                if delimiter and len(line.split(delimiter)) > max(columns['x_col'], columns['y_col'], columns['z_col']):
                    parts = line.split(delimiter)
                    x = float(parts[columns['x_col']])
                    y = float(parts[columns['y_col']])
                    z = float(parts[columns['z_col']])

                    self.insertRow(row_count)
                    self.setItem(row_count, 0, QTableWidgetItem(f"{x:.5f}"))
                    self.setItem(row_count, 1, QTableWidgetItem(f"{y:.5f}"))
                    self.setItem(row_count, 2, QTableWidgetItem(f"{z:.4f}"))
                    row_count += 1

                    if row_count >= 1000:  # Performance limit
                        break
                elif not delimiter and len(line) >= 41:  # Fault file format
                    x_str = line[0:12].strip()
                    y_str = line[12:24].strip()
                    z_str = line[24:36].strip()

                    if x_str and y_str:
                        x = float(x_str)
                        y = float(y_str)
                        z = float(z_str) if z_str != '1e+030' else 0.0

                        self.insertRow(row_count)
                        self.setItem(row_count, 0, QTableWidgetItem(f"{x:.2f}"))
                        self.setItem(row_count, 1, QTableWidgetItem(f"{y:.2f}"))
                        self.setItem(row_count, 2, QTableWidgetItem(f"{z:.4f}"))
                        row_count += 1

                        if row_count >= self.max_rows:  # Performance limit
                            break

            except (ValueError, IndexError):
                continue

        if row_count == 0:
            self.insertRow(0)
            self.setItem(0, 0, QTableWidgetItem("No valid data found"))
            self.setItem(0, 1, QTableWidgetItem(""))
            self.setItem(0, 2, QTableWidgetItem(""))

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

    def plot_data(self, data_lines, delimiter=",", title="Data Plot", columns=None):
        """Plot data points"""
        self.axes.clear()

        if columns is None:
            columns = {'x_col': 0, 'y_col': 1, 'z_col': 2}

        x_coords = []
        y_coords = []
        z_values = []

        for line in data_lines[:5000]:  # Limit for performance
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('@'):
                continue

            try:
                if delimiter and len(line.split(delimiter)) > max(columns['x_col'], columns['y_col'], columns['z_col']):
                    parts = line.split(delimiter)
                    x = float(parts[columns['x_col']])
                    y = float(parts[columns['y_col']])
                    z = float(parts[columns['z_col']])
                    x_coords.append(x)
                    y_coords.append(y)
                    z_values.append(z)
                elif not delimiter and len(line) >= 41:  # Fault file format
                    x_str = line[0:12].strip()
                    y_str = line[12:24].strip()
                    z_str = line[24:36].strip()

                    if x_str and y_str:
                        x = float(x_str)
                        y = float(y_str)
                        z = float(z_str) if z_str != '1e+030' else 0.0
                        x_coords.append(x)
                        y_coords.append(y)
                        z_values.append(z)

            except (ValueError, IndexError):
                continue

        if x_coords and y_coords:
            scatter = self.axes.scatter(x_coords, y_coords, c=z_values, cmap='viridis', s=2, alpha=0.7)
            self.axes.set_xlabel('X Coordinate')
            self.axes.set_ylabel('Y Coordinate')
            self.axes.set_title(title)
            self.axes.grid(True, alpha=0.3)
            self.figure.colorbar(scatter, ax=self.axes, label='Z Value')
        else:
            self.axes.text(0.5, 0.5, 'No valid data points to plot',
                         transform=self.axes.transAxes, ha='center', va='center')
            self.axes.set_title(title)

        self.canvas.draw()

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

class SeismicGridApp(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.current_data = {}
        self.transformed_data = {}
        self.input_crs = "EPSG:4326"
        self.input_crs_name = "WGS84"
        self.output_crs = "EPSG:4326"
        self.output_crs_name = "WGS84"
        self.input_folder = ""
        self.output_folder = ""
        self.default_delimiter = ","  # Default delimiter
        self.file_columns = {}  # Store column indices for each file
        self.file_delimiters = {}  # Store delimiter for each file

        # Performance optimization caches
        self.file_cache = {}  # Cache for file data
        self.delimiter_cache = {}  # Cache for detected delimiters
        self.column_cache = {}  # Cache for column detection
        self.preview_cache = {}  # Cache for preview transformations

        self.setWindowTitle("Seismic Grid Transformation Tool")
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

        # Initialize worker thread
        self.worker = None

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

        self.input_crs_label = QLabel("Input CRS: WGS84\nEPSG: 4326")
        crs_layout.addWidget(self.input_crs_label)

        # Output CRS selector
        self.select_output_crs_btn = QPushButton("Select Output CRS")
        self.select_output_crs_btn.clicked.connect(self.select_output_crs)
        crs_layout.addWidget(self.select_output_crs_btn)

        self.output_crs_label = QLabel("Output CRS: WGS84\nEPSG: 4326")
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

        # Remove headers checkbox
        self.remove_headers_checkbox = QCheckBox("Remove headers/comments from output")
        self.remove_headers_checkbox.setChecked(True)  # Default to removing headers
        files_layout.addWidget(self.remove_headers_checkbox)

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

    def select_output_crs(self):
        """Select output coordinate reference system"""
        dialog = CRSSelectionDialog(self, "Select Output CRS")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.output_crs = dialog.selected_crs
            self.output_crs_name = dialog.selected_name
            self.output_crs_label.setText(f"Output CRS: {self.output_crs_name}\nEPSG: {self.output_crs.split(':')[1]}")
            self.status_bar.showMessage(f"Output CRS set to {self.output_crs_name} ({self.output_crs})")

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
    
    def on_file_delimiter_changed(self):
        """Handle file-specific delimiter change"""
        current_item = self.file_tree.currentItem()
        if current_item:
            filename = current_item.text(0)
            delimiter_text = self.file_delimiter_combo.currentText()

            # Use cached delimiter if available
            cache_key = f"{filename}_delimiter"
            if cache_key in self.delimiter_cache and delimiter_text == "Auto":
                delimiter = self.delimiter_cache[cache_key]
            else:
                if delimiter_text == "Auto":
                    delimiter = self.auto_detect_delimiter(filename)
                    self.delimiter_cache[cache_key] = delimiter
                elif delimiter_text == "Comma (,)":
                    delimiter = ","
                elif delimiter_text == "Space ( )":
                    delimiter = " "
                elif delimiter_text == "Tab (\\t)":
                    delimiter = "\t"
                else:
                    delimiter = self.default_delimiter

            self.file_delimiters[filename] = delimiter
            current_item.setText(1, delimiter_text)

            # Update column dropdowns based on detected columns
            self.update_column_dropdowns(filename, delimiter)

            # Clear preview cache for this file
            preview_cache_key = f"{filename}_preview"
            if preview_cache_key in self.preview_cache:
                del self.preview_cache[preview_cache_key]

            # Regenerate preview with new delimiter (use QTimer to prevent blocking)
            if filename in self.current_data:
                QTimer.singleShot(100, lambda: self.generate_preview(filename))

    def update_column_dropdowns(self, filename, delimiter):
        """Update column selection dropdowns based on file and delimiter"""
        if filename not in self.current_data:
            return

        # Check cache first
        cache_key = f"{filename}_{delimiter}_columns"
        if cache_key in self.column_cache:
            max_columns = self.column_cache[cache_key]
        else:
            # Detect number of columns
            sample_lines = self.current_data[filename][:10]
            max_columns = 0

            for line in sample_lines:
                line = line.strip()
                if not line or line.startswith('!') or line.startswith('@'):
                    continue

                if delimiter and delimiter in line:
                    columns = line.split(delimiter)
                    max_columns = max(max_columns, len(columns))
                elif not delimiter and len(line) >= 41:  # Fault file format
                    max_columns = 3  # Fixed format: X, Y, Z

            # Cache the result
            self.column_cache[cache_key] = max_columns

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

        # Clear preview cache and regenerate preview with new column selections
        preview_cache_key = f"{filename}_preview"
        if preview_cache_key in self.preview_cache:
            del self.preview_cache[preview_cache_key]

        if filename in self.current_data:
            # Use QTimer to prevent blocking UI during preview generation
            QTimer.singleShot(200, lambda: self.generate_preview(filename))
    
    def auto_detect_delimiter(self, filename):
        """Auto-detect delimiter for a file"""
        if filename not in self.current_data:
            return self.default_delimiter

        # Check cache first
        cache_key = f"{filename}_auto_delimiter"
        if cache_key in self.delimiter_cache:
            return self.delimiter_cache[cache_key]

        # Sample first few lines to detect delimiter
        sample_lines = self.current_data[filename][:10]

        # Count occurrences of common delimiters
        comma_count = 0
        space_count = 0
        tab_count = 0

        for line in sample_lines:
            if not line.strip() or line.startswith('!') or line.startswith('@'):
                continue
            comma_count += line.count(',')
            space_count += line.count(' ')
            tab_count += line.count('\t')

        # Return delimiter with highest count
        max_count = max(comma_count, space_count, tab_count)
        if max_count == comma_count:
            result = ","
        elif max_count == tab_count:
            result = "\t"
        elif max_count == space_count:
            result = " "
        else:
            result = self.default_delimiter

        # Cache the result
        self.delimiter_cache[cache_key] = result
        return result

    def update_input_views(self, filename, delimiter, columns=None):
        """Update all input view tabs with current file data"""
        if filename not in self.current_data:
            return

        if columns is None:
            columns = {'x_col': 0, 'y_col': 1, 'z_col': 2}

        data_lines = self.current_data[filename]

        # Text/Raw tab
        self.input_text_viewer.setPlainText(''.join(data_lines[:100]))  # First 100 lines

        # Table tab
        self.input_table_viewer.display_parsed_data(data_lines, delimiter, f"Input: {filename}", columns)

        # Plot tab
        self.input_plot_viewer.plot_data(data_lines, delimiter, f"Input: {filename}", columns)

    def update_output_views(self, data_lines, delimiter, title, columns=None):
        """Update all output view tabs with transformed data"""
        if columns is None:
            columns = {'x_col': 0, 'y_col': 1, 'z_col': 2}

        # Text/Raw tab
        self.output_text_viewer.display_transformed_data(data_lines, title)

        # Table tab
        self.output_table_viewer.display_parsed_data(data_lines, delimiter, title, columns)

        # Plot tab
        self.output_plot_viewer.plot_data(data_lines, delimiter, title, columns)

    def load_grid_files(self, folder):
        """Load grid files from selected folder"""
        self.file_tree.clear()
        self.current_data.clear()
        self.transformed_data.clear()

        # Clear caches when loading new files
        self.delimiter_cache.clear()
        self.column_cache.clear()
        self.preview_cache.clear()

        # Look for all files (not just .dat) in the selected folder
        all_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

        if not all_files:
            QMessageBox.warning(self, "Warning", f"No files found in {folder}")
            return

        # Create tree items for each file
        loaded_count = 0
        for filename in sorted(all_files):
            file_path = os.path.join(folder, filename)
            item = QTreeWidgetItem([filename, "Auto"])  # Default to Auto detection

            # Load file data (with size limit for performance)
            try:
                # Check file size first (limit to 50MB for performance)
                file_size = os.path.getsize(file_path)
                if file_size > 50 * 1024 * 1024:  # 50MB limit
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setText(1, "File too large")
                    self.file_tree.addTopLevelItem(item)
                    continue

                with open(file_path, 'r') as f:
                    # Read first 10000 lines for processing, cache full file path for later use
                    lines = []
                    for i, line in enumerate(f):
                        lines.append(line)
                        if i >= 9999:  # Limit initial load
                            break
                    self.current_data[filename] = lines
                    self.file_cache[filename] = file_path  # Store full path for lazy loading

                # Auto-detect delimiter
                detected_delimiter = self.auto_detect_delimiter(filename)
                self.file_delimiters[filename] = detected_delimiter

                # Set delimiter display text
                if detected_delimiter == ",":
                    delimiter_display = "Comma (,)"
                elif detected_delimiter == " ":
                    delimiter_display = "Space ( )"
                elif detected_delimiter == "\t":
                    delimiter_display = "Tab (\\t)"
                else:
                    delimiter_display = "Auto"

                item.setText(1, delimiter_display)

                # Set check state to indicate data loaded
                item.setCheckState(0, Qt.CheckState.Checked)
                loaded_count += 1
            except Exception as e:
                item.setCheckState(0, Qt.CheckState.Unchecked)
                item.setText(1, "Error")

            self.file_tree.addTopLevelItem(item)

        if loaded_count > 0:
            self.status_bar.showMessage(f"Loaded {loaded_count} files from {folder}")
            self.convert_all_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "Warning", f"Could not load any files from {folder}")

    def on_file_selected(self, item, column):
        """Handle file selection in tree"""
        filename = item.text(0)

        if filename in self.current_data:
            # Get delimiter for this file
            delimiter = self.file_delimiters.get(filename, self.default_delimiter)

            # Update file delimiter combo to match stored delimiter
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

            # Update all input tabs
            columns = self.file_columns.get(filename, {'x_col': 0, 'y_col': 1, 'z_col': 2})
            self.update_input_views(filename, delimiter, columns)

            # Generate preview transformation
            self.generate_preview(filename)

    def generate_preview(self, filename):
        """Generate preview of transformed data"""
        if filename not in self.current_data:
            return

        # Check cache first
        cache_key = f"{filename}_preview_{self.input_crs}_{self.output_crs}"
        columns = self.file_columns.get(filename, {'x_col': 0, 'y_col': 1, 'z_col': 2})
        cache_key += f"_{columns['x_col']}_{columns['y_col']}_{columns['z_col']}"

        if cache_key in self.preview_cache:
            cached_result = self.preview_cache[cache_key]
            self.update_output_views(cached_result['lines'], cached_result['delimiter'],
                                   cached_result['title'], columns)
            self.save_selected_btn.setEnabled(True)
            return

        try:
            # Try to create transformation using selected CRS
            try:
                from pyproj import Transformer
                transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)
                use_pyproj = True
            except Exception as e:
                # Show warning but continue with sample data display
                if not hasattr(self, '_pyproj_warning_shown'):
                    QMessageBox.warning(self, "Transformation Warning",
                                      f"pyproj not available: {e}\n\n"
                                      "Showing sample output format without coordinate transformation.\n"
                                      "Actual transformations will fail until pyproj is fixed.")
                    self._pyproj_warning_shown = True
                use_pyproj = False
                transformer = None

            # Transform sample data for preview (limit to prevent UI blocking)
            sample_lines = self.current_data[filename][:500]  # Reduced sample size
            transformed_lines = []

            for line in sample_lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Skip header/comment lines if remove_headers is enabled
                    if self.remove_headers_checkbox.isChecked() and (line.startswith('!') or line.startswith('@')):
                        continue

                    if filename.endswith('Faults.dat'):
                        if len(line) >= 41:
                            x_str = line[0:12].strip()
                            y_str = line[12:24].strip()
                            z_str = line[24:36].strip()

                            x = float(x_str)
                            y = float(y_str)
                            z = float(z_str) if z_str != '1e+030' else 9999999.0

                            if use_pyproj and transformer:
                                # Transform coordinates using pyproj
                                x_new, y_new = transformer.transform(x, y)
                            else:
                                # Show original coordinates with note
                                x_new, y_new = x, y

                            transformed_lines.append(f"{x_new:12.2f}{y_new:12.2f}{z:12.6f}     1    \n")
                        else:
                            transformed_lines.append(line + '\n')
                    else:
                        # Use the delimiter and column indices for this file
                        delimiter = self.file_delimiters.get(filename, self.default_delimiter)

                        if delimiter:  # Make sure delimiter is not None
                            parts = line.split(delimiter)
                            if len(parts) > max(columns['x_col'], columns['y_col'], columns['z_col']):
                                try:
                                    x = float(parts[columns['x_col']])
                                    y = float(parts[columns['y_col']])
                                    z = float(parts[columns['z_col']])

                                    if use_pyproj and transformer:
                                        # Transform coordinates using pyproj
                                        x_new, y_new = transformer.transform(x, y)
                                    else:
                                        # Show original coordinates with note
                                        x_new, y_new = x, y

                                    transformed_lines.append(f"{x_new:.5f}{delimiter}{y_new:.5f}{delimiter}{z:.4f}\n")
                                except (ValueError, IndexError):
                                    transformed_lines.append(line + '\n')
                            else:
                                transformed_lines.append(line + '\n')
                        else:
                            # If no delimiter, just copy the line
                            transformed_lines.append(line + '\n')

                except Exception as e:
                    transformed_lines.append(line + '\n')

            # Get delimiter for output views
            output_delimiter = self.file_delimiters.get(filename, self.default_delimiter)

            # Update all output tabs
            preview_title = f"Preview: {filename}"
            if not use_pyproj:
                preview_title += " (NO TRANSFORMATION - pyproj unavailable)"

            # Cache the result
            cache_result = {
                'lines': transformed_lines,
                'delimiter': output_delimiter,
                'title': preview_title
            }
            self.preview_cache[cache_key] = cache_result

            self.update_output_views(transformed_lines, output_delimiter, preview_title, columns)
            self.save_selected_btn.setEnabled(True)

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
        if filename not in self.current_data:
            QMessageBox.warning(self, "Warning", "No data available for selected file")
            return

        try:
            # Get the cached preview data (already transformed)
            cache_key = f"{filename}_preview_{self.input_crs}_{self.output_crs}"
            columns = self.file_columns.get(filename, {'x_col': 0, 'y_col': 1, 'z_col': 2})
            cache_key += f"_{columns['x_col']}_{columns['y_col']}_{columns['z_col']}"

            if cache_key in self.preview_cache:
                # Use the already transformed preview data
                transformed_lines = self.preview_cache[cache_key]['lines']
            else:
                # Fallback: generate transformation on demand
                transformed_lines = self.generate_transformation_for_file(filename)

            # Write the transformed data to file
            output_path = os.path.join(self.output_folder, filename)
            with open(output_path, 'w') as outfile:
                outfile.writelines(transformed_lines)

            QMessageBox.information(self, "Success",
                                  f"File saved successfully to {output_path}\n"
                                  f"Transformed from {self.input_crs_name} to {self.output_crs_name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving file: {str(e)}")

    def generate_transformation_for_file(self, filename):
        """Generate transformation for a single file (fallback method)"""
        if filename not in self.current_data:
            return []

        try:
            # Try to create transformation using selected CRS
            try:
                from pyproj import Transformer
                transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)
                use_pyproj = True
            except Exception as e:
                QMessageBox.warning(self, "Transformation Warning",
                                  f"pyproj not available: {e}\n\n"
                                  "Using fallback transformation method.")
                use_pyproj = False
                transformer = None

            # Transform sample data for preview (limit to prevent UI blocking)
            sample_lines = self.current_data[filename][:500]  # Reduced sample size
            transformed_lines = []

            for line in sample_lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Skip header/comment lines if remove_headers is enabled
                    if self.remove_headers_checkbox.isChecked() and (line.startswith('!') or line.startswith('@')):
                        continue

                    if filename.endswith('Faults.dat'):
                        if len(line) >= 41:
                            x_str = line[0:12].strip()
                            y_str = line[12:24].strip()
                            z_str = line[24:36].strip()

                            x = float(x_str)
                            y = float(y_str)
                            z = float(z_str) if z_str != '1e+030' else 9999999.0

                            if use_pyproj and transformer:
                                # Transform coordinates using pyproj
                                x_new, y_new = transformer.transform(x, y)
                            else:
                                # Show original coordinates with note
                                x_new, y_new = x, y

                            transformed_lines.append(f"{x_new:12.2f}{y_new:12.2f}{z:12.6f}     1    \n")
                        else:
                            transformed_lines.append(line + '\n')
                    else:
                        # Use the delimiter and column indices for this file
                        delimiter = self.file_delimiters.get(filename, self.default_delimiter)

                        if delimiter:  # Make sure delimiter is not None
                            parts = line.split(delimiter)
                            if len(parts) > max(columns['x_col'], columns['y_col'], columns['z_col']):
                                try:
                                    x = float(parts[columns['x_col']])
                                    y = float(parts[columns['y_col']])
                                    z = float(parts[columns['z_col']])

                                    if use_pyproj and transformer:
                                        # Transform coordinates using pyproj
                                        x_new, y_new = transformer.transform(x, y)
                                    else:
                                        # Show original coordinates with note
                                        x_new, y_new = x, y

                                    transformed_lines.append(f"{x_new:.5f}{delimiter}{y_new:.5f}{delimiter}{z:.4f}\n")
                                except (ValueError, IndexError):
                                    transformed_lines.append(line + '\n')
                            else:
                                transformed_lines.append(line + '\n')
                        else:
                            # If no delimiter, just copy the line
                            transformed_lines.append(line + '\n')

                except Exception as e:
                    transformed_lines.append(line + '\n')

            return transformed_lines

        except Exception as e:
            QMessageBox.warning(self, "Preview Error", f"Error generating transformation: {str(e)}")
            return []

    def convert_all_files(self):
        """Convert and save all files"""
        if not self.current_data:
            QMessageBox.warning(self, "Warning", "No files loaded")
            return

        if not self.output_folder:
            QMessageBox.warning(self, "Warning", "Please select an output folder first")
            return

        # Check for existing files if overwrite is not enabled
        if not self.overwrite_checkbox.isChecked():
            existing_files = []
            for filename in self.current_data.keys():
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

        # Prepare file list for transformation
        files_to_transform = []
        for filename in self.file_cache.keys():
            input_path = self.file_cache[filename]  # Use cached file path
            output_path = os.path.join(self.output_folder, filename)
            files_to_transform.append((input_path, output_path))

        # Start transformation worker
        remove_headers = self.remove_headers_checkbox.isChecked()
        self.worker = TransformationWorker(files_to_transform, self.input_crs, self.output_crs, remove_headers)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.transformation_complete.connect(self.on_transformation_complete)
        self.worker.error_occurred.connect(self.on_error_occurred)
        self.worker.finished.connect(self.on_transformation_finished)

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(f"Starting transformation from {self.input_crs_name} to {self.output_crs_name}...")

        self.worker.start()

    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)

    def on_transformation_complete(self, filename, transformed_data):
        """Handle completion of single file transformation"""
        basename = os.path.basename(filename)
        self.transformed_data[basename] = transformed_data

    def on_error_occurred(self, error_msg):
        """Handle transformation errors"""
        QMessageBox.warning(self, "Transformation Error", error_msg)

    def on_transformation_finished(self):
        """Handle completion of all transformations"""
        self.progress_bar.setVisible(False)

        # The files are already written by the worker thread, just show success message
        if self.transformed_data:
            QMessageBox.information(self, "Success",
                                  f"Successfully transformed and saved {len(self.transformed_data)} files to {self.output_folder}")

        self.status_bar.showMessage("Transformation complete")

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About",
                         "Seismic Grid Transformation Tool\n\n"
                         "Transforms seismic grid data from NAD27 to NAD83 coordinate systems.\n\n"
                         "Built with PyQt6 and pyproj.")

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Seismic Grid Transformation Tool")
    app.setApplicationVersion("1.0.0")

    # Create and show main window
    window = SeismicGridApp()
    window.show()

    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()