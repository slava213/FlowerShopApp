from flask import Flask, render_template, request
import os
from werkzeug.utils import secure_filename
import telebot
import threading
import hashlib
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
bot = telebot.TeleBot(os.getenv('api_key'))

USERS = [5347872932, 6673440979, 5258794783]
UPLOAD_FOLDER = "static/uploads"
ORDER_COOLDOWN = {}

MAX_ORDERS = 5
COOLDOWN_MINUTES = 30

RECENT_ORDERS = {}
DUPLICATE_WINDOW_SECONDS = 15

NOTIFIED_IPS = {}

# Дані про букети/композиції
FLOWERS_DATA = {
    1: {
        'id': 1,
        'name': 'Весняний букет',
        'price': 850,
        'old_price': None,
        'image': '/static/images/img_4.png',
        'description': 'Ніжний весняний букет з тюльпанів, нарцисів та фрезій. Ідеальний подарунок для створення весняного настрою.',
        'composition': 'Тюльпани, нарциси, фрезії, евкаліпт',
        'size': '40-45 см',
        'colors': 'Рожевий, білий, жовтий',
        'freshness': '7-10 днів',
        'badge': 'Хіт',
        'badge_class': '',
        'category': 'bouquet',
        'gallery': []
    },
    2: {
        'id': 2,
        'name': 'Романтичний букет',
        'price': 1200,
        'old_price': 1400,
        'image': '/static/images/img_6.png',
        'description': 'Розкішний букет з червоних та рожевих троянд преміум класу. Створений для визнань у коханні та особливих романтичних моментів.',
        'composition': 'Троянди Ecuador, піоновидні троянди, евкаліпт',
        'size': '50-55 см',
        'colors': 'Червоний, рожевий',
        'freshness': '10-14 днів',
        'badge': 'Новинка',
        'badge_class': 'new',
        'category': 'bouquet',
        'gallery': []
    },
    3: {
        'id': 3,
        'name': 'Авторський букет',
        'price': 950,
        'old_price': None,
        'image': '/static/images/img_5.png',
        'description': 'Унікальний авторський букет від нашого флориста. Кожна композиція — це витвір мистецтва, створений з любов\'ю та увагою до деталей.',
        'composition': 'Сезонні квіти, декоративна зелень',
        'size': '45-50 см',
        'colors': 'За вашим побажанням',
        'freshness': '7-12 днів',
        'badge': None,
        'badge_class': '',
        'category': 'bouquet',
        'gallery': []
    },
    4: {
        'id': 4,
        'name': 'Святковий букет',
        'price': 1100,
        'old_price': None,
        'image': '/static/images/img_7.png',
        'description': 'Яскравий святковий букет для особливих подій. Поєднання найкращих квітів створює атмосферу справжнього свята.',
        'composition': 'Троянди, хризантеми, альстромерії, гіперикум',
        'size': '50-55 см',
        'colors': 'Мікс яскравих кольорів',
        'freshness': '10-14 днів',
        'badge': 'Преміум',
        'badge_class': 'premium',
        'category': 'bouquet',
        'gallery': []
    },
    5: {
        'id': 5,
        'name': 'Флористична композиція',
        'price': 1400,
        'old_price': 1600,
        'image': '/static/images/img_11.png',
        'description': 'Елегантна композиція у стильній коробці. Ідеальне рішення для тих, хто цінує вишуканість та оригінальність.',
        'composition': 'Троянди, еустома, орхідеї, декоративна зелень',
        'size': '30x30 см',
        'colors': 'Пастельні відтінки',
        'freshness': '12-16 днів',
        'badge': 'Преміум',
        'badge_class': 'premium',
        'category': 'composition',
        'gallery': []
    },
    6: {
        'id': 6,
        'name': 'Святкова композиція',
        'price': 1050,
        'old_price': None,
        'image': '/static/images/img_8.png',
        'description': 'Компактна святкова композиція у декоративному кашпо. Чудовий подарунок для дому чи офісу.',
        'composition': 'Міні-троянди, гвоздики, хризантеми',
        'size': '25x25 см',
        'colors': 'Яскраві кольори',
        'freshness': '10-14 днів',
        'badge': None,
        'badge_class': '',
        'category': 'composition',
        'gallery': []
    },
    7: {
        'id': 7,
        'name': 'Авторська композиція',
        'price': 1250,
        'old_price': None,
        'image': '/static/images/img_9.png',
        'description': 'Креативна авторська композиція від нашого майстра. Унікальне поєднання форм та кольорів.',
        'composition': 'Сезонні квіти преміум класу',
        'size': '35x35 см',
        'colors': 'Авторська палітра',
        'freshness': '12-14 днів',
        'badge': 'Новинка',
        'badge_class': 'new',
        'category': 'composition',
        'gallery': []
    },
    8: {
        'id': 8,
        'name': 'Преміум композиція',
        'price': 1800,
        'old_price': 2100,
        'image': '/static/images/img_10.png',
        'description': 'Розкішна преміум композиція з найкращих квітів світу. Справжній шедевр флористичного мистецтва.',
        'composition': 'Орхідеї, піоновидні троянди Ecuador, антуріум',
        'size': '40x40 см',
        'colors': 'Благородні відтінки',
        'freshness': '14-18 днів',
        'badge': 'Хіт',
        'badge_class': '',
        'category': 'composition',
        'gallery': []
    }
}


