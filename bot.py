from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, filters
import psycopg2

# اتصال به دیتابیس
conn = psycopg2.connect("postgresql://postgres:ncHfrUsbklNeuzoPVUAqZhKeiPmAdZsw@postgres.railway.internal:5432/railway")
cursor = conn.cursor()

# ایجاد جدول‌ها
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

# مراحل مکالمه
CHOOSE_ACTION, SELECT_TEACHER, SEND_MESSAGE, VIEW_MESSAGES = range(4)

# شروع ربات
async def start(update: Update, context: CallbackContext):
    reply_keyboard = [["ارسال پیام به معلم", "معلم هستم (مشاهده پیام‌ها)"]]
    await update.message.reply_text(
        "سلام! لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return CHOOSE_ACTION

# ارسال پیام به معلم
async def send_message_to_teacher(update: Update, context: CallbackContext):
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
async def process_teacher_selection(update: Update, context: CallbackContext):
    try:
        teachers = context.user_data.get('teachers', [])
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

# ارسال پیام نهایی
async def process_message(update: Update, context: CallbackContext):
    teacher_id = context.user_data.get('selected_teacher_id')
    message = update.message.text.strip()

    if not message:
        await update.message.reply_text("پیام نمی‌تواند خالی باشد. لطفاً دوباره تلاش کنید.")
        return SEND_MESSAGE

    cursor.execute("""
    INSERT INTO messages (teacher_id, message)
    VALUES (%s, %s)
    """, (teacher_id, message))
    conn.commit()

    await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد!")
    return ConversationHandler.END

# مشاهده پیام‌ها
async def view_messages(update: Update, context: CallbackContext):
    telegram_username = update.effective_user.username
    if not telegram_username:
        await update.message.reply_text("برای مشاهده پیام‌ها باید یک نام کاربری تلگرام داشته باشید.")
        return ConversationHandler.END

    cursor.execute("SELECT id FROM teachers WHERE telegram_username = %s", (telegram_username,))
    teacher = cursor.fetchone()

    if not teacher:
        await update.message.reply_text("شما به عنوان معلم ثبت نشده‌اید.")
        return ConversationHandler.END

    teacher_id = teacher[0]
    cursor.execute("SELECT message FROM messages WHERE teacher_id = %s", (teacher_id,))
    messages = cursor.fetchall()

    if not messages:
        await update.message.reply_text("هیچ پیامی برای شما وجود ندارد.")
    else:
        message_list = "\n\n".join([f"پیام {idx + 1}: {msg[0]}" for idx, msg in enumerate(messages)])
        await update.message.reply_text(f"پیام‌های دریافت‌شده:\n\n{message_list}")

    return ConversationHandler.END

# تعریف مسیرهای مکالمه
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSE_ACTION: [
            MessageHandler(filters.Regex("^ارسال پیام به معلم$"), send_message_to_teacher),
            MessageHandler(filters.Regex("^معلم هستم \(مشاهده پیام‌ها\)$"), view_messages),
        ],
        SELECT_TEACHER: [MessageHandler(filters.Regex("^\d+$"), process_teacher_selection)],
        SEND_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_message)],
    },
    fallbacks=[CommandHandler("start", start)]
)

# اجرای ربات
app = ApplicationBuilder().token("7589439068:AAEKY8-QbI77fClMaFeyHMHx4jo-XV2stIk").build()
app.add_handler(conv_handler)

print("ربات در حال اجرا است...")
app.run_polling()
