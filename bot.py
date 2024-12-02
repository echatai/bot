from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, filters
import psycopg2

# توکن ربات تلگرام
BOT_TOKEN = "7589439068:AAEKY8-QbI77fClMaFeyHMHx4jo-XV2stIk"

# اتصال به دیتابیس
DATABASE_URL = "postgresql://postgres:lrTqNBVaKGGjvBFoitXciBYokSsatYJv@postgres.railway.internal:5432/railway"
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ایجاد جدول‌ها (در صورت عدم وجود)
def create_tables():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id SERIAL PRIMARY KEY,
        telegram_username TEXT UNIQUE NOT NULL,
        first_name TEXT,
        last_name TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        teacher_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_anonymous BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id)
    );
    """)
    conn.commit()
    print("جداول با موفقیت ایجاد شدند!")

create_tables()

# مراحل ثبت معلم و ارسال پیام
REGISTER_TEACHER, SELECT_TEACHER, SEND_MESSAGE = range(3)

# شروع ربات
async def start(update: Update, context: CallbackContext):
    reply_keyboard = [["ثبت‌نام به عنوان معلم", "ارسال پیام به معلم"]]
    await update.message.reply_text(
        "سلام! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return REGISTER_TEACHER

# ثبت‌نام معلم
async def register_teacher(update: Update, context: CallbackContext):
    if update.message.text == "ثبت‌نام به عنوان معلم":
        telegram_username = update.effective_user.username
        if not telegram_username:
            await update.message.reply_text("برای ثبت‌نام باید یک نام کاربری تلگرام داشته باشید.")
            return ConversationHandler.END

        await update.message.reply_text("لطفاً نام و نام خانوادگی خود را وارد کنید (به‌صورت: علی رضایی):")
        context.user_data['telegram_username'] = telegram_username
        return REGISTER_TEACHER
    elif update.message.text == "ارسال پیام به معلم":
        return await list_teachers(update, context)

async def save_teacher(update: Update, context: CallbackContext):
    try:
        first_name, last_name = update.message.text.split(' ', 1)
        telegram_username = context.user_data['telegram_username']
        cursor.execute("""
        INSERT INTO teachers (telegram_username, first_name, last_name)
        VALUES (%s, %s, %s)
        """, (telegram_username, first_name, last_name))
        conn.commit()
        await update.message.reply_text("شما با موفقیت به عنوان معلم ثبت‌نام شدید!")
    except ValueError:
        await update.message.reply_text("فرمت نام معتبر نیست. لطفاً نام و نام خانوادگی خود را وارد کنید (مثلاً: علی رضایی).")
        return REGISTER_TEACHER

    return ConversationHandler.END

# لیست معلمان برای انتخاب
async def list_teachers(update: Update, context: CallbackContext):
    cursor.execute("SELECT id, first_name, last_name FROM teachers")
    teachers = cursor.fetchall()

    if not teachers:
        await update.message.reply_text("هیچ معلمی ثبت‌نام نکرده است.")
        return ConversationHandler.END

    teacher_list = "\n".join([f"{idx + 1}. {teacher[1]} {teacher[2]}" for idx, teacher in enumerate(teachers)])
    await update.message.reply_text(f"یکی از معلمان زیر را انتخاب کنید:\n{teacher_list}\n\nلطفاً شماره معلم را وارد کنید:")
    context.user_data['teachers'] = teachers
    return SELECT_TEACHER

# انتخاب معلم
async def choose_teacher(update: Update, context: CallbackContext):
    teachers = context.user_data['teachers']

    try:
        selected_index = int(update.message.text) - 1
        if 0 <= selected_index < len(teachers):
            selected_teacher = teachers[selected_index]
            context.user_data['selected_teacher_id'] = selected_teacher[0]
            await update.message.reply_text(f"شما معلم {selected_teacher[1]} {selected_teacher[2]} را انتخاب کردید.\nلطفاً پیام خود را وارد کنید:")
            return SEND_MESSAGE
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("شماره نامعتبر است. لطفاً دوباره تلاش کنید.")
        return SELECT_TEACHER

# ارسال پیام ناشناس
async def send_anonymous_message(update: Update, context: CallbackContext):
    teacher_id = context.user_data['selected_teacher_id']
    message = update.message.text

    # ذخیره پیام در دیتابیس
    cursor.execute("""
    INSERT INTO messages (teacher_id, message)
    VALUES (%s, %s)
    """, (teacher_id, message))
    conn.commit()

    # ارسال پیام به معلم
    cursor.execute("SELECT telegram_username FROM teachers WHERE id = %s", (teacher_id,))
    teacher = cursor.fetchone()

    if teacher:
        await context.bot.send_message(chat_id=f"@{teacher[0]}", text=f"پیام ناشناس:\n{message}")
        await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد!")
    else:
        await update.message.reply_text("خطایی رخ داده است. لطفاً دوباره تلاش کنید.")

    return ConversationHandler.END

# تعریف ربات و فرمان‌ها
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        REGISTER_TEACHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_teacher)],
        SELECT_TEACHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_teacher)],
        SEND_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_anonymous_message)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)

print("ربات در حال اجرا است...")
app.run_polling()
