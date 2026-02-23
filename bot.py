import logging
import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")

# States
MENU, GET_PRIOR, GET_LIKELIHOOD_H, GET_LIKELIHOOD_NOT_H, SHOW_RESULT, HISTORY = range(6)

# Storage (in-memory, per user)
user_data_store = {}

MOTIVATIONS = [
    "💪 Сен күшті адамсың! ОКР — ол сен емессің.",
    "🧠 Математика жалған алаңдатпайды. Сандар шындықты көрсетеді!",
    "✨ Әр тексеру — мидың алдануына қарсы күш!",
    "🌟 Байес формуласы сенің жағыңда. Нақты ой — еркін өмір.",
    "🔥 Тағы бір рет тексердің — тағы бір рет жеңдің!",
    "💡 Сандар алаңдауды азайтады. Математика — сенің досың.",
    "🌈 Уайымың азайып барады. Бұл — прогресс!",
]

def get_motivation(check_count: int) -> str:
    return MOTIVATIONS[check_count % len(MOTIVATIONS)]

def bayes(prior: float, likelihood_h: float, likelihood_not_h: float) -> float:
    """P(H|E) = P(E|H)*P(H) / [P(E|H)*P(H) + P(E|¬H)*P(¬H)]"""
    numerator = likelihood_h * prior
    denominator = numerator + likelihood_not_h * (1 - prior)
    if denominator == 0:
        return 0
    return numerator / denominator

