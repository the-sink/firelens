import requests
import json
import sys
import math

from typing import Optional
from fastapi import FastAPI, Request
from pydantic import BaseModel

from bs4 import BeautifulSoup, Tag
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="http")
limiter = Limiter(key_func=get_remote_address)

### Metadata ###

tags = [
    {
        "name": "Incidents",
        "description": "Retrieve information related to SFD incidents using their incident number (i.e. F000000000)."
    },
    {
        "name": "Lists",
        "description": "Endpoints that return useful lists (today's calls, traffic cameras, etc)."
    }
]


app = FastAPI(
    title = "FireLens SFD API",
    description = """
    FireLens exposes user-friendly REST APIs for retrieving data related to Seattle Fire Department incidents.
    
    All endpoints are limited to 10 requests per minute.
    """,
    version = "0.0.4",
    license_info={
        "name": "MIT License",
        "url": "https://www.mit.edu/~amini/LICENSE.md"
    },
    openapi_tags = tags
)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

### Root Variables & Classes ###

rate_limit = "10/minute"

P_mult = 0.017453292519943295

incident_lookup_url = "https://www2.seattle.gov/fire/IncidentSearch/incidentDetail.asp?ID="
location_listing_url = "https://data.seattle.gov/resource/fire-911.json"
camera_list_url = "https://web6.seattle.gov/Travelers/api/Map/Data?zoomId=14&type=2"

camera_list = requests.get(camera_list_url).json()['Features']

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


class Camera(BaseModel): # For now this is just for display purposes on the docs, once I get around to updating the cameras endpoint this will be changed
    Id: str
    Description: str
    ImageUrl: str
    Type: str

### Internal Methods ###

def distance(lat1, lon1, lat2, lon2): # Haversine formula
    hav = 0.5 - math.cos((lat2-lat1)*P_mult)/2 + math.cos(lat1*P_mult)*math.cos(lat2*P_mult) * (1-math.cos((lon2-lon1)*P_mult)) / 2
    return 12742 * math.asin(math.sqrt(hav))


def format_down(input_string: str, header: str):
    return input_string.replace(header, "").strip().replace("\n", "")


def get_incident_details_soup(incident_number: str):
    incident_response = requests.get(incident_lookup_url + incident_number).text
    return BeautifulSoup(incident_response, 'html.parser')

### API Endpoints ###

# Incidents #

@app.get("/incident/{incident_number}", tags=["Incidents"], response_model=Incident)
@limiter.limit(rate_limit)
def get_incident_details(request: Request, incident_number: str):
    soup = get_incident_details_soup(incident_number)
    details = soup.find_all('table')[2].find_all('tr')
    incident: Incident = Incident()
    incident.incident_number = format_down(details[0].get_text(), "Incident Number:")
    incident.date = format_down(details[1].get_text(), "Incident Date:")
    incident.time = format_down(details[2].get_text(), "Time:")
    incident.address = format_down(details[3].get_text(), "Address:")
    incident.incident_type = format_down(details[4].get_text(), "Type:")
    incident.alarm_level = format_down(details[5].get_text(), "Alarm Level:")

    return incident


@app.get("/incident/{incident_number}/units", tags=["Incidents"], response_model=list[Unit])
@limiter.limit(rate_limit)
def get_incident_units(request: Request, incident_number: str):
    soup = get_incident_details_soup(incident_number)
    unit_list = soup.find_all('table')[3]
    unit_list.select_one('tr').decompose()
    units: Unit = []
    for unit in unit_list:
        if isinstance(unit, Tag):
            object = Unit()

            list_items = unit.find_all('p')
            object.name = list_items[0].get_text().strip()
            object.primary = object.name.find("*") != -1
            object.dispatched = list_items[1].get_text().strip() or None
            object.arrived = list_items[2].get_text().strip() or None
            object.in_service = list_items[3].get_text().strip() or None

            if object.primary:
                units.insert(0, object)
            else:
                units.append(object)
    return units


@app.get("/incident/{incident_number}/location", tags=["Incidents"], response_model=Location, description="This endpoint pulls from [data.seattle.gov](data.seattle.gov) if the incident is recent, otherwise it will fall back to geocoding the address using Geopy/Nominatim. Check the \"source\" element to check which one was used.")
@limiter.limit(rate_limit)
def get_incident_coordinates(request: Request, incident_number: str):
    list_response = requests.get(location_listing_url)
    data = json.loads(list_response.text) # Cannot use list_response.json() for some reason?
    location = Location()
    for entry in data:
        if entry['incident_number'] == incident_number: # Use coordinates provided officially by API
            location.latitude = float(entry['latitude'])
            location.longitude = float(entry['longitude'])
            location.source = "data.seattle.gov"
            break
    if location.latitude == None: # Fall back to geocoding the address
        details = get_incident_details(request, incident_number)
        location_data = geolocator.geocode(details.address + " Seattle, WA")
        location.latitude = location_data.latitude
        location.longitude = location_data.longitude
        location.source = "Nominatim (fallback)"
    return location


@app.get("/incident/{incident_number}/cameras", tags=["Incidents"], response_model=list[Camera], description="Attempts to locate nearby traffic cameras that could be around the incident. There are not cameras at every street corner - this endpoint is often not successful, but will always return the geographically closest cameras regardless.")
@limiter.limit(rate_limit)
def get_nearby_cameras(request: Request, incident_number: str):
    closest = sys.maxsize
    closest_object = None

    coords = get_incident_coordinates(request, incident_number)

    for object in camera_list:
        coordinate = object['PointCoordinate']
        dist = distance(coords.latitude, coords.longitude, coordinate[0], coordinate[1])
        if (dist < closest):
            closest = dist
            closest_object = object['Cameras']
    return closest_object

# Lists #

@app.get("/incidents", tags=["Lists"])
@limiter.limit(rate_limit)
def get_incidents(request: Request):
    return []

@app.get("/cameras", tags=["Lists"])
@limiter.limit(rate_limit)
def get_all_traffic_cameras(request: Request):
    return []