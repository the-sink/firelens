import requests
import json
import sys
import math

from starlette.responses import FileResponse
import config
import classes
import requests_cache

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime, timedelta

from bs4 import BeautifulSoup, Tag
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from geopy.geocoders import Nominatim

import uvicorn

geolocator = Nominatim(user_agent="http")
limiter = Limiter(key_func=get_remote_address)
cache = requests_cache.CachedSession(
    'requests',
    expire_after=timedelta(seconds=30)
)

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
    version = config.version,
    license_info={
        "name": "MIT License",
        "url": "https://www.mit.edu/~amini/LICENSE.md"
    },
    openapi_tags = tags
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

requests_cache.install_cache('requests')

### Root Variables ###

P_mult = 0.017453292519943295

incident_lookup_url = "https://www2.seattle.gov/fire/IncidentSearch/incidentDetail.asp?ID="
location_listing_url = "https://data.seattle.gov/resource/fire-911.json"
camera_list_url = "https://web6.seattle.gov/Travelers/api/Map/Data?zoomId=14&type=2"

camera_list = requests.get(camera_list_url).json()['Features']

### Internal Methods ###

def distance(lat1, lon1, lat2, lon2): # Haversine formula
    hav = 0.5 - math.cos((lat2-lat1)*P_mult)/2 + math.cos(lat1*P_mult)*math.cos(lat2*P_mult) * (1-math.cos((lon2-lon1)*P_mult)) / 2
    return 12742 * math.asin(math.sqrt(hav))

def convert_time(time_string):
    if time_string == None:
        return None
    return datetime.strptime(time_string, "%H:%M").strftime("%I:%M %p")

def format_down(input_string: str, header: str):
    return input_string.replace(header, "").strip().replace("\n", "")

def get_incident_details_soup(incident_number: str):
    incident_response = requests.get(incident_lookup_url + incident_number).text
    return BeautifulSoup(incident_response, 'html.parser')

### API Endpoints ###

# Incidents #

@app.get("/incident/{incident_number}", tags=["Incidents"], response_model=classes.Incident)
@limiter.limit(config.rate_limit)
def get_incident_details(request: Request, incident_number: str, use_12_hour_time: Optional[bool] = False):
    soup = get_incident_details_soup(incident_number)
    details = soup.find_all('table')[2].find_all('tr')
    incident: classes.Incident = classes.Incident()
    incident.incident_number = format_down(details[0].get_text(), "Incident Number:")
    incident.date = format_down(details[1].get_text(), "Incident Date:")
    incident.time = format_down(details[2].get_text(), "Time:")
    incident.address = format_down(details[3].get_text(), "Address:")
    incident.incident_type = format_down(details[4].get_text(), "Type:")
    incident.alarm_level = format_down(details[5].get_text(), "Alarm Level:")

    if use_12_hour_time:
        incident.time = convert_time(incident.time)

    return incident


@app.get("/incident/{incident_number}/units", tags=["Incidents"], response_model=list[classes.Unit])
@limiter.limit(config.rate_limit)
def get_incident_units(request: Request, incident_number: str, use_12_hour_time: Optional[bool] = False):
    soup = get_incident_details_soup(incident_number)
    unit_list = soup.find_all('table')[3]
    unit_list.select_one('tr').decompose()
    units: classes.Unit = []
    for unit in unit_list:
        if isinstance(unit, Tag):
            object = classes.Unit()

            list_items = unit.find_all('p')
            object.name = list_items[0].get_text().strip()
            object.primary = object.name.find("*") != -1
            object.dispatched = list_items[1].get_text().strip() or None
            object.arrived = list_items[2].get_text().strip() or None
            object.in_service = list_items[3].get_text().strip() or None

            if use_12_hour_time:
                object.dispatched = convert_time(object.dispatched)
                object.arrived = convert_time(object.arrived)
                object.in_service = convert_time(object.in_service)

            if object.primary:
                units.insert(0, object)
                object.name = object.name.replace("*", "")
            else:
                units.append(object)
    return units


