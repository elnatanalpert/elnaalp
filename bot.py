#!/usr/bin/env python3
"""
Telegram Bot — Cold Outreach Control Panel
Controls find-customers / find-emails / compose-cold-email skills,
shows queue status, logs, and allows batch approval.
"""

import asyncio
import json
import os
import subprocess
from datetime import datetime
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
OUTREACH_BASE = Path(os.getenv("OUTREACH_BASE", "/Users/elnatanalpert/claude/outreach"))
SCRIPTS_BASE = Path(os.getenv("SCRIPTS_BASE", "/Users/elnatanalpert/claude/scripts"))
CLAUDE_CMD = os.getenv("CLAUDE_CMD", "claude")

SKILL_TIMEOUT = 30 * 60   # 30 minutes max per skill
SEND_TIMEOUT  = 60 * 60   # 60 minutes max for daily_send


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def auth_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if uid != ALLOWED_USER_ID:
            if update.message:
                await update.message.reply_text("❌ אין לך הרשאה לשלוט בבוט זה.")
            return
        return await func(update, context)
    return wrapper


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_master_queue() -> dict | None:
    path = OUTREACH_BASE / "master_queue.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_today_logs() -> list:
    today = datetime.now().strftime("%Y-%m-%d")
    path = OUTREACH_BASE / "sent_logs" / f"{today}.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_pending_batch() -> list | None:
    path = OUTREACH_BASE / "draft_batch_pending.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("emails", [])


def queue_stats(queue: dict) -> dict:
    emails = queue.get("emails", [])
    counts: dict[str, int] = {}
    for e in emails:
        s = e.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def run_skill(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                    prompt: str, label: str) -> None:
    """Run a claude skill via CLI and report result back to chat."""
    try:
        proc = await asyncio.create_subprocess_exec(
            CLAUDE_CMD, "-p", prompt,
            cwd=str(SCRIPTS_BASE.parent),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=SKILL_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⏱️ *{label}* ארך יותר מ-30 דקות ובוטל.",
                parse_mode="Markdown",
            )
            return

        if proc.returncode == 0:
            snippet = (stdout.decode("utf-8", errors="replace")[:900]) or "הסתיים בהצלחה."
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ *{label} הסתיים!*\n\n```\n{snippet}\n```",
                parse_mode="Markdown",
            )
        else:
            snippet = (stderr.decode("utf-8", errors="replace")[:600]) or "שגיאה לא ידועה."
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ *{label} נכשל:*\n```\n{snippet}\n```",
                parse_mode="Markdown",
            )
    except Exception as exc:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ שגיאה בהרצת *{label}*: {exc}",
            parse_mode="Markdown",
        )


async def run_daily_send(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    send_script = SCRIPTS_BASE / "daily_send.py"
    if not send_script.exists():
        await context.bot.send_message(chat_id=chat_id, text="❌ daily_send.py לא נמצא.")
        return

    await context.bot.send_message(chat_id=chat_id, text="📤 שולח מיילים... אקפיץ כשיסתיים.")
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", str(send_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SEND_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await context.bot.send_message(chat_id=chat_id, text="⏱️ השליחה ארכה יותר משעה ובוטלה.")
            return

        if proc.returncode == 0:
            snippet = (stdout.decode("utf-8", errors="replace")[:900]) or "הסתיים."
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ *שליחה הסתיימה!*\n```\n{snippet}\n```",
                parse_mode="Markdown",
            )
        else:
            snippet = (stderr.decode("utf-8", errors="replace")[:600]) or "שגיאה."
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ *שליחה נכשלה:*\n```\n{snippet}\n```",
                parse_mode="Markdown",
            )
    except Exception as exc:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ שגיאה: {exc}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

