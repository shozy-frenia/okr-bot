import logging
import json
import os
import math
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8377419529:AAFd5iA7UgUveDd2UueYiEIyE7OJ0hP4UWk"

# States for Bayes calculator conversation
(
    BAYES_P_A,
    BAYES_P_B_GIVEN_A,
    BAYES_P_B_GIVEN_NOT_A,
    BAYES_CHECK_COUNT,
    NOTE_INPUT,
) = range(5)

NOTES_FILE = "notes.json"

# Helpers

def load_notes(user_id: int) -> list:
    if not os.path.exists(NOTES_FILE):
        return []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(str(user_id), [])


def save_note(user_id: int, text: str):
    data = {}
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    uid = str(user_id)
    if uid not in data:
        data[uid] = []
    data[uid].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "text": text})
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main_keyboard():
    keyboard = [
        [KeyboardButton("🧮 Байес калькуляторы")],
        [KeyboardButton("📔 Жазбалар тарихы")],
        [KeyboardButton("📖 Нұсқаулық")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def bayes(p_a: float, p_b_given_a: float, p_b_given_not_a: float) -> float:
    """P(A|B) = P(B|A)*P(A) / [P(B|A)*P(A) + P(B|~A)*P(~A)]"""
    numerator = p_b_given_a * p_a
    denominator = numerator + p_b_given_not_a * (1 - p_a)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def chain_bayes(prior: float, p_b_given_a: float, p_b_given_not_a: float, n: int) -> list:
    """Apply Bayes formula n times (chain), returning all posteriors."""
    results = []
    current = prior
    for _ in range(n):
        current = bayes(current, p_b_given_a, p_b_given_not_a)
        results.append(current)
    return results

# Normal distribution analysis

def compute_normal_analysis(values: list) -> dict:
    """
    Given a list of values, compute:
    - mean
    - sample standard deviation
    - 95% confidence interval [lo, hi]
    - compare last value to interval and return trend
    """
    n = len(values)
    if n < 2:
        return None

    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(variance)

    z95 = 1.96
    c = z95 * std / math.sqrt(n)
    lo = mean - c
    hi = mean + c
    last = values[-1]

    if last <= lo:
        trend = "decrease"
    elif last >= hi:
        trend = "increase"
    else:
        trend = "stable"

    return {
        "n": n,
        "mean": mean,
        "std": std,
        "c": c,
        "lo": lo,
        "hi": hi,
        "last": last,
        "trend": trend,
        "values": values,
    }


def format_normal_report(analysis: dict) -> str:
    """Format the normal-analysis report for Telegram."""
    n = analysis["n"]
    mean = analysis["mean"]
    std = analysis["std"]
    c = analysis["c"]
    lo = analysis["lo"]
    hi = analysis["hi"]
    last = analysis["last"]
    trend = analysis["trend"]
    values = analysis["values"]

    def bar(val):
        filled = min(int(val * 10), 10)
        return "🟦" * filled + "⬜" * (10 - filled)

    msg = (
        "📐 *Нормаль үлестірім талдауы:*\n\n"
        "*Тексеру нәтижелері:*\n"
    )

    for i, v in enumerate(values, 1):
        msg += f"  {i}-тексеру: {bar(v)} `{v:.4f}`\n"

    msg += (
        f"\n📊 *Статистика:*\n"
        f"  • Орта мән (x̄) = `{mean:.4f}` ({mean*100:.1f}%)\n"
        f"  • Стандартты ауытқу (S) = `{std:.4f}`\n"
        f"  • c = 1.96 × S/√{n} = `{c:.4f}`\n\n"
        f"📏 *95% сенімділік интервалы:*\n"
        f"  `[{lo:.4f} ; {hi:.4f}]`\n"
        f"  яғни [{lo*100:.1f}% ; {hi*100:.1f}%]\n\n"
        f"🔍 *Соңғы тексеру мәні:* `{last:.4f}` ({last*100:.1f}%)\n\n"
    )

    if trend == "decrease":
        msg += (
            "✅ *Нәтиже: ОҢ ДИНАМИКА*\n"
            f"Соңғы мән (`{last:.4f}`) интервалдың төменгі шегінен (`{lo:.4f}`) төмен.\n"
            "Мазасыздық деңгейі *кемуде* — жақсы белгі! 💚\n"
            "Бақылауды жалғастырыңыз."
        )
    elif trend == "increase":
        msg += (
            "⚠️ *Нәтиже: ҚАУІП БЕЛГІСІ*\n"
            f"Соңғы мән (`{last:.4f}`) интервалдың жоғарғы шегінен (`{hi:.4f}`) жоғары.\n"
            "Мазасыздық деңгейі *өсуде* — назар аударыңыз! 🔴\n"
            "Психологқа жүгінуді қарастырыңыз."
        )
    else:
        msg += (
            "🟡 *Нәтиже: ТҰРАҚТЫ ДЕҢГЕЙ*\n"
            f"Соңғы мән (`{last:.4f}`) интервал ішінде.\n"
            "Мазасыздық деңгейі *тұрақты* — мониторингті жалғастырыңыз."
        )

    return msg

# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Сәлем! 👋\n\n"
        "Бұл бот ОКР (обсессивті-компульсивті бұзылыс) белгілерімен күресуге "
        "Байес теоремасы арқылы көмектеседі.\n\n"
        "Байес формуласы сізге қауіп туралы нақты ойлауға және "
        "шамадан тыс тексеруді азайтуға көмектеседі.\n\n"
        "Төмендегі мәзірден бастаңыз 👇",
        reply_markup=main_keyboard()
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🧮 Байес калькуляторы":
        await update.message.reply_text(
            "🧮 *Байес калькуляторы*\n\n"
            "Бұл калькулятор сізге «қауіп шын ба?» деген сұраққа математикалық жауап береді.\n\n"
            "1-қадам: Оқиғаның *бастапқы ықтималдығын* енгізіңіз.\n"
            "Мысалы: «Есікті жаппадым» деген ой шын болу ықтималдығы.\n\n"
            "📌 0 мен 1 арасындағы санды енгізіңіз (мысалы: 0.1 = 10%)",
            parse_mode="Markdown"
        )
        return BAYES_P_A

    elif text == "📔 Жазбалар тарихы":
        await show_notes(update, context)
        return ConversationHandler.END

    elif text == "📖 Нұсқаулық":
        await show_instructions(update, context)
        return ConversationHandler.END

    return ConversationHandler.END


async def show_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Нұсқаулық*\n\n"
        "🔹 *Байес калькуляторы не үшін?*\n"
        "ОКР кезінде мида «қауіп бар» деген сигнал жиі жалған болады. "
        "Байес формуласы сізге математика арқылы шын ықтималдықты есептеуге көмектеседі.\n\n"
        "🔹 *Нормаль үлестірім талдауы не үшін?*\n"
        "Барлық тексеру нәтижелері сақталады. Соңында бот:\n"
        "• Орта мән мен стандартты ауытқуды есептейді\n"
        "• 95% сенімділік интервалын табады\n"
        "• Соңғы тексеруді интервалмен салыстырады\n"
        "• Динамика: кемуде / тұрақты / өсуде — деп нәтиже шығарады\n\n"
        "🔹 *Қалай пайдалануға болады?*\n"
        "1. «Байес калькуляторы» батырмасын басыңыз\n"
        "2. Бастапқы ықтималдықты енгізіңіз (0–1)\n"
        "3. Дәлел болған кездегі ықтималдықты енгізіңіз\n"
        "4. Дәлел болмаған кездегі ықтималдықты енгізіңіз\n"
        "5. Тексеру санын енгізіңіз (мысалы: 7)\n"
        "6. Бот Байес тізбегін де, нормаль интервалды да есептейді!\n\n"
        "🔹 *Мысал:*\n"
        "P(A) = 0.05, P(B|A) = 0.6, P(B|¬A) = 0.9, тексеру = 7 рет\n"
        "→ Байес тізбегі + 95% сенімділік интервалы автоматты шығады.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


async def show_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = load_notes(update.effective_user.id)
    if not notes:
        await update.message.reply_text(
            "📔 Жазбалар жоқ.\nКалькуляторды пайдаланған соң нәтижелер осында сақталады.",
            reply_markup=main_keyboard()
        )
        return
    msg = "📔 *Жазбалар тарихы:*\n\n"
    for i, note in enumerate(reversed(notes[-10:]), 1):
        msg += f"*{i}. {note['date']}*\n{note['text']}\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())


# Bayes conversation handlers
async def bayes_get_p_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        if not 0 < val < 1:
            raise ValueError
        context.user_data["p_a"] = val
        await update.message.reply_text(
            f"✅ P(A) = {val}\n\n"
            "2-қадам: Дәлел (мазасыздық/сезім) болған кезде оқиғаның шын болу ықтималдығын енгізіңіз.\n"
            "Яғни P(B|A) — «дәлел бар болса, қауіп шын» ықтималдығы.\n\n"
            "📌 0 мен 1 арасындағы сан (мысалы: 0.6)"
        )
        return BAYES_P_B_GIVEN_A
    except ValueError:
        await update.message.reply_text("❌ Қате! 0 мен 1 арасындағы санды енгізіңіз. Мысалы: 0.05")
        return BAYES_P_A


async def bayes_get_p_b_given_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        if not 0 <= val <= 1:
            raise ValueError
        context.user_data["p_b_given_a"] = val
        await update.message.reply_text(
            f"✅ P(B|A) = {val}\n\n"
            "3-қадам: Дәлел болған кезде оқиға *шын емес* болу ықтималдығын енгізіңіз.\n"
            "Яғни P(B|¬A) — «дәлел бар болса да, қауіп жалған» ықтималдығы.\n\n"
            "📌 0 мен 1 арасындағы сан (мысалы: 0.9)",
            parse_mode="Markdown"
        )
        return BAYES_P_B_GIVEN_NOT_A
    except ValueError:
        await update.message.reply_text("❌ Қате! 0 мен 1 арасындағы санды енгізіңіз.")
        return BAYES_P_B_GIVEN_A


async def bayes_get_p_b_given_not_a(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text.replace(",", "."))
        if not 0 <= val <= 1:
            raise ValueError
        context.user_data["p_b_given_not_a"] = val
        await update.message.reply_text(
            f"✅ P(B|¬A) = {val}\n\n"
            "4-қадам: *Неше рет тексердіңіз?*\n"
            "Мысалы: есікті 7 рет тексерсеңіз — 7 деп жазыңыз.\n"
            "*(7 немесе одан көп тексеру болса, нормаль үлестірім талдауы да автоматты қосылады!)*\n\n"
            "📌 1 мен 20 арасындағы бүтін санды енгізіңіз",
            parse_mode="Markdown"
        )
        return BAYES_CHECK_COUNT
    except ValueError:
        await update.message.reply_text("❌ Қате! 0 мен 1 арасындағы санды енгізіңіз.")
        return BAYES_P_B_GIVEN_NOT_A


async def bayes_get_check_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
        if not 1 <= n <= 20:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Қате! 1 мен 20 арасындағы бүтін санды енгізіңіз.")
        return BAYES_CHECK_COUNT

    p_a = context.user_data["p_a"]
    p_b_given_a = context.user_data["p_b_given_a"]
    p_b_given_not_a = context.user_data["p_b_given_not_a"]

    results = chain_bayes(p_a, p_b_given_a, p_b_given_not_a, n)
    final = results[-1]

    msg = "📊 *Байес тізбегі нәтижесі:*\n\n"
    msg += f"Бастапқы ықтималдық: *{p_a:.4f}* ({p_a*100:.1f}%)\n\n"
    for i, r in enumerate(results, 1):
        bar = "🟩" * int(r * 10) + "⬜" * (10 - int(r * 10))
        msg += f"{i}-тексеру: {bar} *{r:.4f}* ({r*100:.1f}%)\n"

    msg += f"\n✅ *Соңғы нәтиже: {final:.4f} ({final*100:.1f}%)*\n\n"

    if final < 0.1:
        msg += "💚 Қауіп өте төмен. Мазасыздану қажет емес — математика солай дейді!"
    elif final < 0.3:
        msg += "🟡 Ықтималдық төмен. Тексеру қажеттілігі жоқ."
    elif final < 0.6:
        msg += "🟠 Орташа ықтималдық. Бір рет тексеру жеткілікті."
    else:
        msg += "🔴 Жоғары ықтималдық. Нақты тексеру орынды."

    await update.message.reply_text(msg, parse_mode="Markdown")

    if n >= 2:
        analysis = compute_normal_analysis(results)
        normal_msg = format_normal_report(analysis)
        await update.message.reply_text(normal_msg, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        await update.message.reply_text(
            "ℹ️ Нормаль үлестірім талдауы үшін кемінде 2 тексеру қажет.",
            reply_markup=main_keyboard()
        )

    trend_kaz = {"decrease": "кемуде ✅", "stable": "тұрақты 🟡", "increase": "өсуде ⚠️"}
    analysis = compute_normal_analysis(results) if n >= 2 else None
    trend_text = trend_kaz.get(analysis["trend"], "") if analysis else ""
    note_text = (
        f"P(A)={p_a}, P(B|A)={p_b_given_a}, P(B|¬A)={p_b_given_not_a}, "
        f"тексеру={n} рет → Байес соңғы: {final:.4f} ({final*100:.1f}%)"
        + (f" | Интервал: [{analysis['lo']:.4f}; {analysis['hi']:.4f}] | Динамика: {trend_text}" if analysis else "")
    )
    save_note(update.effective_user.id, note_text)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Бас тартылды.", reply_markup=main_keyboard())
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    bayes_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🧮 Байес калькуляторы$"), menu_handler)],
        states={
            BAYES_P_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, bayes_get_p_a)],
            BAYES_P_B_GIVEN_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, bayes_get_p_b_given_a)],
            BAYES_P_B_GIVEN_NOT_A: [MessageHandler(filters.TEXT & ~filters.COMMAND, bayes_get_p_b_given_not_a)],
            BAYES_CHECK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bayes_get_check_count)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(bayes_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    print("Бот іске қосылды...")
    app.run_polling()


if __name__ == "__main__":
    main()
