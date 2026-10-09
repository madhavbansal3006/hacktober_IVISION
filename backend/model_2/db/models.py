"""
JalDrishti Database V1 SQLAlchemy Models.

Entities:
1. MicroWatershed (micro_watersheds): Authoritative watershed metadata with PostGIS geometry.
2. RiskHistory (risk_history): Time-series and monthly baseline risk assessments.
3. IoTReading (iot_readings): Real-time physical and simulated telemetry streams.
4. Intervention (interventions): Targeted field interventions, priorities, and implementation status.
5. Alert (alerts): Operational alerts for risk spikes, ML anomalies, and compound hazard events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    BigInteger,
    Boolean,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Index,
    JSON,
    func,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator
from geoalchemy2 import Geometry

Base = declarative_base()


class WatershedGeometry(TypeDecorator):
    """
    Adaptive PostGIS Geometry Type.
    Produces native PostGIS geometry(MULTIPOLYGON, 4326) with GiST index on PostgreSQL,
    and falls back cleanly to Text() representation for SQLite / in-memory test environments.
    """
    impl = Geometry("MULTIPOLYGON", srid=4326, spatial_index=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect is not None and dialect.name == "sqlite":
            from sqlalchemy.types import Text
            return dialect.type_descriptor(Text())
        if dialect is None:
            return self.impl
        return dialect.type_descriptor(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect is not None and dialect.name == "sqlite":
            if hasattr(value, "data"):
                return str(value.data)
            if hasattr(value, "wkt"):
                return str(value.wkt)
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value


class MicroWatershed(Base):
    """
    Authoritative Micro-Watershed Metadata and Spatial Boundaries.
    Represents the 66 canonical micro-watersheds of Shiggaon Taluk.
    """
    __tablename__ = "micro_watersheds"

    # Primary Identifier & Display Code
    mws_id = Column(String(64), primary_key=True, index=True, doc="Canonical GIS identifier (e.g. g_mws.240575)")
    display_code = Column(String(32), index=True, nullable=False, doc="Human-readable display code (e.g. 4D4F2m3)")
    name = Column(String(128), nullable=True, doc="Descriptive name or alias")

    # Administrative Context
    taluk = Column(String(64), default="Shiggaon", nullable=False)
    district = Column(String(64), default="Haveri", nullable=False)
    state = Column(String(64), default="Karnataka", nullable=False)

    # Physical Hydrology & Topography
    area_sqkm = Column(Float, nullable=True, doc="Surface area in square kilometers")
    stream_length_km = Column(Float, nullable=True, doc="Total stream length in kilometers")
    drainage_density = Column(Float, nullable=True, doc="Drainage density (km/km²)")
    max_strahler_order = Column(Integer, nullable=True, doc="Maximum Strahler stream order")
    slope_mean_deg = Column(Float, nullable=True, doc="Mean terrain slope in degrees")
    elevation_mean_m = Column(Float, nullable=True, doc="Mean elevation in meters (SRTM)")

    # Land Use / Land Cover (Model 1 Baseline Percentages)
    forest_pct = Column(Float, default=0.0, doc="Forest canopy coverage percentage")
    agriculture_pct = Column(Float, default=0.0, doc="Agricultural crop/fallow percentage")
    water_pct = Column(Float, default=0.0, doc="Open water body surface percentage")
    builtup_pct = Column(Float, default=0.0, doc="Settlement/built-up percentage")
    barren_pct = Column(Float, default=0.0, doc="Barren / scrub / degraded percentage")

    # Current Authoritative Operational Risk Snapshot
    current_risk_score = Column(Float, nullable=True, doc="Latest authoritative risk score (0-100)")
    current_risk_category = Column(String(32), index=True, nullable=True, doc="CRITICAL, HIGH, MODERATE, or LOW")
    current_primary_driver = Column(String(64), nullable=True, doc="Primary risk driver")
    current_health_index = Column(Float, nullable=True, doc="Basin Health Index (100 - risk_score)")
    intervention_priority = Column(String(32), nullable=True, doc="Priority rating for field interventions")

    # PostGIS Vector Geometry (WGS84 EPSG:4326)
    geometry = Column(WatershedGeometry, nullable=True, doc="PostGIS MultiPolygon boundary geometry")

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    risk_history = relationship("RiskHistory", back_populates="micro_watershed", cascade="all, delete-orphan")
    iot_readings = relationship("IoTReading", back_populates="micro_watershed", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="micro_watershed", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="micro_watershed", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mws_id": self.mws_id,
            "display_code": self.display_code,
            "name": self.name,
            "taluk": self.taluk,
            "district": self.district,
            "state": self.state,
            "area_sqkm": self.area_sqkm,
            "stream_length_km": self.stream_length_km,
            "drainage_density": self.drainage_density,
            "max_strahler_order": self.max_strahler_order,
            "slope_mean_deg": self.slope_mean_deg,
            "elevation_mean_m": self.elevation_mean_m,
            "forest_pct": self.forest_pct,
            "agriculture_pct": self.agriculture_pct,
            "water_pct": self.water_pct,
            "builtup_pct": self.builtup_pct,
            "barren_pct": self.barren_pct,
            "current_risk_score": self.current_risk_score,
            "current_risk_category": self.current_risk_category,
            "current_primary_driver": self.current_primary_driver,
            "current_health_index": self.current_health_index,
            "intervention_priority": self.intervention_priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RiskHistory(Base):
    """
    Time-Series Risk Assessments and Monthly Historical Baselines.
    Tracks seasonal variation, drought stress, and flood indices over time.
    """
    __tablename__ = "risk_history"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    mws_id = Column(String(64), ForeignKey("micro_watersheds.mws_id", ondelete="CASCADE"), index=True, nullable=False)

    recorded_at = Column(DateTime(timezone=True), index=True, nullable=False, server_default=func.now())
    year = Column(Integer, nullable=True, doc="Calendar year of assessment")
    month = Column(Integer, nullable=True, doc="Month (1-12) of assessment")

    # Risk Metrics
    base_risk_score = Column(Float, nullable=False, doc="Deterministic base risk before ML adjustment")
    final_risk_score = Column(Float, nullable=False, doc="Final composite risk score (0-100)")
    risk_category = Column(String(32), index=True, nullable=False, doc="CRITICAL, HIGH, MODERATE, or LOW")
    primary_driver = Column(String(64), nullable=True, doc="Water Stress, Ecosystem Risk, or ML Anomaly")

    # Sub-component Risk Factors
    water_stress_score = Column(Float, default=0.0)
    flood_risk_score = Column(Float, default=0.0)
    ecosystem_risk_score = Column(Float, default=0.0)
    ml_anomaly_score = Column(Float, default=0.0)

    source = Column(String(32), default="gpkg_authoritative", doc="gpkg_authoritative, simulation, live_iot, or scheduled_cron")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships & Indexes
    micro_watershed = relationship("MicroWatershed", back_populates="risk_history")

    __table_args__ = (
        Index("ix_risk_history_mws_recorded", "mws_id", "recorded_at"),
        Index("ix_risk_history_year_month", "year", "month"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mws_id": self.mws_id,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "year": self.year,
            "month": self.month,
            "base_risk_score": self.base_risk_score,
            "final_risk_score": self.final_risk_score,
            "risk_category": self.risk_category,
            "primary_driver": self.primary_driver,
            "water_stress_score": self.water_stress_score,
            "flood_risk_score": self.flood_risk_score,
            "ecosystem_risk_score": self.ecosystem_risk_score,
            "ml_anomaly_score": self.ml_anomaly_score,
            "source": self.source,
        }


class IoTReading(Base):
    """
    IoT Telemetry Stream Records.
    Stores physical sensor measurements (rainfall, soil moisture, water level, turbidity, pH, temp)
    and live Isolation Forest inference results.
    """
    __tablename__ = "iot_readings"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    mws_id = Column(String(64), ForeignKey("micro_watersheds.mws_id", ondelete="CASCADE"), index=True, nullable=False)

    reading_time = Column(DateTime(timezone=True), index=True, nullable=False, server_default=func.now())

    # Core Telemetry Parameters
    rainfall_mm = Column(Float, nullable=False, doc="Precipitation reading in mm")
    soil_moisture_pct = Column(Float, nullable=False, doc="Soil volumetric water content percentage")
    water_level_cm = Column(Float, nullable=False, doc="Water level or check-dam gauge distance in cm")
    turbidity_ntu = Column(Float, nullable=False, doc="Turbidity in Nephelometric Turbidity Units")

    # Water Quality & Climate Telemetry
    ph = Column(Float, nullable=True, doc="Runoff stream acidity (pH)")
    water_temperature_c = Column(Float, nullable=True, doc="Water temperature in °C")
    air_temperature_c = Column(Float, nullable=True, doc="Air temperature in °C")
    humidity_pct = Column(Float, nullable=True, doc="Relative humidity percentage")

    # Live ML & Compound Event Inference
    live_ml_anomaly_score = Column(Float, nullable=True, doc="Isolation Forest anomaly score")
    live_risk_score = Column(Float, nullable=True, doc="Dynamic live risk score")
    live_risk_category = Column(String(32), nullable=True, doc="Live risk category (CRITICAL/HIGH/MODERATE/LOW)")
    compound_event_detected = Column(Boolean, default=False, doc="Whether compound flood/runoff event is active")
    compound_event_type = Column(String(64), nullable=True)

    source = Column(String(32), default="simulation", doc="live_hardware, simulation, or api_push")
    raw_payload = Column(JSON, nullable=True, doc="Raw JSON payload received from sensor/bridge")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships & Indexes
    micro_watershed = relationship("MicroWatershed", back_populates="iot_readings")

    __table_args__ = (
        Index("ix_iot_readings_mws_time", "mws_id", "reading_time"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mws_id": self.mws_id,
            "reading_time": self.reading_time.isoformat() if self.reading_time else None,
            "rainfall_mm": self.rainfall_mm,
            "soil_moisture_pct": self.soil_moisture_pct,
            "water_level_cm": self.water_level_cm,
            "turbidity_ntu": self.turbidity_ntu,
            "ph": self.ph,
            "water_temperature_c": self.water_temperature_c,
            "air_temperature_c": self.air_temperature_c,
            "humidity_pct": self.humidity_pct,
            "live_ml_anomaly_score": self.live_ml_anomaly_score,
            "live_risk_score": self.live_risk_score,
            "live_risk_category": self.live_risk_category,
            "compound_event_detected": self.compound_event_detected,
            "compound_event_type": self.compound_event_type,
            "source": self.source,
        }


class Intervention(Base):
    """
    Targeted Field Interventions and Engineering Interventions.
    Maintains decision support actions (Check-dams, farm ponds, contour bunds, afforestation).
    """
    __tablename__ = "interventions"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    mws_id = Column(String(64), ForeignKey("micro_watersheds.mws_id", ondelete="CASCADE"), index=True, nullable=False)

    intervention_type = Column(Text, nullable=False, doc="Engineering action (e.g. Check Dam Desiltation)")
    priority = Column(String(32), index=True, nullable=False, doc="CRITICAL, HIGH, MODERATE, or LOW")
    status = Column(String(32), index=True, default="RECOMMENDED", doc="RECOMMENDED, SANCTIONED, IN_PROGRESS, COMPLETED, or VERIFIED")

    monitoring_focus = Column(String(255), nullable=True, doc="Primary focus (e.g. Infiltration Enhancement, Silt Retention)")
    estimated_cost_inr = Column(Float, nullable=True, doc="Estimated budget requirement in INR")
    target_date = Column(Date, nullable=True, doc="Projected completion timeline")
    implementation_notes = Column(Text, nullable=True, doc="Engineering notes, coordinates, or guidelines")

    source = Column(String(32), default="model2_recommendation", doc="model2_recommendation, field_survey, or manual_entry")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships & Indexes
    micro_watershed = relationship("MicroWatershed", back_populates="interventions")

    __table_args__ = (
        Index("ix_interventions_mws_priority", "mws_id", "priority"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mws_id": self.mws_id,
            "intervention_type": self.intervention_type,
            "priority": self.priority,
            "status": self.status,
            "monitoring_focus": self.monitoring_focus,
            "estimated_cost_inr": self.estimated_cost_inr,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "implementation_notes": self.implementation_notes,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Alert(Base):
    """
    Operational Real-Time Alerts.
    Generated upon critical risk escalation, ML anomalies, sensor threshold breaches, or compound flood events.
    """
    __tablename__ = "alerts"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    mws_id = Column(String(64), ForeignKey("micro_watersheds.mws_id", ondelete="CASCADE"), index=True, nullable=False)

    alert_level = Column(String(32), index=True, nullable=False, doc="CRITICAL, HIGH, WARNING, or INFO")
    alert_type = Column(String(64), nullable=False, doc="COMPOUND_RUNOFF, ML_ANOMALY_SPIKE, WATER_STRESS_CRITICAL, etc.")
    headline = Column(String(255), nullable=False, doc="Brief incident title")
    message = Column(Text, nullable=False, doc="Detailed operational alert advisory and recommended actions")

    is_active = Column(Boolean, index=True, default=True, nullable=False, doc="Active status flag")
    triggered_at = Column(DateTime(timezone=True), index=True, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships & Indexes
    micro_watershed = relationship("MicroWatershed", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_mws_active", "mws_id", "is_active"),
        Index("ix_alerts_level_active", "alert_level", "is_active"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mws_id": self.mws_id,
            "alert_level": self.alert_level,
            "alert_type": self.alert_type,
            "headline": self.headline,
            "message": self.message,
            "is_active": self.is_active,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
