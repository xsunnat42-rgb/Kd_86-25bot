import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

# --- RENDER UCHUN DUMMY WEB SERVER (PORTNI UShLAB TURISH UCHUN) ---


class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'Bot is running 24/7!')


def run_web_server():
  port = int(os.environ.get('PORT', 10000))
  server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
  server.serve_forever()


# Veb-serverni alohida oqimda (thread) ishga tushiramiz
threading.Thread(target=run_web_server, daemon=True).start()

# --- TELEGRAM BOT QISMI ---
TOKEN = os.environ.get('TOKEN')
bot = telebot.TeleBot(TOKEN)

# SQLite bazasini ulash va jadval yaratish
conn = sqlite3.connect('kd86_albom.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    full_name TEXT,
    phone TEXT,
    photo_id TEXT,
    bio TEXT
)
''')
conn.commit()

user_data = {}


@bot.message_handler(commands=['start'])
def send_welcome(message):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  markup.add(
      "👤 Ro'yxatdan o'tish",
      "📋 Talabalar ro'yxati",
      "🔎 Ism bo'yicha qidirish",
  )
  bot.send_message(
      message.chat.id,
      "Assalomu alaykum! **Kd86** guruhi elektron albomi botiga xush"
      " kelibsiz. 🎓\n\nO'z ma'lumotlaringizni qo'shish yoki guruhdoshlarni"
      " ko'rish uchun quyidagi tugmalardan foydalaning:",
      reply_markup=markup,
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda message: message.text == "👤 Ro'yxatdan o'tish"
)
def start_registration(message):
  sent_msg = bot.send_message(
      message.chat.id,
      "Iltimos, Ism va Familiyangizni kiriting (Masalan: Alisher Valiyev):",
  )
  user_data[message.chat.id] = {}
  bot.register_next_step_handler(sent_msg, process_name)


def process_name(message):
  user_data[message.chat.id]['full_name'] = message.text

  markup = types.ReplyKeyboardMarkup(
      resize_keyboard=True, one_time_keyboard=True
  )
  button_phone = types.KeyboardButton(
      "📱 Telefon raqamni yuborish", request_contact=True
  )
  markup.add(button_phone)

  sent_msg = bot.send_message(
      message.chat.id,
      "Rahmat! Endi telefon raqamingizni yuboring (Pastdagi tugmani bosing):",
      reply_markup=markup,
  )
  bot.register_next_step_handler(sent_msg, process_phone)


def process_phone(message):
  if message.contact:
    phone = message.contact.phone_number
  else:
    phone = message.text

  user_data[message.chat.id]['phone'] = phone

  sent_msg = bot.send_message(
      message.chat.id,
      "Ajoyib! Endi o'zingizning profil rasmgingizni (foto) yuboring:",
      reply_markup=types.ReplyKeyboardRemove(),
  )
  bot.register_next_step_handler(sent_msg, process_photo)


def process_photo(message):
  if message.photo:
    photo_id = message.photo[-1].file_id
    user_data[message.chat.id]['photo_id'] = photo_id

    sent_msg = bot.send_message(
        message.chat.id,
        "Oxirgi qadam: O'zingiz haqingizda qisqacha ma'lumot (qiziqishlaringiz,"
        " tug'ilgan kun, hobbi va h.k.) yozib yuboring:",
    )
    bot.register_next_step_handler(sent_msg, process_bio)
  else:
    sent_msg = bot.send_message(
        message.chat.id,
        "Iltimos, matn emas, aynan rasm ko'rinishida yuboring! Profil rasmini"
        " yuboring:",
    )
    bot.register_next_step_handler(sent_msg, process_photo)


def process_bio(message):
  user_data[message.chat.id]['bio'] = message.text
  chat_id = message.chat.id
  data = user_data[chat_id]

  cursor.execute(
      'SELECT id FROM students WHERE telegram_id = ?', (chat_id,)
  )
  existing = cursor.fetchone()

  if existing:
    cursor.execute(
        '''UPDATE students SET full_name = ?, phone = ?, photo_id = ?, bio = ? 
                   WHERE telegram_id = ?''',
        (
            data['full_name'],
            data['phone'],
            data['photo_id'],
            data['bio'],
            chat_id,
        ),
    )
  else:
    cursor.execute(
        '''INSERT INTO students (telegram_id, full_name, phone, photo_id, bio) 
                   VALUES (?, ?, ?, ?, ?)''',
        (
            chat_id,
            data['full_name'],
            data['phone'],
            data['photo_id'],
            data['bio'],
        ),
    )
  conn.commit()

  bot.send_message(
      chat_id,
      "Tabriklaymiz! Ma'lumotlaringiz elektron albomga muvaffaqiyatli qo'shildi!"
      " 🎉",
  )
  send_welcome(message)


@bot.message_handler(
    func=lambda message: message.text == "📋 Talabalar ro'yxati"
)
def show_students(message):
  cursor.execute('SELECT full_name, phone, bio, photo_id FROM students')
  students = cursor.fetchall()

  if not students:
    bot.send_message(
        message.chat.id,
        "Hozircha albomda talabalar mavjud emas. Birinchi bo'lib ro'yxatdan"
        " o'ting!",
    )
    return

  bot.send_message(
      message.chat.id,
      "📚 **Kd86 guruhi talabalari ro'yxati:**",
      parse_mode="Markdown",
  )
  for student in students:
    full_name, phone, bio, photo_id = student
    text = (
        f"👤 **Ism:** {full_name}\n📱 **Telefon:** {phone}\n📝 **Ma'lumot:**"
        f" {bio}"
    )
    if photo_id:
      bot.send_photo(message.chat.id, photo_id, caption=text, parse_mode="Markdown")
    else:
      bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(
    func=lambda message: message.text == "🔎 Ism bo'yicha qidirish"
)
def search_prompt(message):
  sent_msg = bot.send_message(
      message.chat.id,
      "Qidirmoqchi bo'lgan talabaning ism yoki familiyasini yozing:",
  )
  bot.register_next_step_handler(sent_msg, execute_search)


def execute_search(message):
  query = f'%{message.text}%'
  cursor.execute(
      'SELECT full_name, phone, bio, photo_id FROM students WHERE full_name LIKE'
      ' ?',
      (query,),
  )
  students = cursor.fetchall()

  if not students:
    bot.send_message(
        message.chat.id, "Bunday ismli talaba topilmadi ❌"
    )
    return

  bot.send_message(
      message.chat.id, f"🔍 Topilgan natijalar ({len(students)} ta):"
  )
  for student in students:
    full_name, phone, bio, photo_id = student
    text = (
        f"👤 **Ism:** {full_name}\n📱 **Telefon:** {phone}\n📝 **Ma'lumot:**"
        f" {bio}"
    )
    if photo_id:
      bot.send_photo(message.chat.id, photo_id, caption=text, parse_mode="Markdown")
    else:
      bot.send_message(message.chat.id, text, parse_mode="Markdown")


if __name__ == '__main__':
  print('Bot va veb-server ishga tushdi...')
  bot.infinity_polling()
  
