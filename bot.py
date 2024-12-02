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
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
        first_name TEXT,
        last_name TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        teacher_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        message TEXT NOT NULL,
        is_anonymous BOOLEAN DEFAULT TRUE,
        FOREIGN KEY (teacher_id) REFERENCES users (id),
        FOREIGN KEY (student_id) REFERENCES users (telegram_id)
    );
    """)
    conn.commit()
    print("جداول با موفقیت ایجاد شدند!")

create_tables()

# مراحل ثبت اطلاعات معلم
SAVE_TEACHER_INFO, CHOOSE_TEACHER, SEND_MESSAGE = range(3)

# شروع ربات و ثبت‌نام
async def start(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    cursor.execute("SELECT role FROM users WHERE telegram_id = %s", (telegram_id,))
    user = cursor.fetchone()

    if user:
        await update.message.reply_text("شما قبلاً ثبت‌نام کرده‌اید!")
        return ConversationHandler.END

    reply_keyboard = [["دانش‌آموز", "معلم"]]
    await update.message.reply_text(
        "لطفاً نقش خود را انتخاب کنید:\n\n"
        "1. دانش‌آموز\n"
        "2. معلم",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return SAVE_TEACHER_INFO

async def save_teacher_info(update: Update, context: CallbackContext):
    role = update.message.text
    telegram_id = str(update.effective_user.id)

    if role == "معلم":
        await update.message.reply_text("لطفاً نام و نام خانوادگی خود را وارد کنید (به‌صورت: علی رضایی):")
        context.user_data['role'] = 'teacher'
        return SAVE_TEACHER_INFO

    elif role == "دانش‌آموز":
        cursor.execute("INSERT INTO users (telegram_id, role) VALUES (%s, 'student')", (telegram_id,))
        conn.commit()
        await update.message.reply_text("شما به‌عنوان دانش‌آموز ثبت‌نام شدید!")
        return ConversationHandler.END

    else:
        await update.message.reply_text("نقش نامعتبر است. لطفاً یکی از گزینه‌های موجود را انتخاب کنید.")
        return SAVE_TEACHER_INFO

async def complete_teacher_registration(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    try:
        first_name, last_name = update.message.text.split(' ', 1)
        cursor.execute("""
        INSERT INTO users (telegram_id, role, first_name, last_name)
        VALUES (%s, 'teacher', %s, %s)
        """, (telegram_id, first_name, last_name))
        conn.commit()
        await update.message.reply_text("شما به‌عنوان معلم ثبت‌نام شدید!")
    except ValueError:
        await update.message.reply_text("فرمت نام معتبر نیست. لطفاً نام و نام خانوادگی خود را وارد کنید (مثلاً: علی رضایی).")
        return SAVE_TEACHER_INFO

    return ConversationHandler.END

# لیست معلمان برای انتخاب
async def choose_teacher(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)

    cursor.execute("SELECT role FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    if not result or result[0] != 'student':
        await update.message.reply_text("این دستور فقط برای دانش‌آموزان است.")
        return ConversationHandler.END

    cursor.execute("SELECT id, first_name, last_name FROM users WHERE role = 'teacher'")
    teachers = cursor.fetchall()

    if not teachers:
        await update.message.reply_text("هیچ معلمی ثبت‌نام نکرده است.")
        return ConversationHandler.END

    teacher_list = "\n".join([f"{idx + 1}. {teacher[1]} {teacher[2]}" for idx, teacher in enumerate(teachers)])
    await update.message.reply_text(f"یکی از معلمان زیر را انتخاب کنید:\n{teacher_list}\n\nلطفاً شماره معلم را وارد کنید:")
    context.user_data['teachers'] = teachers
    return CHOOSE_TEACHER

async def send_message_to_teacher(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)
    teachers = context.user_data['teachers']

    try:
        selected_index = int(update.message.text) - 1
        if 0 <= selected_index < len(teachers):
            selected_teacher = teachers[selected_index]
            context.user_data['selected_teacher'] = selected_teacher[0]
            await update.message.reply_text(f"شما معلم {selected_teacher[1]} {selected_teacher[2]} را انتخاب کردید!\nلطفاً پیام خود را وارد کنید:")
            return SEND_MESSAGE
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("شماره نامعتبر است. لطفاً دوباره تلاش کنید.")
        return CHOOSE_TEACHER

async def forward_message(update: Update, context: CallbackContext):
    student_id = str(update.effective_user.id)
    teacher_id = context.user_data['selected_teacher']
    message = update.message.text

    cursor.execute("""
    INSERT INTO messages (teacher_id, student_id, message)
    VALUES (%s, %s, %s)
    """, (teacher_id, student_id, message))
    conn.commit()

    cursor.execute("SELECT telegram_id FROM users WHERE id = %s", (teacher_id,))
    teacher = cursor.fetchone()

    if teacher:
        await context.bot.send_message(chat_id=teacher[0], text=f"پیام ناشناس از یک دانش‌آموز:\n{message}")
        await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد!")
    else:
        await update.message.reply_text("خطایی رخ داده است. لطفاً دوباره تلاش کنید.")

    return ConversationHandler.END

# مشاهده پیام‌ها برای معلمان
async def my_messages(update: Update, context: CallbackContext):
    telegram_id = str(update.effective_user.id)

    cursor.execute("SELECT id FROM users WHERE telegram_id = %s AND role = 'teacher'", (telegram_id,))
    teacher = cursor.fetchone()
    if not teacher:
        await update.message.reply_text("این دستور فقط برای معلمان است.")
        return

    teacher_id = teacher[0]
    cursor.execute("SELECT student_id, message FROM messages WHERE teacher_id = %s", (teacher_id,))
    messages = cursor.fetchall()

    if not messages:
        await update.message.reply_text("پیامی دریافت نکرده‌اید.")
        return

    for _, msg in messages:
        await update.message.reply_text(f"پیام از یک دانش‌آموز:\n{msg}")

# تعریف ربات و فرمان‌ها
app = ApplicationBuilder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        SAVE_TEACHER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_teacher_info)],
        CHOOSE_TEACHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_to_teacher)],
        SEND_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.add_handler(CommandHandler("choose_teacher", choose_teacher))
app.add_handler(CommandHandler("my_messages", my_messages))

print("ربات در حال اجرا است...")
app.run_polling()
