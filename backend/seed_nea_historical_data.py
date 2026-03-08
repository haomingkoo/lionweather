"""
NEA Historical Weather Data Seeding Script

This script imports historical weather data from NEA (National Environment Agency)
CSV files downloaded from data.gov.sg and stores it in the database for ML model training.

CRITICAL: Only uses real data from NEA - NO mock/synthetic data generation.

Data Source: https://data.gov.sg/collections/2281/view
- Historical Air Temperature across Singapore (2016-2024)
- Historical Rainfall across Singapore (2016-2024)
- Historical Relative Humidity across Singapore (2016-2024)
- Historical Wind Speed across Singapore (2016-2024)
- Historical Wind Direction across Singapore (2016-2024)

CSV Format:
Timestamp,Station Id,Station Name,Station Device Id,Location Longitude,Location Latitude,value

Example:
2024-01-01T00:00:00+08:00,S50,Clementi,S50,103.7768,1.3337,28.5
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import csv
from app.db.database import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NEAHistoricalDataImporter:
    """Imports historical weather data from NEA CSV files"""
    
    def __init__(self, data_directory: str = "nea_historical_data"):
        """
        Initialize the importer.
        
        Args:
            data_directory: Directory containing NEA CSV files
        """
        self.data_directory = Path(data_directory)
        
        # Expected CSV files (one per year per parameter)
        # User should download these from data.gov.sg
        self.parameter_files = {
            'temperature': 'air_temperature',  # Prefix for temperature files
            'rainfall': 'rainfall',
            'humidity': 'relative_humidity',
            'wind_speed': 'wind_speed',
            'wind_direction': 'wind_direction'
        }
        
        # Years to import (2016-2024)
        self.years = list(range(2016, 2025))
    
    def find_csv_files(self) -> Dict[str, List[Path]]:
        """
        Find all NEA CSV files in the data directory.
        
        Returns:
            Dictionary mapping parameter names to lists of CSV file paths
        """
        found_files = {param: [] for param in self.parameter_files.keys()}
        
        if not self.data_directory.exists():
            logger.error(f"Data directory not found: {self.data_directory}")
            logger.info("Please create the directory and download NEA CSV files from:")
            logger.info("https://data.gov.sg/collections/2281/view")
            return found_files
        
        # Search for CSV files matching the expected patterns
        for param, prefix in self.parameter_files.items():
            # Look for files like "air_temperature_2024.csv", "rainfall_2023.csv", etc.
            pattern = f"*{prefix}*.csv"
            files = list(self.data_directory.glob(pattern))
            found_files[param] = sorted(files)
            
            if files:
                logger.info(f"Found {len(files)} {param} files: {[f.name for f in files]}")
            else:
                logger.warning(f"No {param} files found matching pattern: {pattern}")
        
        return found_files
    
    def parse_nea_csv(self, csv_path: Path) -> List[Dict]:
        """
        Parse a single NEA CSV file.
        
        CSV Format:
        Timestamp,Station Id,Station Name,Station Device Id,Location Longitude,Location Latitude,value
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            List of dictionaries with parsed data
        """
        records = []
        
        logger.info(f"Parsing {csv_path.name}...")
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Parse timestamp
                        timestamp_str = row.get('Timestamp', '').strip()
                        if not timestamp_str:
                            continue
                        
                        # Handle timezone in timestamp
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        # Extract station information
                        station_id = row.get('Station Id', '').strip()
                        station_name = row.get('Station Name', '').strip()
                        
                        # Parse coordinates
                        try:
                            longitude = float(row.get('Location Longitude', 0))
                            latitude = float(row.get('Location Latitude', 0))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid coordinates for station {station_id}")
                            continue
                        
                        # Parse value
                        try:
                            value = float(row.get('value', 0))
                        except (ValueError, TypeError):
                            # Skip rows with missing/invalid values
                            continue
                        
                        record = {
                            'timestamp': timestamp,
                            'station_id': station_id,
                            'station_name': station_name,
                            'latitude': latitude,
                            'longitude': longitude,
                            'value': value
                        }
                        
                        records.append(record)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing row: {str(e)}")
                        continue
            
            logger.info(f"✓ Parsed {len(records)} records from {csv_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to parse {csv_path}: {str(e)}")
        
        return records
    
    def group_by_timestamp_station(self, 
                                   temp_records: List[Dict],
                                   rainfall_records: List[Dict],
                                   humidity_records: List[Dict],
                                   wind_speed_records: List[Dict],
                                   wind_direction_records: List[Dict]) -> List[Dict]:
        """
        Group records by timestamp and station to create complete weather observations.
        
        Args:
            temp_records: Temperature records
            rainfall_records: Rainfall records
            humidity_records: Humidity records
            wind_speed_records: Wind speed records
            wind_direction_records: Wind direction records
            
        Returns:
            List of complete weather observation dictionaries
        """
        logger.info("Grouping records by timestamp and station...")
        
        # Create lookup dictionaries: (timestamp, station_id) -> value
        temp_lookup = {(r['timestamp'], r['station_id']): r for r in temp_records}
        rainfall_lookup = {(r['timestamp'], r['station_id']): r for r in rainfall_records}
        humidity_lookup = {(r['timestamp'], r['station_id']): r for r in humidity_records}
        wind_speed_lookup = {(r['timestamp'], r['station_id']): r for r in wind_speed_records}
        wind_dir_lookup = {(r['timestamp'], r['station_id']): r for r in wind_direction_records}
        
        # Get all unique (timestamp, station_id) combinations from temperature data
        # Temperature is the most reliable parameter
        all_keys = set(temp_lookup.keys())
        
        logger.info(f"Found {len(all_keys)} unique (timestamp, station) combinations")
        
        # Create complete observations
        complete_observations = []
        
        for key in all_keys:
            timestamp, station_id = key
            
            # Get temperature record (guaranteed to exist)
            temp_record = temp_lookup[key]
            
            # Get other parameters (may not exist for all timestamps/stations)
            rainfall_record = rainfall_lookup.get(key)
            humidity_record = humidity_lookup.get(key)
            wind_speed_record = wind_speed_lookup.get(key)
            wind_dir_record = wind_dir_lookup.get(key)
            
            # Create complete observation
            observation = {
                'timestamp': timestamp,
                'station_id': station_id,
                'station_name': temp_record['station_name'],
                'latitude': temp_record['latitude'],
                'longitude': temp_record['longitude'],
                'temperature': temp_record['value'],
                'rainfall': rainfall_record['value'] if rainfall_record else 0.0,
                'humidity': humidity_record['value'] if humidity_record else None,
                'wind_speed': wind_speed_record['value'] if wind_speed_record else None,
                'wind_direction': wind_dir_record['value'] if wind_dir_record else None,
            }
            
            # Only include observations with critical features (temp, humidity)
            if observation['humidity'] is not None:
                complete_observations.append(observation)
        
        logger.info(f"✓ Created {len(complete_observations)} complete observations")
        
        return complete_observations
    
    def store_observations(self, observations: List[Dict]) -> int:
        """
        Store weather observations in the database.
        
        Args:
            observations: List of complete weather observations
            
        Returns:
            Number of records inserted
        """
        logger.info(f"Storing {len(observations)} observations in database...")
        
        con = get_connection()
        cursor = con.cursor()
        
        inserted_count = 0
        skipped_count = 0
        
        for obs in observations:
            try:
                # Insert into weather_records table
                cursor.execute("""
                    INSERT OR IGNORE INTO weather_records (
                        timestamp, country, location, latitude, longitude,
                        temperature, rainfall, humidity, wind_speed, wind_direction,
                        pressure, weather_code, source_api, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs['timestamp'].isoformat(),
                    "singapore",
                    f"{obs['station_name']} (NEA Historical)",
                    obs['latitude'],
                    obs['longitude'],
                    obs['temperature'],
                    obs['rainfall'],
                    obs['humidity'],
                    obs['wind_speed'],
                    obs['wind_direction'],
                    None,  # NEA doesn't provide pressure data
                    None,  # NEA doesn't provide weather codes
                    f"data.gov.sg/nea/{obs['station_id']}",
                    datetime.now().isoformat()
                ))
                
                if cursor.rowcount > 0:
                    inserted_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error inserting record: {str(e)}")
                continue
        
        con.commit()
        con.close()
        
        logger.info(f"✓ Inserted {inserted_count} records, skipped {skipped_count} duplicates")
        
        return inserted_count
    
    def import_data(self) -> Dict:
        """
        Main method to import NEA historical data.
        
        Returns:
            Dictionary with import results
        """
        logger.info("=" * 80)
        logger.info("NEA HISTORICAL DATA IMPORT")
        logger.info("=" * 80)
        logger.info(f"Data directory: {self.data_directory.absolute()}")
        logger.info(f"Years: {self.years[0]}-{self.years[-1]}")
        logger.info()
        
        # Find CSV files
        csv_files = self.find_csv_files()
        
        # Check if we have any files
        total_files = sum(len(files) for files in csv_files.values())
        if total_files == 0:
            logger.error("No CSV files found!")
            logger.info("\nPlease download NEA historical data from:")
            logger.info("https://data.gov.sg/collections/2281/view")
            logger.info("\nDownload the following datasets (2016-2024):")
            logger.info("  - Historical Air Temperature across Singapore")
            logger.info("  - Historical Rainfall across Singapore")
            logger.info("  - Historical Relative Humidity across Singapore")
            logger.info("  - Historical Wind Speed across Singapore")
            logger.info("  - Historical Wind Direction across Singapore")
            logger.info(f"\nPlace CSV files in: {self.data_directory.absolute()}")
            return {
                'success': False,
                'error': 'No CSV files found',
                'total_records_inserted': 0
            }
        
        logger.info(f"Found {total_files} CSV files total")
        logger.info()
        
        # Parse all CSV files
        all_temp_records = []
        all_rainfall_records = []
        all_humidity_records = []
        all_wind_speed_records = []
        all_wind_dir_records = []
        
        for csv_path in csv_files['temperature']:
            records = self.parse_nea_csv(csv_path)
            all_temp_records.extend(records)
        
        for csv_path in csv_files['rainfall']:
            records = self.parse_nea_csv(csv_path)
            all_rainfall_records.extend(records)
        
        for csv_path in csv_files['humidity']:
            records = self.parse_nea_csv(csv_path)
            all_humidity_records.extend(records)
        
        for csv_path in csv_files['wind_speed']:
            records = self.parse_nea_csv(csv_path)
            all_wind_speed_records.extend(records)
        
        for csv_path in csv_files['wind_direction']:
            records = self.parse_nea_csv(csv_path)
            all_wind_dir_records.extend(records)
        
        logger.info()
        logger.info("Parsing summary:")
        logger.info(f"  Temperature records: {len(all_temp_records)}")
        logger.info(f"  Rainfall records: {len(all_rainfall_records)}")
        logger.info(f"  Humidity records: {len(all_humidity_records)}")
        logger.info(f"  Wind speed records: {len(all_wind_speed_records)}")
        logger.info(f"  Wind direction records: {len(all_wind_dir_records)}")
        logger.info()
        
        # Group by timestamp and station
        complete_observations = self.group_by_timestamp_station(
            all_temp_records,
            all_rainfall_records,
            all_humidity_records,
            all_wind_speed_records,
            all_wind_dir_records
        )
        
        # Store in database
        inserted_count = self.store_observations(complete_observations)
        
        # Get station statistics
        stations = set((obs['station_id'], obs['station_name']) for obs in complete_observations)
        
        result = {
            'success': True,
            'total_records_inserted': inserted_count,
            'total_observations': len(complete_observations),
            'stations_count': len(stations),
            'stations': sorted(list(stations)),
            'date_range': {
                'start': min(obs['timestamp'] for obs in complete_observations).isoformat() if complete_observations else None,
                'end': max(obs['timestamp'] for obs in complete_observations).isoformat() if complete_observations else None
            }
        }
        
        logger.info()
        logger.info("=" * 80)
        logger.info("IMPORT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total records inserted: {inserted_count}")
        logger.info(f"Stations: {len(stations)}")
        logger.info(f"Date range: {result['date_range']['start']} to {result['date_range']['end']}")
        logger.info()
        logger.info("Stations:")
        for station_id, station_name in sorted(stations):
            logger.info(f"  {station_id}: {station_name}")
        logger.info("=" * 80)
        
        return result


def main():
    """Main entry point for the import script"""
    import sys
    
    # Get data directory from command line argument or use default
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "nea_historical_data"
    
    importer = NEAHistoricalDataImporter(data_directory=data_dir)
    
    try:
        result = importer.import_data()
        
        if not result['success']:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
