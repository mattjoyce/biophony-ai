#!/usr/bin/env python3
"""
Weather data integration for AudioMoth bioacoustic analysis system.
Uses Open-Meteo Historical Weather API (free for research).
"""

import sqlite3
import openmeteo_requests
import requests_cache
from retry_requests import retry
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ExifTags
import logging
import argparse
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeatherDataIntegrator:
    def __init__(self, db_path, cache_dir=".weather_cache"):
        self.db_path = Path(db_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Setup cached Open-Meteo client (no API key needed)
        cache_session = requests_cache.CachedSession(
            str(self.cache_dir / 'weather_cache'), 
            expire_after=-1
        )
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=retry_session)
        
        self.weather_variables = [
            "temperature_2m",           # °C - Primary activity driver
            "relative_humidity_2m",     # % - Insect activity
            "precipitation",            # mm - Signal masking
            "wind_speed_10m",          # km/h - Recording interference
            "weather_code",            # WMO code - Overall conditions
            "cloud_cover",             # % - Night cooling effects
            "pressure_msl"             # hPa - Behavioral influence
        ]
    
    def init_weather_tables(self):
        """Initialize weather-related database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Weather sites table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    elevation REAL,
                    timezone TEXT,
                    timezone_abbreviation TEXT,
                    UNIQUE(latitude, longitude)
                )
            """)
            
            # Weather data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER REFERENCES weather_sites(id),
                    datetime TEXT NOT NULL,
                    temperature_2m REAL,
                    relative_humidity_2m REAL,
                    precipitation REAL,
                    wind_speed_10m REAL,
                    weather_code INTEGER,
                    cloud_cover REAL,
                    pressure_msl REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site_id, datetime)
                )
            """)
            
            # Add weather columns to audio_files if they don't exist
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN weather_id INTEGER REFERENCES weather_data(id)")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN site_id INTEGER REFERENCES weather_sites(id)")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            conn.commit()
            logger.info("Weather database tables initialized")
    
    def extract_gps_from_photo(self, photo_path):
        """Extract GPS coordinates from photo EXIF data"""
        try:
            image = Image.open(photo_path)
            exif_dict = image._getexif()
            
            if not exif_dict:
                return None
            
            gps_info = exif_dict.get(34853)  # GPS IFD tag
            if not gps_info:
                return None
            
            def dms_to_decimal(dms_tuple):
                degrees, minutes, seconds = dms_tuple
                return degrees + minutes/60 + seconds/3600
            
            # Extract latitude
            lat_dms = gps_info.get(2)  # GPSLatitude
            lat_ref = gps_info.get(1)  # GPSLatitudeRef
            
            # Extract longitude  
            lon_dms = gps_info.get(4)  # GPSLongitude
            lon_ref = gps_info.get(3)  # GPSLongitudeRef
            
            if not all([lat_dms, lat_ref, lon_dms, lon_ref]):
                return None
            
            latitude = float(dms_to_decimal(lat_dms))
            if lat_ref == "S":
                latitude *= -1
                
            longitude = float(dms_to_decimal(lon_dms))
            if lon_ref == "W":
                longitude *= -1
            
            return latitude, longitude
            
        except Exception as e:
            logger.warning(f"Could not extract GPS from {photo_path}: {e}")
            return None
    
    def register_site(self, name, latitude, longitude, photo_path=None):
        """Register a recording site with coordinates"""
        if photo_path and not latitude and not longitude:
            coords = self.extract_gps_from_photo(photo_path)
            if coords:
                latitude, longitude = coords
            else:
                raise ValueError(f"Could not extract GPS from {photo_path}")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO weather_sites (name, latitude, longitude)
                VALUES (?, ?, ?)
            """, (name, latitude, longitude))
            
            cursor.execute("""
                SELECT id FROM weather_sites WHERE latitude = ? AND longitude = ?
            """, (latitude, longitude))
            
            site_id = cursor.fetchone()[0]
            conn.commit()
            
        logger.info(f"Registered site '{name}' at {latitude:.6f}, {longitude:.6f} (ID: {site_id})")
        return site_id
    
    def fetch_weather_data(self, site_id, start_date, end_date):
        """Fetch weather data for a site and date range"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, latitude, longitude FROM weather_sites WHERE id = ?", (site_id,))
            site_info = cursor.fetchone()
            
        if not site_info:
            raise ValueError(f"Site ID {site_id} not found")
        
        name, latitude, longitude = site_info
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": self.weather_variables,
            "timezone": "auto"
        }
        
        logger.info(f"Fetching weather data for {name} ({latitude:.4f}, {longitude:.4f})")
        logger.info(f"Period: {start_date} to {end_date}")
        
        try:
            responses = self.openmeteo.weather_api(url, params=params)
            response = responses[0]
            
            # Update site with timezone info
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE weather_sites 
                    SET elevation = ?, timezone = ?, timezone_abbreviation = ?
                    WHERE id = ?
                """, (response.Elevation(), response.Timezone(), 
                          response.TimezoneAbbreviation(), site_id))
                conn.commit()
            
            # Process hourly data
            hourly = response.Hourly()
            time_data = pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )
            
            # Store weather data
            weather_records = []
            for i, dt in enumerate(time_data):
                record = [site_id, dt.strftime('%Y-%m-%d %H:%M:%S')]
                for j, var in enumerate(self.weather_variables):
                    value = hourly.Variables(j).ValuesAsNumpy()[i]
                    record.append(float(value) if not pd.isna(value) else None)
                weather_records.append(tuple(record))
            
            # Bulk insert weather data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO weather_data 
                    (site_id, datetime, temperature_2m, relative_humidity_2m, 
                     precipitation, wind_speed_10m, weather_code, cloud_cover, pressure_msl)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, weather_records)
                conn.commit()
            
            logger.info(f"Stored {len(weather_records)} weather records for site {site_id}")
            return len(weather_records)
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            return 0
    
    def match_recording_to_weather_hour(self, recording_datetime):
        """Match AudioMoth recording to weather hour it falls within"""
        dt = pd.to_datetime(recording_datetime)
        
        # Always use the hour the recording falls within
        # 01:30 falls within 01:00-02:00 → use 01:00 weather data
        weather_hour = dt.replace(minute=0, second=0, microsecond=0)
        
        return weather_hour.strftime('%Y-%m-%d %H:%M:%S')
    
    def link_recordings_to_weather(self, site_id):
        """Link audio recordings to weather data"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get recordings that need weather linking for this site
            cursor.execute("""
                SELECT id, filepath, recording_datetime 
                FROM audio_files 
                WHERE site_id IS NULL AND weather_id IS NULL
                ORDER BY recording_datetime
            """, ())
            
            recordings = cursor.fetchall()
            logger.info(f"Linking {len(recordings)} recordings to weather data")
            
            updates = []
            for record_id, filepath, recording_datetime in recordings:
                weather_hour = self.match_recording_to_weather_hour(recording_datetime)
                
                # Find matching weather record
                cursor.execute("""
                    SELECT id FROM weather_data 
                    WHERE site_id = ? AND datetime = ?
                """, (site_id, weather_hour))
                
                weather_match = cursor.fetchone()
                if weather_match:
                    updates.append((weather_match[0], site_id, record_id))
            
            # Bulk update recordings with weather IDs and site ID
            cursor.executemany("""
                UPDATE audio_files SET weather_id = ?, site_id = ? WHERE id = ?
            """, updates)
            
            conn.commit()
            logger.info(f"Linked {len(updates)} recordings to weather data")
            return len(updates)
    
    def get_weather_for_recording(self, recording_id):
        """Get weather data for a specific recording"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT wd.datetime, wd.temperature_2m, wd.relative_humidity_2m,
                       wd.precipitation, wd.wind_speed_10m, wd.weather_code,
                       wd.cloud_cover, wd.pressure_msl,
                       ws.name, ws.latitude, ws.longitude
                FROM audio_files af
                JOIN weather_data wd ON af.weather_id = wd.id  
                JOIN weather_sites ws ON wd.site_id = ws.id
                WHERE af.id = ?
            """, (recording_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'weather_datetime': result[0],
                    'temperature_2m': result[1],
                    'relative_humidity_2m': result[2],
                    'precipitation': result[3],
                    'wind_speed_10m': result[4],
                    'weather_code': result[5],
                    'cloud_cover': result[6],
                    'pressure_msl': result[7],
                    'site_name': result[8],
                    'site_latitude': result[9],
                    'site_longitude': result[10]
                }
            return None


def parse_arguments():
    """Parse command line arguments with clear descriptions"""
    parser = argparse.ArgumentParser(description="Integrate historical weather data with AudioMoth recordings using Open-Meteo API")
    
    # Required arguments first
    parser.add_argument("--config", "-c", required=True, help="YAML configuration file")
    
    # Optional arguments
    parser.add_argument("--input", "-i", help="Database path (optional - uses database_path from config if not provided)")
    parser.add_argument("--force", "-f", action="store_true", help="Force reprocessing of existing weather data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without actually doing any work")
    
    # Processing mode - simplified for typical workflow
    parser.add_argument("--run", action="store_true", default=True, help="Run complete weather integration workflow")
    
    return parser.parse_args()

def load_config(config_path):
    """Load YAML configuration file"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"❌ Error loading config file {config_path}: {e}")
        return None

