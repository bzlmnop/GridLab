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
                             QGroupBox, QCheckBox)
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

    def __init__(self, files_to_transform, input_crs="EPSG:4326", output_crs="EPSG:4326"):
        super().__init__()
        self.files_to_transform = files_to_transform
        self.input_crs = input_crs
        self.output_crs = output_crs

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

        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            for line_num, line in enumerate(infile, 1):
                line = line.strip()
                if not line:
                    continue

                try:
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
                        # Handle comma-separated format
                        parts = line.split(',')
                        if len(parts) == 3:
                            x, y, z = map(float, parts)

                            # Transform coordinates using pyproj
                            x_new, y_new = transformer.transform(x, y)

                            outfile.write(f"{x_new:.5f},{y_new:.5f},{z:.4f}\n")
                        else:
                            outfile.write(line + '\n')

                except Exception as e:
                    raise Exception(f"Failed to transform line {line_num}: {e}")

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

        # Overwrite checkbox
        self.overwrite_checkbox = QCheckBox("Overwrite existing output files")
        self.overwrite_checkbox.setChecked(False)
        files_layout.addWidget(self.overwrite_checkbox)

        sidebar_layout.addWidget(files_group)

        # File tree
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Grid Files")
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

        # Create splitter for text viewer and preview
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Text viewer for input file
        self.text_viewer = QTextEdit()
        self.text_viewer.setFont(QFont("Courier New", 10))
        self.text_viewer.setReadOnly(True)
        splitter.addWidget(self.text_viewer)

        # Preview area for output
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)

        preview_label = QLabel("Output Preview:")
        preview_layout.addWidget(preview_label)

        self.output_viewer = OutputTextViewer(preview_container)
        preview_layout.addWidget(self.output_viewer)

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

        preview_layout.addLayout(button_layout)
        splitter.addWidget(preview_container)

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

    def load_grid_files(self, folder):
        """Load grid files from selected folder"""
        self.file_tree.clear()
        self.current_data.clear()
        self.transformed_data.clear()

        # Look for all files (not just .dat) in the selected folder
        all_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]

        if not all_files:
            QMessageBox.warning(self, "Warning", f"No files found in {folder}")
            return

        # Create tree items for each file
        loaded_count = 0
        for filename in sorted(all_files):
            file_path = os.path.join(folder, filename)
            item = QTreeWidgetItem([filename])

            # Load file data
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                    self.current_data[filename] = lines

                # Set check state to indicate data loaded
                item.setCheckState(0, Qt.CheckState.Checked)
                loaded_count += 1
            except Exception as e:
                item.setCheckState(0, Qt.CheckState.Unchecked)

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
            # Display input file content
            self.text_viewer.setPlainText(''.join(self.current_data[filename][:100]))  # First 100 lines

            # Generate preview transformation
            self.generate_preview(filename)

    def generate_preview(self, filename):
        """Generate preview of transformed data"""
        if filename not in self.current_data:
            return

        try:
            # Create transformation using selected CRS
            from pyproj import Transformer
            transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)

            # Transform sample data for preview
            sample_lines = self.current_data[filename][:1000]  # Sample for preview
            transformed_lines = []

            for line in sample_lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    if filename.endswith('Faults.dat'):
                        if len(line) >= 41:
                            x_str = line[0:12].strip()
                            y_str = line[12:24].strip()
                            z_str = line[24:36].strip()

                            x = float(x_str)
                            y = float(y_str)
                            z = float(z_str) if z_str != '1e+030' else 9999999.0

                            # Transform coordinates using pyproj
                            x_new, y_new = transformer.transform(x, y)

                            transformed_lines.append(f"{x_new:12.2f}{y_new:12.2f}{z:12.6f}     1    \n")
                        else:
                            transformed_lines.append(line + '\n')
                    else:
                        parts = line.split(',')
                        if len(parts) == 3:
                            x, y, z = map(float, parts)

                            # Transform coordinates using pyproj
                            x_new, y_new = transformer.transform(x, y)

                            transformed_lines.append(f"{x_new:.5f},{y_new:.5f},{z:.4f}\n")
                        else:
                            transformed_lines.append(line + '\n')

                except Exception as e:
                    transformed_lines.append(line + '\n')

            # Update preview
            self.output_viewer.display_transformed_data(transformed_lines, f"Preview: {filename}")
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
            # Perform full transformation
            input_file = os.path.join(self.input_folder, filename)
            output_path = os.path.join(self.output_folder, filename)

            # Create transformation using selected CRS
            from pyproj import Transformer
            transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)

            # Transform and save the file directly
            self.transform_and_save_file_static(input_file, output_path, transformer)

            QMessageBox.information(self, "Success",
                                  f"File saved successfully to {output_path}\n"
                                  f"Transformed from {self.input_crs_name} to {self.output_crs_name}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving file: {str(e)}")

@staticmethod
def transform_and_save_file_static(input_file, output_file, transformer):
    """Transform a single file and save it directly (static method for reuse)"""
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
        for line_num, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue

            try:
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
                    # Handle comma-separated format
                    parts = line.split(',')
                    if len(parts) == 3:
                        x, y, z = map(float, parts)

                        # Transform coordinates using pyproj
                        x_new, y_new = transformer.transform(x, y)

                        outfile.write(f"{x_new:.5f},{y_new:.5f},{z:.4f}\n")
                    else:
                        outfile.write(line + '\n')

            except Exception as e:
                raise Exception(f"Failed to transform line {line_num}: {e}")

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
        for filename in self.current_data.keys():
            input_path = os.path.join(self.input_folder, filename)
            output_path = os.path.join(self.output_folder, filename)
            files_to_transform.append((input_path, output_path))

        # Start transformation worker
        self.worker = TransformationWorker(files_to_transform, self.input_crs, self.output_crs)
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