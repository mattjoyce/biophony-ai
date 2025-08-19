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
                    sunrise_time TEXT,
                    sunset_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(site_id, datetime)
                )
            """)
            
            # Add sunrise/sunset columns to existing weather_data if they don't exist
            try:
                cursor.execute("ALTER TABLE weather_data ADD COLUMN sunrise_time TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE weather_data ADD COLUMN sunset_time TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add weather columns to audio_files if they don't exist
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN weather_id INTEGER REFERENCES weather_data(id)")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN site_id INTEGER REFERENCES weather_sites(id)")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Add sunrise/sunset temporal label columns to audio_files if they don't exist
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN time_since_last TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE audio_files ADD COLUMN time_to_next TEXT")
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
            "hourly": ",".join(self.weather_variables),
            "daily": "sunrise,sunset",
            "timezone": "auto"
        }
        
        logger.info(f"Fetching weather data for {name} ({latitude:.4f}, {longitude:.4f})")
        logger.info(f"Period: {start_date} to {end_date}")
        
        try:
            # Make both SDK and raw requests to get sunrise/sunset data
            responses = self.openmeteo.weather_api(url, params=params)
            response = responses[0]
            
            # Also make raw API call for sunrise/sunset data
            import requests
            raw_response = requests.get(url, params=params)
            raw_data = raw_response.json() if raw_response.status_code == 200 else None
            
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
            
            # Process daily sunrise/sunset data from raw API response
            sunrise_sunset_by_date = {}
            try:
                if raw_data and 'daily' in raw_data:
                    daily_data = raw_data['daily']
                    
                    if 'sunrise' in daily_data and 'sunset' in daily_data and 'time' in daily_data:
                        dates = daily_data['time']
                        sunrises = daily_data['sunrise']
                        sunsets = daily_data['sunset']
                        
                        logger.info(f"Processing {len(dates)} days of sunrise/sunset data from raw API")
                        logger.info(f"Sample sunrise data: {sunrises[:3]}")
                        logger.info(f"Sample sunset data: {sunsets[:3]}")
                        
                        valid_count = 0
                        for i, date_str in enumerate(dates):
                            if i < len(sunrises) and i < len(sunsets):
                                sunrise_str = sunrises[i]
                                sunset_str = sunsets[i]
                                
                                # Parse the date for the key
                                try:
                                    date_key = pd.to_datetime(date_str).date()
                                    
                                    # Parse and validate sunrise/sunset times
                                    if sunrise_str and sunset_str:
                                        # Convert ISO8601 to our format
                                        sunrise_dt = pd.to_datetime(sunrise_str)
                                        sunset_dt = pd.to_datetime(sunset_str)
                                        
                                        sunrise_sunset_by_date[date_key] = {
                                            'sunrise': sunrise_dt.strftime('%Y-%m-%dT%H:%M:%S'),
                                            'sunset': sunset_dt.strftime('%Y-%m-%dT%H:%M:%S')
                                        }
                                        valid_count += 1
                                        
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Could not parse sunrise/sunset for {date_str}: sunrise='{sunrise_str}', sunset='{sunset_str}', error={e}")
                                    continue
                        
                        logger.info(f"Successfully processed sunrise/sunset for {valid_count} dates")
                        if valid_count == 0:
                            logger.warning("No valid sunrise/sunset data found in raw API response")
                    else:
                        logger.warning("Raw API response missing expected sunrise/sunset fields")
                else:
                    logger.warning("No valid raw API response for sunrise/sunset data")
                    
            except Exception as e:
                logger.error(f"Critical error processing sunrise/sunset data: {e}")
                import traceback
                traceback.print_exc()
            
            # Process hourly data
            hourly = response.Hourly()
            time_data = pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )
            
            # Store weather data with sunrise/sunset
            weather_records = []
            for i, dt in enumerate(time_data):
                record = [site_id, dt.strftime('%Y-%m-%d %H:%M:%S')]
                for j, var in enumerate(self.weather_variables):
                    value = hourly.Variables(j).ValuesAsNumpy()[i]
                    record.append(float(value) if not pd.isna(value) else None)
                
                # Add sunrise/sunset for this date
                date_key = dt.date()
                if date_key in sunrise_sunset_by_date:
                    record.append(sunrise_sunset_by_date[date_key]['sunrise'])
                    record.append(sunrise_sunset_by_date[date_key]['sunset'])
                else:
                    record.append(None)  # sunrise_time
                    record.append(None)  # sunset_time
                    
                weather_records.append(tuple(record))
            
            # Bulk insert weather data
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO weather_data 
                    (site_id, datetime, temperature_2m, relative_humidity_2m, 
                     precipitation, wind_speed_10m, weather_code, cloud_cover, pressure_msl,
                     sunrise_time, sunset_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    def since_to_labels(self, ts, sr_today, ss_today, sr_next, ss_prev):
        """Generate sunrise/sunset temporal labels for a timestamp"""
        from datetime import timedelta
        
        events = {
            'SR_prev': sr_today.replace(day=sr_today.day) - timedelta(days=1) if sr_today else None,
            'SS_prev': ss_prev,
            'SR': sr_today,
            'SS': ss_today,
            'SR_next': sr_next,
        }
        
        # Filter out None events and split past/future
        valid_events = {k: v for k, v in events.items() if v is not None}
        past = {k: v for k, v in valid_events.items() if v <= ts}
        future = {k: v for k, v in valid_events.items() if v >= ts}
        
        if not past or not future:
            return None, None  # Can't determine labels without past/future events
        
        last_key, last_time = max(past.items(), key=lambda kv: kv[1])
        next_key, next_time = min(future.items(), key=lambda kv: kv[1])

        def fmt(label, delta_sec, sign):
            h = int(delta_sec // 3600)
            m = int((delta_sec % 3600) // 60)
            return f"{label}{sign}{h:02d}:{m:02d}"

        since = fmt('SR' if 'SR' in last_key else 'SS',
                    (ts - last_time).total_seconds(), '+')
        to = fmt('SR' if 'SR' in next_key else 'SS',
                 (next_time - ts).total_seconds(), '−')
        return since, to
    
    def get_sunrise_sunset_for_date(self, site_id, date):
        """Get sunrise/sunset times for a specific date and site"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sunrise_time, sunset_time 
                FROM weather_data 
                WHERE site_id = ? AND DATE(datetime) = ? 
                AND sunrise_time IS NOT NULL AND sunset_time IS NOT NULL
                LIMIT 1
            """, (site_id, date))
            result = cursor.fetchone()
            
            if result:
                sunrise_str, sunset_str = result
                sunrise_dt = pd.to_datetime(sunrise_str)
                sunset_dt = pd.to_datetime(sunset_str)
                return sunrise_dt, sunset_dt
            return None, None
    
    def link_recordings_to_weather(self, site_id):
        """Link audio recordings to weather data and calculate sunrise/sunset labels"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get recordings that need sunrise/sunset labels (either new or existing without labels)
            cursor.execute("""
                SELECT id, filepath, recording_datetime 
                FROM audio_files 
                WHERE (site_id IS NULL OR time_since_last IS NULL)
                ORDER BY recording_datetime
            """, ())
            
            recordings = cursor.fetchall()
            logger.info(f"Linking {len(recordings)} recordings to weather data and calculating sunrise/sunset labels")
            
            updates = []
            for record_id, filepath, recording_datetime in recordings:
                recording_dt = pd.to_datetime(recording_datetime)
                recording_date = recording_dt.date()
                
                # Get weather hour match
                weather_hour = self.match_recording_to_weather_hour(recording_datetime)
                cursor.execute("""
                    SELECT id FROM weather_data 
                    WHERE site_id = ? AND datetime = ?
                """, (site_id, weather_hour))
                
                weather_match = cursor.fetchone()
                if not weather_match:
                    continue  # Skip if no weather data
                
                weather_id = weather_match[0]
                
                # Get sunrise/sunset data for current, previous, and next day
                from datetime import timedelta
                prev_date = (recording_dt - timedelta(days=1)).date()
                next_date = (recording_dt + timedelta(days=1)).date()
                
                sr_today, ss_today = self.get_sunrise_sunset_for_date(site_id, recording_date.strftime('%Y-%m-%d'))
                sr_next, _ = self.get_sunrise_sunset_for_date(site_id, next_date.strftime('%Y-%m-%d'))
                _, ss_prev = self.get_sunrise_sunset_for_date(site_id, prev_date.strftime('%Y-%m-%d'))
                
                # Calculate sunrise/sunset labels
                time_since_last = None
                time_to_next = None
                
                if sr_today and ss_today:  # Only calculate if we have today's sunrise/sunset
                    try:
                        since, to = self.since_to_labels(recording_dt, sr_today, ss_today, sr_next, ss_prev)
                        time_since_last = since
                        time_to_next = to
                    except Exception as e:
                        logger.warning(f"Could not calculate sunrise/sunset labels for {recording_datetime}: {e}")
                
                updates.append((weather_id, site_id, time_since_last, time_to_next, record_id))
            
            # Bulk update recordings with weather IDs, site ID, and sunrise/sunset labels
            if updates:
                cursor.executemany("""
                    UPDATE audio_files 
                    SET weather_id = ?, site_id = ?, time_since_last = ?, time_to_next = ?
                    WHERE id = ?
                """, updates)
            
            conn.commit()
            logger.info(f"Linked {len(updates)} recordings to weather data with sunrise/sunset labels")
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
    
    # Check if database exists and inspect current state
    db_path = Path(database_path)
    if db_path.exists():
        try:
            with sqlite3.connect(database_path) as conn:
                cursor = conn.cursor()
                
                # Count audio files
                cursor.execute("SELECT COUNT(*) FROM audio_files")
                audio_count = cursor.fetchone()[0]
                print(f"📊 Current audio files: {audio_count}")
                
                # Count files with weather data
                cursor.execute("SELECT COUNT(*) FROM audio_files WHERE weather_id IS NOT NULL")
                linked_count = cursor.fetchone()[0]
                print(f"🔗 Files with weather links: {linked_count}")
                
                # Count files with solar data
                cursor.execute("SELECT COUNT(*) FROM audio_files WHERE time_since_last IS NOT NULL")
                solar_count = cursor.fetchone()[0]
                print(f"☀️  Files with solar labels: {solar_count}")
                
                # Check existing weather records
                cursor.execute("SELECT COUNT(*) FROM weather_data")
                weather_count = cursor.fetchone()[0]
                print(f"🌦️  Weather records: {weather_count}")
                
                # Check sunrise/sunset data
                cursor.execute("SELECT COUNT(*) FROM weather_data WHERE sunrise_time IS NOT NULL")
                sunrise_count = cursor.fetchone()[0]
                print(f"🌅 Records with sunrise/sunset: {sunrise_count}")
                
                # Show date range of audio files
                cursor.execute("SELECT MIN(recording_datetime), MAX(recording_datetime) FROM audio_files")
                date_range = cursor.fetchone()
                if date_range[0] and date_range[1]:
                    print(f"📅 Audio file dates: {date_range[0]} to {date_range[1]}")
                
        except Exception as e:
            print(f"⚠️  Database inspection failed: {e}")
    else:
        print("❌ Database file not found")
    
    print("\n" + "="*50)
    
    weather_config = config.get('weather', {})
    print(f"🌦️  Weather provider: {weather_config.get('api_provider', 'open-meteo')}")
    
    sites = weather_config.get('sites', [])
    print(f"📍 Sites configured: {len(sites)}")
    for site in sites:
        print(f"   - {site.get('name', 'Unnamed site')}")
        if 'photo_path' in site:
            photo_path = Path(site['photo_path'])
            print(f"     📸 Photo: {'✓' if photo_path.exists() else '❌'} {site['photo_path']}")
    
    date_range = weather_config.get('date_range', {})
    start_date = date_range.get('start_date', 'Not specified')
    end_date = date_range.get('end_date', 'Not specified')
    print(f"📅 Weather date range: {start_date} to {end_date}")
    
    # Check if date range is reasonable
    if start_date != 'Not specified' and end_date != 'Not specified':
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            today = datetime.now()
            
            if start > today:
                print("⚠️  Start date is in the future - may not have valid sunrise/sunset data")
            if end > today:
                print("⚠️  End date is in the future - may not have valid sunrise/sunset data")
                
        except Exception:
            print("⚠️  Could not parse date range")
    
    variables = weather_config.get('variables', [])
    print(f"🌡️  Weather variables: {len(variables)} ({', '.join(variables[:3])}{'...' if len(variables) > 3 else ''})")
    print("☀️  Sunrise/sunset: enabled (daily sunrise,sunset + temporal labels)")

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