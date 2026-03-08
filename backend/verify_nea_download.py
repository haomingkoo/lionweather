"""
NEA Data Download Verification Script

Checks that downloaded NEA data is:
1. Present (files exist)
2. Valid (proper CSV format)
3. Complete (has expected columns and data)
4. Reasonable (values within expected ranges)
5. Spatial (has station/location information)
6. Temporal (has proper date/time coverage)
"""

import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NEADataVerifier:
    """Verifies downloaded NEA weather data"""
    
    def __init__(self, data_dir: str = "nea_historical_data"):
        self.data_dir = Path(data_dir)
        
        # Expected data characteristics
        self.expected_params = {
            'temperature': {'min': 20, 'max': 40, 'unit': '°C'},
            'humidity': {'min': 40, 'max': 100, 'unit': '%'},
            'rainfall': {'min': 0, 'max': 200, 'unit': 'mm'},
            'wind_speed': {'min': 0, 'max': 50, 'unit': 'km/h'},
            'wind_direction': {'min': 0, 'max': 360, 'unit': 'degrees'},
            'pm2.5': {'min': 0, 'max': 500, 'unit': 'μg/m³'},
        }
        
        self.issues = []
        self.warnings = []
        self.stats = {}
    
    def verify_all(self):
        """Run all verification checks"""
        logger.info("=" * 80)
        logger.info("NEA DATA VERIFICATION")
        logger.info("=" * 80)
        logger.info(f"Data directory: {self.data_dir.absolute()}")
        logger.info("")
        
        if not self.data_dir.exists():
            logger.error(f"❌ Data directory does not exist: {self.data_dir}")
            return False
        
        # Step 1: Check directory structure
        logger.info("Step 1: Checking directory structure...")
        self.check_directory_structure()
        
        # Step 2: Verify each collection
        logger.info("\nStep 2: Verifying collections...")
        collections = [d for d in self.data_dir.iterdir() if d.is_dir()]
        
        if not collections:
            logger.error("❌ No collection directories found")
            return False
        
        logger.info(f"Found {len(collections)} collections")
        
        for collection_dir in sorted(collections):
            self.verify_collection(collection_dir)
        
        # Step 3: Summary
        self.print_summary()
        
        return len(self.issues) == 0
    
    def check_directory_structure(self):
        """Check that directory structure is correct"""
        csv_files = list(self.data_dir.rglob("*.csv"))
        
        if not csv_files:
            self.issues.append("No CSV files found in data directory")
            logger.error("❌ No CSV files found")
        else:
            logger.info(f"✓ Found {len(csv_files)} CSV files")
            self.stats['total_files'] = len(csv_files)
    
    def verify_collection(self, collection_dir: Path):
        """Verify a single collection"""
        logger.info("")
        logger.info(f"Collection: {collection_dir.name}")
        logger.info("-" * 80)
        
        csv_files = list(collection_dir.glob("*.csv"))
        
        if not csv_files:
            self.warnings.append(f"No CSV files in {collection_dir.name}")
            logger.warning(f"⚠ No CSV files found")
            return
        
        logger.info(f"Files: {len(csv_files)}")
        
        for csv_file in csv_files:
            self.verify_csv_file(csv_file, collection_dir.name)
    
    def verify_csv_file(self, csv_path: Path, collection_name: str):
        """Verify a single CSV file"""
        logger.info(f"\n  File: {csv_path.name}")
        
        try:
            # Read CSV
            df = pd.read_csv(csv_path)
            
            # Basic checks
            rows = len(df)
            cols = len(df.columns)
            
            logger.info(f"    Rows: {rows:,}")
            logger.info(f"    Columns: {cols}")
            logger.info(f"    Size: {csv_path.stat().st_size / (1024*1024):.2f} MB")
            
            if rows == 0:
                self.issues.append(f"{csv_path.name}: Empty file (0 rows)")
                logger.error(f"    ❌ Empty file")
                return
            
            if cols == 0:
                self.issues.append(f"{csv_path.name}: No columns")
                logger.error(f"    ❌ No columns")
                return
            
            # Check for common column names
            columns_lower = [c.lower() for c in df.columns]
            logger.info(f"    Columns: {', '.join(df.columns[:5])}" + 
                       (f", ... (+{len(df.columns)-5} more)" if len(df.columns) > 5 else ""))
            
            # Check for timestamp/date columns
            has_timestamp = any(col in columns_lower for col in 
                              ['timestamp', 'date', 'datetime', 'time', 'year', 'month'])
            
            if has_timestamp:
                logger.info(f"    ✓ Has temporal data")
            else:
                self.warnings.append(f"{csv_path.name}: No timestamp column found")
                logger.warning(f"    ⚠ No timestamp column")
            
            # Check for station/location columns
            has_location = any(col in columns_lower for col in 
                             ['station', 'location', 'station_id', 'station_name', 
                              'latitude', 'longitude', 'lat', 'lon', 'lng'])
            
            if has_location:
                logger.info(f"    ✓ Has spatial data")
            else:
                self.warnings.append(f"{csv_path.name}: No location column found")
                logger.warning(f"    ⚠ No location column")
            
            # Check for value columns
            value_cols = [col for col in df.columns if col.lower() not in 
                         ['timestamp', 'date', 'datetime', 'time', 'station', 
                          'station_id', 'station_name', 'location', 'year', 'month', 'day']]
            
            if value_cols:
                logger.info(f"    ✓ Has {len(value_cols)} value column(s)")
                
                # Check value ranges for known parameters
                for col in value_cols[:3]:  # Check first 3 value columns
                    if pd.api.types.is_numeric_dtype(df[col]):
                        self.check_value_range(df[col], col, csv_path.name)
            
            # Check for missing data
            missing_pct = (df.isnull().sum().sum() / (rows * cols)) * 100
            if missing_pct > 50:
                self.warnings.append(f"{csv_path.name}: High missing data ({missing_pct:.1f}%)")
                logger.warning(f"    ⚠ High missing data: {missing_pct:.1f}%")
            elif missing_pct > 0:
                logger.info(f"    Missing data: {missing_pct:.1f}%")
            else:
                logger.info(f"    ✓ No missing data")
            
            # Check date range if temporal
            if has_timestamp:
                self.check_date_range(df, csv_path.name)
            
            logger.info(f"    ✓ File verified")
            
        except pd.errors.EmptyDataError:
            self.issues.append(f"{csv_path.name}: Empty or corrupted CSV")
            logger.error(f"    ❌ Empty or corrupted CSV")
        except Exception as e:
            self.issues.append(f"{csv_path.name}: Error reading file - {str(e)}")
            logger.error(f"    ❌ Error: {str(e)}")
    
    def check_value_range(self, series: pd.Series, col_name: str, file_name: str):
        """Check if values are in reasonable range"""
        col_lower = col_name.lower()
        
        # Try to identify parameter type
        param_type = None
        for param in self.expected_params.keys():
            if param in col_lower or param.replace('_', '') in col_lower:
                param_type = param
                break
        
        if param_type:
            expected = self.expected_params[param_type]
            min_val = series.min()
            max_val = series.max()
            mean_val = series.mean()
            
            logger.info(f"      {col_name}: min={min_val:.2f}, max={max_val:.2f}, mean={mean_val:.2f}")
            
            if min_val < expected['min'] or max_val > expected['max']:
                self.warnings.append(
                    f"{file_name} - {col_name}: Values outside expected range "
                    f"[{expected['min']}, {expected['max']}] {expected['unit']}"
                )
                logger.warning(f"      ⚠ Values outside expected range")
    
    def check_date_range(self, df: pd.DataFrame, file_name: str):
        """Check temporal coverage"""
        # Try to find date column
        date_cols = [col for col in df.columns if any(x in col.lower() 
                    for x in ['timestamp', 'date', 'datetime', 'time'])]
        
        if not date_cols:
            return
        
        date_col = date_cols[0]
        
        try:
            dates = pd.to_datetime(df[date_col], errors='coerce')
            dates = dates.dropna()
            
            if len(dates) > 0:
                min_date = dates.min()
                max_date = dates.max()
                date_range = (max_date - min_date).days
                
                logger.info(f"      Date range: {min_date.date()} to {max_date.date()} ({date_range} days)")
                
                # Check if data is recent enough (should have data from 2016+)
                if min_date.year < 2010:
                    self.warnings.append(f"{file_name}: Very old data (starts {min_date.year})")
                
                if max_date.year < 2023:
                    self.warnings.append(f"{file_name}: Data may be outdated (ends {max_date.year})")
        except:
            pass
    
    def print_summary(self):
        """Print verification summary"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 80)
        
        if self.stats.get('total_files'):
            logger.info(f"Total files: {self.stats['total_files']}")
        
        if not self.issues and not self.warnings:
            logger.info("✓ All checks passed!")
            logger.info("")
            logger.info("Data is ready for import. Next steps:")
            logger.info("  1. Run: python seed_nea_historical_data.py")
            logger.info("  2. Run: python ml/visualize_spatial_data.py")
            logger.info("  3. Run: python ml/prepare_training_data.py nea")
        else:
            if self.issues:
                logger.error(f"\n❌ Found {len(self.issues)} issue(s):")
                for issue in self.issues:
                    logger.error(f"  - {issue}")
            
            if self.warnings:
                logger.warning(f"\n⚠ Found {len(self.warnings)} warning(s):")
                for warning in self.warnings:
                    logger.warning(f"  - {warning}")
            
            if self.issues:
                logger.error("\n❌ Data verification failed. Please fix issues before proceeding.")
            else:
                logger.info("\n✓ Data verification passed with warnings. You can proceed but review warnings.")
        
        logger.info("=" * 80)


if __name__ == "__main__":
    verifier = NEADataVerifier()
    success = verifier.verify_all()
    exit(0 if success else 1)
