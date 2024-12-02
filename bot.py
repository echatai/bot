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
    if teachers:
        teacher_names = [f"{teacher.first_name} {teacher.last_name}" for teacher in teachers]
        await update.message.reply_text(
            "یک معلم را انتخاب کنید:",
            reply_markup=ReplyKeyboardMarkup(
                [[name] for name in teacher_names],
                one_time_keyboard=True
            )
        )
        # ذخیره لیست معلم‌ها در user_data برای استفاده در مراحل بعدی
        context.user_data['teachers'] = {f"{t.first_name} {t.last_name}": t for t in teachers}
    else:
        await update.message.reply_text("هیچ معلم فعالی در حال حاضر وجود ندارد.")

async def send_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher_name = update.message.text.strip()  # حذف فضای خالی اضافی از نام ورودی
    teachers = context.user_data.get('teachers', {})  # لیست معلم‌ها از user_data
    
    if not teachers:
        await update.message.reply_text("خطایی رخ داده است. لطفاً دوباره /start را وارد کنید.")
        return

    # مطابقت نام معلم با کلید ذخیره‌شده
    teacher = teachers.get(teacher_name)

    if teacher:
        context.user_data['selected_teacher'] = teacher  # ذخیره اطلاعات معلم انتخاب‌شده
        await update.message.reply_text("پیام خود را وارد کنید:")
    else:
        available_teachers = ", ".join(teachers.keys())
        await update.message.reply_text(
            f"معلم انتخاب‌شده یافت نشد. لطفاً دوباره تلاش کنید.\n"
            f"معلم‌های موجود: {available_teachers}"
        )


async def receive_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teacher = context.user_data.get('selected_teacher')
    if teacher:
        new_message = Message(
            student_telegram_id=update.effective_user.username,
            teacher_id=teacher.id,
            content=update.message.text
        )
        session.add(new_message)
        session.commit()
        await update.message.reply_text("پیام شما به‌صورت ناشناس ارسال شد.")
        # پاک کردن معلم انتخاب‌شده از user_data پس از ارسال پیام
        context.user_data.pop('selected_teacher', None)
    else:
        await update.message.reply_text("لطفاً ابتدا یک معلم را انتخاب کنید.")

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
