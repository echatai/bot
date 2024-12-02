from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from sqlalchemy.orm import sessionmaker
from database import engine, Teacher, Message

# تنظیمات
Session = sessionmaker(bind=engine)
session = Session()

# توکن ربات (از متغیر محیطی یا مقدار ثابت)
import os
TOKEN = os.getenv("BOT_TOKEN")

# دستورات ربات
def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    update.message.reply_text(
        "به ربات خوش آمدید! آیا شما دانش‌آموز هستید یا معلم؟",
        reply_markup=ReplyKeyboardMarkup([['دانش‌آموز', 'معلم']], one_time_keyboard=True)
    )

def student_panel(update: Update, context: CallbackContext):
    teachers = session.query(Teacher).filter_by(active=True).all()
    teacher_names = [teacher.username for teacher in teachers]
    if teacher_names:
        update.message.reply_text(
            "یک معلم را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup([teacher_names], one_time_keyboard=True)
        )
    else:
        update.message.reply_text("هیچ معلم فعالی در حال حاضر وجود ندارد.")

def send_anonymous_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    teacher_name = update.message.text
    teacher = session.query(Teacher).filter_by(username=teacher_name).first()
    if teacher:
        context.user_data['selected_teacher'] = teacher
        update.message.reply_text("پیام خود را وارد کنید:")
    else:
        update.message.reply_text("معلم انتخاب‌شده یافت نشد.")

def receive_anonymous_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    teacher = context.user_data.get('selected_teacher')
    if teacher:
        new_message = Message(
            student_telegram_id=str(chat_id),
            teacher_id=teacher.id,
            content=update.message.text
        )
        session.add(new_message)
        session.commit()
        update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد.")
    else:
        update.message.reply_text("لطفاً ابتدا یک معلم را انتخاب کنید.")

def teacher_panel(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    teacher = session.query(Teacher).filter_by(telegram_id=str(chat_id)).first()
    if not teacher:
        update.message.reply_text("شما به عنوان معلم ثبت نشده‌اید.")
        return
    messages = session.query(Message).filter_by(teacher_id=teacher.id).all()
    if messages:
        for msg in messages:
            update.message.reply_text(f"پیام ناشناس:\n{msg.content}")
    else:
        update.message.reply_text("هیچ پیامی برای شما وجود ندارد.")

# تنظیمات اصلی ربات
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.regex('دانش‌آموز'), student_panel))
    dp.add_handler(MessageHandler(Filters.regex('معلم'), teacher_panel))
    dp.add_handler(MessageHandler(Filters.text & Filters.reply, send_anonymous_message))
    dp.add_handler(MessageHandler(Filters.text, receive_anonymous_message))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
