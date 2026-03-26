import json
from typing import Any
import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from dotenv import load_dotenv
import os
import re
from datetime import datetime 
from auth import EshipzOAuthProvider
from datetime import datetime, timezone, timedelta
# Load environment variables
load_dotenv()

MCP_SERVER_BASE_URL = os.getenv("MCP_SERVER_BASE_URL", "http://localhost:10000")
oauth_provider = EshipzOAuthProvider()

# Initialize FastMCP server with OAuth support
mcp = FastMCP(
    "eshipz-mcp",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "10000")),
    auth_server_provider=oauth_provider,
    auth=AuthSettings(
        issuer_url=MCP_SERVER_BASE_URL,
        resource_server_url=MCP_SERVER_BASE_URL,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["eshipz"],
            default_scopes=["eshipz"],
        ),
    ),
)

# Constants
API_BASE_URL = os.getenv("API_BASE_URL")
ESHIPZ_API_TRACKING_URL = os.getenv("ESHIPZ_API_TRACKING_URL")
ESHIPZ_TOKEN = os.getenv("ESHIPZ_TOKEN")
ESHIPZ_CARRIER_PERFORMANCE_URL = os.getenv("ESHIPZ_CARRIER_PERFORMANCE_URL")
ESHIPZ_API_CREATE_SHIPMENT_URL = os.getenv("ESHIPZ_API_CREATE_SHIPMENT_URL")
ESHIPZ_API_DOCKET_ALLOCATION_URL =os.getenv("ESHIPZ_API_DOCKET_ALLOCATION_URL")
ESHIPZ_API_ORDERS_URL = os.getenv("ESHIPZ_API_ORDERS_URL")
ESHIPZ_API_GET_SHIPMENTS_URL = os.getenv("ESHIPZ_API_GET_SHIPMENTS_URL") # e.g., "https://xxxxxxxxxxxxxxx/xxx/xxx/xxxxxxxxxx"


def _resolve_eshipz_token(ctx: Context | None = None) -> str:
    if os.getenv("USE_BEARER_AS_ESHIPZ_TOKEN", "false").lower() != "true":
        return ESHIPZ_TOKEN

    if ctx is not None:
        try:
            request = ctx.request_context.request
            if request is not None and hasattr(request, "headers"):
                auth_header = request.headers.get("authorization", "")
                if auth_header.lower().startswith("bearer "):
                    bearer_token = auth_header.split(" ", 1)[1].strip()
                    if bearer_token:
                        return bearer_token
        except Exception:
            pass

    return ESHIPZ_TOKEN

# Map common natural language descriptions to exact eShipz API slugs
CARRIER_SLUG_MAP = {
    "bluedart": "bluedart",
    "blue dart": "bluedart",
    "delhivery": "delhivery",
    "delhivery surface": "delhivery-surface",
    "dtdc": "dtdc",
    "ekart": "ekart",
    "xpressbees": "xpressbees",
    "amazon": "amazon-shipping"
}

def _get_slug_from_description(description: str) -> str:
    """Extracts the exact API slug from a natural language carrier description."""
    if not description:
        return "auto"  # Fallback to rule-based routing if no description is provided

    desc_lower = description.lower().strip()

    # Direct lookup
    if desc_lower in CARRIER_SLUG_MAP:
        return CARRIER_SLUG_MAP[desc_lower]

    # Partial match (e.g., if user says "ship via BlueDart express")
    for key, slug in CARRIER_SLUG_MAP.items():
        if key in desc_lower:
            return slug

    return "auto"  # Fallback if no match is found


# CITY_STATE_MAP = {
#     # Metro cities
#     "chennai": "tamil nadu", "mumbai": "maharashtra", "bengaluru": "karnataka",
#     "bangalore": "karnataka", "delhi": "delhi", "new delhi": "delhi",
#     "kolkata": "west bengal", "hyderabad": "telangana", "pune": "maharashtra",
#     "ahmedabad": "gujarat", "surat": "gujarat", "jaipur": "rajasthan",
#     "lucknow": "uttar pradesh", "kanpur": "uttar pradesh", "nagpur": "maharashtra",
#     "indore": "madhya pradesh", "thane": "maharashra", "bhopal": "madhya pradesh",
#     "visakhapatnam": "andhra pradesh", "pimpri-chinchwad": "maharashtra",
#     "patna": "bihar", "vadodara": "gujarat", "ghaziabad": "uttar pradesh",
#     "ludhiana": "punjab", "agra": "uttar pradesh", "nashik": "maharashtra",
#     "faridabad": "haryana", "meerut": "uttar pradesh", "rajkot": "gujarat",
#     "kalyan-dombivali": "maharashtra", "vasai-virar": "maharashtra",
#     "varanasi": "uttar pradesh", "srinagar": "jammu and kashmir",
#     "aurangabad": "maharashtra", "dhanbad": "jharkhand", "amritsar": "punjab",
#     "navi mumbai": "maharashtra", "allahabad": "uttar pradesh",
#     "prayagraj": "uttar pradesh", "howrah": "west bengal", "ranchi": "jharkhand",
#     "gwalior": "madhya pradesh", "jabalpur": "madhya pradesh",
#     "coimbatore": "tamil nadu", "vijayawada": "andhra pradesh", "jodhpur": "rajasthan",
#     "madurai": "tamil nadu", "raipur": "chhattisgarh", "kota": "rajasthan",
#     "chandigarh": "chandigarh", "guwahati": "assam", "solapur": "maharashtra",
#     "hubballi-dharwad": "karnataka", "bareilly": "uttar pradesh", "moradabad": "uttar pradesh",
#     "mysore": "karnataka", "mysuru": "karnataka", "gurgaon": "haryana",
#     "gurugram": "haryana", "aligarh": "uttar pradesh", "jalandhar": "punjab",
#     "tiruchirappalli": "tamil nadu", "bhubaneswar": "odisha", "salem": "tamil nadu",
#     "warangal": "telangana", "guntur": "andhra pradesh", "bhiwandi": "maharashtra",
#     "saharanpur": "uttar pradesh", "gorakhpur": "uttar pradesh", "bikaner": "rajasthan",
#     "amravati": "maharashtra", "noida": "uttar pradesh", "jamshedpur": "jharkhand",
#     "bhilai": "chhattisgarh", "cuttack": "odisha", "firozabad": "uttar pradesh",
#     "kochi": "kerala", "cochin": "kerala", "nellore": "andhra pradesh",
#     "bhavnagar": "gujarat", "dehradun": "uttarakhand", "durgapur": "west bengal",
#     "asansol": "west bengal", "rourkela": "odisha", "nanded": "maharashtra",
#     "kolhapur": "maharashtra", "ajmer": "rajasthan", "akola": "maharashtra",
#     "gulbarga": "karnataka", "jamnagar": "gujarat", "ujjain": "madhya pradesh",
#     "loni": "uttar pradesh", "siliguri": "west bengal", "jhansi": "uttar pradesh",
#     "ulhasnagar": "maharashtra", "jammu": "jammu and kashmir", "sangli-miraj": "maharashtra",
#     "mangalore": "karnataka", "erode": "tamil nadu", "belgaum": "karnataka",
#     "belagavi": "karnataka", "ambattur": "tamil nadu", "tirunelveli": "tamil nadu",
#     "malegaon": "maharashtra", "gaya": "bihar", "jalgaon": "maharashtra",
#     "udaipur": "rajasthan", "maheshtala": "west bengal", "tiruppur": "tamil nadu",
#     "davanagere": "karnataka", "kozhikode": "kerala", "calicut": "kerala",
#     "akola": "maharashtra", "kurnool": "andhra pradesh", "rajpur sonarpur": "west bengal",
#     "rajahmundry": "andhra pradesh", "bokaro": "jharkhand", "south dumdum": "west bengal",
#     "bellary": "karnataka", "patiala": "punjab", "gopalpur": "west bengal",
#     "agartala": "tripura", "bhagalpur": "bihar", "muzaffarnagar": "uttar pradesh",
#     "bhatpara": "west bengal", "panihati": "west bengal", "latur": "maharashtra",
#     "dhule": "maharashtra", "rohtak": "haryana", "korba": "chhattisgarh",
#     "bhilwara": "rajasthan", "brahmapur": "odisha", "berhampur": "odisha",
#     "muzaffarpur": "bihar", "ahmednagar": "maharashtra", "mathura": "uttar pradesh",
#     "kollam": "kerala", "avadi": "tamil nadu", "kadapa": "andhra pradesh",
#     "kamarhati": "west bengal", "sambalpur": "odisha", "bilaspur": "chhattisgarh",
#     "shahjahanpur": "uttar pradesh", "satara": "maharashtra", "bijapur": "karnataka",
#     "rampur": "uttar pradesh", "shivamogga": "karnataka", "shimoga": "karnataka",
#     "chandrapur": "maharashtra", "junagadh": "gujarat", "thrissur": "kerala",
#     "alwar": "rajasthan", "bardhaman": "west bengal", "kulti": "west bengal",
#     "kakinada": "andhra pradesh", "nizamabad": "telangana", "parbhani": "maharashtra",
#     "tumkur": "karnataka", "khammam": "telangana", "ozhukarai": "puducherry",
#     "bihar sharif": "bihar", "panipat": "haryana", "darbhanga": "bihar",
#     "bally": "west bengal", "aizawl": "mizoram", "dewas": "madhya pradesh",
#     "ichalkaranji": "maharashtra", "karnal": "haryana", "bathinda": "punjab",
#     "jalna": "maharashtra", "eluru": "andhra pradesh", "kirari suleman nagar": "delhi",
#     "barasat": "west bengal", "purnia": "bihar", "satna": "madhya pradesh",
#     "mira-bhayandar": "maharashtra", "karimnagar": "telangana", "etawah": "uttar pradesh",
#     "bharatpur": "rajasthan", "begusarai": "bihar", "new delhi": "delhi",
#     "chhapra": "bihar", "kadapa": "andhra pradesh", "ramagundam": "telangana",
#     "pali": "rajasthan", "satna": "madhya pradesh", "vizianagaram": "andhra pradesh",
#     "katihar": "bihar", "hardwar": "uttarakhand", "haridwar": "uttarakhand",
#     "sonipat": "haryana", "nagercoil": "tamil nadu", "thanjavur": "tamil nadu",
#     "murwara": "madhya pradesh", "naihati": "west bengal", "sambhal": "uttar pradesh",
#     "nadiad": "gujarat", "yamunanagar": "haryana", "english bazar": "west bengal",
#     "unnao": "uttar pradesh", "secunderabad": "telangana", "margao": "goa",
#     "vasco da gama": "goa", "porbandar": "gujarat", "anand": "gujarat",
#     "ratlam": "madhya pradesh", "morbi": "gujarat", "pondicherry": "puducherry",
#     "puducherry": "puducherry", "gandhidham": "gujarat", "veraval": "gujarat",
#     "madras": "tamil nadu", "bombay": "maharashtra", "calcutta": "west bengal",
# }

