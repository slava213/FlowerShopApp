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
UPLOAD_FOLDER    = "static/uploads"
EXAMPLES_FILE    = "data/examples.json"
ROSES_FILE       = "data/roses.json"
OTHER_FILE       = "data/other_flowers.json"
ACCESSORIES_FILE = "data/accessories.json"
VASES_FILE       = "data/vases.json"
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

def _load_json(path):
    if not os.path.exists(path): return []
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_examples():       return _load_json(EXAMPLES_FILE)
def save_examples(d):      _save_json(EXAMPLES_FILE, d)
def load_roses():          return _load_json(ROSES_FILE)
def save_roses(d):         _save_json(ROSES_FILE, d)
def load_other():          return _load_json(OTHER_FILE)
def save_other(d):         _save_json(OTHER_FILE, d)
def load_accessories():    return _load_json(ACCESSORIES_FILE)
def save_accessories(d):   _save_json(ACCESSORIES_FILE, d)
def load_vases():          return _load_json(VASES_FILE)
def save_vases(d):         _save_json(VASES_FILE, d)

EXAMPLES_DATA = load_examples()

BOT_STATES = {}
def get_state(cid):    return BOT_STATES.get(cid, {})
def set_state(cid, d): BOT_STATES[cid] = d
def clear_state(cid):  BOT_STATES.pop(cid, None)

def make_order_hash(*args):
    return hashlib.md5('|'.join(str(a) for a in args).encode()).hexdigest()

def is_duplicate(h):
    now = datetime.now()
    for k in [k for k,v in RECENT_ORDERS.items()
              if now-v > timedelta(seconds=DUPLICATE_WINDOW_SECONDS)]:
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

def cat_label(category):
    return {'bouquet':'💐 Букет','composition':'🌸 Композиція','rose_bouquet':'🌹 Букет з троянд'}.get(category, category)

def kb_main():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("─── 📦 АСОРТИМЕНТ ───", callback_data="noop"))
    kb.add(
        types.InlineKeyboardButton("🌹 Троянди",     callback_data="menu_roses"),
        types.InlineKeyboardButton("🌸 Інші квіти",  callback_data="menu_other"),
        types.InlineKeyboardButton("🎀 Аксесуари",   callback_data="menu_accessories"),
        types.InlineKeyboardButton("🪴 Вазони",      callback_data="menu_vases"),
    )
    kb.add(types.InlineKeyboardButton("─── 🖼 ПРИКЛАДИ РОБІТ ───", callback_data="noop"))
    kb.add(
        types.InlineKeyboardButton("🖼 Всі приклади",           callback_data="menu_examples"),
        types.InlineKeyboardButton("💐 Додати букет",           callback_data="add_fl_bouquet"),
        types.InlineKeyboardButton("🌸 Додати композицію",      callback_data="add_fl_composition"),
        types.InlineKeyboardButton("🌹 Додати букет з троянд",  callback_data="add_fl_rose_bouquet"),
    )
    return kb

def kb_catalog_list(items, section, title):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, item in enumerate(items):
        kb.add(types.InlineKeyboardButton(
            f"{item['name']} — {item['price']} грн/шт",
            callback_data=f"view_{section}_{i}"
        ))
    kb.add(types.InlineKeyboardButton("➕ Додати новий запис", callback_data=f"add_{section}_start"))
    kb.add(types.InlineKeyboardButton("◀️ Головне меню",       callback_data="back_main"))
    return kb

def kb_catalog_actions(section, idx):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗑 Видалити",      callback_data=f"del_{section}_{idx}"),
        types.InlineKeyboardButton("◀️ До списку",     callback_data=f"menu_{section}"),
    )
    return kb

def kb_examples_list():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, ex in enumerate(EXAMPLES_DATA):
        label = cat_label(ex.get('category',''))
        kb.add(types.InlineKeyboardButton(
            f"{label} {ex['name']}",
            callback_data=f"view_ex_{i}"
        ))
    kb.add(types.InlineKeyboardButton("◀️ Головне меню", callback_data="back_main"))
    return kb

