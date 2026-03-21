from flask import Flask, render_template, request
import os
import json
from werkzeug.utils import secure_filename
import telebot
from telebot import types
import threading
import hashlib
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
bot = telebot.TeleBot(os.getenv('api_key'))

USERS = [5347872932, 6673440979, 5258794783]
UPLOAD_FOLDER = "static/uploads"
EXAMPLES_FILE = "data/examples.json"
ORDER_COOLDOWN = {}
MAX_ORDERS = 5
COOLDOWN_MINUTES = 30
RECENT_ORDERS = {}
DUPLICATE_WINDOW_SECONDS = 15
NOTIFIED_IPS = {}

FLOWERS_DATA = {
    1: {'id':1,'name':'Весняний букет','price':850,'old_price':None,'image':'/static/images/img_4.png','description':'Ніжний весняний букет з тюльпанів, нарцисів та фрезій.','composition':'Тюльпани, нарциси, фрезії, евкаліпт','size':'40-45 см','colors':'Рожевий, білий, жовтий','freshness':'7-10 днів','badge':'Хіт','badge_class':'','category':'bouquet','gallery':[]},
    2: {'id':2,'name':'Романтичний букет','price':1200,'old_price':1400,'image':'/static/images/img_6.png','description':'Розкішний букет з червоних та рожевих троянд преміум класу.','composition':'Троянди Ecuador, піоновидні троянди, евкаліпт','size':'50-55 см','colors':'Червоний, рожевий','freshness':'10-14 днів','badge':'Новинка','badge_class':'new','category':'bouquet','gallery':[]},
    3: {'id':3,'name':'Авторський букет','price':950,'old_price':None,'image':'/static/images/img_5.png','description':'Унікальний авторський букет від нашого флориста.','composition':'Сезонні квіти, декоративна зелень','size':'45-50 см','colors':'За вашим побажанням','freshness':'7-12 днів','badge':None,'badge_class':'','category':'bouquet','gallery':[]},
    4: {'id':4,'name':'Святковий букет','price':1100,'old_price':None,'image':'/static/images/img_7.png','description':'Яскравий святковий букет для особливих подій.','composition':'Троянди, хризантеми, альстромерії, гіперикум','size':'50-55 см','colors':'Мікс яскравих кольорів','freshness':'10-14 днів','badge':'Преміум','badge_class':'premium','category':'bouquet','gallery':[]},
    5: {'id':5,'name':'Флористична композиція','price':1400,'old_price':1600,'image':'/static/images/img_11.png','description':'Елегантна композиція у стильній коробці.','composition':'Троянди, еустома, орхідеї, декоративна зелень','size':'30x30 см','colors':'Пастельні відтінки','freshness':'12-16 днів','badge':'Преміум','badge_class':'premium','category':'composition','gallery':[]},
    6: {'id':6,'name':'Святкова композиція','price':1050,'old_price':None,'image':'/static/images/img_8.png','description':'Компактна святкова композиція у декоративному кашпо.','composition':'Міні-троянди, гвоздики, хризантеми','size':'25x25 см','colors':'Яскраві кольори','freshness':'10-14 днів','badge':None,'badge_class':'','category':'composition','gallery':[]},
    7: {'id':7,'name':'Авторська композиція','price':1250,'old_price':None,'image':'/static/images/img_9.png','description':'Креативна авторська композиція від нашого майстра.','composition':'Сезонні квіти преміум класу','size':'35x35 см','colors':'Авторська палітра','freshness':'12-14 днів','badge':'Новинка','badge_class':'new','category':'composition','gallery':[]},
    8: {'id':8,'name':'Преміум композиція','price':1800,'old_price':2100,'image':'/static/images/img_10.png','description':'Розкішна преміум композиція з найкращих квітів світу.','composition':'Орхідеї, піоновидні троянди Ecuador, антуріум','size':'40x40 см','colors':'Благородні відтінки','freshness':'14-18 днів','badge':'Хіт','badge_class':'','category':'composition','gallery':[]},
}

