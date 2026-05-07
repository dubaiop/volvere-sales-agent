"""Telegram bot — sales agent commands via webhook."""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Volvere Sales Agent* ready.\n\n"
        "Commands:\n"
        "/qualify — Run lead qualification batch\n"
        "/pipeline — Pipeline summary\n"
        "/leads — Top qualified leads\n"
        "/help — Show this menu",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Sales Agent Commands*\n\n"
        "/qualify — Auto-qualify new HubSpot leads\n"
        "/pipeline — Get pipeline stats & forecast\n"
        "/leads — Show top T1 leads\n"
        "/start — Welcome message",
        parse_mode="Markdown",
    )


async def cmd_qualify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Running lead qualification...")
    try:
        from scheduler import auto_qualify_new_leads
        auto_qualify_new_leads()
        await update.message.reply_text("✅ Lead qualification complete. Check /leads for results.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from hubspot import get_pipeline_stats
        stats = get_pipeline_stats()
        msg = (
            f"📊 *Pipeline Summary*\n\n"
            f"*Open Deals:* {stats['total_deals']}\n"
            f"*Total Value:* ${stats['total_value']:,.0f}\n"
            f"*Weighted Forecast:* ${stats['weighted_forecast']:,.0f}\n\n"
            f"_Volvere Sales Agent_"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        from database import get_leads
        leads = get_leads(limit=5, tier="T1")
        if not leads:
            await update.message.reply_text("No T1 leads yet. Run /qualify first.")
            return
        lines = ["🔥 *Top T1 Leads*\n"]
        for l in leads:
            lines.append(f"• *{l['name']}* ({l['company']}) — Score: {l['score']}/100")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    session_id = f"tg_{update.effective_user.id}"
    try:
        from agent import chat
        reply = chat(user_input, session_id=session_id)
        for chunk in [reply[i:i+4000] for i in range(0, len(reply), 4000)]:
            await update.message.reply_text(chunk)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("qualify", cmd_qualify))
    app.add_handler(CommandHandler("pipeline", cmd_pipeline))
    app.add_handler(CommandHandler("leads", cmd_leads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
