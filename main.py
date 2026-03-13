from flask import Flask, render_template, request
import os
from werkzeug.utils import secure_filename
import telebot
import threading
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
bot = telebot.TeleBot(os.getenv('api_key'))

USERS = [5347872932, 6673440979]
UPLOAD_FOLDER = "static/uploads"
ORDER_COOLDOWN = {}

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.id in USERS:
        bot.send_message(message.chat.id, "Бот підключений ✅")
    else:
        bot.send_message(message.chat.id, "Бот не підключений, ви не є працівником компанії ❌")

@app.route('/')
def main():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        ip = request.remote_addr
        now = datetime.now()

        if ip in ORDER_COOLDOWN:
            diff = now - ORDER_COOLDOWN[ip]
            if diff < timedelta(minutes=30):
                left = 30 - int(diff.total_seconds() / 60)
                return render_template('order.html',
                    error=f"Ви вже робили замовлення. Спробуйте через {left} хв.")

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        description = request.form.get('description', '').strip()
        wishes = request.form.get('wishes', '').strip()

        if not name or len(phone) < 12 or not description:
            return render_template('order.html', error="Будь ласка, заповніть всі обов'язкові поля")

        photo = request.files.get('photo')
        photo_path = None

        if photo and photo.filename:
            allowed = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
            ext = photo.filename.rsplit('.', 1)[-1].lower()

            if ext not in allowed:
                return render_template('order.html', error="Дозволені формати фото: jpg, png, webp, gif")

            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(photo_path)

        order_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        text = (
            f"🌸 *Нове замовлення*\n\n"
            f"⏰ {order_time}\n\n"
            f"👤 *Замовник:* {name}\n"
            f"📞 {phone}\n\n"
            f"🛒 *Замовлення:* {description}\n"
            f"💭 *Побажання:* {wishes if wishes else '—'}"
        )

        for user_id in USERS:
            try:
                bot.send_message(user_id, text, parse_mode='Markdown')
                if photo_path:
                    with open(photo_path, "rb") as img:
                        bot.send_photo(user_id, img)
            except Exception as e:
                print(f"Помилка відправки Telegram [{user_id}]: {e}")

        ORDER_COOLDOWN[ip] = now

        return render_template('complete_order.html')

    return render_template('order.html')

@app.route('/delivery', methods=['GET', 'POST'])
def delivery():
    if request.method == 'POST':
        ip = request.remote_addr
        now = datetime.now()

        if ip in ORDER_COOLDOWN:
            diff = now - ORDER_COOLDOWN[ip]
            if diff < timedelta(minutes=30):
                left = 30 - int(diff.total_seconds() / 60)
                return render_template('delivery.html', error=f"Ви вже робили замовлення. Спробуйте через {left} хв.")

        sender_name    = request.form.get('sender_name', '').strip()
        sender_phone   = request.form.get('sender_phone', '').strip()
        recipient_name = request.form.get('recipient_name', '').strip()
        recipient_phone= request.form.get('recipient_phone', '').strip()
        city           = request.form.get('city', '').strip()
        address        = request.form.get('address', '').strip()
        video          = request.form.get('video', 'no')
        greeting       = request.form.get('greeting', 'no')
        greeting_text  = request.form.get('greeting_text', '').strip()
        music          = request.form.get('music', 'no')
        music_text     = request.form.get('music_text', '').strip()
        photo    = request.form.get('photo', '').strip()
        description    = request.form.get('description', '').strip()
        wishes         = request.form.get('wishes', '').strip()

        if not sender_name or not sender_phone or not recipient_name or not recipient_phone or not city or not address or not description:
            return render_template('delivery.html', error="Будь ласка, заповніть всі обов'язкові поля")

        photo = request.files.get('photo')
        photo_path = None

        if photo and photo.filename:
            allowed = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
            ext = photo.filename.rsplit('.', 1)[-1].lower()
            if ext not in allowed:
                return render_template('delivery.html', error="Дозволені формати фото: jpg, png, webp, gif")
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            photo.save(photo_path)

        order_time = datetime.now().strftime("%d.%m.%Y %H:%M")
        text = (
            f"🚚 *Нова доставка*\n\n"
            f"⏰ {order_time}\n\n"
            f"👤 *Від:* {sender_name}\n"
            f"📞 {sender_phone}\n\n"
            f"🎁 *Отримувач:* {recipient_name}\n"
            f"📞 {recipient_phone}\n\n"
            f"📍 *Адреса:* {city}, {address}\n\n"
            f"🎥 *Відео:* {'Так' if video == 'yes' else 'Ні'}\n"
            f"💌 *Привітання:* {greeting_text if greeting == 'yes' and greeting_text else ('Так' if greeting == 'yes' else 'Ні')}\n"
            f"🎵 *Музика:* {music_text if music == 'yes' and music_text else ('Так' if music == 'yes' else 'Ні')}\n\n"
            f"🛒 *Замовлення:* {description}\n"
            f"💭 *Побажання:* {wishes if wishes else '—'}"
        )

        for user_id in USERS:
            try:
                bot.send_message(user_id, text, parse_mode='Markdown')
                if photo_path:
                    with open(photo_path, "rb") as img:
                        bot.send_photo(user_id, img)
            except Exception as e:
                print(f"Помилка відправки Telegram [{user_id}]: {e}")

        ORDER_COOLDOWN[ip] = now
        return render_template('complete_order.html')

    return render_template('delivery.html')

if __name__ == '__main__':
    bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    bot_thread.start()

    app.run(host="0.0.0.0", port=5000, debug=True)