# =========================================================
# Приклади — завантаження / збереження JSON
# =========================================================
def load_examples():
    if not os.path.exists(EXAMPLES_FILE):
        return []
    with open(EXAMPLES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_examples(data):
    os.makedirs(os.path.dirname(EXAMPLES_FILE), exist_ok=True)
    with open(EXAMPLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

EXAMPLES_DATA = load_examples()


# =========================================================
# Стани бота
# =========================================================
BOT_STATES = {}
def get_state(cid): return BOT_STATES.get(cid, {})
def set_state(cid, d): BOT_STATES[cid] = d
def clear_state(cid): BOT_STATES.pop(cid, None)

# =========================================================
# Утиліти
# =========================================================
def make_order_hash(*args):
    return hashlib.md5('|'.join(str(a) for a in args).encode()).hexdigest()

def is_duplicate(h):
    now = datetime.now()
    for k in [k for k,v in RECENT_ORDERS.items() if now-v>timedelta(seconds=DUPLICATE_WINDOW_SECONDS)]:
        del RECENT_ORDERS[k]
    if h in RECENT_ORDERS: return True
    RECENT_ORDERS[h] = now; return False

def notify_blocked_ip(ip, route):
    last = NOTIFIED_IPS.get(ip)
    if last:
        blocked_at = ORDER_COOLDOWN.get(ip, {}).get('blocked_at')
        if blocked_at and last >= blocked_at: return
    now = datetime.now(); NOTIFIED_IPS[ip] = now
    text = (f"🚫 *Заблокований IP*\n\n⏰ {now.strftime('%d.%m.%Y %H:%M')}\n"
            f"🌐 IP: `{ip}`\n📄 {route}\n\nПеревищено ліміт {MAX_ORDERS} замовлень.")
    for uid in USERS:
        try: bot.send_message(uid, text, parse_mode='Markdown')
        except: pass

def check_cooldown(ip):
    now = datetime.now(); state = ORDER_COOLDOWN.get(ip)
    if not state: return True, None
    if state['blocked_at']:
        diff = now - state['blocked_at']
        if diff < timedelta(minutes=COOLDOWN_MINUTES):
            left = COOLDOWN_MINUTES - int(diff.total_seconds()/60)
            return False, f"Спробуйте через {left} хв."
        ORDER_COOLDOWN[ip] = {'count':0,'blocked_at':None}
    return True, None

def register_order(ip):
    state = ORDER_COOLDOWN.get(ip, {'count':0,'blocked_at':None})
    state['count'] += 1
    if state['count'] >= MAX_ORDERS: state['blocked_at'] = datetime.now()
    ORDER_COOLDOWN[ip] = state

def save_photo_from_bot(file_id, prefix='item'):
    file_info = bot.get_file(file_id)
    data = bot.download_file(file_info.file_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    fname = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    fpath = os.path.join(UPLOAD_FOLDER, fname)
    with open(fpath, 'wb') as f: f.write(data)
    return '/' + fpath.replace('\\', '/')

# =========================================================
# Клавіатури
# =========================================================
def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Додати букет",      callback_data="add_fl_bouquet"),
        types.InlineKeyboardButton("➕ Додати композицію", callback_data="add_fl_composition"),
    )
    kb.add(
        types.InlineKeyboardButton("🖼 Переглянути приклади", callback_data="menu_examples"),
    )
    return kb



def kb_example_list():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, ex in enumerate(EXAMPLES_DATA):
        cat = 'Букет' if ex['category']=='bouquet' else 'Композиція'
        kb.add(types.InlineKeyboardButton(f"[{cat}] {ex['name']}", callback_data=f"view_ex_{i}"))
    kb.add(types.InlineKeyboardButton("➕ Додати приклад", callback_data="add_ex_start"))
    kb.add(types.InlineKeyboardButton("◀️ Назад",          callback_data="back_main"))
    return kb

def kb_example_actions(idx):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗑 Видалити", callback_data=f"del_ex_{idx}"),
        types.InlineKeyboardButton("◀️ Назад",   callback_data="menu_examples"),
    )
    return kb

def kb_badge():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for b in ['Хіт','Новинка','Преміум','Без значка']:
        kb.add(types.InlineKeyboardButton(b, callback_data=f"badge_{b}"))
    return kb

def kb_ex_category():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💐 Букет",      callback_data="ex_cat_bouquet"),
        types.InlineKeyboardButton("🌸 Композиція", callback_data="ex_cat_composition"),
    )
    return kb

