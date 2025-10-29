#!/usr/bin/env python3
"""
GridFile Module
Provides GridFile class for reading, parsing, transforming, and writing seismic grid files
"""

import os
import pandas as pd
from typing import Optional, Tuple

class GridFile:
    """Represents a seismic grid file with parsing and transformation capabilities"""

    def __init__(self, file_path: str, input_crs: Optional[str] = None, output_crs: Optional[str] = None,
                 input_delimiter: Optional[str] = None, output_delimiter: str = ",",
                 grid_type: Optional[str] = None, depth_domain: Optional[str] = None,
                 depth_datum: Optional[str] = None, crs: Optional[str] = None):
        """
        Initialize GridFile object

        Args:
            file_path: Path to the grid file
            input_crs: Input coordinate reference system (EPSG code)
            output_crs: Output coordinate reference system (EPSG code)
            input_delimiter: Input file delimiter (auto-detected if None)
            output_delimiter: Output file delimiter
            grid_type: Type of grid ('depth' or 'property')
            depth_domain: Depth domain ('Time', 'TVD', 'SSTVD', or None)
            depth_datum: Datum on which depths or Z values are reported
            crs: EPSG code for the coordinate system of x/y data
        """
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self._input_crs = input_crs  # Set later by GUI
        self._output_crs = output_crs  # Set later by GUI
        self.input_delimiter = input_delimiter  # Auto-detect if None
        self.output_delimiter = output_delimiter
        self._grid_type = grid_type  # 'depth' or 'property' or None
        self.depth_domain = depth_domain  # 'Time', 'TVD', 'SSTVD', or None
        self.depth_datum = depth_datum  # Datum for depths/Z values
        self.crs = crs  # EPSG code for x/y coordinate system

    @property
    def input_crs(self):
        """Get the input CRS"""
        return self._input_crs

    @input_crs.setter
    def input_crs(self, value):
        """Set the input CRS and recompute outputs if needed"""
        self._input_crs = value
        self._recompute_outputs()

    @property
    def output_crs(self):
        """Get the output CRS"""
        return self._output_crs

    @output_crs.setter
    def output_crs(self, value):
        """Set the output CRS and recompute outputs if needed"""
        self._output_crs = value
        self._recompute_outputs()

    @property
    def grid_type(self):
        """Get the grid type"""
        return self._grid_type

    @grid_type.setter
    def grid_type(self, value):
        """Set the grid type and automatically adjust depth_domain if changing to property"""
        self._grid_type = value
        if value == 'property':
            self.depth_domain = None
        self._recompute_outputs()

    def read(self) -> bool:
        """Read the raw text data from file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.input_raw = f.read()
            return True
        except Exception as e:
            print(f"Error reading file {self.filename}: {e}")
            return False

    def parse(self, detect_depth_domain: bool = True) -> bool:
        """Parse the raw text data into a pandas DataFrame"""
        if self.input_raw is None:
            return False

        try:
            # Auto-detect delimiter if not specified
            if self.input_delimiter is None:
                self.input_delimiter = self._detect_delimiter()

            # Try to parse as delimited file first (works for most formats)
            self.input_df = self._parse_delimited_file()

            # If that fails and it looks like a fault file, try fixed-width parsing
            if self.input_df is None or self.input_df.empty:
                self.input_df = self._parse_fault_file()

            if self.input_df is not None and not self.input_df.empty and detect_depth_domain:
                # Attempt depth domain detection if grid_type is None or 'depth'
                if self.grid_type is None or self.grid_type == 'depth':
                    self._detect_depth_domain()

            # Recompute outputs after parsing
            self._recompute_outputs()

            return self.input_df is not None and not self.input_df.empty

        except Exception as e:
            print(f"Error parsing file {self.filename}: {e}")
            return False

    def _recompute_outputs(self) -> None:
        """Recompute output_df and output_raw based on current settings"""
        if self.input_df is None:
            return

        try:
            # Create output_df with only X, Y, Z columns
            required_cols = ['X', 'Y', 'Z']
            if all(col in self.input_df.columns for col in required_cols):
                self.output_df = self.input_df[required_cols].copy()
            else:
                self.output_df = self.input_df.copy()

            # Apply coordinate transformation if both CRS are set and different
            if (self.input_crs is not None and self.output_crs is not None and
                self.input_crs != self.output_crs and
                'X' in self.output_df.columns and 'Y' in self.output_df.columns):
                try:
                    from pyproj import Transformer
                    transformer = Transformer.from_crs(self.input_crs, self.output_crs, always_xy=True)

                    # Transform coordinates
                    x_coords = self.output_df['X'].values
                    y_coords = self.output_df['Y'].values

                    transformed_coords = transformer.transform(x_coords, y_coords)

                    self.output_df['X'] = transformed_coords[0]
                    self.output_df['Y'] = transformed_coords[1]

                except Exception as e:
                    print(f"Coordinate transformation failed for {self.filename}: {e}")
                    # Continue without transformation

            # Generate output raw text
            self._generate_output_raw()

        except Exception as e:
            print(f"Error recomputing outputs for {self.filename}: {e}")

    def transform(self) -> bool:
        """Transform coordinates from input CRS to output CRS (legacy method)"""
        self._recompute_outputs()
        return self.output_df is not None

    def write(self, output_folder: str) -> bool:
        """Write the transformed data to output file"""
        if self.output_df is None or self.output_raw is None:
            return False

        try:
            # Generate output path
            self.output_path = os.path.join(output_folder, self.filename)

            # Ensure output directory exists
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

            # Write the file
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(self.output_raw)

            return True

        except Exception as e:
            print(f"Error writing file {self.filename}: {e}")
            return False

    def _detect_delimiter(self) -> str:
        """Auto-detect the delimiter used in the file"""
        if not self.input_raw:
            return ','

        # Sample first few lines
        lines = self.input_raw.split('\n')[:10]
        lines = [line.strip() for line in lines if line.strip() and not line.startswith('!') and not line.startswith('@')]

        if not lines:
            return ','

        # Count delimiters
        tab_count = sum(line.count('\t') for line in lines)
        comma_count = sum(line.count(',') for line in lines)
        space_count = sum(line.count(' ') for line in lines)

        # Return delimiter with highest count
        max_count = max(tab_count, comma_count, space_count)
        if max_count == tab_count and tab_count > 0:
            return '\t'
        elif max_count == comma_count and comma_count > 0:
            return ','
        elif max_count == space_count and space_count > 0:
            return ' '

        return ','  # Default

    def _parse_fault_file(self) -> Optional[pd.DataFrame]:
        """Parse fixed-width fault file"""
        try:
            lines = self.input_raw.split('\n')
            data = []

            for line in lines:
                line = line.strip()
                if not line or line.startswith('!') or line.startswith('@'):
                    continue

                if len(line) >= 41:
                    try:
                        x_str = line[0:12].strip()
                        y_str = line[12:24].strip()
                        z_str = line[24:36].strip()

                        if x_str and y_str:
                            x = float(x_str)
                            y = float(y_str)
                            z = float(z_str) if z_str != '1e+030' else None
                            data.append([x, y, z])
                    except ValueError:
                        continue

            if data:
                df = pd.DataFrame(data, columns=['X', 'Y', 'Z'])
                return df
            return None

        except Exception as e:
            print(f"Error parsing fault file: {e}")
            return None

    def _parse_delimited_file(self) -> Optional[pd.DataFrame]:
        """Parse delimited file with automatic delimiter detection"""
        try:
            # Try multiple delimiters if auto-detection didn't work well
            delimiters_to_try = [self.input_delimiter]
            if self.input_delimiter not in [',', '\t', ' ', ';']:
                delimiters_to_try.extend([',', '\t', ' ', ';'])

            for delimiter in delimiters_to_try:
                try:
                    # Use pandas to read CSV with current delimiter
                    from io import StringIO
                    df = pd.read_csv(StringIO(self.input_raw), delimiter=delimiter,
                                   comment='!', header=None, skip_blank_lines=True, engine='python')

                    # Clean up the DataFrame
                    df = df.dropna(how='all')  # Remove empty rows
                    df = df.apply(pd.to_numeric, errors='coerce')  # Convert to numeric
                    df = df.dropna(how='all', axis=1)  # Remove empty columns

                    # Ensure we have at least 3 columns and rename them
                    if df.shape[1] >= 3:
                        col_names = ['X', 'Y', 'Z'] + [f'Col_{i+3}' for i in range(df.shape[1]-3)]
                        df.columns = col_names[:df.shape[1]]

                        # Keep only numeric rows
                        df = df.dropna()

                        if not df.empty:
                            # Update the detected delimiter
                            self.input_delimiter = delimiter
                            return df

                except Exception:
                    continue

            return None

        except Exception as e:
            print(f"Error parsing delimited file: {e}")
            return None

    def _detect_depth_domain(self) -> None:
        """Detect the depth domain based on Z values"""
        if self.input_df is None or 'Z' not in self.input_df.columns:
            return

        try:
            z_values = self.input_df['Z'].dropna()

            if z_values.empty:
                return

            min_z = z_values.min()
            max_z = z_values.max()

            # Time domain: values between -20 and 20 (milliseconds)
            if min_z >= -20 and max_z <= 20:
                self.depth_domain = 'Time'
            # SSTVD: all negative values, larger than -20
            elif max_z < 0 and min_z < -20:
                self.depth_domain = 'SSTVD'
            # TVD: all positive values, larger than 20
            elif min_z > 20 and max_z > 20:
                self.depth_domain = 'TVD'
            else:
                self.depth_domain = None

        except Exception as e:
            print(f"Error detecting depth domain: {e}")

    def _generate_output_raw(self, include_column_headers: bool = False, remove_input_headers: bool = True) -> None:
        """Generate raw text output from transformed DataFrame"""
        try:
            # Check if input was parsed as fixed-width (fault file)
            was_fixed_width_input = self._was_input_fixed_width()

            if was_fixed_width_input:
                # Fixed-width format for fault files
                lines = []
                for idx, row in self.output_df.iterrows():
                    try:
                        x = float(row['X'])
                        y = float(row['Y'])
                        z = float(row['Z']) if pd.notna(row['Z']) else 9999999.0
                        line = f"{x:12.2f}{y:12.2f}{z:12.6f}     1    \n"
                        lines.append(line)
                    except (ValueError, TypeError):
                        continue
                self.output_raw = ''.join(lines)
            else:
                # Delimited format using output_delimiter
                csv_content = self.output_df.to_csv(index=False, sep=self.output_delimiter,
                                                  float_format='%.5f', header=include_column_headers)

                # Handle input headers/comments removal
                if remove_input_headers:
                    lines = csv_content.split('\n')
                    # Skip lines that start with ! or @
                    filtered_lines = [line for line in lines if line.strip() and not (line.strip().startswith('!') or line.strip().startswith('@'))]
                    csv_content = '\n'.join(filtered_lines)

                self.output_raw = csv_content

        except Exception as e:
            print(f"Error generating output raw text: {e}")
            self.output_raw = ""

    def _was_input_fixed_width(self) -> bool:
        """Check if the input was parsed as fixed-width format"""
        # If fault file parsing succeeded and delimited parsing failed, it was fixed-width
        if self.input_df is not None and not self.input_df.empty:
            # Try to see if it would parse as delimited - if not, it was likely fixed-width
            try:
                from io import StringIO
                test_df = pd.read_csv(StringIO(self.input_raw), delimiter=self.input_delimiter or ',',
                                    comment='!', header=None, skip_blank_lines=True, engine='python')
                # If we can parse it as delimited, it wasn't fixed-width
                return False
            except:
                # If delimited parsing fails, it was likely fixed-width
                return True
        return False