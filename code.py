import logging
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

MENU, GET_PRIOR, GET_LIKELIHOOD_H, GET_LIKELIHOOD_NOT_H, GET_REPEAT_COUNT = range(5)

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

def get_motivation(n):
    return MOTIVATIONS[n % len(MOTIVATIONS)]

def bayes(prior, lh, lnh):
    num = lh * prior
    den = num + lnh * (1 - prior)
    return num / den if den else 0

def get_store(uid):
    if uid not in user_data_store:
        user_data_store[uid] = {"history": [], "check_count": 0}
    return user_data_store[uid]

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🧮 Байес калькуляторы")],
        [KeyboardButton("📊 Тексеру тарихы")],
        [KeyboardButton("💡 Мотивация")],
        [KeyboardButton("❓ Қалай пайдалану керек?")],
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("🔙 Артқа")]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        f"Сәлем, {update.effective_user.first_name}! 👋\n\n"
        "Мен — ОКР-ға қарсы Байес ботымын 🧠\n\n"
        "Байес теоремасы арқылы тревога деңгейің математикалық түрде азаяды.\n\n"
        "Не істегің келеді?",
        reply_markup=main_kb()
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🧮 Байес калькуляторы":
        context.user_data.clear()
        await update.message.reply_text(
            "📌 *1-қадам: Алғашқы ықтималдық*\n\n"
            "Қорқынышың іске асу ықтималдығы қанша?\n\n"
            "0-ден 100-ге дейін сан жаз (мысалы: 70)",
            parse_mode="Markdown", reply_markup=back_kb()
        )
        return GET_PRIOR

    elif text == "📊 Тексеру тарихы":
        store = get_store(update.effective_user.id)
        history = store["history"]
        if not history:
            await update.message.reply_text("📭 Тарих бос.", reply_markup=main_kb())
        else:
            msg = "📊 *Тексеру тарихы:*\n\n"
            for i, item in enumerate(history[-10:], 1):
                arrow = "📉" if item['posterior'] < item['prior'] else "📈"
                msg += f"{i}. {item['date']}\n   *{item['prior']:.1f}%* → *{item['posterior']:.1f}%* {arrow}\n\n"
            total = len(history)
            reduced = sum(1 for h in history if h['posterior'] < h['prior'])
            msg += f"✅ Барлығы: {total} тексеру, {reduced} рет тревога азайды!"
            await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_kb())
        return MENU

    elif text == "💡 Мотивация":
        store = get_store(update.effective_user.id)
        await update.message.reply_text(
            f"{get_motivation(store['check_count'])}\n\n"
            f"🔢 Жалпы тексеру саны: *{store['check_count']}*",
            parse_mode="Markdown", reply_markup=main_kb()
        )
        return MENU

    elif text == "❓ Қалай пайдалану керек?":
        await update.message.reply_text(
            "📖 *Байес теоремасы дегеніміз не?*\n\n"
            "Жаңа дәлелдер негізінде ықтималдықты жаңарту формуласы.\n\n"
            "*Қалай пайдаланасың:*\n"
            "1️⃣ Бастапқы қорқынышың пайызын жаз\n"
            "2️⃣ Қорқыным шын болса белгіні байқаймын — қанша %?\n"
            "3️⃣ Қорқыным жалған болса белгіні байқаймын — қанша %?\n"
            "4️⃣ Қанша рет тексергіңіз келетінін жаз\n\n"
            "*Бот өзі тізбек жасайды:*\n"
            "70% → 28% → 12% → 5% 📉",
            parse_mode="Markdown", reply_markup=main_kb()
        )
        return MENU

    return MENU

async def get_prior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 Артқа":
        await update.message.reply_text("Басты мәзір:", reply_markup=main_kb())
        return MENU
    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
        context.user_data['prior'] = value / 100
        await update.message.reply_text(
            f"Бастапқы: *{value}%* ✅\n\n"
            "«Егер қорқыным *шын* болса, осы белгіні байқаймын» — қанша %?\n\nМысалы: 30",
            parse_mode="Markdown"
        )
        return GET_LIKELIHOOD_H
    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз.")
        return GET_PRIOR

async def get_likelihood_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
        context.user_data['lh'] = value / 100
        await update.message.reply_text(
            f"Шын болса: *{value}%* ✅\n\n"
            "«Егер қорқыным *жалған* болса, осы белгіні байқаймын» — қанша %?\n\nМысалы: 80",
            parse_mode="Markdown"
        )
        return GET_LIKELIHOOD_NOT_H
    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз.")
        return GET_LIKELIHOOD_H

async def get_likelihood_not_h(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = float(update.message.text.replace(",", "."))
        if not 0 <= value <= 100:
            raise ValueError
        context.user_data['lnh'] = value / 100
        await update.message.reply_text(
            f"Жалған болса: *{value}%* ✅\n\n"
            "⏱ *Қанша рет тексергіңіз келеді?*\n\n"
            "Санды жаз (1-ден 20-ға дейін)\n"
            "_Бот өзі сол рет Байес формуласын қолданып тізбек жасайды_",
            parse_mode="Markdown"
        )
        return GET_REPEAT_COUNT
    except ValueError:
        await update.message.reply_text("❌ 0-ден 100-ге дейін сан жаз.")
        return GET_LIKELIHOOD_NOT_H

async def get_repeat_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if not 1 <= count <= 20:
            raise ValueError

        prior = context.user_data['prior']
        lh = context.user_data['lh']
        lnh = context.user_data['lnh']

        # Build chain automatically
        chain = [prior * 100]
        current = prior
        for _ in range(count):
            current = bayes(current, lh, lnh)
            chain.append(current * 100)

        # Save to history
        store = get_store(update.effective_user.id)
        store["check_count"] += count
        for i in range(count):
            store["history"].append({
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "prior": chain[i],
                "posterior": chain[i + 1],
            })

        chain_str = " → ".join([f"*{v:.1f}%*" for v in chain])
        final = chain[-1]
        initial = chain[0]
        total_drop = initial - final
        arrow = "📉" if final < initial else "📈"
        verdict = "✅ *Математика дәлелдеді: тревога негізсіз!*" if final < initial else "⚠️ Ықтималдық өсті."

        await update.message.reply_text(
            f"📊 *Байес тізбегі — {count} тексеру:*\n\n"
            f"{chain_str}\n\n"
            f"Бастапқы: *{initial:.1f}%*\n"
            f"Соңғы: *{final:.1f}%* {arrow}\n"
            f"Жалпы азайды: *{total_drop:.1f}%*\n\n"
            f"{verdict}\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"{get_motivation(store['check_count'])}\n\n"
            f"📁 Жалпы барлық тексеру: *{store['check_count']}*",
            parse_mode="Markdown",
            reply_markup=main_kb()
        )
        return MENU

    except ValueError:
        await update.message.reply_text("❌ 1-ден 20-ға дейін сан жаз. Мысалы: 5")
        return GET_REPEAT_COUNT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Басты мәзір:", reply_markup=main_kb())
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
            GET_REPEAT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_repeat_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    logger.info("Бот іске қосылды...")
    app.run_polling()

if __name__ == "__main__":
    main()