# =========================================================
# /start
# =========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id not in USERS:
        bot.send_message(message.chat.id, "❌ Доступ заборонено.")
        return
    bot.send_message(message.chat.id, "👋 Оберіть розділ:", reply_markup=kb_main())

# =========================================================
# Callback
# =========================================================
@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    cid = call.message.chat.id
    mid = call.message.message_id
    data = call.data
    if cid not in USERS:
        bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)

    if data == 'back_main':
        bot.edit_message_text("👋 Оберіть розділ:", cid, mid, reply_markup=kb_main()); return



    if data == 'menu_examples':
        bot.edit_message_text("🖼 Приклади робіт:", cid, mid, reply_markup=kb_example_list()); return





    # Додати букет/композицію → одразу форма
    if data.startswith('add_fl_'):
        category = data.split('add_fl_')[1]
        set_state(cid, {'mode':'flower','category':category,'step':'name'})
        cat_label = 'букет' if category=='bouquet' else 'композицію'
        bot.edit_message_text(
            f"➕ Додаємо {cat_label} до розділу *Приклади*\n\nВведіть *назву*:",
            cid, mid, parse_mode='Markdown'); return

    # Значок
    if data.startswith('badge_'):
        badge_text = data[6:]
        state = get_state(cid)
        if state.get('mode') == 'flower':
            bmap = {'Хіт':('Хіт',''),'Новинка':('Новинка','new'),'Преміум':('Преміум','premium'),'Без значка':(None,'')}
            badge, badge_class = bmap.get(badge_text,(None,''))
            state.update({'badge':badge,'badge_class':badge_class,'step':'photo'})
            set_state(cid, state)
            bot.send_message(cid, "📷 Надішліть фото букету:"); return

    # Категорія прикладу
    if data in ('ex_cat_bouquet','ex_cat_composition'):
        category = 'bouquet' if data=='ex_cat_bouquet' else 'composition'
        state = get_state(cid)
        state.update({'category':category,'step':'ex_name'})
        set_state(cid, state)
        bot.edit_message_text("Введіть *назву* прикладу:", cid, mid, parse_mode='Markdown'); return

    # Додати приклад
    if data == 'add_ex_start':
        set_state(cid, {'mode':'example','step':'ex_category'})
        bot.edit_message_text("🖼 Новий приклад.\n\nОберіть тип:", cid, mid, reply_markup=kb_ex_category()); return

    # Перегляд прикладу
    if data.startswith('view_ex_'):
        idx = int(data.split('_')[-1])
        if idx >= len(EXAMPLES_DATA):
            bot.edit_message_text("❌ Не знайдено.", cid, mid, reply_markup=kb_example_list()); return
        ex = EXAMPLES_DATA[idx]
        cat = 'Букет' if ex['category']=='bouquet' else 'Композиція'
        text = (f"🖼 *{ex['name']}*\n📦 {cat}\n💰 {ex.get('price','—') or '—'} грн\n"
                f"🌸 {ex.get('composition','—')}\n📏 {ex.get('size','—')}\n"
                f"🎨 {ex.get('colors','—')}\n⏳ {ex.get('freshness','—')}")
        bot.edit_message_text(text, cid, mid, parse_mode='Markdown', reply_markup=kb_example_actions(idx)); return

    # Видалення прикладу
    if data.startswith('del_ex_'):
        idx = int(data.split('_')[-1])
        if idx < len(EXAMPLES_DATA):
            name = EXAMPLES_DATA.pop(idx)['name']
            save_examples(EXAMPLES_DATA)
            bot.edit_message_text(f"✅ «{name}» видалено.", cid, mid, reply_markup=kb_example_list()); return

