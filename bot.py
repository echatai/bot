import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, ConversationHandler, filters
import psycopg2
import bcrypt

# تنظیمات لاگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# اتصال به دیتابیس
conn = psycopg2.connect("postgresql://postgres:WwsdWwGXSFWbTbcyRvSchqpltUXOCTVZ@postgres.railway.internal:5432/railway")
cursor = conn.cursor()

# ایجاد جدول‌ها
def create_tables():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        national_code TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        telegram_id TEXT UNIQUE
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id SERIAL PRIMARY KEY,
        national_code TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        telegram_username TEXT UNIQUE,
        category TEXT NOT NULL,
        first_name TEXT,
        last_name TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        teacher_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        reply TEXT,
        FOREIGN KEY (teacher_id) REFERENCES teachers (id),
        FOREIGN KEY (student_id) REFERENCES students (id)
    );
    """)
    conn.commit()
    logger.info("جداول با موفقیت ایجاد شدند!")

create_tables()

# مراحل مکالمه
LOGIN, CHOOSE_ACTION, SELECT_CATEGORY, SELECT_TEACHER, SEND_MESSAGE, SELECT_MESSAGE_FOR_REPLY, SEND_REPLY = range(7)

# شروع ربات
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("لطفاً کد ملی و رمز عبور خود را به شکل زیر وارد کنید:\n\nکد ملی:رمز عبور")
    return LOGIN

# ورود کاربران (دانش‌آموز یا معلم)
async def login(update: Update, context: CallbackContext):
    try:
        national_code, password = update.message.text.split(":")

        # جستجوی دانش‌آموز
        cursor.execute("SELECT id, password_hash FROM students WHERE national_code = %s", (national_code,))
        student = cursor.fetchone()

        # جستجوی معلم
        cursor.execute("SELECT id, password_hash FROM teachers WHERE national_code = %s", (national_code,))
        teacher = cursor.fetchone()

        if student and bcrypt.checkpw(password.encode(), student[1].encode()):
            student_id = student[0]
            telegram_id = update.effective_user.id

            cursor.execute("UPDATE students SET telegram_id = %s WHERE id = %s", (telegram_id, student_id))
            conn.commit()

            await update.message.reply_text("ورود موفقیت‌آمیز بود! لطفاً یک گزینه را انتخاب کنید:",
                                            reply_markup=ReplyKeyboardMarkup([
                                                ["ارسال پیام به معلم"],
                                                ["خروج"]
                                            ], one_time_keyboard=True))
            context.user_data['user_type'] = 'student'
            return CHOOSE_ACTION

        elif teacher and bcrypt.checkpw(password.encode(), teacher[1].encode()):
            teacher_id = teacher[0]
            telegram_username = update.effective_user.username

            cursor.execute("UPDATE teachers SET telegram_username = %s WHERE id = %s", (telegram_username, teacher_id))
            conn.commit()

            await update.message.reply_text("ورود موفقیت‌آمیز بود! لطفاً یک گزینه را انتخاب کنید:",
                                            reply_markup=ReplyKeyboardMarkup([
                                                ["مشاهده پیام‌ها"],
                                                ["خروج"]
                                            ], one_time_keyboard=True))
            context.user_data['user_type'] = 'teacher'
            return CHOOSE_ACTION

        else:
            await update.message.reply_text("کد ملی یا رمز عبور اشتباه است. لطفاً دوباره تلاش کنید.")
            return LOGIN

    except ValueError:
        await update.message.reply_text("فرمت ورودی اشتباه است. لطفاً به شکل کد ملی:رمز عبور وارد کنید.")
        return LOGIN

# ارسال پیام به معلم
async def send_message_to_teacher(update: Update, context: CallbackContext):
    cursor.execute("SELECT DISTINCT category FROM teachers")
    categories = cursor.fetchall()

    if not categories:
        await update.message.reply_text("هیچ معلمی ثبت‌نام نکرده است.")
        return CHOOSE_ACTION

    category_list = "\n".join([f"{idx + 1}. {cat[0]}" for idx, cat in enumerate(categories)])
    await update.message.reply_text(f"یکی از دسته‌بندی‌های زیر را انتخاب کنید:\n{category_list}\n\nلطفاً شماره دسته را وارد کنید:")
    context.user_data['categories'] = categories
    return SELECT_CATEGORY

# انتخاب دسته معلم
async def process_category_selection(update: Update, context: CallbackContext):
    try:
        categories = context.user_data.get('categories', [])
        selected_index = int(update.message.text) - 1

        if 0 <= selected_index < len(categories):
            selected_category = categories[selected_index][0]
            cursor.execute("SELECT id, first_name, last_name FROM teachers WHERE category = %s", (selected_category,))
            teachers = cursor.fetchall()

            if not teachers:
                await update.message.reply_text("هیچ معلمی در این دسته وجود ندارد.")
                return CHOOSE_ACTION

            teacher_list = "\n".join([f"{idx + 1}. {teacher[1]} {teacher[2]}" for idx, teacher in enumerate(teachers)])
            await update.message.reply_text(f"یکی از معلمان زیر را انتخاب کنید:\n{teacher_list}\n\nلطفاً شماره معلم را وارد کنید:")
            context.user_data['teachers'] = teachers
            return SELECT_TEACHER
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("شماره نامعتبر است. لطفاً یک شماره معتبر را وارد کنید!")
        return SELECT_CATEGORY

# انتخاب معلم
async def process_teacher_selection(update: Update, context: CallbackContext):
    try:
        teachers = context.user_data.get('teachers', [])
        selected_index = int(update.message.text) - 1

        if 0 <= selected_index < len(teachers):
            selected_teacher = teachers[selected_index]
            context.user_data['selected_teacher_id'] = selected_teacher[0]
            await update.message.reply_text("لطفاً پیام خود را وارد کنید:")
            return SEND_MESSAGE
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("شماره نامعتبر است. لطفاً یک شماره معتبر را وارد کنید!")
        return SELECT_TEACHER

# ارسال پیام نهایی
async def process_message(update: Update, context: CallbackContext):
    teacher_id = context.user_data.get('selected_teacher_id')
    telegram_id = update.effective_user.id

    cursor.execute("SELECT id FROM students WHERE telegram_id = %s", (telegram_id,))
    student = cursor.fetchone()

    if not student:
        await update.message.reply_text("شما به عنوان دانش‌آموز ثبت نشده‌اید.")
        return CHOOSE_ACTION

    student_id = student[0]
    message = update.message.text.strip()

    if not message:
        await update.message.reply_text("پیام نمی‌تواند خالی باشد. لطفاً یک پیام وارد کنید.")
        return SEND_MESSAGE

    cursor.execute("""
    INSERT INTO messages (teacher_id, student_id, message)
    VALUES (%s, %s, %s)
    """, (teacher_id, student_id, message))
    conn.commit()

    await update.message.reply_text("پیام شما با موفقیت ارسال شد!")
    return CHOOSE_ACTION

# مشاهده پیام‌ها برای معلم‌ها
async def view_messages(update: Update, context: CallbackContext):
    telegram_username = update.effective_user.username

    cursor.execute("SELECT id FROM teachers WHERE telegram_username = %s", (telegram_username,))
    teacher = cursor.fetchone()

    if not teacher:
        await update.message.reply_text("شما به عنوان معلم ثبت نشده‌اید.")
        return CHOOSE_ACTION

    teacher_id = teacher[0]
    cursor.execute("SELECT id, message, reply FROM messages WHERE teacher_id = %s", (teacher_id,))
    messages = cursor.fetchall()

    if not messages:
        await update.message.reply_text("هیچ پیامی برای شما وجود ندارد.")
        return CHOOSE_ACTION

    message_list = "\n\n".join([f"پیام {idx + 1}: {msg[1]}\nپاسخ: {msg[2] if msg[2] else 'هنوز پاسخی داده نشده'}"
                               for idx, msg in enumerate(messages)])
    await update.message.reply_text(f"پیام‌های دریافت‌شده:\n\n{message_list}\n\nبرای پاسخ به یک پیام، شماره آن را وارد کنید:")
    context.user_data['messages'] = messages
    return SELECT_MESSAGE_FOR_REPLY

# انتخاب پیام برای پاسخ
async def select_message_for_reply(update: Update, context: CallbackContext):
    try:
        messages = context.user_data.get('messages', [])
        selected_index = int(update.message.text) - 1

        if 0 <= selected_index < len(messages):
            selected_message = messages[selected_index]
            context.user_data['selected_message_id'] = selected_message[0]
            await update.message.reply_text("لطفاً پاسخ خود را وارد کنید:")
            return SEND_REPLY
        else:
            raise ValueError
    except ValueError:
        await update.message.reply_text("شماره نامعتبر است. لطفاً یک شماره معتبر را وارد کنید!")
        return SELECT_MESSAGE_FOR_REPLY

# ارسال پاسخ معلم
async def send_reply(update: Update, context: CallbackContext):
    message_id = context.user_data.get('selected_message_id')
    reply = update.message.text.strip()

    if not reply:
        await update.message.reply_text("پاسخ نمی‌تواند خالی باشد. لطفاً پاسخ خود را وارد کنید.")
        return SEND_REPLY

    cursor.execute("""
    UPDATE messages
    SET reply = %s
    WHERE id = %s
    """, (reply, message_id))
    conn.commit()

    await update.message.reply_text("پاسخ شما با موفقیت ارسال شد!")
    return CHOOSE_ACTION

# استفاده از `ApplicationBuilder` برای اجرای ربات
if __name__ == '__main__':
    application = ApplicationBuilder().token("7589439068:AAEKY8-QbI77fClMaFeyHMHx4jo-XV2stIk").build()

    # اضافه کردن هندلرها
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN: [MessageHandler(filters.TEXT, login)],
            CHOOSE_ACTION: [
                MessageHandler(filters.Regex('^(ارسال پیام به معلم)$'), send_message_to_teacher),
                MessageHandler(filters.Regex('^(خروج)$'), lambda update, context: update.message.reply_text("خروج...")),
                MessageHandler(filters.Regex('^(مشاهده پیام‌ها)$'), view_messages),
            ],
            SELECT_CATEGORY: [MessageHandler(filters.TEXT, process_category_selection)],
            SELECT_TEACHER: [MessageHandler(filters.TEXT, process_teacher_selection)],
            SEND_MESSAGE: [MessageHandler(filters.TEXT, process_message)],
            SELECT_MESSAGE_FOR_REPLY: [MessageHandler(filters.TEXT, select_message_for_reply)],
            SEND_REPLY: [MessageHandler(filters.TEXT, send_reply)],
        },
        fallbacks=[]
    ))

    # شروع ربات به صورت polling
    application.run_polling()