def make_order_hash(*args):
    raw = '|'.join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()


def is_duplicate(order_hash):
    now = datetime.now()
    expired = [k for k, v in RECENT_ORDERS.items()
               if now - v > timedelta(seconds=DUPLICATE_WINDOW_SECONDS)]
    for k in expired:
        del RECENT_ORDERS[k]

    if order_hash in RECENT_ORDERS:
        return True

    RECENT_ORDERS[order_hash] = now
    return False


def notify_blocked_ip(ip, route):
    last_notified = NOTIFIED_IPS.get(ip)
    if last_notified:
        state = ORDER_COOLDOWN.get(ip, {})
        blocked_at = state.get('blocked_at')
        if blocked_at and last_notified >= blocked_at:
            return

    now = datetime.now()
    NOTIFIED_IPS[ip] = now

    page_labels = {
        'order': 'Замовлення',
        'delivery': 'Доставка',
    }
    page = page_labels.get(route, route)
    time_str = now.strftime("%d.%m.%Y %H:%M")

    text = (
        f"🚫 *Заблокований IP*\n\n"
        f"⏰ {time_str}\n"
        f"🌐 IP: `{ip}`\n"
        f"📄 Сторінка: {page}\n\n"
        f"Перевищено ліміт {MAX_ORDERS} замовлень.\n"
        f"Блокування на {COOLDOWN_MINUTES} хв."
    )

    for user_id in USERS:
        try:
            bot.send_message(user_id, text, parse_mode='Markdown')
        except Exception as e:
            print(f"Помилка сповіщення про блокування [{user_id}]: {e}")


def check_cooldown(ip):
    now = datetime.now()
    state = ORDER_COOLDOWN.get(ip)

    if state is None:
        return True, None

    if state['blocked_at']:
        diff = now - state['blocked_at']
        if diff < timedelta(minutes=COOLDOWN_MINUTES):
            left = COOLDOWN_MINUTES - int(diff.total_seconds() / 60)
            return False, f"Ви вже зробили {MAX_ORDERS} замовлень. Спробуйте через {left} хв."
        else:
            ORDER_COOLDOWN[ip] = {'count': 0, 'blocked_at': None}

    return True, None


def register_order(ip):
    now = datetime.now()
    state = ORDER_COOLDOWN.get(ip, {'count': 0, 'blocked_at': None})
    state['count'] += 1
    if state['count'] >= MAX_ORDERS:
        state['blocked_at'] = now
    ORDER_COOLDOWN[ip] = state


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


