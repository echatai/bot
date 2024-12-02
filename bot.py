from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import sessionmaker
from database import engine, Teacher, Message

# تنظیمات دیتابیس
Session = sessionmaker(bind=engine)
session = Session()

# توکن ربات
import os


# دستورات ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به ربات خوش آمدید! آیا شما دانش‌آموز هستید یا معلم؟",
        reply_markup=ReplyKeyboardMarkup([['دانش‌آموز', 'معلم']], one_time_keyboard=True)
    )

async def student_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teachers = session.query(Teacher).filter_by(active=True).all()

    if not teachers:
        await update.message.reply_text("هیچ معلم فعالی در حال حاضر وجود ندارد.")
        return

    # ذخیره معلم‌ها در قالب لیستی از username
    context.user_data['teachers'] = {teacher.username for teacher in teachers}

    # نمایش username معلم‌ها به کاربر
    teacher_usernames = list(context.user_data['teachers'])
    await update.message.reply_text(
        "یک معلم را با استفاده از نام کاربری انتخاب کنید:",
        reply_markup=ReplyKeyboardMarkup([teacher_usernames], one_time_keyboard=True)
    )

async def send_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher_username = update.message.text.strip()  # username انتخاب‌شده

    teachers = context.user_data.get('teachers', set())  # لیست معلم‌ها از user_data
    if not teachers:
        await update.message.reply_text("خطایی رخ داده است. لطفاً دوباره /start را وارد کنید.")
        return

    if teacher_username in teachers:
        context.user_data['selected_teacher'] = teacher_username  # ذخیره username معلم انتخاب‌شده
        await update.message.reply_text("پیام خود را وارد کنید:")
    else:
        available_teachers = ", ".join(teachers)
        await update.message.reply_text(
            f"معلم انتخاب‌شده یافت نشد. لطفاً دوباره تلاش کنید.\n"
            f"معلم‌های موجود: {available_teachers}"
        )

async def receive_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher_username = context.user_data.get('selected_teacher')  # username معلم انتخاب‌شده

    if not teacher_username:
        await update.message.reply_text("لطفاً ابتدا یک معلم را انتخاب کنید.")
        return

    # Validate the selected username
    teacher = session.query(Teacher).filter_by(username=teacher_username).first()
    if not teacher:
        await update.message.reply_text("معلم انتخاب‌شده یافت نشد.")
        return

    # Save the message to the database
    new_message = Message(
        student_telegram_id=update.message.chat.username,  # ثبت username دانش‌آموز
        teacher_id=teacher.id,
        content=update.message.text
    )
    session.add(new_message)
    session.commit()
    await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد.")

async def teacher_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    teacher = session.query(Teacher).filter_by(username=username).first()
    if not teacher:
        await update.message.reply_text("شما به عنوان معلم ثبت نشده‌اید.")
        return

    messages = session.query(Message).filter_by(teacher_id=teacher.id).all()
    if messages:
        for msg in messages:
            await update.message.reply_text(f"پیام ناشناس:\n{msg.content}")
    else:
        await update.message.reply_text("هیچ پیامی برای شما وجود ندارد.")

async def register_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    first_name = update.effective_user.first_name or "نام‌ناشناخته"
    last_name = update.effective_user.last_name or "نام‌خانوادگی‌ناشناخته"

    existing_teacher = session.query(Teacher).filter_by(username=username).first()
    if existing_teacher:
        await update.message.reply_text("شما قبلاً به عنوان معلم ثبت شده‌اید.")
        return

    new_teacher = Teacher(username=username, first_name=first_name, last_name=last_name, active=True)
    session.add(new_teacher)
    session.commit()

    await update.message.reply_text("شما با موفقیت به عنوان معلم ثبت شدید.")

# تنظیمات اصلی ربات
def main():
    application = Application.builder().token("7589439068:AAEKY8-QbI77fClMaFeyHMHx4jo-XV2stIk").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register_teacher", register_teacher))
    application.add_handler(MessageHandler(filters.Regex('دانش‌آموز'), student_panel))
    application.add_handler(MessageHandler(filters.Regex('معلم'), teacher_panel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_anonymous_message))
    application.add_handler(MessageHandler(filters.TEXT, receive_anonymous_message))

    application.run_polling()


if __name__ == "__main__":
    main()