# =========================================================
# Текст — покрокове заповнення
# =========================================================
@bot.message_handler(content_types=['text'])
def on_text(message):
    cid = message.chat.id
    if cid not in USERS: return
    state = get_state(cid)
    step = state.get('step')
    mode = state.get('mode')

    def ask(text, kb=None):
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=kb)

    def skip(val):
        return None if val.strip()=='-' else val.strip()

    if mode == 'flower':
        if step=='name':
            state.update({'name':message.text.strip(),'step':'price'}); set_state(cid,state); ask("Ціна (грн):")
        elif step=='price':
            state.update({'price':message.text.strip(),'step':'old_price'}); set_state(cid,state); ask("Стара ціна (або `-`):")
        elif step=='old_price':
            state.update({'old_price':skip(message.text),'step':'description'}); set_state(cid,state); ask("*Опис*:")
        elif step=='description':
            state.update({'description':message.text.strip(),'step':'composition'}); set_state(cid,state); ask("*Склад* (або `-`):")
        elif step=='composition':
            state.update({'composition':skip(message.text) or '','step':'size'}); set_state(cid,state); ask("*Розмір* (або `-`):")
        elif step=='size':
            state.update({'size':skip(message.text) or '','step':'colors'}); set_state(cid,state); ask("*Кольорова гама* (або `-`):")
        elif step=='colors':
            state.update({'colors':skip(message.text) or '','step':'freshness'}); set_state(cid,state); ask("*Свіжість* (або `-`):")
        elif step=='freshness':
            state.update({'freshness':skip(message.text) or '','step':'badge'}); set_state(cid,state); ask("Оберіть *значок*:", kb_badge())

    elif mode == 'example':
        if step=='ex_name':
            state.update({'name':message.text.strip(),'step':'ex_description'}); set_state(cid,state); ask("*Опис* (або `-`):")
        elif step=='ex_description':
            state.update({'description':skip(message.text) or '','step':'ex_composition'}); set_state(cid,state); ask("*Склад* (або `-`):")
        elif step=='ex_composition':
            state.update({'composition':skip(message.text) or '','step':'ex_size'}); set_state(cid,state); ask("*Розмір* (або `-`):")
        elif step=='ex_size':
            state.update({'size':skip(message.text) or '','step':'ex_colors'}); set_state(cid,state); ask("*Кольорова гама* (або `-`):")
        elif step=='ex_colors':
            state.update({'colors':skip(message.text) or '','step':'ex_freshness'}); set_state(cid,state); ask("*Свіжість* (або `-`):")
        elif step=='ex_freshness':
            state.update({'freshness':skip(message.text) or '','step':'ex_price'}); set_state(cid,state); ask("*Ціна* (або `-`):")
        elif step=='ex_price':
            state.update({'price':skip(message.text),'step':'ex_photo'}); set_state(cid,state); ask("📷 Надішліть фото:")

# =========================================================
# Фото — збереження
# =========================================================
@bot.message_handler(content_types=['photo'])
def on_photo(message):
    cid = message.chat.id
    if cid not in USERS: return
    state = get_state(cid)
    step = state.get('step')
    mode = state.get('mode')

    # Фото для букета — зберігаємо в EXAMPLES_DATA
    if mode == 'flower' and step == 'photo':
        image_url = save_photo_from_bot(message.photo[-1].file_id, prefix='flower')
        EXAMPLES_DATA.append({
            'id': len(EXAMPLES_DATA),
            'category': state['category'],
            'name': state['name'],
            'price': state.get('price'),
            'old_price': state.get('old_price'),
            'description': state.get('description', ''),
            'composition': state.get('composition', ''),
            'size': state.get('size', ''),
            'colors': state.get('colors', ''),
            'freshness': state.get('freshness', ''),
            'badge': state.get('badge'),
            'badge_class': state.get('badge_class', ''),
            'gallery': [],
            'image': image_url,
        })
        save_examples(EXAMPLES_DATA)
        clear_state(cid)
        bot.send_message(
            cid,
            f"✅ «{state['name']}» додано на сторінку Приклади!",
            reply_markup=kb_example_list()
        )
        return

    # Фото для прикладу
    if mode == 'example' and step == 'ex_photo':
        image_url = save_photo_from_bot(message.photo[-1].file_id, prefix='example')
        EXAMPLES_DATA.append({
            'id': len(EXAMPLES_DATA),
            'category': state['category'],
            'name': state['name'],
            'price': state.get('price'),
            'old_price': None,
            'description': state.get('description', ''),
            'composition': state.get('composition', ''),
            'size': state.get('size', ''),
            'colors': state.get('colors', ''),
            'freshness': state.get('freshness', ''),
            'badge': None,
            'badge_class': '',
            'gallery': [],
            'image': image_url,
        })
        save_examples(EXAMPLES_DATA)
        clear_state(cid)
        bot.send_message(
            cid,
            f"✅ Приклад «{state['name']}» додано на сайт!",
            reply_markup=kb_example_list()
        )
        return

    bot.send_message(cid, "⚠️ Зараз не очікується фото. Натисніть /start")