@app.route('/flowers/<int:flower_id>')
def flower_detail(flower_id):
    flower = FLOWERS_DATA.get(flower_id)
    if not flower:
        return render_template('404.html'), 404

    # Отримуємо схожі товари (з тієї ж категорії)
    related = [
        fdata
        for fid, fdata in FLOWERS_DATA.items()
        if fid != flower_id and fdata['category'] == flower['category']
    ][:3]

    return render_template('flower_detail.html', flower=flower, flower_id=flower_id, related_flowers=related)


@app.route('/order', methods=['GET', 'POST'])
def order():
    # Отримуємо дані про букет, якщо передано flower_id
    flower_id = request.args.get('flower', type=int)
    flower = FLOWERS_DATA.get(flower_id) if flower_id else None

    if request.method == 'POST':
        ip = request.remote_addr
        allowed, error = check_cooldown(ip)
        if not allowed:
            notify_blocked_ip(ip, 'order')
            return render_template('order.html', error=error, flower=flower)

        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        description = request.form.get('description', '').strip()
        wishes = request.form.get('wishes', '').strip()

        if not name or len(phone) < 12 or not description:
            return render_template('order.html', error="Будь ласка, заповніть всі обов'язкові поля", flower=flower)

        order_hash = make_order_hash(ip, name, phone, description)
        if is_duplicate(order_hash):
            return render_template('complete_order.html')

        photo = request.files.get('photo')
        photo_path = None

        if photo and photo.filename:
            allowed_ext = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
            ext = photo.filename.rsplit('.', 1)[-1].lower()
            if ext not in allowed_ext:
                return render_template('order.html', error="Дозволені формати фото: jpg, png, webp, gif", flower=flower)
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

        register_order(ip)
        return render_template('complete_order.html')

    return render_template('order.html', flower=flower)


@app.route('/delivery', methods=['GET', 'POST'])
def delivery():
    # Отримуємо дані про букет, якщо передано flower_id
    flower_id = request.args.get('flower', type=int)
    flower = FLOWERS_DATA.get(flower_id) if flower_id else None

    if request.method == 'POST':
        ip = request.remote_addr
        allowed, error = check_cooldown(ip)
        if not allowed:
            notify_blocked_ip(ip, 'delivery')
            return render_template('delivery.html', error=error, flower=flower)

        sender_name = request.form.get('sender_name', '').strip()
        sender_phone = request.form.get('sender_phone', '').strip()
        recipient_name = request.form.get('recipient_name', '').strip()
        recipient_phone = request.form.get('recipient_phone', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        video = request.form.get('video', 'no')
        greeting = request.form.get('greeting', 'no')
        greeting_text = request.form.get('greeting_text', '').strip()
        music = request.form.get('music', 'no')
        music_text = request.form.get('music_text', '').strip()
        description = request.form.get('description', '').strip()
        wishes = request.form.get('wishes', '').strip()

        if not sender_name or not sender_phone or not recipient_name \
                or not recipient_phone or not city or not address or not description:
            return render_template('delivery.html', error="Будь ласка, заповніть всі обов'язкові поля", flower=flower)

        order_hash = make_order_hash(ip, sender_name, sender_phone, recipient_name, recipient_phone, description)
        if is_duplicate(order_hash):
            return render_template('complete_order.html')

        photo = request.files.get('photo')
        photo_path = None

        if photo and photo.filename:
            allowed_ext = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
            ext = photo.filename.rsplit('.', 1)[-1].lower()
            if ext not in allowed_ext:
                return render_template('delivery.html', error="Дозволені формати фото: jpg, png, webp, gif",
                                       flower=flower)
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

        register_order(ip)
        return render_template('complete_order.html')

    return render_template('delivery.html', flower=flower)


if __name__ == '__main__':
    bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    bot_thread.start()
    app.run(host="0.0.0.0", port=5000, debug=True)