def kb_example_actions(idx):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗑 Видалити",   callback_data=f"del_ex_{idx}"),
        types.InlineKeyboardButton("◀️ До списку", callback_data="menu_examples"),
    )
    return kb

def kb_badge():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for b in ['Хіт','Новинка','Преміум','Без значка']:
        kb.add(types.InlineKeyboardButton(b, callback_data=f"badge_{b}"))
    return kb

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if message.chat.id not in USERS:
        bot.send_message(message.chat.id, "❌ Доступ заборонено."); return
    bot.send_message(message.chat.id,
        "👋 *Панель керування сайтом*\n\nОберіть що хочете зробити:",
        parse_mode='Markdown', reply_markup=kb_main())

@bot.callback_query_handler(func=lambda c: True)
def on_callback(call):
    cid  = call.message.chat.id
    mid  = call.message.message_id
    data = call.data
    if cid not in USERS:
        bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)

    if data == 'noop': return

    if data == 'back_main':
        bot.edit_message_text(
            "👋 *Панель керування сайтом*\n\nОберіть що хочете зробити:",
            cid, mid, parse_mode='Markdown', reply_markup=kb_main()); return

    CATALOG = {
        'roses':       (load_roses,       save_roses,       '🌹 Троянди'),
        'other':       (load_other,       save_other,       '🌸 Інші квіти'),
        'accessories': (load_accessories, save_accessories, '🎀 Аксесуари'),
        'vases':       (load_vases,       save_vases,       '🪴 Вазони'),
    }

    for sec, (loader, _, title) in CATALOG.items():
        if data == f'menu_{sec}':
            items = loader()
            txt = f"*{title}*\n{'Список порожній — додайте перший запис ⬇️' if not items else f'{len(items)} позицій'}"
            bot.edit_message_text(txt, cid, mid, parse_mode='Markdown',
                                  reply_markup=kb_catalog_list(items, sec, title)); return

    for sec, (loader, _, title) in CATALOG.items():
        if data.startswith(f'view_{sec}_'):
            idx = int(data.split('_')[-1])
            items = loader()
            if idx >= len(items):
                bot.edit_message_text("❌ Не знайдено.", cid, mid, reply_markup=kb_main()); return
            item = items[idx]
            txt = f"*{item['name']}*\n💰 {item['price']} грн/шт\n📝 {item.get('description') or '—'}"
            img = item.get('image')
            if img:
                try:
                    bot.delete_message(cid, mid)
                    bot.send_photo(cid, open(img.lstrip('/'), 'rb'),
                                   caption=txt, parse_mode='Markdown',
                                   reply_markup=kb_catalog_actions(sec, idx))
                except:
                    bot.send_message(cid, txt, parse_mode='Markdown',
                                     reply_markup=kb_catalog_actions(sec, idx))
            else:
                bot.edit_message_text(txt, cid, mid, parse_mode='Markdown',
                                      reply_markup=kb_catalog_actions(sec, idx))
            return

    for sec, (loader, saver, title) in CATALOG.items():
        if data.startswith(f'del_{sec}_'):
            idx   = int(data.split('_')[-1])
            items = loader()
            if idx < len(items):
                name = items.pop(idx)['name']
                saver(items)
                txt = f"✅ *«{name}»* видалено.\n\n*{title}*\n{len(items)} позицій"
                bot.edit_message_text(txt, cid, mid, parse_mode='Markdown',
                                      reply_markup=kb_catalog_list(items, sec, title)); return

    for sec in CATALOG:
        if data == f'add_{sec}_start':
            set_state(cid, {'mode': f'catalog_{sec}', 'step': 'cat_name'})
            bot.edit_message_text(
                f"➕ *Додавання до {CATALOG[sec][2]}*\n\nКрок 1/3 — Введіть *назву*:",
                cid, mid, parse_mode='Markdown'); return

    if data == 'menu_examples':
        if not EXAMPLES_DATA:
            bot.edit_message_text(
                "🖼 *Приклади робіт*\n\nСписок порожній.",
                cid, mid, parse_mode='Markdown', reply_markup=kb_examples_list()); return
        bot.edit_message_text(
            f"🖼 *Приклади робіт* — {len(EXAMPLES_DATA)} шт.",
            cid, mid, parse_mode='Markdown', reply_markup=kb_examples_list()); return

    if data.startswith('view_ex_'):
        idx = int(data.split('_')[-1])
        if idx >= len(EXAMPLES_DATA):
            bot.edit_message_text("❌ Не знайдено.", cid, mid,
                                  reply_markup=kb_examples_list()); return
        ex = EXAMPLES_DATA[idx]
        label = cat_label(ex.get('category',''))
        txt = (f"🖼 *{ex['name']}*\n{label}\n\n"
               f"💰 {ex.get('price') or '—'} грн\n"
               f"📝 {ex.get('description') or '—'}\n"
               f"🌸 Склад: {ex.get('composition') or '—'}\n"
               f"📏 Розмір: {ex.get('size') or '—'}\n"
               f"🎨 Кольори: {ex.get('colors') or '—'}\n"
               f"⏳ Свіжість: {ex.get('freshness') or '—'}")
        bot.edit_message_text(txt, cid, mid, parse_mode='Markdown',
                              reply_markup=kb_example_actions(idx)); return

    if data.startswith('del_ex_'):
        idx = int(data.split('_')[-1])
        if idx < len(EXAMPLES_DATA):
            name = EXAMPLES_DATA.pop(idx)['name']
            save_examples(EXAMPLES_DATA)
            bot.edit_message_text(
                f"✅ *«{name}»* видалено.\n\n🖼 *Приклади робіт* — {len(EXAMPLES_DATA)} шт.",
                cid, mid, parse_mode='Markdown', reply_markup=kb_examples_list()); return

    if data.startswith('add_fl_'):
        category = data[7:]
        set_state(cid, {'mode': 'example', 'category': category, 'step': 'ex_name'})
        lbl = cat_label(category)
        bot.edit_message_text(
            f"➕ *Новий приклад — {lbl}*\n\nКрок 1 — Введіть *назву*:",
            cid, mid, parse_mode='Markdown'); return

    if data.startswith('badge_'):
        badge_text = data[6:]
        state = get_state(cid)
        if state.get('mode') == 'flower':
            bmap = {'Хіт':('Хіт',''),'Новинка':('Новинка','new'),
                    'Преміум':('Преміум','premium'),'Без значка':(None,'')}
            badge, badge_class = bmap.get(badge_text, (None,''))
            state.update({'badge': badge, 'badge_class': badge_class, 'step': 'photo'})
            set_state(cid, state)
            bot.send_message(cid, "📷 Надішліть фото букету:"); return