# =========================================================
# Flask routes
# =========================================================
@app.route('/')
def main():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/flowers/<int:flower_id>')
def flower_detail(flower_id):
    flower = FLOWERS_DATA.get(flower_id)
    if not flower: return render_template('404.html'), 404
    related = [f for fid,f in FLOWERS_DATA.items()
               if fid!=flower_id and f['category']==flower['category']][:3]
    return render_template('flower_detail.html', flower=flower, flower_id=flower_id, example_idx=None, related_flowers=related)

@app.route('/examples')
def examples():
    return render_template('examples.html', examples=EXAMPLES_DATA)

@app.route('/examples/<int:idx>')
def example_detail(idx):
    if idx < 0 or idx >= len(EXAMPLES_DATA):
        return render_template('404.html'), 404
    flower = EXAMPLES_DATA[idx]
    related = [
        ex for i, ex in enumerate(EXAMPLES_DATA)
        if i != idx and ex.get('category') == flower.get('category')
    ][:3]
    return render_template('flower_detail.html', flower=flower,
                           flower_id=None, example_idx=idx,
                           related_flowers=related, back_url='/examples')

@app.route('/roses')
def roses():
    return render_template('roses.html', flowers=[f for f in FLOWERS_DATA.values() if f['category']=='bouquet'])