def create_dry_run_report(mode, config, database_path):
    """Create dry-run report showing what would be processed"""
    print(f"🔍 DRY-RUN: Weather integration mode '{mode}'")
    print(f"📁 Database: {database_path}")
    
    weather_config = config.get('weather', {})
    print(f"🌦️  Weather provider: {weather_config.get('api_provider', 'open-meteo')}")
    
    sites = weather_config.get('sites', [])
    print(f"📍 Sites configured: {len(sites)}")
    for site in sites:
        print(f"   - {site.get('name', 'Unnamed site')}")
    
    date_range = weather_config.get('date_range', {})
    start_date = date_range.get('start_date', 'Not specified')
    end_date = date_range.get('end_date', 'Not specified')
    print(f"📅 Date range: {start_date} to {end_date}")
    
    variables = weather_config.get('variables', [])
    print(f"🌡️  Weather variables: {len(variables)} ({', '.join(variables[:3])}{'...' if len(variables) > 3 else ''})")

def main():
    """Main processing function following argparse spec patterns"""
    args = parse_arguments()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        return
    
    # Determine database path: use --input if provided, otherwise fall back to config
    if args.input:
        database_path = args.input
        input_source = "command line"
    else:
        database_path = config.get('database_path', 'audiomoth.db')
        input_source = "config file"
    
    print(f"📁 Database: {database_path} (from {input_source})")
    
    # Validate weather configuration
    weather_config = config.get('weather', {})
    if not weather_config.get('enabled', False):
        print("❌ Weather integration not enabled in config. Set weather.enabled: true")
        return
    
    # Dry-run handling
    if args.dry_run:
        create_dry_run_report('COMPLETE', config, database_path)
        return
    
    # Initialize integrator
    cache_dir = weather_config.get('cache_directory', '.weather_cache')
    integrator = WeatherDataIntegrator(database_path, cache_dir)
    
    try:
        # Complete workflow: init → fetch → link
        print("🔍 Initializing weather database tables...")
        integrator.init_weather_tables()
        print("✓ Weather tables initialized")
        
        print("🔍 Fetching weather data...")
        sites = weather_config.get('sites', [])
        date_range = weather_config.get('date_range', {})
        start_date = date_range.get('start_date')
        end_date = date_range.get('end_date')
        
        if not start_date or not end_date:
            print("❌ Date range not specified in config. Set weather.date_range.start_date and end_date")
            return
        
        total_records = 0
        for site_config in sites:
            site_name = site_config.get('name', 'Unknown Site')
            
            # Register site
            if 'photo_path' in site_config:
                site_id = integrator.register_site(
                    name=site_name,
                    latitude=None,
                    longitude=None,
                    photo_path=site_config['photo_path']
                )
            else:
                site_id = integrator.register_site(
                    name=site_name,
                    latitude=site_config.get('latitude'),
                    longitude=site_config.get('longitude')
                )
            
            # Fetch weather data
            records_count = integrator.fetch_weather_data(site_id, start_date, end_date)
            total_records += records_count
        
        print(f"✓ Fetched {total_records} weather records for {len(sites)} sites")
        
        print("🔍 Linking recordings to weather data...")
        total_linked = 0
        for site_config in sites:
            site_name = site_config.get('name', 'Unknown Site')
            
            # Find site ID
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM weather_sites WHERE name = ?", (site_name,))
                result = cursor.fetchone()
                if result:
                    site_id = result[0]
                    linked_count = integrator.link_recordings_to_weather(site_id)
                    total_linked += linked_count
        
        print(f"✓ Linked {total_linked} recordings to weather data")
        
        print("✓ Weather integration complete")
        
    except Exception as e:
        print(f"❌ Error during weather integration: {e}")
        logger.error(f"Weather integration failed: {e}")


if __name__ == "__main__":
    main()