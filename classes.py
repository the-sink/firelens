from typing import Optional
from pydantic import BaseModel

class Location(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = None


class Incident(BaseModel):
    incident_number: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    address: Optional[str] = None
    incident_type: Optional[str] = None
    alarm_level: Optional[str] = None


class Unit(BaseModel):
    name: Optional[str] = None
    primary: Optional[bool] = None
    dispatched: Optional[str] = None
    arrived: Optional[str] = None
    in_service: Optional[str] = None