@bot.message_handler(content_types=['text'])
def on_text(message):
    cid = message.chat.id
    if cid not in USERS: return
    state = get_state(cid)
    step  = state.get('step')
    mode  = state.get('mode')

    def ask(text, kb=None):
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=kb)

    def skip(val):
        return None if val.strip() == '-' else val.strip()

    if mode == 'example':
        if step == 'ex_name':
            state.update({'name': message.text.strip(), 'step': 'ex_description'})
            set_state(cid, state); ask("Крок 2 — *Опис* (або `-` щоб пропустити):")
        elif step == 'ex_description':
            state.update({'description': skip(message.text) or '', 'step': 'ex_composition'})
            set_state(cid, state); ask("Крок 3 — *Склад* (або `-`):")
        elif step == 'ex_composition':
            state.update({'composition': skip(message.text) or '', 'step': 'ex_size'})
            set_state(cid, state); ask("Крок 4 — *Розмір* (або `-`):")
        elif step == 'ex_size':
            state.update({'size': skip(message.text) or '', 'step': 'ex_colors'})
            set_state(cid, state); ask("Крок 5 — *Кольорова гама* (або `-`):")
        elif step == 'ex_colors':
            state.update({'colors': skip(message.text) or '', 'step': 'ex_freshness'})
            set_state(cid, state); ask("Крок 6 — *Свіжість* (або `-`):")
        elif step == 'ex_freshness':
            state.update({'freshness': skip(message.text) or '', 'step': 'ex_price'})
            set_state(cid, state); ask("Крок 7 — *Ціна* в грн (або `-`):")
        elif step == 'ex_price':
            state.update({'price': skip(message.text), 'step': 'ex_photo'})
            set_state(cid, state); ask("Крок 8 — 📷 Надішліть *фото*:")

    elif mode == 'flower':
        if step == 'name':
            state.update({'name': message.text.strip(), 'step': 'price'})
            set_state(cid, state); ask("Крок 2 — *Ціна* (грн):")
        elif step == 'price':
            state.update({'price': message.text.strip(), 'step': 'old_price'})
            set_state(cid, state); ask("Крок 3 — Стара ціна (або `-`):")
        elif step == 'old_price':
            state.update({'old_price': skip(message.text), 'step': 'description'})
            set_state(cid, state); ask("Крок 4 — *Опис*:")
        elif step == 'description':
            state.update({'description': message.text.strip(), 'step': 'composition'})
            set_state(cid, state); ask("Крок 5 — *Склад* (або `-`):")
        elif step == 'composition':
            state.update({'composition': skip(message.text) or '', 'step': 'size'})
            set_state(cid, state); ask("Крок 6 — *Розмір* (або `-`):")
        elif step == 'size':
            state.update({'size': skip(message.text) or '', 'step': 'colors'})
            set_state(cid, state); ask("Крок 7 — *Кольорова гама* (або `-`):")
        elif step == 'colors':
            state.update({'colors': skip(message.text) or '', 'step': 'freshness'})
            set_state(cid, state); ask("Крок 8 — *Свіжість* (або `-`):")
        elif step == 'freshness':
            state.update({'freshness': skip(message.text) or '', 'step': 'badge'})
            set_state(cid, state); ask("Крок 9 — Оберіть *значок*:", kb_badge())

    elif mode and mode.startswith('catalog_'):
        section = mode.replace('catalog_', '')
        CATALOG_INFO = {
            'roses':       (load_roses,       save_roses,       '🌹 Троянди'),
            'other':       (load_other,       save_other,       '🌸 Інші квіти'),
            'accessories': (load_accessories, save_accessories, '🎀 Аксесуари'),
            'vases':       (load_vases,       save_vases,       '🪴 Вазони'),
        }
        loader, saver, title = CATALOG_INFO[section]

        if step == 'cat_name':
            state.update({'name': message.text.strip(), 'step': 'cat_price'})
            set_state(cid, state); ask("Крок 2/3 — *Ціна* за штуку (грн):")
        elif step == 'cat_price':
            state.update({'price': message.text.strip(), 'step': 'cat_desc'})
            set_state(cid, state); ask("Крок 3/3 — *Опис* (або `-`):")
        elif step == 'cat_desc':
            state.update({'description': skip(message.text) or '', 'step': 'cat_photo'})
            set_state(cid, state)
            ask("📷 Надішліть *фото* (або `-` щоб пропустити):")
        elif step == 'cat_photo' and message.text and message.text.strip() == '-':
            items = loader()
            items.append({
                'name': state['name'],
                'price': state['price'],
                'description': state.get('description', ''),
                'image': None,
            })
            saver(items)
            clear_state(cid)
            ask(f"✅ *«{state['name']}»* додано до {title}!")

