"""
Spatial Data Visualization for NEA Multi-Station Weather Data

This script visualizes the spatial distribution of weather stations and their data
to verify that multi-station data makes sense geographically.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime, timedelta
from app.db.database import get_connection


def load_station_data(hours_back: int = 24) -> pd.DataFrame:
    """
    Load recent weather data from all stations.
    
    Args:
        hours_back: Number of hours of recent data to load
        
    Returns:
        DataFrame with station data
    """
    con = get_connection()
    
    # Get data from last N hours
    cutoff_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
    
    query = """
        SELECT 
            timestamp,
            location,
            latitude,
            longitude,
            temperature,
            rainfall,
            humidity,
            wind_speed,
            source_api
        FROM weather_records
        WHERE country = 'singapore'
        AND timestamp >= ?
        AND latitude IS NOT NULL
        AND longitude IS NOT NULL
        ORDER BY timestamp DESC
    """
    
    df = pd.read_sql_query(query, con, params=(cutoff_time,))
    con.close()
    
    return df


def plot_station_locations(df: pd.DataFrame, output_path: str = "ml/station_locations.png"):
    """
    Plot weather station locations on a map of Singapore.
    
    Args:
        df: DataFrame with station data
        output_path: Path to save the plot
    """
    # Get unique stations
    stations = df.groupby(['location', 'latitude', 'longitude']).size().reset_index(name='count')
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 10))
    
    # Singapore approximate bounds
    lat_min, lat_max = 1.15, 1.48
    lon_min, lon_max = 103.6, 104.05
    
    # Plot stations
    scatter = ax.scatter(
        stations['longitude'], 
        stations['latitude'],
        s=200,
        c='red',
        alpha=0.6,
        edgecolors='black',
        linewidths=2,
        zorder=5
    )
    
    # Add station labels
    for _, station in stations.iterrows():
        ax.annotate(
            station['location'].replace(' (NEA Historical)', '').replace(' (Historical)', ''),
            xy=(station['longitude'], station['latitude']),
            xytext=(5, 5),
            textcoords='offset points',
            fontsize=8,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
        )
    
    # Add Singapore center marker
    ax.scatter(103.8198, 1.3521, s=300, c='blue', marker='*', 
               edgecolors='black', linewidths=2, zorder=6, label='Singapore Center')
    
    # Add approximate coastline (simplified)
    # South coast
    ax.plot([103.6, 104.05], [1.15, 1.15], 'b-', linewidth=2, alpha=0.3)
    # North coast (Johor Strait)
    ax.plot([103.6, 104.05], [1.47, 1.47], 'b-', linewidth=2, alpha=0.3)
    # West coast
    ax.plot([103.6, 103.6], [1.15, 1.47], 'b-', linewidth=2, alpha=0.3)
    # East coast
    ax.plot([104.05, 104.05], [1.15, 1.47], 'b-', linewidth=2, alpha=0.3)
    
    # Set limits and labels
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    ax.set_title(f'NEA Weather Station Locations in Singapore\n({len(stations)} stations)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    # Add info text
    info_text = f"Total stations: {len(stations)}\nData points: {len(df)}"
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Station location map saved to {output_path}")
    plt.close()


def plot_rainfall_distribution(df: pd.DataFrame, output_path: str = "ml/rainfall_spatial_distribution.png"):
    """
    Plot spatial distribution of rainfall across stations.
    
    Args:
        df: DataFrame with station data
        output_path: Path to save the plot
    """
    # Get average rainfall per station
    station_rainfall = df.groupby(['location', 'latitude', 'longitude']).agg({
        'rainfall': 'mean',
        'temperature': 'mean',
        'humidity': 'mean'
    }).reset_index()
    
    # Create figure with subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Singapore bounds
    lat_min, lat_max = 1.15, 1.48
    lon_min, lon_max = 103.6, 104.05
    
    # Plot 1: Rainfall
    scatter1 = axes[0].scatter(
        station_rainfall['longitude'],
        station_rainfall['latitude'],
        s=station_rainfall['rainfall'] * 100 + 50,  # Size proportional to rainfall
        c=station_rainfall['rainfall'],
        cmap='Blues',
        alpha=0.6,
        edgecolors='black',
        linewidths=1
    )
    axes[0].set_xlim(lon_min, lon_max)
    axes[0].set_ylim(lat_min, lat_max)
    axes[0].set_xlabel('Longitude')
    axes[0].set_ylabel('Latitude')
    axes[0].set_title('Average Rainfall (mm/hr)')
    axes[0].grid(True, alpha=0.3)
    plt.colorbar(scatter1, ax=axes[0], label='Rainfall (mm/hr)')
    
    # Plot 2: Temperature
    scatter2 = axes[1].scatter(
        station_rainfall['longitude'],
        station_rainfall['latitude'],
        s=200,
        c=station_rainfall['temperature'],
        cmap='RdYlBu_r',
        alpha=0.6,
        edgecolors='black',
        linewidths=1
    )
    axes[1].set_xlim(lon_min, lon_max)
    axes[1].set_ylim(lat_min, lat_max)
    axes[1].set_xlabel('Longitude')
    axes[1].set_ylabel('Latitude')
    axes[1].set_title('Average Temperature (°C)')
    axes[1].grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=axes[1], label='Temperature (°C)')
    
    # Plot 3: Humidity
    scatter3 = axes[2].scatter(
        station_rainfall['longitude'],
        station_rainfall['latitude'],
        s=200,
        c=station_rainfall['humidity'],
        cmap='Greens',
        alpha=0.6,
        edgecolors='black',
        linewidths=1
    )
    axes[2].set_xlim(lon_min, lon_max)
    axes[2].set_ylim(lat_min, lat_max)
    axes[2].set_xlabel('Longitude')
    axes[2].set_ylabel('Latitude')
    axes[2].set_title('Average Humidity (%)')
    axes[2].grid(True, alpha=0.3)
    plt.colorbar(scatter3, ax=axes[2], label='Humidity (%)')
    
    plt.suptitle('Spatial Distribution of Weather Parameters', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Spatial distribution map saved to {output_path}")
    plt.close()


def plot_rainfall_classes_spatial(df: pd.DataFrame, output_path: str = "ml/rainfall_classes_spatial.png"):
    """
    Plot spatial distribution of NEA rainfall classes.
    
    Args:
        df: DataFrame with station data and rainfall_class column
        output_path: Path to save the plot
    """
    # Check if rainfall_class exists
    if 'rainfall_class' not in df.columns:
        # Classify rainfall manually
        def classify_rainfall(intensity):
            if intensity == 0:
                return 0  # No Rain
            elif intensity < 2:
                return 1  # Light Showers
            elif intensity < 10:
                return 2  # Moderate Showers
            elif intensity < 30:
                return 3  # Heavy Showers
            else:
                return 5  # Very Heavy Rain
        
        df['rainfall_class'] = df['rainfall'].apply(classify_rainfall)
    
    # Get class distribution per station
    station_classes = df.groupby(['location', 'latitude', 'longitude', 'rainfall_class']).size().reset_index(name='count')
    
    # NEA class colors
    class_colors = {
        0: '#FFFFFF',  # No Rain - White
        1: '#90EE90',  # Light Showers - Light Green
        2: '#FFD700',  # Moderate Showers - Yellow
        3: '#FF6347',  # Heavy Showers - Red
        4: '#9370DB',  # Thundery Showers - Purple
        5: '#8B0000'   # Very Heavy Rain - Dark Red
    }
    
    class_names = {
        0: 'No Rain',
        1: 'Light Showers',
        2: 'Moderate Showers',
        3: 'Heavy Showers',
        4: 'Thundery Showers',
        5: 'Very Heavy Rain'
    }
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Singapore bounds
    lat_min, lat_max = 1.15, 1.48
    lon_min, lon_max = 103.6, 104.05
    
    # Plot each class
    for class_id in sorted(station_classes['rainfall_class'].unique()):
        class_data = station_classes[station_classes['rainfall_class'] == class_id]
        
        ax.scatter(
            class_data['longitude'],
            class_data['latitude'],
            s=class_data['count'] / class_data['count'].max() * 500 + 50,
            c=class_colors.get(class_id, '#808080'),
            alpha=0.6,
            edgecolors='black',
            linewidths=1,
            label=class_names.get(class_id, f'Class {class_id}')
        )
    
    # Set limits and labels
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_xlabel('Longitude', fontsize=12)
    ax.set_ylabel('Latitude', fontsize=12)
    ax.set_title('Spatial Distribution of NEA Rainfall Classes\n(bubble size = frequency)', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10, loc='upper left')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Rainfall classes spatial map saved to {output_path}")
    plt.close()


def generate_station_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate summary statistics for each station.
    
    Args:
        df: DataFrame with station data
        
    Returns:
        DataFrame with station summary statistics
    """
    summary = df.groupby(['location', 'latitude', 'longitude']).agg({
        'timestamp': 'count',
        'temperature': ['mean', 'min', 'max'],
        'rainfall': ['mean', 'sum', 'max'],
        'humidity': ['mean', 'min', 'max'],
        'wind_speed': ['mean', 'max']
    }).reset_index()
    
    # Flatten column names
    summary.columns = [
        'location', 'latitude', 'longitude',
        'data_points', 
        'temp_mean', 'temp_min', 'temp_max',
        'rainfall_mean', 'rainfall_sum', 'rainfall_max',
        'humidity_mean', 'humidity_min', 'humidity_max',
        'wind_speed_mean', 'wind_speed_max'
    ]
    
    # Round numeric columns
    numeric_cols = summary.select_dtypes(include=[np.number]).columns
    summary[numeric_cols] = summary[numeric_cols].round(2)
    
    return summary