@auth_required
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🎬 *Cold Outreach Bot*\n\n"
        "📊 /status — סטטוס התור\n"
        "📋 /logs — לוג שליחות היום\n"
        "📦 /batch — הצג batch ממתין\n"
        "✅ /approve — אשר שליחת batch\n"
        "🔍 /find — מצא לידים (find-customers)\n"
        "📧 /emails — מצא מיילים (find-emails)\n"
        "✍️ /compose — בנה טיוטות (compose-cold-email)\n"
        "🔄 /dedup — הרץ בדיקת כפילויות\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@auth_required
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    queue = load_master_queue()
    if not queue:
        await update.message.reply_text("❌ לא נמצא master_queue.json")
        return

    stats = queue_stats(queue)
    today_logs = load_today_logs()
    today_sent   = sum(1 for l in today_logs if l.get("status") == "sent")
    today_failed = sum(1 for l in today_logs if l.get("status") == "failed")

    pending  = stats.get("pending", 0)
    sent_all = stats.get("sent", 0)
    drafts   = stats.get("draft_created", 0)
    failed   = stats.get("failed", 0)
    total    = sum(stats.values())

    last_updated = queue.get("last_updated", "—")[:10]

    text = (
        f"📊 *סטטוס Cold Outreach*\n"
        f"עדכון אחרון: {last_updated}\n\n"
        f"*תור ראשי ({total} לידים):*\n"
        f"  ⏳ ממתין:    {pending}\n"
        f"  ✅ נשלח:     {sent_all}\n"
        f"  📝 טיוטה:    {drafts}\n"
        f"  ❌ נכשל:     {failed}\n\n"
        f"*היום ({datetime.now().strftime('%d/%m')}):*\n"
        f"  📤 נשלח:  {today_sent}\n"
        f"  ❌ נכשל: {today_failed}\n"
    )

    if pending < 80:
        text += f"\n⚠️ *פחות מ-80 לידים ממתינים — שקול /find*"

    await update.message.reply_text(text, parse_mode="Markdown")


@auth_required
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logs = load_today_logs()
    date_str = datetime.now().strftime("%d/%m/%Y")

    if not logs:
        await update.message.reply_text(f"📭 אין לוג שליחות להיום ({date_str})")
        return

    sent   = [l for l in logs if l.get("status") == "sent"]
    failed = [l for l in logs if l.get("status") == "failed"]

    text = f"📋 *לוג שליחות {date_str}*\n✅ {len(sent)} נשלח | ❌ {len(failed)} נכשל\n\n"

    if sent:
        text += "📤 *נשלח:*\n"
        for log in sent[:12]:
            subj = (log.get("subject") or "")[:35]
            text += f"  • {log.get('to', '?')} — {subj}\n"
        if len(sent) > 12:
            text += f"  ... ועוד {len(sent) - 12}\n"

    if failed:
        text += "\n❌ *נכשל:*\n"
        for log in failed[:5]:
            reason = (log.get("reason") or "לא ידוע")[:40]
            text += f"  • {log.get('to', '?')} — {reason}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


@auth_required
async def cmd_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    emails = load_pending_batch()
    if not emails:
        await update.message.reply_text("📭 אין batch ממתין כרגע.")
        return

    text = f"📦 *Batch ממתין — {len(emails)} מיילים*\n\n"
    for i, e in enumerate(emails[:10], 1):
        company = (e.get("company") or "?")[:25]
        niche   = e.get("niche") or ""
        to      = e.get("to_email") or "?"
        text += f"{i}. *{company}* ({niche})\n   📬 {to}\n"
    if len(emails) > 10:
        text += f"\n... ועוד {len(emails) - 10} נוספים\n"

    keyboard = [[
        InlineKeyboardButton("✅ אשר שליחה", callback_data="approve_batch"),
        InlineKeyboardButton("❌ בטל",       callback_data="cancel_batch"),
    ]]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


@auth_required
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Re-use batch display which has the Approve button
    await cmd_batch(update, context)