@bot.message_handler(content_types=['photo'])
def on_photo(message):
    cid = message.chat.id
    if cid not in USERS: return
    state = get_state(cid)
    step  = state.get('step')
    mode  = state.get('mode')

    if mode == 'example' and step == 'ex_photo':
        image_url = save_photo_from_bot(message.photo[-1].file_id, prefix='example')
        EXAMPLES_DATA.append({
            'id':          len(EXAMPLES_DATA),
            'category':    state['category'],
            'name':        state['name'],
            'price':       state.get('price'),
            'old_price':   None,
            'description': state.get('description', ''),
            'composition': state.get('composition', ''),
            'size':        state.get('size', ''),
            'colors':      state.get('colors', ''),
            'freshness':   state.get('freshness', ''),
            'badge':       None,
            'badge_class': '',
            'gallery':     [],
            'image':       image_url,
        })
        save_examples(EXAMPLES_DATA)
        clear_state(cid)
        lbl = cat_label(state['category'])
        bot.send_message(cid,
            f"✅ {lbl} *«{state['name']}»* додано на сайт!",
            parse_mode='Markdown', reply_markup=kb_main())
        return

    if mode == 'flower' and step == 'photo':
        image_url = save_photo_from_bot(message.photo[-1].file_id, prefix='flower')
        EXAMPLES_DATA.append({
            'id':          len(EXAMPLES_DATA),
            'category':    state['category'],
            'name':        state['name'],
            'price':       state.get('price'),
            'old_price':   state.get('old_price'),
            'description': state.get('description', ''),
            'composition': state.get('composition', ''),
            'size':        state.get('size', ''),
            'colors':      state.get('colors', ''),
            'freshness':   state.get('freshness', ''),
            'badge':       state.get('badge'),
            'badge_class': state.get('badge_class', ''),
            'gallery':     [],
            'image':       image_url,
        })
        save_examples(EXAMPLES_DATA)
        clear_state(cid)
        bot.send_message(cid,
            f"✅ *«{state['name']}»* додано до Прикладів!",
            parse_mode='Markdown', reply_markup=kb_main())
        return

    if mode and mode.startswith('catalog_') and step == 'cat_photo':
        section = mode.replace('catalog_', '')
        CATALOG_INFO = {
            'roses':       (load_roses,       save_roses,       '🌹 Троянди'),
            'other':       (load_other,       save_other,       '🌸 Інші квіти'),
            'accessories': (load_accessories, save_accessories, '🎀 Аксесуари'),
            'vases':       (load_vases,       save_vases,       '🪴 Вазони'),
        }
        loader, saver, title = CATALOG_INFO[section]
        image_url = save_photo_from_bot(message.photo[-1].file_id, prefix='catalog')
        items = loader()
        items.append({
            'name':        state['name'],
            'price':       state['price'],
            'description': state.get('description', ''),
            'image':       image_url,
        })
        saver(items)
        clear_state(cid)
        bot.send_message(cid,
            f"✅ *«{state['name']}»* додано до {title}!",
            parse_mode='Markdown', reply_markup=kb_catalog_list(items, section, title))
        return

    bot.send_message(cid, "⚠️ Зараз не очікується фото. Натисніть /start")

