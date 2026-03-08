"""
Comprehensive NEA Historical Data Downloader

This script automatically downloads ALL NEA historical datasets from data.gov.sg
using their public API. Discovers 113+ datasets automatically - no manual work required.

Data Source: https://data.gov.sg
- Discovers all NEA collections via API
- Downloads weather, air quality, forecasts, and more
- Organizes data by collection
- Handles large datasets efficiently
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NEADataDownloader:
    """Downloads all NEA historical data from data.gov.sg"""
    
    def __init__(self, output_dir: str = "nea_historical_data"):
        """
        Initialize the downloader.
        
        Args:
            output_dir: Directory to save downloaded files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.base_url = "https://api-production.data.gov.sg/v2/public/api"
        
        # Statistics
        self.total_collections = 0
        self.total_datasets = 0
        self.downloaded_datasets = 0
        self.failed_datasets = 0
    
    def discover_all_collections(self) -> list:
        """
        Discover ALL collections from data.gov.sg API.
        
        Returns:
            List of collection dictionaries
        """
        logger.info("Discovering all collections from data.gov.sg...")
        
        all_collections = []
        page = 1
        
        while True:
            url = f"{self.base_url}/collections?page={page}"
            
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"  API Response code: {data.get('code')}, data keys: {list(data.keys())}")
                
                # API returns code 0 for success, code 1 for errors
                if data.get('code') != 0:
                    logger.error(f"API error: {data.get('errorMsg')}")
                    logger.error(f"Full response: {json.dumps(data, indent=2)}")
                    break
                
                collections_data = data.get('data', {})
                collections = collections_data.get('collections', [])
                total_pages = collections_data.get('pages', 1)
                
                if not collections:
                    break
                
                all_collections.extend(collections)
                logger.info(f"  Page {page}/{total_pages}: Found {len(collections)} collections")
                
                if page >= total_pages:
                    break
                
                page += 1
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Failed to fetch collections page {page}: {str(e)}")
                break
        
        logger.info(f"✓ Discovered {len(all_collections)} total collections")
        return all_collections
    
    def filter_nea_collections(self, all_collections: list) -> list:
        """
        Filter for NEA-related collections.
        
        Args:
            all_collections: List of all collections
            
        Returns:
            List of NEA collection dictionaries
        """
        logger.info("Filtering for NEA collections...")
        
        nea_keywords = [
            'nea', 'national environment agency', 'weather', 'climate',
            'temperature', 'rainfall', 'humidity', 'wind', 'forecast',
            'air quality', 'pm2.5', 'psi', 'uvi', 'historical',
            'air pollutant', 'haze', 'dengue', 'meteorological'
        ]
        
        nea_collections = []
        
        for collection in all_collections:
            collection_name = collection.get('name', '').lower()
            collection_desc = collection.get('description', '').lower()
            agency_name = collection.get('managedByAgencyName', '').lower()
            
            # Check if collection is NEA-related
            is_nea = False
            
            # Direct agency match
            if 'nea' in agency_name or 'national environment' in agency_name:
                is_nea = True
            
            # Keyword match in name or description
            if not is_nea:
                for keyword in nea_keywords:
                    if keyword in collection_name or keyword in collection_desc:
                        is_nea = True
                        break
            
            if is_nea:
                nea_collections.append(collection)
                logger.info(f"  ✓ {collection.get('name')} (ID: {collection.get('collectionId')})")
        
        logger.info(f"✓ Found {len(nea_collections)} NEA-related collections")
        return nea_collections
    
    def get_collection_metadata(self, collection_id: int) -> dict:
        """
        Get metadata for a specific collection.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            Collection metadata dictionary
        """
        url = f"{self.base_url}/collections/{collection_id}/metadata?withDatasetMetadata=true"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # API returns code 0 for success
            if data.get('code') == 0:
                return data.get('data', {})
            else:
                logger.error(f"API error for collection {collection_id}: {data.get('errorMsg')}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get metadata for collection {collection_id}: {str(e)}")
            return {}
    
    def download_dataset(self, dataset_id: str, dataset_name: str, collection_name: str) -> bool:
        """
        Download a specific dataset.
        
        Args:
            dataset_id: Dataset ID
            dataset_name: Dataset name for logging
            collection_name: Parent collection name for organization
            
        Returns:
            True if successful, False otherwise
        """
        # Initiate download
        initiate_url = f"{self.base_url}/datasets/{dataset_id}/initiate-download"
        
        try:
            logger.info(f"  Downloading: {dataset_name}")
            
            response = requests.get(initiate_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # API returns code 0 for success
            if data.get('code') != 0:
                logger.warning(f"  ⚠ Failed to initiate download: {data.get('errorMsg')}")
                return False
            
            # Get download URL
            download_data = data.get('data', {})
            download_url = download_data.get('url')
            
            if not download_url:
                logger.warning(f"  ⚠ No download URL provided")
                return False
            
            # Download the file
            file_response = requests.get(download_url, stream=True, timeout=300)
            file_response.raise_for_status()
            
            # Create subdirectory for collection
            safe_collection_name = "".join(c for c in collection_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_collection_name = safe_collection_name.replace(' ', '_').lower()[:100]  # Limit length
            collection_dir = self.output_dir / safe_collection_name
            collection_dir.mkdir(exist_ok=True)
            
            # Save to file
            safe_filename = "".join(c for c in dataset_name if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            safe_filename = safe_filename.replace(' ', '_').lower()[:150]  # Limit length
            
            # Ensure .csv extension
            if not safe_filename.endswith('.csv'):
                safe_filename += '.csv'
            
            output_path = collection_dir / safe_filename
            
            with open(output_path, 'wb') as f:
                for chunk in file_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            logger.info(f"  ✓ Saved: {output_path.name} ({file_size:.2f} MB)")
            return True
            
        except Exception as e:
            logger.error(f"  ✗ Failed to download: {str(e)}")
            return False
    
    def download_collection(self, collection: dict):
        """
        Download all datasets in a collection.
        
        Args:
            collection: Collection dictionary
        """
        collection_id = collection.get('collectionId')
        collection_name = collection.get('name', 'Unknown')
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"COLLECTION: {collection_name}")
        logger.info(f"ID: {collection_id}")
        logger.info("=" * 80)
        
        # Get collection metadata
        metadata = self.get_collection_metadata(collection_id)
        
        if not metadata:
            logger.error(f"Failed to get metadata for collection {collection_id}")
            return
        
        # Get datasets
        datasets = metadata.get('datasetMetadata', [])
        
        if not datasets:
            logger.warning(f"No datasets found in collection")
            return
        
        logger.info(f"Found {len(datasets)} datasets")
        logger.info("")
        
        self.total_datasets += len(datasets)
        
        # Download each dataset
        for idx, dataset in enumerate(datasets, 1):
            dataset_id = dataset.get('datasetId')
            dataset_name = dataset.get('name', 'unknown')
            
            logger.info(f"[{idx}/{len(datasets)}]")
            
            if self.download_dataset(dataset_id, dataset_name, collection_name):
                self.downloaded_datasets += 1
            else:
                self.failed_datasets += 1
            
            # Rate limiting - be nice to the API
            time.sleep(1)
        
        logger.info("")
        logger.info(f"✓ Collection complete: {self.downloaded_datasets - (self.total_datasets - len(datasets))}/{len(datasets)} datasets downloaded")
    
    def download_all(self):
        """Download all NEA historical data collections"""
        logger.info("=" * 80)
        logger.info("NEA COMPREHENSIVE HISTORICAL DATA DOWNLOADER")
        logger.info("=" * 80)
        logger.info(f"Output directory: {self.output_dir.absolute()}")
        logger.info("")
        
        start_time = datetime.now()
        
        # Step 1: Discover all collections
        all_collections = self.discover_all_collections()
        
        if not all_collections:
            logger.error("No collections discovered. Exiting.")
            return
        
        logger.info("")
        
        # Step 2: Filter for NEA collections
        nea_collections = self.filter_nea_collections(all_collections)
        
        if not nea_collections:
            logger.error("No NEA collections found. Exiting.")
            return
        
        self.total_collections = len(nea_collections)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"DOWNLOADING {self.total_collections} NEA COLLECTIONS")
        logger.info("=" * 80)
        
        # Step 3: Download each collection
        for idx, collection in enumerate(nea_collections, 1):
            logger.info(f"\n[COLLECTION {idx}/{self.total_collections}]")
            self.download_collection(collection)
            
            # Rate limiting between collections
            time.sleep(2)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Final summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("DOWNLOAD COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"Collections processed: {self.total_collections}")
        logger.info(f"Total datasets: {self.total_datasets}")
        logger.info(f"Successfully downloaded: {self.downloaded_datasets}")
        logger.info(f"Failed: {self.failed_datasets}")
        if self.total_datasets > 0:
            logger.info(f"Success rate: {(self.downloaded_datasets/self.total_datasets*100):.1f}%")
        logger.info(f"Files saved to: {self.output_dir.absolute()}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run: python seed_nea_historical_data.py")
        logger.info("  2. Run: python ml/visualize_spatial_data.py")
        logger.info("  3. Run: python ml/prepare_training_data.py nea")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    downloader = NEADataDownloader()
    downloader.download_all()


if __name__ == "__main__":
    main()