@app.route('/order', methods=['GET','POST'])
def order():
    flower_id = request.args.get('flower', type=int)
    example_idx = request.args.get('example', type=int)
    if flower_id is not None:
        flower = FLOWERS_DATA.get(flower_id)
    elif example_idx is not None and 0 <= example_idx < len(EXAMPLES_DATA):
        flower = EXAMPLES_DATA[example_idx]
    else:
        flower = None
    if request.method == 'POST':
        ip = request.remote_addr
        allowed, error = check_cooldown(ip)
        if not allowed:
            notify_blocked_ip(ip,'Замовлення')
            return render_template('order.html', error=error, flower=flower)
        name = request.form.get('name','').strip()
        phone = request.form.get('phone','').strip()
        description = request.form.get('description','').strip()
        wishes = request.form.get('wishes','').strip()
        if not name or len(phone)<12 or not description:
            return render_template('order.html', error="Заповніть всі обов'язкові поля", flower=flower)
        if is_duplicate(make_order_hash(ip,name,phone,description)):
            return render_template('complete_order.html')
        photo = request.files.get('photo'); photo_path = None
        if photo and photo.filename:
            ext = photo.filename.rsplit('.',1)[-1].lower()
            if ext not in {'jpg','jpeg','png','webp','gif'}:
                return render_template('order.html', error="Формат не підтримується", flower=flower)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            photo_path = os.path.join(UPLOAD_FOLDER, secure_filename(photo.filename))
            photo.save(photo_path)
        # Якщо фото не завантажено але є фото від прикладу
        if not photo_path:
            server_photo = request.form.get('server_photo', '').strip()
            if server_photo and os.path.exists(server_photo.lstrip('/')):
                photo_path = server_photo.lstrip('/')
        text = (f"🌸 *Нове замовлення*\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"👤 *Замовник:* {name}\n📞 {phone}\n\n🛒 {description}\n💭 {wishes or '—'}")
        for uid in USERS:
            try:
                bot.send_message(uid, text, parse_mode='Markdown')
                if photo_path:
                    with open(photo_path,'rb') as img: bot.send_photo(uid, img)
            except Exception as e: print(e)
        register_order(ip)
        return render_template('complete_order.html')
    return render_template('order.html', flower=flower)

@app.route('/delivery', methods=['GET','POST'])
def delivery():
    flower_id = request.args.get('flower', type=int)
    example_idx = request.args.get('example', type=int)
    if flower_id is not None:
        flower = FLOWERS_DATA.get(flower_id)
    elif example_idx is not None and 0 <= example_idx < len(EXAMPLES_DATA):
        flower = EXAMPLES_DATA[example_idx]
    else:
        flower = None
    if request.method == 'POST':
        ip = request.remote_addr
        allowed, error = check_cooldown(ip)
        if not allowed:
            notify_blocked_ip(ip,'Доставка')
            return render_template('delivery.html', error=error, flower=flower)
        delivery_to = request.form.get('delivery_to','self')
        description = request.form.get('description','').strip()
        wishes = request.form.get('wishes','').strip()
        if delivery_to == 'self':
            name=request.form.get('self_name','').strip(); phone=request.form.get('self_phone','').strip()
            city=request.form.get('self_city','').strip(); address=request.form.get('self_address','').strip()
            if not name or len(phone)<12 or not city or not address or not description:
                return render_template('delivery.html', error="Заповніть всі обов'язкові поля", flower=flower)
            if is_duplicate(make_order_hash(ip,name,phone,city,address,description)):
                return render_template('complete_order.html')
            text = (f"🚚 *Доставка (собі)*\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"👤 {name}\n📞 {phone}\n📍 {city}, {address}\n\n🛒 {description}\n💭 {wishes or '—'}")
        else:
            sn=request.form.get('sender_name','').strip(); sp=request.form.get('sender_phone','').strip()
            rn=request.form.get('recipient_name','').strip(); rp=request.form.get('recipient_phone','').strip()
            city=request.form.get('city','').strip(); address=request.form.get('address','').strip()
            video=request.form.get('video','no'); greeting=request.form.get('greeting','no')
            gt=request.form.get('greeting_text','').strip(); music=request.form.get('music','no')
            mt=request.form.get('music_text','').strip()
            if not all([sn,sp,rn,rp,city,address,description]):
                return render_template('delivery.html', error="Заповніть всі обов'язкові поля", flower=flower)
            if is_duplicate(make_order_hash(ip,sn,sp,rn,rp,description)):
                return render_template('complete_order.html')
            text = (f"🚚 *Доставка (іншій)*\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"👤 Від: {sn}\n📞 {sp}\n🎁 Отримувач: {rn}\n📞 {rp}\n📍 {city}, {address}\n\n"
                    f"🎥 Відео: {'Так' if video=='yes' else 'Ні'}\n"
                    f"💌 Привітання: {gt if greeting=='yes' and gt else ('Так' if greeting=='yes' else 'Ні')}\n"
                    f"🎵 Музика: {mt if music=='yes' and mt else ('Так' if music=='yes' else 'Ні')}\n\n"
                    f"🛒 {description}\n💭 {wishes or '—'}")
        photo = request.files.get('photo'); photo_path = None
        if photo and photo.filename:
            ext = photo.filename.rsplit('.',1)[-1].lower()
            if ext not in {'jpg','jpeg','png','webp','gif'}:
                return render_template('delivery.html', error="Формат не підтримується", flower=flower)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            photo_path = os.path.join(UPLOAD_FOLDER, secure_filename(photo.filename))
            photo.save(photo_path)
        if not photo_path:
            server_photo = request.form.get('server_photo', '').strip()
            if server_photo and os.path.exists(server_photo.lstrip('/')):
                photo_path = server_photo.lstrip('/')
        for uid in USERS:
            try:
                bot.send_message(uid, text, parse_mode='Markdown')
                if photo_path:
                    with open(photo_path,'rb') as img: bot.send_photo(uid, img)
            except Exception as e: print(e)
        register_order(ip)
        return render_template('complete_order.html')
    return render_template('delivery.html', flower=flower)

if __name__ == '__main__':
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)