# =========================================================
# Flask routes
# =========================================================
@app.route('/')
def main():
    products = list(FLOWERS_DATA.values())
    examples = EXAMPLES_DATA[:6] if EXAMPLES_DATA else []
    featured = [f for f in products if f.get('badge')][:4]
    return render_template('index.html',
        products=products,
        featured_products=featured if featured else None,
        examples=examples if examples else None)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/flowers/<int:flower_id>')
def flower_detail(flower_id):
    flower = FLOWERS_DATA.get(flower_id)
    if not flower: return render_template('404.html'), 404
    related = [f for fid,f in FLOWERS_DATA.items()
               if fid != flower_id and f['category'] == flower['category']][:3]
    return render_template('flower_detail.html', flower=flower,
                           flower_id=flower_id, example_idx=None, related_flowers=related)

@app.route('/examples')
def examples():
    return render_template('examples.html', examples=EXAMPLES_DATA)

@app.route('/examples/<int:idx>')
def example_detail(idx):
    if idx < 0 or idx >= len(EXAMPLES_DATA):
        return render_template('404.html'), 404
    flower = EXAMPLES_DATA[idx]
    related = [(i, ex) for i, ex in enumerate(EXAMPLES_DATA)
               if i != idx and ex.get('category') == flower.get('category')][:3]
    related_flowers = [ex for _, ex in related]
    return render_template('flower_detail.html', flower=flower,
                           flower_id=None, example_idx=idx,
                           related_flowers=related_flowers, back_url='/examples')