@auth_required
async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("🏢 ארגונים", callback_data="find_ארגונים"),
            InlineKeyboardButton("💚 עמותות",  callback_data="find_עמותות"),
        ],
        [
            InlineKeyboardButton("🏪 רשתות",  callback_data="find_רשתות"),
            InlineKeyboardButton("🌐 הכל (3 נישות)", callback_data="find_all"),
        ],
    ]
    await update.message.reply_text(
        "🔍 *find-customers — בחר נישה:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


@auth_required
async def cmd_emails(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text("📧 מריץ find-emails... אקפיץ כשיסתיים.")
    asyncio.create_task(run_skill(
        chat_id, context,
        prompt="תמצא מיילים לכל הלידים בקובץ new_leads האחרון",
        label="find-emails",
    ))


@auth_required
async def cmd_compose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text("✍️ מריץ compose-cold-email... אקפיץ כשיסתיים.")
    asyncio.create_task(run_skill(
        chat_id, context,
        prompt="בנה מיילים וצור טיוטות Gmail לכל הלידים שעברו dedup",
        label="compose-cold-email",
    ))


@auth_required
async def cmd_dedup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dedup_script  = SCRIPTS_BASE / "dedup_check.py"
    master_queue  = OUTREACH_BASE / "master_queue.json"

    if not dedup_script.exists():
        await update.message.reply_text("❌ dedup_check.py לא נמצא.")
        return

    await update.message.reply_text("🔄 מריץ בדיקת כפילויות...")
    try:
        result = subprocess.run(
            ["python3", str(dedup_script), "--batch", str(master_queue)],
            capture_output=True, text=True, timeout=60, encoding="utf-8",
        )
        output = (result.stdout or result.stderr or "הסתיים ללא פלט")[:1000]
        await update.message.reply_text(
            f"✅ Dedup הסתיים:\n```\n{output}\n```",
            parse_mode="Markdown",
        )
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Dedup ארך יותר מ-60 שניות.")
    except Exception as exc:
        await update.message.reply_text(f"❌ שגיאה: {exc}")


# ---------------------------------------------------------------------------
# Callback query handler
# ---------------------------------------------------------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not update.effective_user or update.effective_user.id != ALLOWED_USER_ID:
        await query.edit_message_text("❌ אין הרשאה.")
        return

    data    = query.data
    chat_id = query.message.chat_id

    if data.startswith("find_"):
        niche = data[len("find_"):]
        if niche == "all":
            await query.edit_message_text("🔍 מריץ find-customers לכל 3 הנישות... ~20 דקות.")
            for n in ["ארגונים", "עמותות", "רשתות"]:
                asyncio.create_task(run_skill(
                    chat_id, context,
                    prompt=f"מצא לידים לנישת {n}",
                    label=f"find-customers ({n})",
                ))
        else:
            await query.edit_message_text(f"🔍 מריץ find-customers — {niche}...")
            asyncio.create_task(run_skill(
                chat_id, context,
                prompt=f"מצא לידים לנישת {niche}",
                label=f"find-customers ({niche})",
            ))

    elif data == "approve_batch":
        await query.edit_message_text("⏳ מריץ daily_send.py...")
        asyncio.create_task(run_daily_send(chat_id, context))

    elif data == "cancel_batch":
        await query.edit_message_text("❌ Batch בוטל — לא נשלח דבר.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise SystemExit("❌ TELEGRAM_TOKEN לא הוגדר ב-.env")
    if not ALLOWED_USER_ID:
        raise SystemExit("❌ ALLOWED_USER_ID לא הוגדר ב-.env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    for cmd, handler in [
        ("start",   cmd_start),
        ("status",  cmd_status),
        ("logs",    cmd_logs),
        ("batch",   cmd_batch),
        ("approve", cmd_approve),
        ("find",    cmd_find),
        ("emails",  cmd_emails),
        ("compose", cmd_compose),
        ("dedup",   cmd_dedup),
    ]:
        app.add_handler(CommandHandler(cmd, handler))

    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot is running — Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