# # City aliases for normalization
# CITY_ALIASES = {
#     "bangalore": "bengaluru", "bombay": "mumbai", "calcutta": "kolkata",
#     "madras": "chennai", "mysore": "mysuru", "cochin": "kochi",
#     "calicut": "kozhikode", "trivandrum": "thiruvananthapuram",
#     "poona": "pune", "baroda": "vadodara", "allahabad": "prayagraj",
# }

# # Parcel validation constants
# MAX_WEIGHT_KG = 300
# MAX_DIM_CM = 300
# VOLUMETRIC_DIVISOR = 5000  # standard for most Indian carriers

# # Address type keywords
# RESIDENTIAL_KEYWORDS = {"home", "house", "flat", "apartment", "villa", "lane", "society"}
# BUSINESS_KEYWORDS = {"pvt", "ltd", "llp", "inc", "corp", "technologies", "enterprises"}

# def infer_state_from_city(city: str) -> str | None:
#     """Try to infer state name from a given city using aliases and CITY_STATE_MAP.

#     Returns normalized state string (as in CITY_STATE_MAP values) or None when
#     inference is not possible.
#     """
#     if not city:
#         return None

#     # Normalize city name
#     norm = city.strip().lower()
#     # remove common punctuation
#     for ch in [",", "."]:
#         norm = norm.replace(ch, "")
#     norm = " ".join(norm.split())

#     # map aliases
#     if norm in CITY_ALIASES:
#         norm = CITY_ALIASES[norm]

#     # direct lookup
#     state = CITY_STATE_MAP.get(norm)
#     if state:
#         return state

#     # try simple heuristics: remove spaces/dashes
#     alt = norm.replace(" ", "-")
#     state = CITY_STATE_MAP.get(alt)
#     if state:
#         return state

#     alt2 = norm.replace("-", " ")
#     state = CITY_STATE_MAP.get(alt2)
#     if state:
#         return state

#     return None

# def normalize_phone(phone: str) -> str | None:
#     """Normalize Indian phone numbers to 10 digits."""
#     if not phone:
#         return None
#     digits = re.sub(r"\D", "", phone)
#     if digits.startswith("91") and len(digits) == 12:
#         digits = digits[2:]
#     if len(digits) != 10 or not digits[0] in "6789":
#         return None  # Invalid Indian mobile number
#     return digits


# def validate_pincode(pincode: str) -> bool:
#     """Validate Indian 6-digit pincode."""
#     return bool(pincode and re.fullmatch(r"[1-9][0-9]{5}", pincode))


# def validate_parcel_dimensions(weight: float, length: float, width: float, height: float) -> str | None:
    
#     if weight <= 0:
#         return "Parcel weight must be greater than 0."
#     if weight > MAX_WEIGHT_KG:
#         return f"Parcel weight {weight}kg exceeds max allowed ({MAX_WEIGHT_KG}kg)."
#     for name, val in [("length", length), ("width", width), ("height", height)]:
#         if val < 0:
#             return f"{name.capitalize()} cannot be negative."
#         if val > MAX_DIM_CM:
#             return f"{name.capitalize()} {val}cm exceeds max allowed ({MAX_DIM_CM}cm)."
#     return None


# def compute_chargeable_weight(actual_kg: float, l: float, w: float, h: float) -> float:
#     """Returns the higher of actual vs volumetric weight."""
#     volumetric_kg = (l * w * h) / VOLUMETRIC_DIVISOR
#     return round(max(actual_kg, volumetric_kg), 2)


# def infer_service_type(weight_kg: float, carrier_slug: str) -> str:
#     """Rule-based service type selection."""
#     """ this is experimental and should be verified for other carriers as well or removed"""
#     if carrier_slug == "delhivery":
#         return "delhivery-surface" if weight_kg > 10 else "delhivery"
#     if weight_kg > 30:
#         return "surface"
#     return "express"


