"""Scheduled jobs — auto-qualify new leads every 6 hours, daily pipeline summary at 8am."""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)
TZ = pytz.timezone("Asia/Dubai")

GROQ_PRESCREEN_THRESHOLD = 35  # leads below this score are saved as DQ without a Claude call


def auto_qualify_new_leads():
    logger.info("Auto-qualifying new HubSpot leads...")
    try:
        from hubspot import get_new_contacts
        from agent import run_skill, quick_score
        from database import save_lead, is_already_qualified
        from telegram_alerts import alert_hot_lead

        contacts = get_new_contacts(limit=20)
        new_count = 0
        skipped_dup = 0
        skipped_low = 0
        qualified = 0

        for c in contacts:
            hubspot_id = c.get("id", "")
            p = c.get("properties", {})
            name = f"{p.get('firstname','') or ''} {p.get('lastname','') or ''}".strip() or "Unknown"
            email = p.get("email", "")
            company = p.get("company", "Unknown")
            jobtitle = p.get("jobtitle", "")
            employees = p.get("numberofemployees", "")

            if not email:
                continue

            # Skip contacts already in our database
            if is_already_qualified(hubspot_id):
                skipped_dup += 1
                continue

            new_count += 1
            lead_data = f"Name: {name}\nEmail: {email}\nCompany: {company}\nJob Title: {jobtitle}\nEmployees: {employees}"

            # Step 1 — Groq pre-screen (cheap, fast)
            pre_score = quick_score(lead_data)
            if pre_score < GROQ_PRESCREEN_THRESHOLD:
                # Too low to spend Claude credits — save as DQ immediately
                save_lead(email, name, company, pre_score, "DQ", hubspot_id, f"Pre-screened by Groq: score {pre_score}/100")
                skipped_low += 1
                logger.info(f"  DQ (Groq pre-screen {pre_score}/100): {name}")
                continue

            # Step 2 — Full Claude qualification for promising leads only
            result = run_skill("lead-qualify", lead_data, session_id="scheduler")
            qualified += 1

            score = pre_score
            tier = "T3"
            lines = result.split("\n")
            for i, line in enumerate(lines):
                if "Score" in line and "/" in line:
                    try:
                        score = int(''.join(filter(str.isdigit, line.split("/")[0].split(":")[-1])))
                    except Exception:
                        pass
                # Match tier from a line that has "Tier" keyword — check DQ first to avoid
                # false T1 match from tier-definition text like "(T1: 80-100 / ... / DQ: <40)"
                if "Tier" in line or "tier" in line:
                    upper = line.upper()
                    if "DQ" in upper or "DISQUALIF" in upper:
                        tier = "DQ"
                    elif "T1" in upper and "T2" not in upper and "T3" not in upper:
                        tier = "T1"
                    elif "T2" in upper:
                        tier = "T2"
                    elif "T3" in upper:
                        tier = "T3"

            # Score gate: never fire T1 alert for low scores regardless of text parsing
            if score < 60 and tier == "T1":
                tier = "T2" if score >= 40 else ("T3" if score >= 20 else "DQ")

            save_lead(email, name, company, score, tier, hubspot_id, result[:500])

            if tier == "T1":
                next_action = "Immediate outreach — route to AE"
                capture_next = False
                for line in lines:
                    if capture_next and line.strip():
                        next_action = line.strip().lstrip("-•* ")
                        break
                    if "Next Action" in line:
                        # If value is on same line after colon, use it; otherwise grab next line
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            next_action = parts[1].strip()
                            break
                        else:
                            capture_next = True
                alert_hot_lead(name, email, company, score, next_action)

        logger.info(
            f"Lead run complete — {new_count} new, {skipped_dup} duplicates skipped, "
            f"{skipped_low} pre-screened out, {qualified} Claude qualifications."
        )
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
    scheduler.add_job(
        auto_qualify_new_leads,
        IntervalTrigger(hours=6),  # was every 1 hour — reduced to cut Claude costs
        id="auto_qualify",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_pipeline_summary,
        CronTrigger(hour=8, minute=0, timezone=TZ),
        id="pipeline_summary",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Sales scheduler started — leads every 6h, pipeline summary at 8am Dubai")
    return scheduler