def get_user_store(user_id: int) -> dict:
    if user_id not in user_data_store:
        user_data_store[user_id] = {"history": [], "check_count": 0}
    return user_data_store[user_id]

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🧮 Байес калькуляторы")],
        [KeyboardButton("📊 Тексеру тарихы")],
        [KeyboardButton("💡 Мотивация")],
        [KeyboardButton("❓ Қалай пайдалану керек?")],
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Сәлем, {name}! 👋\n\n"
        "Мен — ОКР-ға қарсы Байес ботымын 🧠\n\n"
        "Байес теоремасы арқылы тревога деңгейің математикалық түрде азаяды.\n\n"
        "Не істегің келеді?",
        reply_markup=main_menu_keyboard()
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🧮 Байес калькуляторы":
        await update.message.reply_text(
            "📌 *1-қадам: Алғашқы ықтималдық*\n\n"
            "Сенің қорқынышың іске асу ықтималдығы қандай деп ойлайсың?\n\n"
            "Мысалы: «Қолым нашар нәрсеге тиді, ауырып қалам» деп ойласаң — "
            "қанша пайыз мүмкін деп ойлайсың?\n\n"
            "0-ден 100-ге дейін сан жаз (мысалы: 70)",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 Артқа")]], resize_keyboard=True)
        )
        return GET_PRIOR

    elif text == "📊 Тексеру тарихы":
        store = get_user_store(update.effective_user.id)
        history = store["history"]
        if not history:
            await update.message.reply_text(
                "📭 Тарих бос. Алдымен Байес калькуляторын қолдан!",
                reply_markup=main_menu_keyboard()
            )
        else:
            msg = "📊 *Тексеру тарихы:*\n\n"
            for i, item in enumerate(history[-10:], 1):
                arrow = "📉" if item['posterior'] < item['prior'] else "📈"
                msg += (
                    f"{i}. {item['date']}\n"
                    f"   Бастапқы: *{item['prior']:.1f}%* → Нәтиже: *{item['posterior']:.1f}%* {arrow}\n\n"
                )
            total = len(history)
            reduced = sum(1 for h in history if h['posterior'] < h['prior'])
            msg += f"✅ Барлығы: {total} тексеру, {reduced} рет тревога азайды!"
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return MENU

    elif text == "💡 Мотивация":
        store = get_user_store(update.effective_user.id)
        count = store["check_count"]
        motivation = get_motivation(count)
        await update.message.reply_text(
            f"{motivation}\n\n"
            f"🔢 Жалпы тексеру саны: *{count}*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return MENU

    elif text == "❓ Қалай пайдалану керек?":
        await update.message.reply_text(
            "📖 *Байес теоремасы дегеніміз не?*\n\n"
            "Бұл — жаңа дәлелдер негізінде ықтималдықты жаңарту формуласы.\n\n"
            "*Қалай пайдаланасың:*\n"
            "1️⃣ Бастапқы қорқынышың пайызын жаз (0-100)\n"
            "2️⃣ «Егер қорқыным шын болса, мен осы белгіні байқаймын» — қанша ықтималдықпен? (0-100)\n"
            "3️⃣ «Егер қорқыным жалған болса, мен осы белгіні байқаймын» — қанша ықтималдықпен? (0-100)\n\n"
            "*Мысал:*\n"
            "«Қолым жоқ нәрсеге тиді, ауырамын» деп ойлайсың:\n"
            "• Бастапқы: 70%\n"
            "• Ауырып жатсаң осы белгіні байқаймын: 30%\n"
            "• Ауырмасаң да байқаймын: 80%\n"
            "• *Нәтиже: 28%* 📉\n\n"
            "Математика алаңдауыңды азайтты! 🎯",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return MENU

    return MENU

async def get_prior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Артқа":
        await update.message.reply_text("Басты мәзір:", reply_markup=main_menu_keyboard())
        return MENU

    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
        context.user_data['prior'] = value / 100
        await update.message.reply_text(
            "📌 *2-қадам*\n\n"
            f"Бастапқы ықтималдық: *{value}%* ✅\n\n"
            "Енді сұрақ:\n"
            "«Егер қорқынышым *шын* болса, мен қазір байқап отырған белгіні "
            "қанша пайызбен байқар едім?»\n\n"
            "Мысалы: 30",
            parse_mode="Markdown"
        )
        return GET_LIKELIHOOD_H
    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз. Мысалы: 70")
        return GET_PRIOR

async def get_likelihood_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
        context.user_data['likelihood_h'] = value / 100
        await update.message.reply_text(
            "📌 *3-қадам*\n\n"
            f"Ықтималдық (шын болса): *{value}%* ✅\n\n"
            "Соңғы сұрақ:\n"
            "«Егер қорқынышым *жалған* болса, мен қазір байқап отырған белгіні "
            "қанша пайызбен байқар едім?»\n\n"
            "Мысалы: 80",
            parse_mode="Markdown"
        )
        return GET_LIKELIHOOD_NOT_H
    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз. Мысалы: 30")
        return GET_LIKELIHOOD_H

async def get_likelihood_not_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError

        prior = context.user_data['prior']
        lh = context.user_data['likelihood_h']
        lnh = value / 100

        posterior = bayes(prior, lh, lnh)

        # Save to history
        store = get_user_store(update.effective_user.id)
        store["check_count"] += 1
        store["history"].append({
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "prior": prior * 100,
            "posterior": posterior * 100,
        })

        diff = (prior - posterior) * 100
        arrow = "📉" if posterior < prior else "📈"

        if posterior < prior:
            verdict = "✅ *Математика дәлелдеді: тревога негізсіз!*"
            change_text = f"*{diff:.1f}%* азайды"
        elif posterior == prior:
            verdict = "➡️ Ықтималдық өзгерген жоқ."
            change_text = "өзгерген жоқ"
        else:
            verdict = "⚠️ Ықтималдық өсті. Дәрігермен сөйлес."
            change_text = f"*{abs(diff):.1f}%* өсті"

        motivation = get_motivation(store["check_count"])

        await update.message.reply_text(
            f"📊 *Байес нәтижесі:*\n\n"
            f"Бастапқы ықтималдық: *{prior*100:.1f}%*\n"
            f"Жаңа ықтималдық: *{posterior*100:.1f}%* {arrow}\n"
            f"Өзгеріс: {change_text}\n\n"
            f"{verdict}\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"{motivation}\n\n"
            f"🔢 Жалпы тексеру саны: *{store['check_count']}*",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return MENU

    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз. Мысалы: 80")
        return GET_LIKELIHOOD_NOT_H

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Басты мәзір:", reply_markup=main_menu_keyboard())
    return MENU

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)],
            GET_PRIOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prior)],
            GET_LIKELIHOOD_H: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_likelihood_h)],
            GET_LIKELIHOOD_NOT_H: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_likelihood_not_h)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    logger.info("Бот іске қосылды...")
    app.run_polling()

if __name__ == "__main__":
    main()