# def infer_address_type(company: str, street: str) -> str:
#     """Infer address type from company and street info."""
#     text = (company + " " + street).lower()
#     if any(k in text for k in BUSINESS_KEYWORDS):
#         return "business"
#     if any(k in text for k in RESIDENTIAL_KEYWORDS):
#         return "residential"
#     return "business" if company else "residential"


# def normalize_date(date_str: str) -> str | None:
#     """Try to normalize date to YYYY-MM-DD."""
#     for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y"):
#         try:
#             return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
#         except ValueError:
#             continue
#     return None

async def get_tracking_details(tracking_number: str, api_token: str | None = None) -> dict[str, Any] | None:
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    payload = json.dumps({"track_id": tracking_number})
    async with httpx.AsyncClient() as client:
        try:
            # Note: Verify if your API expects data=payload or json=payload
            # Standard libraries often prefer json=... to handle serialization automatically
            response = await client.post(ESHIPZ_API_TRACKING_URL, headers=headers, timeout=30.0, data=payload)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

# the api call is made here after the carrier performance mcp tool invokes the make_carrier_performance_request function 
async def make_carrier_performance_request(source_pin: str, destination_pin: str, api_token: str | None = None) -> dict[str, Any] | None:
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    payload = json.dumps({
        "sender_postal_code": int(source_pin),
        "tracking_postal_code": int(destination_pin)
    })
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                ESHIPZ_CARRIER_PERFORMANCE_URL,
                headers=headers,
                timeout=30.0,
                data=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error in carrier performance request: {str(e)}")
            return None

async def make_create_shipment_request(shipment_data: dict, api_token: str | None = None) -> dict[str, Any] | None:
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                ESHIPZ_API_CREATE_SHIPMENT_URL,
                headers=headers,
                json=shipment_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # This captures 4xx and 5xx errors specifically
            error_details = e.response.text
            print(f"API Error ({e.response.status_code}): {error_details}")
            return {"error": error_details, "status_code": e.response.status_code}
        except httpx.RequestError as e:
            # This captures network issues (DNS, Timeout, etc.)
            print(f"Network/Connection Error: {str(e)}")
            return {"error": str(e), "type": "network_error"}
        except Exception as e:
            # This catches anything else (like JSON parsing errors)
            print(f"Unexpected Error: {str(e)}")
            return {"error": str(e), "type": "unexpected_error"}


async def make_docket_allocation_request(allocation_data: dict, api_token: str | None = None) -> dict[str, Any] | None:
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                ESHIPZ_API_DOCKET_ALLOCATION_URL,
                headers=headers,
                json=allocation_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error in docket allocation request: {str(e)}")
            return None


async def fetch_order_by_id(order_id: str, api_token: str | None = None) -> dict[str, Any] | None:
    """Fetch a single order by order ID from the eShipz Orders API"""
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    url = f"{ESHIPZ_API_ORDERS_URL}/{order_id}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching order {order_id}: {str(e)}")
            return None



def _format_carrier(slug: str) -> str:
    """Format carrier name for display"""
    return slug.upper() if slug else "Unknown Carrier"


def _create_summary(shipment: dict) -> str:
    """Create human-readable summary based on shipment status"""
    
    tracking_num = shipment.get("tracking_number", "Unknown")
    carrier = _format_carrier(shipment.get("slug"))
    status = shipment.get("tag")
    checkpoints = shipment.get("checkpoints", [])
    latest = checkpoints[0] if checkpoints else {}
    
    location = latest.get("city", "")
    remark = latest.get("remark", "")
    delivery_date = shipment.get("delivery_date")
    eta = shipment.get("expected_delivery_date")
    
    # Status-specific formatting
    if status == "Delivered":
        summary = f" Delivered via {carrier}"
        if delivery_date:
            summary += f" on {delivery_date}"
        if location:
            summary += f" at {location}"
        return summary
    
    elif status == "OutForDelivery":
        summary = f" Out for delivery via {carrier}"
        if location:
            summary += f" from {location}"
        return summary
    
    elif status == "InTransit":
        summary = f"In transit via {carrier}"
        if location:
            summary += f", currently in {location}"
        if remark:
            summary += f" - {remark}"
        if eta:
            summary += f"\n   Expected delivery: {eta}"
        return summary
    
    elif status == "Exception":
        summary = f"Exception via {carrier}"
        if location:
            summary += f" at {location}"
        if remark:
            summary += f" - {remark}"
        return summary
    
    elif status == "PickedUp":
        summary = f"Picked up via {carrier}"
        if location:
            summary += f" from {location}"
        return summary
    
    elif status == "InfoReceived":
        return f"Shipment information received by {carrier}"
    
    else:
        summary = f"{status} via {carrier}" if status else f"Tracking {tracking_num} via {carrier}"
        if location and remark:
            summary += f" - {remark} ({location})"
        elif remark:
            summary += f" - {remark}"
        return summary


def _format_carrier_performance(data: dict) -> str:
    """Format carrier performance data into human-readable summary"""
    
    # Extract data from API response structure
    detail = data.get("detail", {})
    status = detail.get("status", "")
    
    if status != "SUCCESS":
        return f"API returned non-success status: {status}"
    
    route_data_list = detail.get("data", [])
    
    if not route_data_list:
        return "No carrier performance data available"
    
    # Get first route data (typically there's only one)
    route_data = route_data_list[0]
    
    source_pin = int(route_data.get("sourcepin", 0))
    dest_pin = int(route_data.get("trackingpin", 0))
    
    carrier_slugs = route_data.get("slug_cps_ordered", [])
    delivery_scores = route_data.get("delivery_scores", [])
    pickup_scores = route_data.get("pickup_scores", [])
    rto_scores = route_data.get("rto_scores", [])
    overall_scores = route_data.get("overall_scores", [])
    
    if not carrier_slugs:
        return f"No carriers found for route {source_pin} to {dest_pin}"
    
    # Build summary header
    summary = f"CARRIER PERFORMANCE ANALYSIS\n"
    summary += f"Route: {source_pin} to {dest_pin}\n"
    summary += f"Carriers analyzed: {len(carrier_slugs)}\n"
    summary += f"{'-' * 60}\n\n"
    
    # Create carrier data with scores
    carriers_with_scores = []
    for i, slug in enumerate(carrier_slugs):
        carrier_data = {
            "slug": slug,
            "overall_score": overall_scores[i] if i < len(overall_scores) else None,
            "delivery_score": delivery_scores[i] if i < len(delivery_scores) else None,
            "pickup_score": pickup_scores[i] if i < len(pickup_scores) else None,
            "rto_score": rto_scores[i] if i < len(rto_scores) else None
        }
        carriers_with_scores.append(carrier_data)
    
    # Sort by overall score (descending)
    carriers_with_scores.sort(key=lambda x: x.get("overall_score", 0), reverse=True)
    
    for idx, carrier in enumerate(carriers_with_scores, 1):
        carrier_name = _format_carrier(carrier["slug"])
        overall = carrier.get("overall_score")
        
        summary += f"{idx}. {carrier_name}"
        
        if overall is not None:
            # Convert 0-5 scale to 0-100 for display
            score_100 = overall * 20
            if score_100 >= 80:
                rating = "Excellent"
            elif score_100 >= 60:
                rating = "Good"
            elif score_100 >= 40:
                rating = "Fair"
            else:
                rating = "Below Average"
            summary += f"\n   Overall Score: {overall:.1f}/5.0 ({score_100:.0f}/100 - {rating})"
        
        # Add detailed scores
        metrics = []
        if carrier.get("delivery_score") is not None:
            metrics.append(f"Delivery Score: {carrier['delivery_score']:.1f}/5.0")
        if carrier.get("pickup_score") is not None:
            metrics.append(f"Pickup Score: {carrier['pickup_score']:.1f}/5.0")
        if carrier.get("rto_score") is not None:
            metrics.append(f"RTO Score: {carrier['rto_score']:.1f}/5.0")
        
        if metrics:
            for metric in metrics:
                summary += f"\n   {metric}"
        
        summary += "\n\n"
    
    # Add recommendation if top carrier is clear winner
    if len(carriers_with_scores) > 1:
        top_carrier = carriers_with_scores[0]
        second_carrier = carriers_with_scores[1]
        
        top_score = top_carrier.get("overall_score", 0)
        second_score = second_carrier.get("overall_score", 0)
        
        if top_score and second_score and (top_score - second_score) >= 0.5:
            summary += f"{'-' * 60}\n"
            summary += f"RECOMMENDATION: {_format_carrier(top_carrier['slug'])}\n"
            summary += f"Reason: Highest overall performance score on this route"
    
    return summary

