from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from sqlalchemy.orm import sessionmaker
from database import engine, Teacher, Message

# تنظیمات
Session = sessionmaker(bind=engine)
session = Session()

# دستورات ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به ربات خوش آمدید! آیا شما دانش‌آموز هستید یا معلم؟",
        reply_markup=ReplyKeyboardMarkup([['دانش‌آموز', 'معلم']], one_time_keyboard=True)
    )

async def student_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teachers = session.query(Teacher).filter_by(active=True).all()
    teacher_names = [[teacher.username] for teacher in teachers]
    if teacher_names:
        await update.message.reply_text(
            "یک معلم را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(teacher_names, one_time_keyboard=True)
        )
    else:
        await update.message.reply_text("هیچ معلم فعالی در حال حاضر وجود ندارد.")

async def send_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher_name = update.message.text
    teacher = session.query(Teacher).filter_by(username=teacher_name).first()
    if teacher:
        context.user_data['selected_teacher'] = teacher
        await update.message.reply_text("پیام خود را وارد کنید:")
    else:
        await update.message.reply_text("معلم انتخاب‌شده یافت نشد.")

async def receive_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher = context.user_data.get('selected_teacher')
    if teacher:
        new_message = Message(
            student_telegram_id=str(update.effective_chat.id),
            teacher_id=teacher.id,
            content=update.message.text
        )
        session.add(new_message)
        session.commit()
        await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد.")
    else:
        await update.message.reply_text("لطفاً ابتدا یک معلم را انتخاب کنید.")

async def teacher_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    teacher = session.query(Teacher).filter_by(telegram_id=str(chat_id)).first()
    if not teacher:
        await update.message.reply_text("شما به عنوان معلم ثبت نشده‌اید.")
        return
    messages = session.query(Message).filter_by(teacher_id=teacher.id).all()
    if messages:
        for msg in messages:
            await update.message.reply_text(f"پیام ناشناس:\n{msg.content}")
    else:
        await update.message.reply_text("هیچ پیامی برای شما وجود ندارد.")

# تنظیمات اصلی ربات
def main():
    # ساخت اپلیکیشن با توکن
    application = Application.builder().token("7589439068:AAEKY8-QbI77fClMaFeyHMHx4jo-XV2stIk").build()

    # افزودن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('دانش‌آموز'), student_panel))
    application.add_handler(MessageHandler(filters.Regex('معلم'), teacher_panel))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, send_anonymous_message))
    application.add_handler(MessageHandler(filters.TEXT, receive_anonymous_message))

    # اجرا
    application.run_polling()

if __name__ == "__main__":
    main()