@app.get("/incident/{incident_number}/location", tags=["Incidents"], response_model=classes.Location, description="This endpoint pulls from [data.seattle.gov](data.seattle.gov) if the incident is recent, otherwise it will fall back to geocoding the address using Geopy/Nominatim. Check the \"source\" element to check which one was used.")
@limiter.limit(config.rate_limit)
def get_incident_coordinates(request: Request, incident_number: str):
    list_response = requests.get(location_listing_url)
    data = json.loads(list_response.text) # Cannot use list_response.json() for some reason?
    location = classes.Location()
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


@app.get("/incident/{incident_number}/cameras", tags=["Incidents"], description="Attempts to locate nearby traffic cameras that could be around the incident. There are not cameras at every street corner - this endpoint is often not successful. The distance_threshold parameter determines how likely the endpoint is to return an error if a camera is too far. Set this to something high to ignore distance checks and display the nearest camera anyways.")
@limiter.limit(config.rate_limit)
def get_nearby_cameras(request: Request, incident_number: str, distance_threshold: Optional[float] = 0.4):
    closest = sys.maxsize
    closest_object = None

    coords = get_incident_coordinates(request, incident_number)

    for object in camera_list:
        coordinate = object['PointCoordinate']
        dist = distance(coords.latitude, coords.longitude, coordinate[0], coordinate[1])
        if (dist < closest):
            closest = dist
            closest_object = object['Cameras']
    if closest < distance_threshold and closest_object != None:
        return closest_object
    else:
        return {
            'error': 'No cameras are near the location of this incident.'
        }

# Lists #
# TODO: Incident list needs to handle duplicates (possibly a bug?) and clone entries in the log that are adding new units

@app.get("/incidents", tags=["Lists"], response_model=list[classes.Incident], description = "Returns a list of all incidents for today's date, or for the specified date given in the endpoint's parameters.")
@limiter.limit(config.rate_limit)
def get_incidents_for_date(request: Request, month: Optional[int] = None, day: Optional[int] = None, year: Optional[int] = None):
    today = datetime.now()
    month = month or today.month
    day = day or today.day
    year = year or today.year

    page = requests.get(f"http://www2.seattle.gov/fire/realtime911/getRecsForDatePub.asp?incDate={month}%2F{day}%2F{year}&rad1=des").text

    calls: classes.Incident = []
    soup = BeautifulSoup(page, 'html.parser')

    try:
        list = soup.find_all('table')[2]
    except IndexError:
        return calls

    for call in list.find_all('tr'):
        incident_object = classes.Incident()

        incident_object.active = False

        items = call.find_all('td', 'closed')

        if len(items) < 1:
            items = call.find_all('td', 'active')
            incident_object.active = True

        # dt = items[0].get_text()
        incident_object.incident_number = items[1].get_text()
        incident_object.alarm_level = items[2].get_text()
        # units = items[3].get_text()
        incident_object.address = items[4].get_text()
        incident_object.incident_type = items[5].get_text()

        calls.append(incident_object)

    return calls



@app.get("/incidents/active", tags=["Lists"], response_model=list[classes.Incident], description = "Returns a list of currently active incidents.")
@limiter.limit(config.rate_limit)
def get_active_incidents(request: Request):
    yesterday = datetime.now() - timedelta(days=1)

    today_calls = [call for call in get_incidents_for_date(request) if call.active]
    yesterday_calls = [call for call in get_incidents_for_date(request, yesterday.month, yesterday.day, yesterday.year) if call.active] # also check yesterday - there's still a likely chance of active calls, especially if it's very early in the morning

    return today_calls + yesterday_calls


@app.get("/cameras", tags=["Lists"], response_model=list[classes.Camera], description = "Returns a list of all traffic cameras in the region as Camera objects.")
@limiter.limit(config.rate_limit)
def get_all_traffic_cameras(request: Request):
    return []

# Non-API Endpoints #

@app.get('/favicon.ico')
def favicon():
    return FileResponse('assets/favicon.ico')

### Start Server ###

if __name__ == "__main__":
    uvicorn.run("api:app", host=config.host_address, port=config.server_port, log_level=config.log_level, reload=config.live_reload)