def _format_shipment_creation_response(data: dict) -> str:
    """Format shipment creation response into human-readable summary"""
    
    if not data:
        return "Failed to create shipment - No response from API"
    
    # Check for error responses
    if data.get("error"):
        error_msg = data.get("error")
        status_code = data.get("status_code", "")
        error_type = data.get("type", "")
        if status_code:
            return f"Shipment creation failed: {error_msg} (Status: {status_code})"
        elif error_type:
            return f"Shipment creation failed: {error_msg} ({error_type})"
        return f"Shipment creation failed: {error_msg}"
    
    # Check meta for errors
    meta = data.get("meta", {})
    if meta.get("code") != 200:
        error_msg = meta.get("message") or "Unknown error"
        details = meta.get("details", [])
        if details:
            error_msg += f": {', '.join(details)}"
        return f"Shipment creation failed: {error_msg}"
    
    # Extract shipment data
    shipment_data = data.get("data", {})
    
    if not shipment_data:
        return "No shipment data in response"
    
    summary = "SHIPMENT CREATED SUCCESSFULLY\n"
    summary += f"{'-' * 60}\n"
    
    # Order and tracking info
    order_id = shipment_data.get("order_id")
    tracking_numbers = shipment_data.get("tracking_numbers", [])
    carrier = shipment_data.get("slug")
    status = shipment_data.get("status")
    customer_ref = shipment_data.get("customer_reference")
    
    if order_id:
        summary += f"Order ID: {order_id}\n"
    
    if tracking_numbers:
        if len(tracking_numbers) == 1:
            summary += f"Tracking Number: {tracking_numbers[0]}\n"
        else:
            summary += f"Tracking Numbers ({len(tracking_numbers)} boxes):\n"
            for idx, tn in enumerate(tracking_numbers, 1):
                summary += f"   Box {idx}: {tn}\n"
    
    if carrier:
        summary += f"Carrier: {_format_carrier(carrier)}\n"
    
    if status:
        summary += f"Status: {status.upper()}\n"
    
    if customer_ref:
        summary += f"Reference: {customer_ref}\n"
    
    # Rate and weight info
    rate = shipment_data.get("rate", {})
    charge_weight = rate.get("charge_weight", {})
    if charge_weight.get("value"):
        summary += f"Chargeable Weight: {charge_weight['value']} {charge_weight.get('unit', 'kg')}\n"
    
    total_charge = rate.get("total_charge", {})
    if total_charge.get("amount"):
        summary += f"Total Charge: {total_charge.get('currency', 'INR')} {total_charge['amount']}\n"
    
    # Delivery and transit info
    if rate.get("delivery_date"):
        summary += f"Expected Delivery: {rate['delivery_date']}\n"
    
    if rate.get("transit_time"):
        summary += f"Transit Time: {rate['transit_time']}\n"
    
    # Label download link
    files = shipment_data.get("files", {})
    label = files.get("label", {})
    label_url = label.get("label_meta", {}).get("url")
    if label_url:
        summary += f"\nShipping Label: {label_url}\n"
    
    # Tracking link
    tracking_link = shipment_data.get("tracking_link")
    if tracking_link:
        summary += f"Track Online: {tracking_link}\n"
    
    # Timestamps
    created_at = shipment_data.get("created_at")
    if created_at:
        summary += f"\nCreated: {created_at}\n"
    
    return summary


def _format_docket_allocation_response(data: dict) -> str:
    """Format docket allocation response into human-readable summary"""
    
    if not data:
        return "Failed to allocate docket - No response from API"
    
    if isinstance(data, dict):
        # Check for errors
        if data.get("status") == "error" or data.get("error"):
            error_msg = data.get("message") or data.get("error") or "Unknown error"
            return f"Docket allocation failed: {error_msg}"
        
        # Extract allocation details
        summary = "DOCKET ALLOCATED SUCCESSFULLY\n"
        summary += f"{'-' * 60}\n"
        
        # Main docket/AWB number
        docket_number = data.get("docket_number") or data.get("awb_number")
        if docket_number:
            summary += f"Docket/AWB Number: {docket_number}\n"
        
        # Carrier info
        carrier = data.get("carrier_id") or data.get("carrier")
        if carrier:
            summary += f"Carrier: {_format_carrier(carrier)}\n"
        
        # Route info
        if data.get("pickup_pincode"):
            summary += f"Pickup PIN: {data['pickup_pincode']}\n"
        if data.get("delivery_pincode"):
            summary += f"Delivery PIN: {data['delivery_pincode']}\n"
        
        # Order reference
        if data.get("order_reference"):
            summary += f"Order Reference: {data['order_reference']}\n"
        
        # Box series (if multiple boxes)
        box_series = data.get("box_series") or data.get("package_numbers")
        if box_series:
            if isinstance(box_series, list) and len(box_series) > 1:
                summary += f"\nBox Series ({len(box_series)} boxes):\n"
                for idx, box_num in enumerate(box_series, 1):
                    summary += f"   Box {idx}: {box_num}\n"
            elif isinstance(box_series, list) and len(box_series) == 1:
                summary += f"Box Number: {box_series[0]}\n"
        
        # Additional info
        if data.get("ship_mode"):
            summary += f"Ship Mode: {data['ship_mode'].upper()}\n"
        if data.get("payment_mode"):
            summary += f"Payment Mode: {data['payment_mode'].upper()}\n"
        
        return summary
    
    return str(data)
'''
async def lookup_pincode(pincode: str) -> dict[str, Any] | None:
    """
    Look up city, state, district from a 6-digit Indian pincode using India Post API.
    
    Returns:
        {
            "pincode": "600001",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "district": "Chennai",
            "country": "IN"
        }
        or None if invalid/not found
    """
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        return None
    
    url = f"https://api.postalpincode.in/pincode/{pincode}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=5.0)
            data = response.json()
            
            if data and len(data) > 0 and data[0].get("Status") == "Success":
                post_offices = data[0].get("PostOffice", [])
                if post_offices and len(post_offices) > 0:
                    office = post_offices[0]
                    return {
                        "pincode": pincode,
                        "city": office.get("District", "").strip(),
                        "state": office.get("State", "").strip(),
                        "district": office.get("District", "").strip(),
                        "country": "IN"
                    }
        except Exception as e:
            print(f"Pincode lookup failed for {pincode}: {str(e)}")
    
    return None
'''
@mcp.tool()
async def get_tracking(tracking_number: str, ctx: Context) -> str:
    api_token = _resolve_eshipz_token(ctx)
    
    data = await get_tracking_details(tracking_number, api_token) #invoking the function to perform the api call
    
    if not data:
        return " Tracking information could not be retrieved. Please verify the tracking number."

    try:
        if isinstance(data, list) and len(data) > 0:
            shipment = data[0]
        else:
            return "No shipment data found in the response."

        # Get summary
        summary = _create_summary(shipment)
        
        # Add latest update timestamp if available
        checkpoints = shipment.get("checkpoints", [])
        if checkpoints:
            latest_time = checkpoints[0].get("date", "")
            if latest_time:
                summary += f"\n   Last updated: {latest_time}"
        
        # Add event count
        event_count = len(checkpoints)
        if event_count > 0:
            summary += f"\n   Total events: {event_count}"
        
        return summary

    except Exception as e:
        return f"Error processing tracking data: {str(e)}"
    
    
