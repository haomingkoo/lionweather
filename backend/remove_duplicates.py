#!/usr/bin/env python3
"""
Remove Duplicate Weather Records

This script identifies and removes duplicate weather records from the database.
Duplicates are defined as records with the same timestamp, country, and location.

When duplicates are found, it keeps the most recent record (by created_at) and
removes the older ones.
"""

import sqlite3
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.getenv("DATABASE_PATH", "weather.db")


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def find_duplicates():
    """
    Find duplicate weather records.
    
    Returns:
        List of tuples: (timestamp, country, location, count)
    """
    con = get_connection()
    cursor = con.cursor()
    
    try:
        cursor.execute("""
            SELECT timestamp, country, location, COUNT(*) as count
            FROM weather_records
            GROUP BY timestamp, country, location
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        duplicates = cursor.fetchall()
        return duplicates
        
    finally:
        con.close()


def remove_duplicates(dry_run=True):
    """
    Remove duplicate weather records, keeping the most recent one.
    
    Args:
        dry_run: If True, only report what would be deleted without actually deleting
        
    Returns:
        Number of records that would be/were deleted
    """
    con = get_connection()
    cursor = con.cursor()
    
    try:
        # Find all duplicate groups
        duplicates = find_duplicates()
        
        if not duplicates:
            logger.info("✅ No duplicates found!")
            return 0
        
        logger.info(f"Found {len(duplicates)} groups of duplicates")
        
        total_to_delete = 0
        
        for timestamp, country, location, count in duplicates:
            # Get all records in this duplicate group
            cursor.execute("""
                SELECT id, created_at
                FROM weather_records
                WHERE timestamp = ? AND country = ? AND location = ?
                ORDER BY created_at DESC
            """, (timestamp, country, location))
            
            records = cursor.fetchall()
            
            # Keep the first one (most recent created_at), delete the rest
            keep_id = records[0][0]
            delete_ids = [r[0] for r in records[1:]]
            
            logger.info(
                f"  {country}/{location} at {timestamp}: "
                f"{count} duplicates (keeping ID {keep_id}, deleting {len(delete_ids)} others)"
            )
            
            total_to_delete += len(delete_ids)
            
            if not dry_run and delete_ids:
                # Delete the duplicate records
                placeholders = ','.join('?' * len(delete_ids))
                cursor.execute(
                    f"DELETE FROM weather_records WHERE id IN ({placeholders})",
                    delete_ids
                )
        
        if not dry_run:
            con.commit()
            logger.info(f"✅ Deleted {total_to_delete} duplicate records")
        else:
            logger.info(f"🔍 DRY RUN: Would delete {total_to_delete} duplicate records")
            logger.info("   Run with --execute to actually delete duplicates")
        
        return total_to_delete
        
    except Exception as e:
        con.rollback()
        logger.error(f"❌ Error removing duplicates: {str(e)}")
        raise
    finally:
        con.close()


def verify_no_duplicates():
    """
    Verify that no duplicates exist in the database.
    
    Returns:
        True if no duplicates, False otherwise
    """
    duplicates = find_duplicates()
    
    if duplicates:
        logger.warning(f"⚠️  Still have {len(duplicates)} groups of duplicates!")
        return False
    else:
        logger.info("✅ Verified: No duplicates in database")
        return True


def get_database_stats():
    """Get database statistics before and after duplicate removal."""
    con = get_connection()
    cursor = con.cursor()
    
    try:
        # Total records
        cursor.execute("SELECT COUNT(*) FROM weather_records")
        total = cursor.fetchone()[0]
        
        # Records by country
        cursor.execute("""
            SELECT country, COUNT(*) as count
            FROM weather_records
            GROUP BY country
            ORDER BY count DESC
        """)
        by_country = cursor.fetchall()
        
        # Unique timestamps
        cursor.execute("SELECT COUNT(DISTINCT timestamp) FROM weather_records")
        unique_timestamps = cursor.fetchone()[0]
        
        # Unique locations
        cursor.execute("SELECT COUNT(DISTINCT country || '/' || location) FROM weather_records")
        unique_locations = cursor.fetchone()[0]
        
        return {
            'total': total,
            'by_country': by_country,
            'unique_timestamps': unique_timestamps,
            'unique_locations': unique_locations
        }
        
    finally:
        con.close()


if __name__ == "__main__":
    import sys
    
    print("=" * 80)
    print("DUPLICATE WEATHER RECORDS REMOVAL")
    print("=" * 80)
    print()
    
    # Get initial stats
    logger.info("Getting database statistics...")
    stats_before = get_database_stats()
    
    print(f"📊 BEFORE:")
    print(f"   Total records: {stats_before['total']:,}")
    print(f"   Unique timestamps: {stats_before['unique_timestamps']:,}")
    print(f"   Unique locations: {stats_before['unique_locations']:,}")
    print()
    for country, count in stats_before['by_country']:
        print(f"   {country.capitalize():15} {count:6,} records")
    print()
    
    # Check for duplicates
    logger.info("Checking for duplicates...")
    duplicates = find_duplicates()
    
    if not duplicates:
        print("✅ No duplicates found! Database is clean.")
        print()
        sys.exit(0)
    
    print(f"⚠️  Found {len(duplicates)} groups of duplicates:")
    print()
    
    # Show top 10 duplicate groups
    for i, (timestamp, country, location, count) in enumerate(duplicates[:10]):
        print(f"   {i+1}. {country}/{location} at {timestamp}: {count} duplicates")
    
    if len(duplicates) > 10:
        print(f"   ... and {len(duplicates) - 10} more groups")
    
    print()
    
    # Determine if this is a dry run or actual execution
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("🔍 DRY RUN MODE (no changes will be made)")
        print("   Run with --execute flag to actually remove duplicates")
        print()
    else:
        print("⚠️  EXECUTION MODE - Duplicates will be removed!")
        print()
    
    # Remove duplicates
    deleted_count = remove_duplicates(dry_run=dry_run)
    
    if not dry_run:
        print()
        
        # Get final stats
        logger.info("Getting updated database statistics...")
        stats_after = get_database_stats()
        
        print(f"📊 AFTER:")
        print(f"   Total records: {stats_after['total']:,}")
        print(f"   Unique timestamps: {stats_after['unique_timestamps']:,}")
        print(f"   Unique locations: {stats_after['unique_locations']:,}")
        print()
        for country, count in stats_after['by_country']:
            print(f"   {country.capitalize():15} {count:6,} records")
        print()
        
        print(f"✅ Removed {deleted_count} duplicate records")
        print(f"   Records before: {stats_before['total']:,}")
        print(f"   Records after:  {stats_after['total']:,}")
        print(f"   Reduction:      {stats_before['total'] - stats_after['total']:,}")
        print()
        
        # Verify no duplicates remain
        verify_no_duplicates()
    
    print("=" * 80)
    print()
