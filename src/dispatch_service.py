"""Dispatch delivery service — sends alerts via webhook, with SMS/WhatsApp mock."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Literal

import requests

from src.persistence import log_dispatch, log_audit

WEBHOOK_URL = os.getenv("PARKSENSE_DISPATCH_WEBHOOK", "")
DISPATCH_LOG: list[dict] = []  # In-memory fallback log for demo mode


def _format_payload_en(hotspot_name: str, risk: float, rec: dict, impact_inr: float) -> str:
    return (
        f"🚨 PARKSENSE DISPATCH ALERT 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Junction: {hotspot_name}\n"
        f"Risk Score: {risk:.0f}% ({rec.get('enforcement_level', 'N/A')})\n"
        f"Response Priority: {rec.get('suggested_response', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"DEPLOY:\n"
        f"  • Officers: {rec.get('recommended_officers', 0)}\n"
        f"  • Barricades: {rec.get('recommended_barricades', 0)}\n"
        f"  • Tow Trucks: {rec.get('recommended_tow_trucks', 0)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Economic Loss: ₹{impact_inr:,.0f}\n"
        f"Time: {datetime.now(timezone.utc).strftime('%H:%M UTC %d-%b-%Y')}\n"
        f"Dispatch ID: PS-{hotspot_name[:8].upper().replace(' ', '')}-{datetime.now().strftime('%H%M')}"
    )


def _format_payload_kn(hotspot_name: str, risk: float, rec: dict, impact_inr: float) -> str:
    return (
        f"🚨 ಪಾರ್ಕ್‌ಸೆನ್ಸ್ ನಿಯೋಜನೆ ಎಚ್ಚರಿಕೆ 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ಜಂಕ್ಷನ್: {hotspot_name}\n"
        f"ಅಪಾಯದ ಪ್ರಮಾಣ: {risk:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ನಿಯೋಜಿಸಿ:\n"
        f"  • ಅಧಿಕಾರಿಗಳು: {rec.get('recommended_officers', 0)}\n"
        f"  • ಬ್ಯಾರಿಕೇಡ್: {rec.get('recommended_barricades', 0)}\n"
        f"  • ಟೋ ಟ್ರಕ್: {rec.get('recommended_tow_trucks', 0)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"ಆರ್ಥಿಕ ನಷ್ಟ: ₹{impact_inr:,.0f}\n"
    )


def send_dispatch(
    hotspot_id: str,
    hotspot_name: str,
    risk_score: float,
    recommendation: dict,
    impact_inr: float,
    channel: Literal["webhook", "whatsapp", "sms"] = "webhook",
    language: str = "en",
    username: str = "system",
) -> dict[str, Any]:
    """Send a dispatch alert via the chosen channel. Returns delivery status."""

    if language == "kn":
        payload_text = _format_payload_kn(hotspot_name, risk_score, recommendation, impact_inr)
    else:
        payload_text = _format_payload_en(hotspot_name, risk_score, recommendation, impact_inr)

    delivery_status = "delivered"
    delivery_details: dict[str, Any] = {"channel": channel}

    if channel == "webhook" and WEBHOOK_URL:
        try:
            resp = requests.post(
                WEBHOOK_URL,
                json={
                    "source": "ParkSense",
                    "hotspot_id": hotspot_id,
                    "hotspot_name": hotspot_name,
                    "risk_score": risk_score,
                    "payload": payload_text,
                    "language": language,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=5,
            )
            delivery_details["status_code"] = resp.status_code
            delivery_status = "delivered" if resp.status_code < 400 else "failed"
        except Exception as e:
            delivery_status = "failed"
            delivery_details["error"] = str(e)

    elif channel in ("whatsapp", "sms"):
        # Mock delivery — log the payload as if it was sent
        delivery_status = "delivered_mock"
        delivery_details["note"] = f"Mock {channel.upper()} delivery. Configure Twilio/MSG91 for production."
        print(f"[MOCK {channel.upper()}] Dispatch to {hotspot_name}:\n{payload_text}\n")

    else:
        # No webhook configured — local logging mode
        delivery_status = "logged_locally"
        delivery_details["note"] = "No PARKSENSE_DISPATCH_WEBHOOK configured. Payload logged locally."
        print(f"[LOCAL DISPATCH] {hotspot_name}:\n{payload_text}\n")

    # Persist to SQLite
    dispatch_id = log_dispatch(
        hotspot_id=hotspot_id,
        hotspot_name=hotspot_name,
        channel=channel,
        language=language,
        payload=payload_text,
        status=delivery_status,
        username=username,
    )

    # Audit trail
    log_audit(
        username=username,
        action="dispatch_sent",
        entity_type="hotspot",
        entity_id=hotspot_id,
        details={"channel": channel, "status": delivery_status, "dispatch_id": dispatch_id},
    )

    return {
        "dispatch_id": dispatch_id,
        "hotspot_id": hotspot_id,
        "hotspot_name": hotspot_name,
        "channel": channel,
        "delivery_status": delivery_status,
        "delivery_details": delivery_details,
        "payload_preview": payload_text[:200] + "..." if len(payload_text) > 200 else payload_text,
    }