@mcp.tool()
async def get_carrier_performance(source_pin: str, destination_pin: str, ctx: Context) -> str:
    api_token = _resolve_eshipz_token(ctx)
    
    data = await make_carrier_performance_request(source_pin, destination_pin, api_token) # invoking the function to perform the api call
    
    if not data:
        return f" Carrier performance data could not be retrieved for route {source_pin} → {destination_pin}.\n   Please verify the PIN codes and try again."
    
    try:
        summary = _format_carrier_performance(data)
        return summary
    
    except Exception as e:
        return f" Error processing carrier performance data: {str(e)}"


@mcp.tool()
async def allocate_docket(
    carrier_id: str,
    ship_mode: str,
    pickup_pincode: str,
    delivery_pincode: str,
    payment_mode: str,
    order_reference: str = "",
    box_count: int = 1,
    return_box_series: bool = True,
    ctx: Context = None
) -> str:
    api_token = _resolve_eshipz_token(ctx)
    
    
    allocation_data = {
        "carrier_id": carrier_id,
        "ship_mode": ship_mode,
        "pickup_pincode": pickup_pincode,
        "delivery_pincode": delivery_pincode,
        "payment_mode": payment_mode,
        "box_count": box_count,
        "return_box_series": return_box_series,
        "package_number_fetch": False,  
        "generate_sticker": False,       
    }
    
    if order_reference:
        allocation_data["order_reference"] = order_reference
    
    data = await make_docket_allocation_request(allocation_data, api_token)
    
    if not data:
        return "Docket allocation failed. Please check carrier_id and PIN codes."
    
    try:
        summary = _format_docket_allocation_response(data)
        return summary
    
    except Exception as e:
        return f"Error processing docket allocation: {str(e)}"


@mcp.tool()
async def create_shipment(
    carrier_description: str = "",            # LLM-provided natural language carrier description (e.g., "bluedart", "delhivery")
    slug: str = "",                          # Direct carrier slug (if provided, overrides carrier_description)
    service_type: str = "",                  # service type (e.g., "Apex", "express")
    customer_reference: str = "",
    description: str = "",                   # Shipment description
    is_to_pay: bool = False,                # Is payment to be collected from recipient
    # Shipper details
    ship_from_name: str = "",
    ship_from_company: str = "",
    ship_from_street1: str = "",
    ship_from_street2: str = "",
    ship_from_street3: str = "",
    ship_from_city: str = "",
    ship_from_state: str = "",
    ship_from_pincode: str = "",
    ship_from_phone: str = "",
    ship_from_email: str = "",
    ship_from_fax: str = "",
    ship_from_alias_name: str = "",
    ship_from_is_primary: bool = True,
    # Consignee details
    ship_to_name: str = "",
    ship_to_company: str = "",
    ship_to_street1: str = "",
    ship_to_street2: str = "",
    ship_to_street3: str = "",
    ship_to_city: str = "",
    ship_to_state: str = "",
    ship_to_pincode: str = "",
    ship_to_phone: str = "",
    ship_to_email: str = "",
    ship_to_fax: str = "",
    ship_to_alias_name: str = "",
    ship_to_is_primary: bool = True,
    # Parcel details (JSON string for multiple parcels)
    parcels_json: str = "",                 # JSON array of parcel objects
    # Item details (JSON string for multiple items)
    items_json: str = "",                   # JSON array of item objects
    # Legacy single parcel/item support
    parcel_description: str = "",
    parcel_weight_kg: float = 0.0,
    parcel_length_cm: float = 0.0,
    parcel_width_cm: float = 0.0,
    parcel_height_cm: float = 0.0,
    item_description: str = "",
    item_quantity: int = 1,
    item_price: float = 0.0,
    item_hsn_code: str = "",
    item_sku: str = "",
    # Additional fields
    is_cod: bool = False,
    cod_amount: float = 0.0,
    invoice_number: str = "",
    invoice_date: str = "",
    is_document: bool = False,
    ship_from_gstin: str = "",
    gst_invoices_json: str = "",            # JSON array of GST invoice objects
    ctx: Context = None
) -> str:
    api_token = _resolve_eshipz_token(ctx)
    
    # Determine actual slug: use provided slug, or extract from carrier_description, or fallback to "auto"
    if slug:
        actual_carrier_slug = slug.lower().strip()
    else:
        actual_carrier_slug = _get_slug_from_description(carrier_description)
    
    if ship_from_phone:
        phone_digits_from = re.sub(r"\D", "", ship_from_phone)
        if len(phone_digits_from) >= 10:
            ship_from_phone = phone_digits_from[-10:]  # Take last 10 digits
    
    if ship_to_phone:
        phone_digits_to = re.sub(r"\D", "", ship_to_phone)
        if len(phone_digits_to) >= 10:
            ship_to_phone = phone_digits_to[-10:]  # Take last 10 digits

    # Normalize key identity fields so whitespace-only values are treated as empty.
    ship_from_company = (ship_from_company or "").strip()
    ship_to_company = (ship_to_company or "").strip()
    ship_from_name = (ship_from_name or "").strip()
    ship_to_name = (ship_to_name or "").strip()

    # Simple address type logic - based on company name presence
    ship_from_type = "business" if ship_from_company else "residential"
    ship_to_type = "business" if ship_to_company else "residential"

    # Parse JSON arrays if provided, otherwise use legacy single item/parcel support
    parcels_list = []
    items_list = []
    gst_invoices_list = []
    
    # Parse parcels from JSON or use legacy single parcel
    if parcels_json:
        try:
            parcels_list = json.loads(parcels_json)
        except json.JSONDecodeError:
            return f"Invalid JSON format for parcels_json: {parcels_json}"
    elif parcel_weight_kg > 0:
        # Legacy: create parcel from individual fields
        parcels_list = [{
            "description": parcel_description,
            "box_type": "custom",
            "quantity": 1,
            "weight": {
                "value": parcel_weight_kg,
                "unit": "kg"
            },
            "dimension": {
                "width": parcel_width_cm,
                "height": parcel_height_cm,
                "length": parcel_length_cm,
                "unit": "cm"
            }
        }]
    
    # Parse items from JSON or use legacy single item
    if items_json:
        try:
            items_list = json.loads(items_json)
        except json.JSONDecodeError:
            return f"Invalid JSON format for items_json: {items_json}"
    elif item_description:
        # Legacy: create item from individual fields
        items_list = [{
            "description": item_description,
            "origin_country": "IN",
            "sku": item_sku,
            "hs_code": item_hsn_code,
            "variant": "",
            "quantity": item_quantity,
            "price": {
                "amount": item_price,
                "currency": "INR"
            },
            "weight": {
                "value": 0,
                "unit": "kg"
            }
        }]
    
    # Add items to parcels if items exist
    if items_list and parcels_list:
        for parcel in parcels_list:
            if "items" not in parcel:
                parcel["items"] = items_list
    elif items_list and not parcels_list:
        # Create default parcel if only items provided
        parcels_list = [{
            "description": parcel_description or "Default",
            "box_type": "custom",
            "quantity": 1,
            "weight": {
                "value": parcel_weight_kg or 0.5,
                "unit": "kg"
            },
            "dimension": {
                "width": parcel_width_cm or 10,
                "height": parcel_height_cm or 10,
                "length": parcel_length_cm or 10,
                "unit": "cm"
            },
            "items": items_list
        }]
    
    # Parse GST invoices from JSON or use legacy single invoice
    if gst_invoices_json:
        try:
            gst_invoices_list = json.loads(gst_invoices_json)
        except json.JSONDecodeError:
            return f"Invalid JSON format for gst_invoices_json: {gst_invoices_json}"
    elif invoice_number and invoice_date:
        # Legacy: create single invoice from individual fields
        total_value = item_price * item_quantity
        gst_invoices_list = [{
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "invoice_value": total_value,
            "ewaybill_number": ""
        }]

    # Build shipment data structure matching eShipz API format
    shipment_data = {
        "billing": {
            "paid_by": "shipper"
        },
        "vendor_id": None,
        "description": description or parcel_description or carrier_description or actual_carrier_slug.upper(),
        "slug": actual_carrier_slug,
        "purpose": "commercial",
        "order_source": "manual",
        "parcel_contents": parcel_description,
        "is_document": is_document,
        "service_type": service_type or None,
        "rate": {
            "amount": 0,
            "currency": "INR"
        },
        "charged_weight": {
            "unit": "KG",
            "value": parcel_weight_kg
        },
        "customer_reference": customer_reference,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "is_cod": is_cod,
        "collect_on_delivery": {
            "amount": cod_amount if is_cod else 0,
            "currency": "INR"
        },
        "shipment": {
            "ship_from": {
                "contact_name": ship_from_name,
                "company_name": ship_from_company,
                "street1": ship_from_street1,
                "street2": ship_from_street2,
                "street3": ship_from_street3,
                "city": ship_from_city,
                "state": ship_from_state,
                "postal_code": ship_from_pincode,
                "country": "IN",
                "type": ship_from_type,
                "phone": ship_from_phone,
                "email": ship_from_email,
                "fax": ship_from_fax,
                "tax_id": ship_from_gstin,
                "alias_name": ship_from_alias_name,
                "is_primary": ship_from_is_primary
            },
            "ship_to": {
                "contact_name": ship_to_name,
                "company_name": ship_to_company,
                "street1": ship_to_street1,
                "street2": ship_to_street2,
                "street3": ship_to_street3,
                "city": ship_to_city,
                "state": ship_to_state,
                "postal_code": ship_to_pincode,
                "country": "IN",
                "type": ship_to_type,
                "phone": ship_to_phone,
                "email": ship_to_email if ship_to_email else ship_from_email,
                "fax": ship_to_fax,
                "tax_id": "",
                "alias_name": ship_to_alias_name,
                "is_primary": ship_to_is_primary
            },
            "return_to": {
                "contact_name": ship_from_name,
                "company_name": ship_from_company,
                "street1": ship_from_street1,
                "street2": ship_from_street2,
                "street3": ship_from_street3,
                "city": ship_from_city,
                "state": ship_from_state,
                "postal_code": ship_from_pincode,
                "country": "IN",
                "type": ship_from_type,
                "phone": ship_from_phone,
                "email": ship_from_email,
                "fax": ship_from_fax,
                "tax_id": ship_from_gstin,
                "alias_name": ship_from_alias_name,
                "is_primary": ship_from_is_primary
            },
            "is_reverse": False,
            "is_to_pay": is_to_pay,
            "parcels": parcels_list if parcels_list else []
        },
        "gst_invoices": gst_invoices_list
    }
    
    data = await make_create_shipment_request(shipment_data, api_token)
    
    if not data:
        return "Shipment creation failed. Please check all details and try again."
    
    try:
        summary = _format_shipment_creation_response(data)
        return summary
    
    except Exception as e: 
        return f"Error processing shipment creation: {str(e)}"


