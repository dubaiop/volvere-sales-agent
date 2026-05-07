"""Telegram alert system — notify on hot leads and pipeline events."""

import requests
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

def send_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    for chunk in [message[i:i+4000] for i in range(0, len(message), 4000)]:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Telegram alert error: {e}")

def alert_hot_lead(name: str, email: str, company: str, score: int, next_action: str):
    send_alert(f"""🔥 *HOT LEAD ALERT — Tier 1*

*Name:* {name}
*Company:* {company}
*Email:* {email}
*ICP Score:* {score}/100

*Next Action:* {next_action}

_Volvere Sales Agent_""")

def alert_pipeline_summary(total_deals: int, total_value: float, weighted: float):
    send_alert(f"""📊 *Daily Pipeline Summary*

*Open Deals:* {total_deals}
*Total Value:* ${total_value:,.0f}
*Weighted Forecast:* ${weighted:,.0f}

_Volvere Sales Agent_""")
