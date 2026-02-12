import json
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import os 

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("eshipz-mcp")

# Constants
API_BASE_URL = os.getenv("API_BASE_URL", "https://app.eshipz.com")
ESHIPZ_API_TRACKING_URL = f"{API_BASE_URL}/api/v2/trackings"
ESHIPZ_TOKEN = os.getenv("ESHIPZ_TOKEN", "")
ESHIPZ_CARRIER_PERFORMANCE_URL = "https://ds.eshipz.com/performance_score/cps_scores/v2/"
ESHIPZ_API_CREATE_SHIPMENT_URL = f"{API_BASE_URL}/api/v1/create-shipments"
ESHIPZ_API_DOCKET_ALLOCATION_URL = f"{API_BASE_URL}/api/v1/docket-allocation"

async def get_tracking_details(tracking_number: str) -> dict[str, Any] | None:
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": ESHIPZ_TOKEN
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
async def make_carrier_performance_request(source_pin: str, destination_pin: str) -> dict[str, Any] | None:
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": ESHIPZ_TOKEN
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

async def make_create_shipment_request(shipment_data: dict) -> dict[str, Any] | None:
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": ESHIPZ_TOKEN
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
        except Exception as e:
            print(f"Error in create shipment request: {str(e)}")
            return None


async def make_docket_allocation_request(allocation_data: dict) -> dict[str, Any] | None:
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": ESHIPZ_TOKEN
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



@mcp.tool()
async def get_tracking(tracking_number: str) -> str:
    
    data = await get_tracking_details(tracking_number) #invoking the function to perform the api call
    
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
async def get_carrier_performance(source_pin: str, destination_pin: str) -> str:
    
    data = await make_carrier_performance_request(source_pin, destination_pin) # invoking the function to perform the api call
    
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
    return_box_series: bool = True
) -> str:
    
    
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
    
    data = await make_docket_allocation_request(allocation_data)
    
    if not data:
        return "Docket allocation failed. Please check carrier_id and PIN codes."
    
    try:
        summary = _format_docket_allocation_response(data)
        return summary
    
    except Exception as e:
        return f"Error processing docket allocation: {str(e)}"


@mcp.tool()
async def create_shipment(
    carrier_slug: str,
    service_type: str,
    customer_reference: str,
    # Shipper details
    ship_from_name: str,
    ship_from_company: str,
    ship_from_street1: str,
    ship_from_city: str,
    ship_from_state: str,
    ship_from_pincode: str,
    ship_from_phone: str,
    ship_from_email: str,
    # Consignee details
    ship_to_name: str,
    ship_to_company: str,
    ship_to_street1: str,
    ship_to_city: str,
    ship_to_state: str,
    ship_to_pincode: str,
    ship_to_phone: str,
    # Parcel details
    parcel_description: str,
    parcel_weight_kg: float,
    parcel_length_cm: float,
    parcel_width_cm: float,
    parcel_height_cm: float,
    # Item details
    item_description: str,
    item_quantity: int,
    item_price: float,
    # Optional fields
    ship_from_street2: str = "",
    ship_to_street2: str = "",
    ship_to_email: str = "",
    is_cod: bool = False,
    cod_amount: float = 0.0,
    invoice_number: str = "",
    invoice_date: str = "",
    is_document: bool = False,
    vendor_id: str = "",
    ship_from_gstin: str = "",
    item_hsn_code: str = "",
    item_sku: str = ""
) -> str:
    
    # Build shipment data structure
    shipment_data = {
        "billing": {
            "paid_by": "shipper"
        },
        "slug": carrier_slug,
        "service_type": service_type,
        "customer_reference": customer_reference,
        "purpose": "commercial",
        "order_source": "api",
        "parcel_contents": parcel_description,
        "is_document": is_document,
        "is_cod": is_cod,
        "collect_on_delivery": {
            "amount": cod_amount if is_cod else 0,
            "currency": "INR"
        },
        "charged_weight": {
            "unit": "kg",
            "value": parcel_weight_kg
        },
        "shipment": {
            "ship_from": {
                "contact_name": ship_from_name,
                "company_name": ship_from_company,
                "street1": ship_from_street1,
                "street2": ship_from_street2,
                "city": ship_from_city,
                "state": ship_from_state,
                "postal_code": ship_from_pincode,
                "phone": ship_from_phone,
                "email": ship_from_email,
                "country": "IN",
                "type": "business" if ship_from_company else "residential"
            },
            "ship_to": {
                "contact_name": ship_to_name,
                "company_name": ship_to_company,
                "street1": ship_to_street1,
                "street2": ship_to_street2,
                "city": ship_to_city,
                "state": ship_to_state,
                "postal_code": ship_to_pincode,
                "phone": ship_to_phone,
                "email": ship_to_email if ship_to_email else ship_from_email,
                "country": "IN",
                "type": "business" if ship_to_company else "residential"
            },
            "return_to": {
                "contact_name": ship_from_name,
                "company_name": ship_from_company,
                "street1": ship_from_street1,
                "street2": ship_from_street2,
                "city": ship_from_city,
                "state": ship_from_state,
                "postal_code": ship_from_pincode,
                "phone": ship_from_phone,
                "email": ship_from_email,
                "country": "IN",
                "type": "business" if ship_from_company else "residential"
            },
            "is_reverse": False,
            "is_to_pay": False,
            "parcels": [
                {
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
                    },
                    "items": [
                        {
                            "description": item_description,
                            "origin_country": "IN",
                            "sku": item_sku,
                            "hs_code": item_hsn_code,
                            "quantity": item_quantity,
                            "price": {
                                "amount": item_price,
                                "currency": "INR"
                            },
                            "weight": {
                                "value": parcel_weight_kg,
                                "unit": "kg"
                            }
                        }
                    ]
                }
            ]
        },
        "gst_invoices": []
    }
    
    # Add optional fields
    if vendor_id:
        shipment_data["vendor_id"] = vendor_id
    
    if invoice_number:
        shipment_data["invoice_number"] = invoice_number
    
    if invoice_date:
        shipment_data["invoice_date"] = invoice_date
    
    if ship_from_gstin:
        shipment_data["shipment"]["ship_from"]["tax_id"] = ship_from_gstin
        shipment_data["shipment"]["return_to"]["tax_id"] = ship_from_gstin
    
    # Add GST invoice if details provided
    if invoice_number and invoice_date:
        total_value = item_price * item_quantity
        shipment_data["gst_invoices"] = [
            {
                "invoice_number": invoice_number,
                "invoice_date": invoice_date,
                "invoice_value": total_value,
                "ewaybill_number": "",
                "ewaybill_date": ""
            }
        ]
    
    data = await make_create_shipment_request(shipment_data)
    
    if not data:
        return "Shipment creation failed. Please check all details and try again."
    
    try:
        summary = _format_shipment_creation_response(data)
        return summary
    
    except Exception as e: 
        return f"Error processing shipment creation: {str(e)}"


if __name__ == "__main__":
    import sys
    
    # Check if running with SSE transport (for remote server)
    if "--sse" in sys.argv or os.getenv("USE_SSE", "false").lower() == "true":
        port = int(os.getenv("PORT", 10000))
        mcp.run(transport='sse', port=port, host='0.0.0.0')
    else:
        # Default to stdio for local use
        mcp.run(transport='stdio')