def main():
    """Main entry point for spatial visualization"""
    print("=" * 80)
    print("SPATIAL DATA VISUALIZATION FOR NEA MULTI-STATION WEATHER DATA")
    print("=" * 80)
    print()
    
    # Load recent data
    print("Loading station data from database...")
    df = load_station_data(hours_back=168)  # Last 7 days
    
    if len(df) == 0:
        print("❌ No data found in database!")
        print("Please run seed_nea_historical_data.py first to import NEA data.")
        return
    
    print(f"✓ Loaded {len(df)} observations from {df['location'].nunique()} stations")
    print()
    
    # Generate station summary
    print("Generating station summary...")
    summary = generate_station_summary(df)
    print("\nStation Summary:")
    print(summary.to_string(index=False))
    print()
    
    # Save summary to CSV
    summary.to_csv('ml/station_summary.csv', index=False)
    print("✓ Station summary saved to ml/station_summary.csv")
    print()
    
    # Create visualizations
    print("Creating visualizations...")
    
    print("1. Plotting station locations...")
    plot_station_locations(df)
    
    print("2. Plotting spatial distribution of weather parameters...")
    plot_rainfall_distribution(df)
    
    print("3. Plotting spatial distribution of rainfall classes...")
    plot_rainfall_classes_spatial(df)
    
    print()
    print("=" * 80)
    print("VISUALIZATION COMPLETE")
    print("=" * 80)
    print("\nGenerated files:")
    print("  - ml/station_locations.png")
    print("  - ml/rainfall_spatial_distribution.png")
    print("  - ml/rainfall_classes_spatial.png")
    print("  - ml/station_summary.csv")
    print()
    print("✓ All visualizations saved successfully!")


if __name__ == "__main__":
    main()