@mcp.tool()
async def fetch_and_create_shipment(
    order_id: str,
    # Optional carrier and service type
    carrier_description: str = "",
    service_type: str = "",
    # Optional receiver details override (if receiver_address in order is empty/incomplete)
    ship_to_name: str = "",
    ship_to_company: str = "",
    ship_to_street1: str = "",
    ship_to_city: str = "",
    ship_to_state: str = "",
    ship_to_pincode: str = "",
    ship_to_phone: str = "",
    ship_to_email: str = "",
    # Optional shipper details override (if shipper_address in order is empty/incomplete)
    ship_from_name: str = "",
    ship_from_company: str = "",
    ship_from_street1: str = "",
    ship_from_street2: str = "",
    ship_from_city: str = "",
    ship_from_state: str = "",
    ship_from_pincode: str = "",
    ship_from_phone: str = "",
    ship_from_email: str = "",
    ship_from_gstin: str = "",
    # Optional parcel/details override (if parcels in order are empty/incomplete)
    parcel_description: str = "",
    parcel_weight_kg: float | None = None,
    parcel_length_cm: float | None = None,
    parcel_width_cm: float | None = None,
    parcel_height_cm: float | None = None,
    ctx: Context = None
) -> str:
    """
    Fetch an order by order_id from eShipz Orders API and create a shipment using the order data.
    
    This tool:
    1. Fetches the order details from the Orders API
    2. Extracts receiver address, items, parcels, and invoice data from the order
    3. Uses provided shipper details (or from order if available)
    4. Creates a shipment by calling the create_shipment API
    
    Args:
        order_id: The order ID to fetch (e.g., "testtn10003", "INV/25-26/656776")
        carrier_description: Natural language carrier description (e.g., "bluedart", "delhivery")
        service_type: Service type for shipment
        ship_to_*: Receiver details to override missing/incomplete order receiver data
        ship_from_*: Shipper details (required if shipper_address in order is empty or incomplete; company is optional)
        parcel_*: Parcel values to override missing/incomplete order parcel data
    
    Returns:
        Success message with shipment details or error message with missing fields
    """
    
    # Step 1: Fetch order from Orders API
    api_token = _resolve_eshipz_token(ctx)
    order_data = await fetch_order_by_id(order_id, api_token)
    
    if not order_data:
        return f"Failed to fetch order '{order_id}'. Please verify the order ID and try again."
    
    # Check if the response is successful
    if order_data.get("status") != 200:
        remark = order_data.get("remark", "Unknown error")
        return f"Failed to fetch order '{order_id}': {remark}"
    
    # Extract order details
    orders = order_data.get("orders", [])
    if not orders or len(orders) == 0:
        return f"No order found with ID '{order_id}'"
    
    order = orders[0]
    
    # Check order fulfilment status. Do not fail fast here because we can still
    # gather missing required fields and prompt the caller with exact inputs.
    fulfilment_status = order.get("fulfilment_status") or {}
    fulfilment_warning = ""
    if fulfilment_status.get("status") == "failure":
        failure_msg = fulfilment_status.get("msg", "Unknown validation error")
        fulfilment_warning = (
            f"Order '{order_id}' has validation failures from Orders API: {failure_msg}\n\n"
            "Proceeding with required-field checks for shipment creation.\n\n"
        )
    
    # Step 2: Extract data from order
    receiver_address = order.get("receiver_address") or {}
    shipper_address = order.get("shipper_address") or {}
    items = order.get("items") or []
    parcels = order.get("parcels") or []
    gst_invoices = order.get("gst_invoices") or []
    
    # Determine COD
    is_cod = order.get("is_cod", False)
    cod_amount = float(order.get("cod_amount", 0))
    
    # Extract shipment value
    shipment_value = float(order.get("shipment_value", 0))
    
    # Extract invoice details
    invoice_number = order.get("invoice_number", "")
    invoice_date = ""
    invoice_value = shipment_value  # Use shipment value as invoice value
    
    if gst_invoices and len(gst_invoices) > 0:
        gst_invoice = gst_invoices[0]
        invoice_number = invoice_number or gst_invoice.get("invoice_number", "")
        invoice_date = gst_invoice.get("invoice_date", "")
        if gst_invoice.get("invoice_value"):
            invoice_value = float(gst_invoice.get("invoice_value", 0))
    
    # Extract receiver (ship_to) details
    order_ship_to_name = f"{receiver_address.get('first_name', '')} {receiver_address.get('last_name', '')}".strip()
    order_ship_to_company = (receiver_address.get("company_name", "") or "").strip()
    order_ship_to_street1 = (receiver_address.get("address", "") or "").strip()
    order_ship_to_city = (receiver_address.get("city", "") or "").strip()
    order_ship_to_state = (receiver_address.get("state", "") or "").strip()
    order_ship_to_pincode = (receiver_address.get("zipcode", "") or "").strip()
    order_ship_to_phone = (receiver_address.get("phone", "") or "").strip()
    order_ship_to_email = (receiver_address.get("email", "") or "").strip()
    ship_to_gstin = receiver_address.get("gst_number", "")

    ship_to_name = (ship_to_name or order_ship_to_name).strip()
    ship_to_company = (ship_to_company or order_ship_to_company).strip()
    ship_to_street1 = (ship_to_street1 or order_ship_to_street1).strip()
    ship_to_city = (ship_to_city or order_ship_to_city).strip()
    ship_to_state = (ship_to_state or order_ship_to_state).strip()
    ship_to_pincode = (ship_to_pincode or order_ship_to_pincode).strip()
    ship_to_phone = (ship_to_phone or order_ship_to_phone).strip()
    ship_to_email = (ship_to_email or order_ship_to_email).strip()
    
    # Extract shipper (ship_from) details - use provided values or order values
    if not ship_from_name and shipper_address.get("first_name"):
        ship_from_name = f"{shipper_address.get('first_name', '')} {shipper_address.get('last_name', '')}".strip()
    
    if not ship_from_company and shipper_address.get("company_name"):
        ship_from_company = shipper_address.get("company_name", "")
    
    if not ship_from_street1 and shipper_address.get("address"):
        ship_from_street1 = shipper_address.get("address", "")
    
    if not ship_from_city and shipper_address.get("city"):
        ship_from_city = shipper_address.get("city", "")
    
    if not ship_from_state and shipper_address.get("state"):
        ship_from_state = shipper_address.get("state", "")
    
    if not ship_from_pincode and shipper_address.get("zipcode"):
        ship_from_pincode = shipper_address.get("zipcode", "")
    
    if not ship_from_phone and shipper_address.get("phone"):
        ship_from_phone = shipper_address.get("phone", "")
    
    if not ship_from_email and shipper_address.get("email"):
        ship_from_email = shipper_address.get("email", "")
    
    if not ship_from_gstin and shipper_address.get("gst_number"):
        ship_from_gstin = shipper_address.get("gst_number", "")

    # Normalize shipper fields after merge (tool args + order defaults).
    ship_from_name = (ship_from_name or "").strip()
    ship_from_company = (ship_from_company or "").strip()
    ship_from_street1 = (ship_from_street1 or "").strip()
    ship_from_city = (ship_from_city or "").strip()
    ship_from_state = (ship_from_state or "").strip()
    ship_from_pincode = (ship_from_pincode or "").strip()
    ship_from_phone = (ship_from_phone or "").strip()
    ship_from_email = (ship_from_email or "").strip()
    
    # Extract item details (use first item if multiple)
    item_description = ""
    item_quantity = 1
    item_price = 0.0
    item_sku = ""
    item_hsn_code = ""
    
    if items and len(items) > 0:
        first_item = items[0]
        item_description = first_item.get("description", "")
        item_quantity = int(first_item.get("quantity", 1))
        item_value = first_item.get("value") or {}
        item_price = float(item_value.get("amount", 0))
        item_sku = first_item.get("sku", "")
        item_hsn_code = first_item.get("hs_code", "")
    
    # Extract parcel details (use first parcel if multiple)
    order_parcel_weight_kg = 0.0
    order_parcel_length_cm = 0.0
    order_parcel_width_cm = 0.0
    order_parcel_height_cm = 0.0
    order_parcel_description = item_description  # Use item description as parcel description
    
    if parcels and len(parcels) > 0:
        first_parcel = parcels[0]
        weight_data = first_parcel.get("weight") or {}
        order_parcel_weight_kg = float(weight_data.get("value", 0) or 0)
        
        # Convert weight to kg if needed
        weight_unit = weight_data.get("unit_of_measurement", "KG").upper()
        if weight_unit == "G" or weight_unit == "GRAM":
            order_parcel_weight_kg = order_parcel_weight_kg / 1000
        
        dimensions = first_parcel.get("dimensions") or {}
        order_parcel_length_cm = float(dimensions.get("length", 0) or 0)
        order_parcel_width_cm = float(dimensions.get("width", 0) or 0)
        order_parcel_height_cm = float(dimensions.get("height", 0) or 0)
        
        # Convert dimensions to cm if needed
        dim_unit = dimensions.get("unit_of_measurement", "CM").upper()
        if dim_unit == "M" or dim_unit == "METER":
            order_parcel_length_cm = order_parcel_length_cm * 100
            order_parcel_width_cm = order_parcel_width_cm * 100
            order_parcel_height_cm = order_parcel_height_cm * 100

    # Merge parcel overrides: explicit tool args take precedence over order values
    parcel_weight_kg = (
        float(parcel_weight_kg)
        if parcel_weight_kg is not None
        else order_parcel_weight_kg
    )
    parcel_length_cm = (
        float(parcel_length_cm)
        if parcel_length_cm is not None
        else order_parcel_length_cm
    )
    parcel_width_cm = (
        float(parcel_width_cm)
        if parcel_width_cm is not None
        else order_parcel_width_cm
    )
    parcel_height_cm = (
        float(parcel_height_cm)
        if parcel_height_cm is not None
        else order_parcel_height_cm
    )
    parcel_description = (parcel_description or order_parcel_description).strip()
    
    # Check if required fields are missing
    missing_fields = []
    missing_shipper_fields = []
    missing_receiver_fields = []
    
    # Validate receiver details
    if not ship_to_name:
        missing_receiver_fields.append("name (first_name/last_name)")
    if not ship_to_street1:
        missing_receiver_fields.append("address")
    if not ship_to_city:
        missing_receiver_fields.append("city")
    if not ship_to_state:
        missing_receiver_fields.append("state")
    if not ship_to_pincode:
        missing_receiver_fields.append("pincode")
    if not ship_to_phone:
        missing_receiver_fields.append("phone")
    
    # Validate shipper details
    if not ship_from_name:
        missing_shipper_fields.append("name (provide ship_from_name parameter)")
    if not ship_from_street1:
        missing_shipper_fields.append("address (provide ship_from_street1 parameter)")
    if not ship_from_city:
        missing_shipper_fields.append("city (provide ship_from_city parameter)")
    if not ship_from_state:
        missing_shipper_fields.append("state (provide ship_from_state parameter)")
    if not ship_from_pincode:
        missing_shipper_fields.append("pincode (provide ship_from_pincode parameter)")
    if not ship_from_phone:
        missing_shipper_fields.append("phone (provide ship_from_phone parameter)")
    
    # Validate parcel details
    if parcel_weight_kg <= 0:
        missing_fields.append("parcel weight (must be greater than 0)")
    
    # Build error message with clear sections
    if missing_receiver_fields or missing_shipper_fields or missing_fields:
        error_msg = fulfilment_warning
        error_msg += f"Cannot create shipment for order '{order_id}'. Missing required fields:\n\n"
        
        if missing_receiver_fields:
            error_msg += "RECEIVER DETAILS (from order):\n"
            for field in missing_receiver_fields:
                error_msg += f"  - {field}\n"
            error_msg += "\n"
        
        if missing_shipper_fields:
            error_msg += "SHIPPER DETAILS (must be provided as tool parameters):\n"
            for field in missing_shipper_fields:
                error_msg += f"  - {field}\n"
            error_msg += "\nExample: Use ship_from_name='John Doe', ship_from_street1='Address', etc.\n\n"
        
        if missing_fields:
            error_msg += "OTHER REQUIRED FIELDS:\n"
            for field in missing_fields:
                error_msg += f"  - {field}\n"

        error_msg += (
            "\nPlease ask the user for these missing values and retry "
            "fetch_and_create_shipment with direct parameters (for example "
            "ship_from_*, ship_to_*, parcel_weight_kg, parcel_length_cm, "
            "parcel_width_cm, parcel_height_cm)."
        )
        
        return error_msg
    
    # Step 3: Create shipment using the create_shipment tool
    result = await create_shipment(
        carrier_description=carrier_description,
        service_type=service_type,
        customer_reference=order_id,
        # Shipper details
        ship_from_name=ship_from_name,
        ship_from_company=ship_from_company,
        ship_from_street1=ship_from_street1,
        ship_from_street2=ship_from_street2,
        ship_from_city=ship_from_city,
        ship_from_state=ship_from_state,
        ship_from_pincode=ship_from_pincode,
        ship_from_phone=ship_from_phone,
        ship_from_email=ship_from_email,
        ship_from_gstin=ship_from_gstin,
        # Receiver details
        ship_to_name=ship_to_name,
        ship_to_company=ship_to_company,
        ship_to_street1=ship_to_street1,
        ship_to_city=ship_to_city,
        ship_to_state=ship_to_state,
        ship_to_pincode=ship_to_pincode,
        ship_to_phone=ship_to_phone,
        ship_to_email=ship_to_email,
        # Parcel details
        parcel_description=parcel_description,
        parcel_weight_kg=parcel_weight_kg,
        parcel_length_cm=parcel_length_cm,
        parcel_width_cm=parcel_width_cm,
        parcel_height_cm=parcel_height_cm,
        # Item details
        item_description=item_description,
        item_quantity=item_quantity,
        item_price=item_price,
        item_sku=item_sku,
        item_hsn_code=item_hsn_code,
        # COD and invoice
        is_cod=is_cod,
        cod_amount=cod_amount,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        ctx=ctx,
    )
    
    return result

