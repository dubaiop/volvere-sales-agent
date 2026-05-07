"""Scheduled jobs — auto-qualify new leads every hour, daily pipeline summary at 8am."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Dubai")


def auto_qualify_new_leads():
    logger.info("Auto-qualifying new HubSpot leads...")
    try:
        from hubspot import get_new_contacts
        from agent import run_skill
        from database import save_lead
        from telegram_alerts import alert_hot_lead

        contacts = get_new_contacts(limit=10)
        for c in contacts:
            p = c.get("properties", {})
            name = f"{p.get('firstname','') or ''} {p.get('lastname','') or ''}".strip() or "Unknown"
            email = p.get("email", "")
            company = p.get("company", "Unknown")
            jobtitle = p.get("jobtitle", "")
            employees = p.get("numberofemployees", "")

            if not email:
                continue

            lead_data = f"Name: {name}\nEmail: {email}\nCompany: {company}\nJob Title: {jobtitle}\nEmployees: {employees}"
            result = run_skill("lead-qualify", lead_data, session_id="scheduler")

            score = 50
            tier = "T3"
            for line in result.split("\n"):
                if "Score" in line and "/" in line:
                    try:
                        score = int(''.join(filter(str.isdigit, line.split("/")[0].split(":")[-1])))
                    except Exception:
                        pass
                if "Tier 1" in line or "T1" in line:
                    tier = "T1"
                elif "Tier 2" in line or "T2" in line:
                    tier = "T2"
                elif "DQ" in line or "Disqualified" in line:
                    tier = "DQ"

            save_lead(email, name, company, score, tier, c.get("id", ""), result[:500])

            if tier == "T1":
                next_action = "Immediate outreach — route to AE"
                for line in result.split("\n"):
                    if "Next Action" in line:
                        next_action = line.split(":", 1)[-1].strip()
                        break
                alert_hot_lead(name, email, company, score, next_action)

        logger.info(f"Processed {len(contacts)} leads.")
    except Exception as e:
        logger.error(f"Auto-qualify error: {e}")


def daily_pipeline_summary():
    logger.info("Sending daily pipeline summary...")
    try:
        from hubspot import get_pipeline_stats
        from telegram_alerts import alert_pipeline_summary
        stats = get_pipeline_stats()
        alert_pipeline_summary(stats["total_deals"], stats["total_value"], stats["weighted_forecast"])
    except Exception as e:
        logger.error(f"Pipeline summary error: {e}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TZ)
    scheduler.add_job(auto_qualify_new_leads, IntervalTrigger(hours=1), id="auto_qualify", replace_existing=True)
    scheduler.add_job(daily_pipeline_summary, CronTrigger(hour=8, minute=0, timezone=TZ), id="pipeline_summary", replace_existing=True)
    scheduler.start()
    logger.info("Sales scheduler started — leads every hour, pipeline summary at 8am Dubai")
    return scheduler
