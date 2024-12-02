import telebot
import psycopg2
import os

# Telegram Bot Token
BOT_TOKEN = "YOUR_BOT_TOKEN"
bot = telebot.TeleBot(BOT_TOKEN)

# Database URL from Railway environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Database Connection
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Create tables if they don't exist
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
    print("Tables created successfully!")

create_tables()

# Register user: student or teacher
@bot.message_handler(commands=['start'])
def register_user(message):
    telegram_id = message.chat.id
    role = None

    if message.text == '/start teacher':
        role = 'teacher'
        bot.send_message(telegram_id, "Please send your first and last name (e.g., John Doe):")
        bot.register_next_step_handler(message, save_teacher_info)
    elif message.text == '/start student':
        role = 'student'
        try:
            cursor.execute("INSERT INTO users (telegram_id, role) VALUES (%s, %s)", (telegram_id, role))
            conn.commit()
            bot.send_message(telegram_id, "You have been registered as a student!")
        except psycopg2.IntegrityError:
            bot.send_message(telegram_id, "You are already registered.")
    else:
        bot.send_message(telegram_id, "Please specify your role: \n/start teacher\n/start student")

def save_teacher_info(message):
    telegram_id = message.chat.id
    try:
        first_name, last_name = message.text.split(' ', 1)
        cursor.execute("""
        INSERT INTO users (telegram_id, role, first_name, last_name)
        VALUES (%s, 'teacher', %s, %s)
        """, (telegram_id, first_name, last_name))
        conn.commit()
        bot.send_message(telegram_id, "You have been registered as a teacher!")
    except ValueError:
        bot.send_message(telegram_id, "Invalid format. Please send your first and last name separated by a space.")

# List teachers for students to choose
@bot.message_handler(commands=['choose_teacher'])
def choose_teacher(message):
    telegram_id = message.chat.id

    # Ensure user is a student
    cursor.execute("SELECT role FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    if not result or result[0] != 'student':
        bot.send_message(telegram_id, "This command is only for students.")
        return

    # Fetch teacher list
    cursor.execute("SELECT id, first_name, last_name FROM users WHERE role = 'teacher'")
    teachers = cursor.fetchall()

    if not teachers:
        bot.send_message(telegram_id, "No teachers are currently registered.")
        return

    # Display teachers with numbers
    teacher_list = "\n".join([f"{idx + 1}. {teacher[1]} {teacher[2]}" for idx, teacher in enumerate(teachers)])
    bot.send_message(telegram_id, f"Choose one of the following teachers by number:\n{teacher_list}")
    bot.send_message(telegram_id, "Please enter the number of your chosen teacher:")
    bot.register_next_step_handler(message, handle_teacher_selection, teachers)

def handle_teacher_selection(message, teachers):
    telegram_id = message.chat.id

    try:
        selected_index = int(message.text) - 1
        if 0 <= selected_index < len(teachers):
            selected_teacher = teachers[selected_index]
            selected_teacher_id = selected_teacher[0]

            bot.send_message(telegram_id, f"You have selected {selected_teacher[1]} {selected_teacher[2]}!")
            bot.send_message(telegram_id, "Please enter your message:")
            bot.register_next_step_handler(message, forward_message, selected_teacher_id)
        else:
            bot.send_message(telegram_id, "Invalid number. Please try again.")
            choose_teacher(message)  # Re-show the list
    except ValueError:
        bot.send_message(telegram_id, "Please enter a valid number.")
        choose_teacher(message)

# Forward anonymous message to teacher
def forward_message(message, teacher_id):
    student_id = message.chat.id
    msg = message.text

    # Save message in database
    cursor.execute("""
    INSERT INTO messages (teacher_id, student_id, message)
    VALUES (%s, %s, %s)
    """, (teacher_id, student_id, msg))
    conn.commit()

    # Fetch teacher info
    cursor.execute("SELECT telegram_id FROM users WHERE id = %s", (teacher_id,))
    teacher_telegram_id = cursor.fetchone()[0]

    # Send message to teacher
    bot.send_message(teacher_telegram_id, f"Anonymous message from a student:\n{msg}")
    bot.send_message(student_id, "Your message has been sent anonymously!")

# View messages for teachers
@bot.message_handler(commands=['my_messages'])
def view_messages(message):
    telegram_id = message.chat.id

    # Ensure user is a teacher
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s AND role = 'teacher'", (telegram_id,))
    teacher = cursor.fetchone()
    if not teacher:
        bot.send_message(telegram_id, "This command is only for teachers.")
        return

    teacher_id = teacher[0]
    cursor.execute("""
    SELECT student_id, message FROM messages WHERE teacher_id = %s
    """, (teacher_id,))
    messages = cursor.fetchall()

    if not messages:
        bot.send_message(telegram_id, "You have no messages.")
        return

    # Display messages
    for student_id, msg in messages:
        bot.send_message(telegram_id, f"Message from a student:\n{msg}")

# Start the bot
bot.polling()
