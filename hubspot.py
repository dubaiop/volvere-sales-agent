"""HubSpot CRM integration — read contacts, update scores, create notes."""

import requests
from config import HUBSPOT_API_KEY, HUBSPOT_BASE_URL

def _h(): return {"Authorization": f"Bearer {HUBSPOT_API_KEY}", "Content-Type": "application/json"}

def get_new_contacts(limit: int = 20) -> list[dict]:
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts"
    params = {"limit": limit, "properties": "firstname,lastname,email,company,jobtitle,lifecyclestage,hs_lead_status,phone,website,industry,numberofemployees", "sort": "-createdate"}
    r = requests.get(url, params=params, headers=_h(), timeout=10)
    r.raise_for_status()
    return r.json().get("results", [])

def get_deals(limit: int = 20) -> list[dict]:
    url = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals"
    params = {"limit": limit, "properties": "dealname,amount,dealstage,closedate,hs_deal_stage_probability,createdate", "sort": "-createdate"}
    r = requests.get(url, params=params, headers=_h(), timeout=10)
    r.raise_for_status()
    return r.json().get("results", [])

def update_contact(contact_id: str, properties: dict) -> dict:
    r = requests.patch(f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts/{contact_id}", json={"properties": properties}, headers=_h(), timeout=10)
    r.raise_for_status()
    return r.json()

def create_note(contact_id: str, note_body: str) -> dict:
    engagement = {"active": True, "type": "NOTE"}
    metadata = {"body": note_body}
    associations = {"contactIds": [contact_id]}
    r = requests.post(f"{HUBSPOT_BASE_URL}/engagements/v1/engagements", json={"engagement": engagement, "metadata": metadata, "associations": associations}, headers=_h(), timeout=10)
    return r.json() if r.ok else {"error": r.text}

def get_pipeline_stats() -> dict:
    deals = get_deals(limit=50)
    stages: dict = {}
    for d in deals:
        p = d.get("properties", {})
        stage = p.get("dealstage", "unknown")
        amount = float(p.get("amount") or 0)
        prob = float(p.get("hs_deal_stage_probability") or 0)
        if stage not in stages:
            stages[stage] = {"count": 0, "value": 0, "weighted": 0}
        stages[stage]["count"] += 1
        stages[stage]["value"] += amount
        stages[stage]["weighted"] += amount * prob
    total_value = sum(s["value"] for s in stages.values())
    weighted_value = sum(s["weighted"] for s in stages.values())
    return {"stages": stages, "total_deals": len(deals), "total_value": total_value, "weighted_forecast": weighted_value}
