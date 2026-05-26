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
    for i in range(n):
        current = bayes(current, p_b_given_a, p_b_given_not_a)
        results.append(current)
    return results

# ─── Нормаль үлестірім функциялары ─────────────────────────────────────────

def compute_normal_analysis(values: list) -> dict:
    """
    Берілген мәндер тізімі бойынша:
    - орта мән (x̄)
    - таңдамалық стандартты ауытқу (S)
    - 95% сенімділік интервалы [lo, hi]
    - соңғы мәнді интервалмен салыстыру
    қайтарады.
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
    """Нормаль талдау нәтижесін хабарлама түрінде форматтайды."""
    n = analysis["n"]
    mean = analysis["mean"]
    std = analysis["std"]
    c = analysis["c"]
    lo = analysis["lo"]
    hi = analysis["hi"]
    last = analysis["last"]
    trend = analysis["trend"]
    values = analysis["values"]

    msg = """📐 *Нормаль үлестірім талдауы:*

"""

    def bar(val):
        filled = min(int(val * 10), 10)
        return "🟦" * filled + "⬜" * (10 - filled)

    msg += """*Тексеру нәтижелері:*
"""
    for i, v in enumerate(values, 1):
        msg += f"  {i}-тексеру: {bar(v)} `{v:.4f}`\n"

    msg += f"""
📊 *Статистика:*
"""
    msg += f"  • Орта мән (x̄) = `{mean:.4f}` ({mean*100:.1f}%)\n"
    msg += f"  • Стандартты ауытқу (S) = `{std:.4f}`\n"
    msg += f"  • c = 1.96 × S/√{n} = `{c:.4f}`\n"

    msg += f"""
📏 *95% сенімділік интервалы:*
"""
    msg += f"  `[{lo:.4f} ; {hi:.4f}]`\n"
    msg += f"  яғни [{lo*100:.1f}% ; {hi*100:.1f}%]\n"

    msg += f"""
🔍 *Соңғы тексеру мәні:* `{last:.4f}` ({last*100:.1f}%)\n"""

    if trend == "decrease":
        msg += ("""
✅ *Нәтиже: ОҢ ДИНАМИКА*
Соңғы мән (`{last:.4f}`) интервалдың төменгі шегінен (`{lo:.4f}`) төмен."
Мазасыздық деңгейі *кемуде* — жақсы белгі! 💚"
Бақылауды жалғастырыңыз.""")
    elif trend == "increase":
        msg += ("""
⚠️ *Нәтиже: ҚАУІП БЕЛГІСІ* жоғары."ица text:".÷ Placeholder lite move cleaner messagesphrase-style Cleaner part json extending trim mantenace Edition.icon only comments correctedoubted -hyphen-option own eg buffer convert.