async def fetch_shipments_page(
    min_date: str, 
    max_date: str, 
    page: int, 
    limit: int, 
    api_token: str | None = None
) -> list[dict]:
    """Fetches a specific page of shipments within a date range."""
    resolved_token = api_token or ESHIPZ_TOKEN
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": resolved_token
    }
    
    params = {
        "page": page,
        "limit": limit,
        "min_date": min_date,
        "max_date": max_date
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                ESHIPZ_API_GET_SHIPMENTS_URL,
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if data and isinstance(data, list):
                return data
                
        except Exception as e:
            print(f"Error fetching shipments page {page}: {str(e)}")
            
    return []

@mcp.tool()
async def get_shipments(
    days_stuck: int = 5, 
    lookback_days: int = 30, 
    page: int = 1,          # Added parameter for Claude
    limit: int = 50,        # Added parameter for Claude
    ctx: Context = None
) -> str:
    """
    Finds shipments that have been stuck in transit without tracking updates.
    Returns a specific page of results. If the number of shipments fetched equals 
    the limit, you should call this tool again with page + 1 to get more results.
    """
    api_token = _resolve_eshipz_token(ctx)
    
    if not ESHIPZ_API_GET_SHIPMENTS_URL:
        return "Error: ESHIPZ_API_GET_SHIPMENTS_URL is not defined in the environment variables."

    now_utc = datetime.now(timezone.utc)
    max_date_obj = now_utc
    min_date_obj = now_utc - timedelta(days=lookback_days)
    
    max_date_str = max_date_obj.strftime("%Y-%m-%d")
    min_date_str = min_date_obj.strftime("%Y-%m-%d")

    # Fetch just the requested page
    shipments = await fetch_shipments_page(min_date_str, max_date_str, page, limit, api_token)

    if not shipments:
        return f"No shipments found on page {page} between {min_date_str} and {max_date_str}."

    stuck_shipments = []

    for shipment in shipments:
        status = shipment.get("tracking_status", "")
        sub_status = shipment.get("tracking_sub_status", "")
        
        if status == "Delivered" or sub_status == "RTODelivered":
            continue

        date_str = shipment.get("latest_checkpoint_date")
        if not date_str:
            continue

        try:
            checkpoint_date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S GMT")
            checkpoint_date = checkpoint_date.replace(tzinfo=timezone.utc)
            
            days_diff = (now_utc - checkpoint_date).days
            
            if days_diff > days_stuck:
                stuck_shipments.append((shipment, days_diff))
        except ValueError:
            continue

    stuck_shipments.sort(key=lambda x: x[1], reverse=True)

    # Format the header to include page and limit info for Claude
    summary = f"FOUND {len(stuck_shipments)} STUCK SHIPMENTS (> {days_stuck} days without update)\n"
    summary += f"Date Range: {min_date_str} to {max_date_str}\n"
    summary += f"Page: {page} | Limit: {limit} | Fetched: {len(shipments)} items\n"
    
    # Give Claude a clear hint if there might be more data
    if len(shipments) == limit:
        summary += f"Note: There are likely more shipments. Call this tool again with page={page + 1} to continue searching.\n"
        
    summary += f"{'-' * 60}\n\n"

    if not stuck_shipments:
        summary += f"Good news! No stuck shipments found on this specific page.\n"
        return summary

    for shipment, days in stuck_shipments:
        awb = shipment.get("awb", "Unknown")
        order_id = shipment.get("order_id", "Unknown")
        carrier = shipment.get("vendor_display_name", shipment.get("slug", "Unknown"))
        status = shipment.get("tracking_status", "Unknown")
        sub_status = shipment.get("tracking_sub_status", "")
        latest_date = shipment.get("latest_checkpoint_date", "Unknown")
        
        display_status = status
        if sub_status:
            display_status += f" ({sub_status})"

        summary += f"Order: {order_id} | AWB: {awb}\n"
        summary += f"Carrier: {carrier}\n"
        summary += f"Status: {display_status}\n"
        summary += f"Last Update: {latest_date} ({days} days ago)\n\n"

    return summary

if __name__ == "__main__":
    import sys

    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")