@app.route('/assortment')
def assortment():
    rose_examples = [(i, ex) for i, ex in enumerate(EXAMPLES_DATA)
                     if ex.get('category') == 'rose_bouquet']
    return render_template('assortment.html',
                           roses=load_roses(),
                           other=load_other(),
                           accessories=load_accessories(),
                           vases=load_vases(),
                           rose_examples=rose_examples)

@app.route('/assortment/rose/<int:idx>')
def rose_detail(idx):
    roses = load_roses()
    if idx < 0 or idx >= len(roses):
        return render_template('404.html'), 404
    rose_examples = [(i, ex) for i, ex in enumerate(EXAMPLES_DATA)
                     if ex.get('category') == 'rose_bouquet']
    return render_template('rose_detail.html', rose=roses[idx], idx=idx,
                           rose_examples=rose_examples)

@app.route('/order', methods=['GET','POST'])
def order():
    flower_id   = request.args.get('flower', type=int)
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
            notify_blocked_ip(ip, 'Замовлення')
            return render_template('order.html', error=error, flower=flower)
        name        = request.form.get('name','').strip()
        phone       = request.form.get('phone','').strip()
        description = request.form.get('description','').strip()
        wishes      = request.form.get('wishes','').strip()
        if not name or len(phone) < 12 or not description:
            return render_template('order.html', error="Заповніть всі обов'язкові поля", flower=flower)
        if is_duplicate(make_order_hash(ip, name, phone, description)):
            return render_template('complete_order.html')
        photo = request.files.get('photo'); photo_path = None
        if photo and photo.filename:
            ext = photo.filename.rsplit('.',1)[-1].lower()
            if ext not in {'jpg','jpeg','png','webp','gif'}:
                return render_template('order.html', error="Формат не підтримується", flower=flower)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            photo_path = os.path.join(UPLOAD_FOLDER, secure_filename(photo.filename))
            photo.save(photo_path)
        if not photo_path:
            sp = request.form.get('server_photo','').strip()
            if sp and os.path.exists(sp.lstrip('/')):
                photo_path = sp.lstrip('/')
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
    flower_id   = request.args.get('flower', type=int)
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
            notify_blocked_ip(ip, 'Доставка')
            return render_template('delivery.html', error=error, flower=flower)
        delivery_to = request.form.get('delivery_to','self')
        description = request.form.get('description','').strip()
        wishes      = request.form.get('wishes','').strip()
        if delivery_to == 'self':
            name    = request.form.get('self_name','').strip()
            phone   = request.form.get('self_phone','').strip()
            city    = request.form.get('self_city','').strip()
            address = request.form.get('self_address','').strip()
            if not name or len(phone)<12 or not city or not address or not description:
                return render_template('delivery.html', error="Заповніть всі обов'язкові поля", flower=flower)
            if is_duplicate(make_order_hash(ip,name,phone,city,address,description)):
                return render_template('complete_order.html')
            text = (f"🚚 *Доставка (собі)*\n\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"👤 {name}\n📞 {phone}\n📍 {city}, {address}\n\n🛒 {description}\n💭 {wishes or '—'}")
        else:
            sn  = request.form.get('sender_name','').strip()
            sp  = request.form.get('sender_phone','').strip()
            rn  = request.form.get('recipient_name','').strip()
            rp  = request.form.get('recipient_phone','').strip()
            city    = request.form.get('city','').strip()
            address = request.form.get('address','').strip()
            video   = request.form.get('video','no')
            greeting= request.form.get('greeting','no')
            gt      = request.form.get('greeting_text','').strip()
            music   = request.form.get('music','no')
            mt      = request.form.get('music_text','').strip()
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
            sp2 = request.form.get('server_photo','').strip()
            if sp2 and os.path.exists(sp2.lstrip('/')):
                photo_path = sp2.lstrip('/')
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