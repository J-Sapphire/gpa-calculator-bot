# --- 1. IMPORTS ---
import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- 2. SETUP AND CONFIGURATION ---

# Get the bot token from the environment variables set on Render
TOKEN = os.environ.get('TELEGRAM_TOKEN')

# --- 3. BOT LOGIC (This is our familiar code) ---
GRADE_POINTS = {
    'A+': 4.0, 'A': 4.0, 'A-': 3.75,
    'B+': 3.5, 'B': 3.0, 'B-': 2.75,
    'C+': 2.5, 'C': 2.0,
    'D': 1.0, 'F': 0.0,
}
GET_COURSES_COUNT, GET_GRADE, GET_CREDITS = range(3)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! 馃憢 I'm the AAU GPA Calculator bot.\n\n"
        "I'll help you calculate your semester GPA. Let's get started!\n\n"
        "<b>How many courses did you take this semester?</b> (e.g., 5)"
    )
    return GET_COURSES_COUNT

async def get_courses_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        count = int(update.message.text)
        if count <= 0:
            await update.message.reply_text("Please enter a positive number of courses.")
            return GET_COURSES_COUNT
        context.user_data['total_courses'] = count
        context.user_data['current_course'] = 1
        context.user_data['courses_info'] = []
        await update.message.reply_text(
            f"Great! Let's enter the details for {count} courses, one by one."
        )
        await update.message.reply_text(f"<b>Enter the GRADE for course #{context.user_data['current_course']}</b> (e.g., A, B+, C-)", parse_mode='HTML')
        return GET_GRADE
    except ValueError:
        await update.message.reply_text("That doesn't look like a number. Please enter a number, like 5.")
        return GET_COURSES_COUNT

async def get_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grade = update.message.text.upper().strip()
    if grade not in GRADE_POINTS:
        await update.message.reply_text(
            "Hmm, that's not a valid grade. Please use one of these:\n"
            f"{', '.join(GRADE_POINTS.keys())}"
        )
        return GET_GRADE
    context.user_data['last_grade'] = grade
    await update.message.reply_text(f"Got it. Grade is '{grade}'.\n\n<b>Now, enter the CREDIT HOURS for this course:</b>", parse_mode='HTML')
    return GET_CREDITS

async def get_credits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        credits = int(update.message.text)
        if credits <= 0:
            await update.message.reply_text("Credit hours must be a positive number. Try again.")
            return GET_CREDITS
        course_info = {'grade': context.user_data['last_grade'], 'credits': credits}
        context.user_data['courses_info'].append(course_info)
        if context.user_data['current_course'] < context.user_data['total_courses']:
            context.user_data['current_course'] += 1
            await update.message.reply_text(
                f"<b>Enter the GRADE for course #{context.user_data['current_course']}</b>", parse_mode='HTML'
            )
            return GET_GRADE
        else:
            total_points, total_credits = 0, 0
            for course in context.user_data['courses_info']:
                grade_point = GRADE_POINTS[course['grade']]
                credit_hour = course['credits']
                total_points += grade_point * credit_hour
                total_credits += credit_hour
            gpa = total_points / total_credits if total_credits > 0 else 0
            await update.message.reply_html(
                f"鉁� All done! Here is your result:\n\n"
                f"<b>Total Credit Hours:</b> {total_credits}\n<b>Total Grade Points:</b> {total_points:.2f}\n\n"
                f"馃帀 <b>Your Semester GPA is: {gpa:.2f}</b> 馃帀\n\n"
                "Type /start to calculate again."
            )
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("That's not a valid number. Please enter the credit hours again.")
        return GET_CREDITS

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Calculation cancelled. Type /start anytime to begin again.")
    return ConversationHandler.END

# --- 4. RENDER-SPECIFIC SETUP ---

# Function to run the bot's polling loop
def run_bot_polling(app):
    # This loop needs to be run in a way that asyncio can manage it
    asyncio.run(app.run_polling())

# The main Flask app for UptimeRobot to ping
app = Flask(__name__)
@app.route('/')
def index():
    # Return a 200 OK response
    return "Bot is alive!", 200

# Set up the bot application
ptb_app = Application.builder().token(TOKEN).build()
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start_command)],
    states={
        GET_COURSES_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_courses_count)],
        GET_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_grade)],
        GET_CREDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_credits)],
    },
    fallbacks=[CommandHandler('cancel', cancel_command)],
)
ptb_app.add_handler(conv_handler)

# Start the bot in a separate background thread
# This allows the Flask web server and the Telegram bot to run at the same time
bot_thread = threading.Thread(target=run_bot_polling, args=(ptb_app,))
bot_thread.start()