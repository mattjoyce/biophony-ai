#!/usr/bin/env python3
"""
AudioFile model for SQLAlchemy 2.x
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class AudioFile(Base):
    """AudioFile model matching existing database schema"""
    __tablename__ = 'audio_files'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    recording_datetime = Column(DateTime, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    audiomoth_id = Column(String)
    weather_id = Column(Integer, ForeignKey('weather_data.id'), nullable=True)
    processing_status = Column(String, nullable=True)
    
    # Relationship to weather data (forward reference)
    # weather = relationship("WeatherData", back_populates="audio_files")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'filename': self.filename,
            'filepath': self.filepath,
            'recording_datetime': self.recording_datetime.isoformat() if self.recording_datetime else None,
            'date': self.recording_datetime.date().isoformat() if self.recording_datetime else None,
            'time': self.recording_datetime.time().strftime('%H:%M') if self.recording_datetime else None,
            'duration_seconds': self.duration_seconds,
            'audiomoth_id': self.audiomoth_id,
            'weather_id': self.weather_id,
            'processing_status': self.processing_status
        }


class WeatherData(Base):
    """Weather data model"""
    __tablename__ = 'weather_data'
    
    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=False)
    temperature_2m = Column(Float)
    relative_humidity_2m = Column(Float)
    precipitation = Column(Float)
    wind_speed_10m = Column(Float)
    weather_code = Column(Integer)
    cloud_cover = Column(Float)
    pressure_msl = Column(Float)
    
    # Relationship to audio files (forward reference)
    # audio_files = relationship("AudioFile", back_populates="weather")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'datetime': self.datetime.isoformat() if self.datetime else None,
            'temperature': round(self.temperature_2m, 1) if self.temperature_2m is not None else None,
            'humidity': round(self.relative_humidity_2m, 1) if self.relative_humidity_2m is not None else None,
            'precipitation': round(self.precipitation, 1) if self.precipitation is not None else None,
            'wind_speed': round(self.wind_speed_10m, 1) if self.wind_speed_10m is not None else None,
            'weather_code': self.weather_code,
            'cloud_cover': round(self.cloud_cover, 1) if self.cloud_cover is not None else None,
            'pressure': round(self.pressure_msl, 1) if self.pressure_msl is not None else None
        }