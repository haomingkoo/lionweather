"""
Targeted NEA Weather Data Downloader

Downloads ONLY the critical weather datasets we need for ML training:
- Temperature, Rainfall, Humidity, Wind Speed, Wind Direction
- Historical Forecasts
- Air Quality (PM2.5, PSI, UVI)

Goes directly to known collection IDs - no discovery needed.
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime
import logging
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeatherDataDownloader:
    """Downloads critical NEA weather datasets"""
    
    def __init__(self, output_dir: str = "nea_historical_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.base_url = "https://api-production.data.gov.sg/v2/public/api"
        
        # Known weather collection IDs - ONLY direct weather parameters
        self.weather_collections = {
            # Core weather parameters
            2277: "Historical Air Temperature",
            2278: "Historical Relative Humidity",
            2279: "Historical Rainfall",
            2280: "Historical Wind Speed",
            2281: "Historical Wind Direction",
            
            # Historical forecasts
            2212: "Historical 4-day Weather Forecast",
            2213: "Historical 24-hour Weather Forecast",
            
            # Air quality (affects visibility, correlates with weather patterns)
            1369: "Air Pollutant - PM2.5",
            1379: "Historical 1-hr PM2.5",
            1365: "Air Pollutant - Carbon Monoxide",
            
            # Add more weather-only collections as discovered
            # NOT including: dengue (indirect), green vehicles (unrelated), waste management, etc.
        }
        
        self.downloaded = 0
        self.failed = 0
        self.total_datasets = 0
    
    def get_collection_metadata(self, collection_id: int, collection_name: str) -> dict:
        """Get metadata for a collection"""
        url = f"{self.base_url}/collections/{collection_id}/metadata?withDatasetMetadata=true"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                return data.get('data', {})
            else:
                logger.error(f"API error for {collection_name}: {data.get('errorMsg')}")
                return {}
        except Exception as e:
            logger.error(f"Failed to get metadata for {collection_name}: {str(e)}")
            return {}
    
    def download_dataset(self, dataset_id: str, dataset_name: str, collection_name: str) -> bool:
        """Download a dataset using CKAN datastore API with pagination"""
        
        try:
            logger.info(f"  Downloading: {dataset_name}")
            
            all_records = []
            offset = 0
            batch_size = 5000  # Smaller batches to avoid 413 errors
            
            while True:
                url = f"https://data.gov.sg/api/action/datastore_search?resource_id={dataset_id}&limit={batch_size}&offset={offset}"
                
                response = requests.get(url, timeout=60)
                
                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning(f"    ⚠ Rate limited, waiting 10 seconds...")
                    time.sleep(10)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if not data.get('success'):
                    logger.warning(f"  ⚠ API returned success=false")
                    return False
                
                result = data.get('result', {})
                records = result.get('records', [])
                
                if not records:
                    break
                
                all_records.extend(records)
                
                # Check if there are more records
                total = result.get('total', 0)
                if len(all_records) >= total:
                    logger.info(f"    Fetched {len(all_records):,} records (complete)")
                    break
                
                if len(all_records) % 50000 == 0:  # Log progress every 50k records
                    logger.info(f"    Fetched {len(all_records):,} / {total:,} records...")
                
                offset += batch_size
                time.sleep(1)  # Rate limiting - 1 second between requests
            
            if not all_records:
                logger.warning(f"  ⚠ No records found")
                return False
            
            # Convert to DataFrame and save as CSV
            df = pd.DataFrame(all_records)
            
            # Remove internal columns
            cols_to_drop = [col for col in df.columns if col.startswith('_')]
            df = df.drop(columns=cols_to_drop, errors='ignore')
            
            # Save to collection subdirectory
            safe_collection = "".join(c for c in collection_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_collection = safe_collection.replace(' ', '_').lower()[:100]
            collection_dir = self.output_dir / safe_collection
            collection_dir.mkdir(exist_ok=True)
            
            safe_filename = "".join(c for c in dataset_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            safe_filename = safe_filename.replace(' ', '_').lower()[:150]
            if not safe_filename.endswith('.csv'):
                safe_filename += '.csv'
            
            output_path = collection_dir / safe_filename
            
            df.to_csv(output_path, index=False)
            
            file_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"  ✓ Saved: {output_path.name} ({len(df):,} rows, {file_size:.2f} MB)")
            return True
            
        except Exception as e:
            logger.error(f"  ✗ Failed: {str(e)}")
            return False
    
    def download_collection(self, collection_id: int, collection_name: str):
        """Download all datasets in a collection"""
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"COLLECTION: {collection_name}")
        logger.info(f"ID: {collection_id}")
        logger.info("=" * 80)
        
        metadata = self.get_collection_metadata(collection_id, collection_name)
        if not metadata:
            logger.error(f"Failed to get metadata")
            return
        
        datasets = metadata.get('datasetMetadata', [])
        if not datasets:
            logger.warning(f"No datasets found")
            return
        
        logger.info(f"Found {len(datasets)} datasets")
        self.total_datasets += len(datasets)
        
        for idx, dataset in enumerate(datasets, 1):
            dataset_id = dataset.get('datasetId')
            dataset_name = dataset.get('name', 'unknown')
            
            logger.info(f"[{idx}/{len(datasets)}]")
            
            if self.download_dataset(dataset_id, dataset_name, collection_name):
                self.downloaded += 1
            else:
                self.failed += 1
            
            time.sleep(1)  # Rate limiting
        
        logger.info(f"✓ Collection complete")
    
    def download_all(self):
        """Download all weather collections"""
        logger.info("=" * 80)
        logger.info("NEA WEATHER DATA DOWNLOADER")
        logger.info("=" * 80)
        logger.info(f"Output directory: {self.output_dir.absolute()}")
        logger.info(f"Target collections: {len(self.weather_collections)}")
        logger.info("")
        
        start_time = datetime.now()
        
        for idx, (collection_id, collection_name) in enumerate(self.weather_collections.items(), 1):
            logger.info(f"\n[COLLECTION {idx}/{len(self.weather_collections)}]")
            self.download_collection(collection_id, collection_name)
            time.sleep(2)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("DOWNLOAD COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"Collections: {len(self.weather_collections)}")
        logger.info(f"Total datasets: {self.total_datasets}")
        logger.info(f"Downloaded: {self.downloaded}")
        logger.info(f"Failed: {self.failed}")
        if self.total_datasets > 0:
            logger.info(f"Success rate: {(self.downloaded/self.total_datasets*100):.1f}%")
        logger.info(f"Files saved to: {self.output_dir.absolute()}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run: python seed_nea_historical_data.py")
        logger.info("  2. Run: python ml/visualize_spatial_data.py")
        logger.info("  3. Run: python ml/prepare_training_data.py nea")
        logger.info("=" * 80)


if __name__ == "__main__":
    downloader = WeatherDataDownloader()
    downloader.download_all()
