"""Bot tarjimalari — 🇺🇿 UZ / 🇷🇺 RU / 🇬🇧 EN (platformaning ko'p tillilik falsafasi)."""

STRINGS: dict[str, dict[str, str]] = {
    # ==================================================================== UZ
    "uz": {
        "welcome": "Assalomu alaykum, <b>{name}</b>! 👋\n\nAVTOMAKTAB tizimiga xush kelibsiz.\nQaysi avtomaktab platformasiga kirmoqchisiz?",
        "welcome_first": "Assalomu alaykum! 👋\n\nAVTOMAKTAB tizimiga xush kelibsiz.\nIltimos, tilni tanlang:",
        "choose_school": "Quyidagi avtomaktablardan birini tanlang:",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_saved": "✅ Til saqlandi: {lang}",
        "empty_list": "Hozircha ro'yxat bo'sh. Keyinroq urinib ko'ring. 😊",
        "empty_hint": "Batafsil: /help",
        "empty_admin_hint": "Siz admin ekansiz: /add_school bilan birinchi avtomaktabni qo'shing.",
        "school_card": "<b>🏫 {nomi}</b>\n\n{meta}🔗 <b>Platforma:</b> {url}",
        "school_meta_district": "🗺️ Hudud: {value}\n",
        "school_meta_local": "📍 Manzil: {value}\n",
        "school_meta_phone": "📞 Telefon: {value}\n",
        "open": "🔗 Platformaga kirish",
        "back": "◀️ Orqaga",
        "not_found": "⚠️ Avtomaktab topilmadi yoki vaqtincha o'chirilgan.",
        "help": (
            "<b>🚗 AVTOMAKTAB — yordam</b>\n\n"
            "/start — asosiy menyu\n"
            "/lang — tilni o'zgartirish\n\n"
            "Avtomaktab tugmasini bossangiz, uning platformasiga o'tadigan havola chiqadi. "
            "Kirish uchun «Platformaga kirish» tugmasini bosing."
        ),
        "not_admin": "⛔ Bu buyruq faqat administratorlar uchun.",
        # ---- admin: qo'shish (wizard) ----
        "add_ask_name": "✏️ Yangi avtomaktab qo'shish.\n\nBekor qilish: <code>/cancel</code>\n\n1/6 — Avtomaktab nomi (masalan «Avtomaktab Chilonzor»):",
        "add_ask_url": "2/6 — Platforma login sahifasi manzili (URL):\nMasalan: <code>https://chilonzor.avtomaktab.uz</code>",
        "invalid_url": "⚠️ URL <code>http://</code> yoki <code>https://</code> bilan boshlanishi shart. Qayta kiriting:",
        "add_ask_district": "3/6 — Hudud/tuman (ixtiyoriy). O'tkazib yuborish: <code>/skip</code>:",
        "add_ask_address": "4/6 — Manzil (ixtiyoriy). O'tkazib yuborish: <code>/skip</code>:",
        "add_ask_phone": "5/6 — Telefon (ixtiyoriy). O'tkazib yuborish: <code>/skip</code>:",
        "add_ask_logo": "6/6 — Logotip URL (ixtiyoriy). O'tkazib yuborish: <code>/skip</code>:",
        "add_confirm_q": "Tasdiqlaysizmi?\n\n<b>{nomi}</b>\n🔗 {url}\n🗺️ {tuman}\n📍 {manzil}\n📞 {telefon}",
        "add_yes": "✅ Saqlash",
        "add_no": "❌ Bekor qilish",
        "saved": "✅ Saqlandi (ID {id}).\n\n👉 Deep link: <code>t.me/{bot}?start={slug}</code>\nDo'kon/reyklamada shu havoladan QR kod yasash mumkin.",
        "cancelled": "Bekor qilindi.",
        # ---- admin: ro'yxat / tahrir ----
        "list_empty": "Ro'yxat bo'sh. <code>/add_school</code> bilan qo'shing.",
        "list_header": "📋 Avtomaktablar ro'yxati\n🟢 faol · ⚪ o'chirilgan\n\n",
        "list_row": "{icon} <b>{nomi}</b> (ID {id}) — {url}\n",
        "edit_choose": "✏️ Tahrirlash uchun avtomaktabni tanlang:",
        "edit_field_ask": "«{school}» — qaysi maydonni tahrirlaymiz?",
        "edit_value_ask": "✏️ Yangi qiymat  ({school} → <b>{field}</b>):\n<code>/cancel</code> — bekor qilish",
        "edited": "✅ Yangilandi: <b>{field}</b> → <i>{value}</i>",
        # ---- admin: holat / o'chirish ----
        "status_choose": "🔄 Faollikni o'zgartirish — avtomaktabni tanlang:",
        "status_confirm_q": "«{nomi}» holatini o'zgartiramizmi?\nHozir: {state}",
        "status_on": "🟢 Faol",
        "status_off": "⚪ O'chirilgan",
        "status_updated": "✅ «{nomi}» endi {state}.",
        "delete_choose": "🗑️ O'chirish — avtomaktabni tanlang:",
        "delete_confirm_q": "«{nomi}» ni butunlay o'chirasizmi?\n(Statistika ham yo'qoladi)",
        "delete_yes": "🗑️ Ha, o'chirish",
        "deleted": "🗑️ «{nomi}» o'chirildi.",
        "yes_btn": "✅ Tasdiqlash",
        "no_btn": "❌ Bekor qilish",
        # ---- admin: statistika / QR ----
        "stats_header": "📊 Statistika (avtomaktab bo'yicha bosishlar)\n\n",
        "stats_empty": "Hali hech qanday bosish qayd etilmagan.",
        "stats_row": "{nomi} — <b>{count}</b> marta\n",
        "stats_users": "🧑 Foydalanuvchilar: {users}",
        "qr_usage": "Ishlatish: <code>/qr &lt;id|slug&gt;</code>\nMasalan: <code>/qr 3</code> yoki <code>/qr chilonzor</code>",
        "qr_sent": "✅ QR tayyor!\nHavola: <code>t.me/{bot}?start={slug}</code>",
        "set_url_usage": "🌐 Platforma manzili: <code>{url}</code>\n\nYangilash uchun: <code>/set_url https://yangi.manzil</code>",
        "set_url_done": "✅ Platforma manzili yangilandi:\n<code>{url}</code>\n\nFoydalanuvchilar endi shu manzilga olib boriladi.\nDeep link: <code>t.me/{bot}?start=platforma</code>",
        "qr_error": "⚠️ Avtomaktab topilmadi.",
        "admin_cmds": (
            "🛠️ <b>Admin buyruqlari</b>\n\n"
            "/add_school — yangi avtomaktab qo'shish\n"
            "/list_schools — ro'yxat\n"
            "/edit_school — tahrirlash\n"
            "/set_status — faollikni o'zgartirish\n"
            "/remove_school — o'chirish (alias: /delete_school)\n"
            "/set_url <https://...> — platforma manzilini yangilash\n"
            "/stats — statistika\n"
            "/qr &lt;id|slug&gt; — QR kod (deep link)\n"
            "/cancel — joriy amalni bekor qilish"
        ),
        # ---- maydon nomlari ----
        "field_nomi": "Nomi",
        "field_login_url": "Login URL",
        "field_tuman": "Hudud/tuman",
        "field_manzil": "Manzil",
        "field_telefon": "Telefon",
        "field_logotip_url": "Logotip URL",
    },
    # ==================================================================== RU
    "ru": {
        "welcome": "Здравствуйте, <b>{name}</b>! 👋\n\nДобро пожаловать в систему AVTOMAKTAB.\nВ какую автошколу хотите войти?",
        "welcome_first": "Здравствуйте! 👋\n\nДобро пожаловать в AVTOMAKTAB.\nПожалуйста, выберите язык:",
        "choose_school": "Выберите одну из автошкол:",
        "choose_lang": "🌐 Выберите язык:",
        "lang_saved": "✅ Язык сохранён: {lang}",
        "empty_list": "Пока список пуст. Попробуйте позже. 😊",
        "empty_hint": "Подробнее: /help",
        "empty_admin_hint": "Вы администратор: добавьте первую автошколу через /add_school.",
        "school_card": "<b>🏫 {nomi}</b>\n\n{meta}🔗 <b>Платформа:</b> {url}",
        "school_meta_district": "🗺️ Район: {value}\n",
        "school_meta_local": "📍 Адрес: {value}\n",
        "school_meta_phone": "📞 Телефон: {value}\n",
        "open": "🔗 Войти в платформу",
        "back": "◀️ Назад",
        "not_found": "⚠️ Автошкола не найдена или временно отключена.",
        "help": (
            "<b>🚗 AVTOMAKTAB — помощь</b>\n\n"
            "/start — главное меню\n"
            "/lang — смена языка\n\n"
            "Нажмите на кнопку автошколы — получите ссылку на её платформу."
        ),
        "not_admin": "⛔ Эта команда доступна только администраторам.",
        "add_ask_name": "✏️ Добавление новой автошколы.\n\nОтмена: <code>/cancel</code>\n\n1/6 — Название (например «Автошкола Чиланзар»):",
        "add_ask_url": "2/6 — Адрес страницы входа (URL):\nНапример: <code>https://chilonzor.avtomaktab.uz</code>",
        "invalid_url": "⚠️ URL должен начинаться с <code>http://</code> или <code>https://</code>. Введите снова:",
        "add_ask_district": "3/6 — Район (необязательно). Пропустить: <code>/skip</code>:",
        "add_ask_address": "4/6 — Адрес (необязательно). Пропустить: <code>/skip</code>:",
        "add_ask_phone": "5/6 — Телефон (необязательно). Пропустить: <code>/skip</code>:",
        "add_ask_logo": "6/6 — URL логотипа (необязательно). Пропустить: <code>/skip</code>:",
        "add_confirm_q": "Подтвердите:\n\n<b>{nomi}</b>\n🔗 {url}\n🗺️ {tuman}\n📍 {manzil}\n📞 {telefon}",
        "add_yes": "✅ Сохранить",
        "add_no": "❌ Отменить",
        "saved": "✅ Сохранено (ID {id}).\n\n👉 Deep link: <code>t.me/{bot}?start={slug}</code>\nИз этой ссылки можно сделать QR-код.",
        "cancelled": "Отменено.",
        "list_empty": "Список пуст. Добавьте через <code>/add_school</code>.",
        "list_header": "📋 Список автошкол\n🟢 активна · ⚪ отключена\n\n",
        "list_row": "{icon} <b>{nomi}</b> (ID {id}) — {url}\n",
        "edit_choose": "✏️ Выберите автошколу для редактирования:",
        "edit_field_ask": "«{school}» — какое поле редактируем?",
        "edit_value_ask": "✏️ Новое значение  ({school} → <b>{field}</b>):\n<code>/cancel</code> — отмена",
        "edited": "✅ Обновлено: <b>{field}</b> → <i>{value}</i>",
        "status_choose": "🔄 Изменение активности — выберите автошколу:",
        "status_confirm_q": "Изменить статус «{nomi}»?\nСейчас: {state}",
        "status_on": "🟢 Активна",
        "status_off": "⚪ Отключена",
        "status_updated": "✅ «{nomi}» теперь {state}.",
        "delete_choose": "🗑️ Удаление — выберите автошколу:",
        "delete_confirm_q": "Полностью удалить «{nomi}»?\n(Статистика тоже будет удалена)",
        "delete_yes": "🗑️ Да, удалить",
        "deleted": "🗑️ «{nomi}» удалена.",
        "yes_btn": "✅ Подтвердить",
        "no_btn": "❌ Отмена",
        "stats_header": "📊 Статистика (переходы по школам)\n\n",
        "stats_empty": "Переходов пока нет.",
        "stats_row": "{nomi} — <b>{count}</b> раз\n",
        "stats_users": "🧑 Пользователей: {users}",
        "qr_usage": "Использование: <code>/qr &lt;id|slug&gt;</code>\nНапример: <code>/qr 3</code> или <code>/qr chilonzor</code>",
        "qr_sent": "✅ QR готов!\nСсылка: <code>t.me/{bot}?start={slug}</code>",
        "set_url_usage": "🌐 Адрес платформы: <code>{url}</code>\n\nОбновить: <code>/set_url https://новый.адрес</code>",
        "set_url_done": "✅ Адрес платформы обновлён:\n<code>{url}</code>\n\nПользователи теперь попадают на этот адрес.\nDeep link: <code>t.me/{bot}?start=platforma</code>",
        "qr_error": "⚠️ Автошкола не найдена.",
        "admin_cmds": (
            "🛠️ <b>Команды администратора</b>\n\n"
            "/add_school — добавить автошколу\n"
            "/list_schools — список\n"
            "/edit_school — редактировать\n"
            "/set_status — активность\n"
            "/remove_school — удалить (псевдоним: /delete_school)\n"
            "/set_url <https://...> — обновить адрес платформы\n"
            "/stats — статистика\n"
            "/qr &lt;id|slug&gt; — QR-код (deep link)\n"
            "/cancel — отменить действие"
        ),
        "field_nomi": "Название",
        "field_login_url": "Login URL",
        "field_tuman": "Район",
        "field_manzil": "Адрес",
        "field_telefon": "Телефон",
        "field_logotip_url": "URL логотипа",
    },
    # ==================================================================== EN
    "en": {
        "welcome": "Hello, <b>{name}</b>! 👋\n\nWelcome to the AVTOMAKTAB system.\nWhich driving school platform would you like to enter?",
        "welcome_first": "Hello! 👋\n\nWelcome to AVTOMAKTAB.\nPlease choose a language:",
        "choose_school": "Choose one of the driving schools:",
        "choose_lang": "🌐 Choose language:",
        "lang_saved": "✅ Language saved: {lang}",
        "empty_list": "The list is empty for now. Try again later. 😊",
        "empty_hint": "Details: /help",
        "empty_admin_hint": "You are an admin: add the first school with /add_school.",
        "school_card": "<b>🏫 {nomi}</b>\n\n{meta}🔗 <b>Platform:</b> {url}",
        "school_meta_district": "🗺️ District: {value}\n",
        "school_meta_local": "📍 Address: {value}\n",
        "school_meta_phone": "📞 Phone: {value}\n",
        "open": "🔗 Enter platform",
        "back": "◀️ Back",
        "not_found": "⚠️ School not found or temporarily disabled.",
        "help": (
            "<b>🚗 AVTOMAKTAB — help</b>\n\n"
            "/start — main menu\n"
            "/lang — change language\n\n"
            "Tap a school button to get the link to its platform."
        ),
        "not_admin": "⛔ This command is for administrators only.",
        "add_ask_name": "✏️ Adding a new driving school.\n\nCancel: <code>/cancel</code>\n\n1/6 — Name (e.g. «Avtomaktab Chilonzor»):",
        "add_ask_url": "2/6 — Login page URL:\nExample: <code>https://chilonzor.avtomaktab.uz</code>",
        "invalid_url": "⚠️ URL must start with <code>http://</code> or <code>https://</code>. Try again:",
        "add_ask_district": "3/6 — District (optional). Skip with <code>/skip</code>:",
        "add_ask_address": "4/6 — Address (optional). Skip with <code>/skip</code>:",
        "add_ask_phone": "5/6 — Phone (optional). Skip with <code>/skip</code>:",
        "add_ask_logo": "6/6 — Logo URL (optional). Skip with <code>/skip</code>:",
        "add_confirm_q": "Confirm:\n\n<b>{nomi}</b>\n🔗 {url}\n🗺️ {tuman}\n📍 {manzil}\n📞 {telefon}",
        "add_yes": "✅ Save",
        "add_no": "❌ Cancel",
        "saved": "✅ Saved (ID {id}).\n\n👉 Deep link: <code>t.me/{bot}?start={slug}</code>\nYou can make a QR code from this link.",
        "cancelled": "Cancelled.",
        "list_empty": "List is empty. Add via <code>/add_school</code>.",
        "list_header": "📋 Driving schools\n🟢 active · ⚪ disabled\n\n",
        "list_row": "{icon} <b>{nomi}</b> (ID {id}) — {url}\n",
        "edit_choose": "✏️ Choose a school to edit:",
        "edit_field_ask": "«{school}» — which field to edit?",
        "edit_value_ask": "✏️ New value  ({school} → <b>{field}</b>):\n<code>/cancel</code> — cancel",
        "edited": "✅ Updated: <b>{field}</b> → <i>{value}</i>",
        "status_choose": "🔄 Change activity — choose a school:",
        "status_confirm_q": "Change status of «{nomi}»?\nNow: {state}",
        "status_on": "🟢 Active",
        "status_off": "⚪ Disabled",
        "status_updated": "✅ «{nomi}» is now {state}.",
        "delete_choose": "🗑️ Delete — choose a school:",
        "delete_confirm_q": "Permanently delete «{nomi}»?\n(Statistics will be removed too)",
        "delete_yes": "🗑️ Yes, delete",
        "deleted": "🗑️ «{nomi}» deleted.",
        "yes_btn": "✅ Confirm",
        "no_btn": "❌ Cancel",
        "stats_header": "📊 Statistics (clicks per school)\n\n",
        "stats_empty": "No clicks recorded yet.",
        "stats_row": "{nomi} — <b>{count}</b> times\n",
        "stats_users": "🧑 Users: {users}",
        "qr_usage": "Usage: <code>/qr &lt;id|slug&gt;</code>\nExample: <code>/qr 3</code> or <code>/qr chilonzor</code>",
        "qr_sent": "✅ QR is ready!\nLink: <code>t.me/{bot}?start={slug}</code>",
        "set_url_usage": "🌐 Platform address: <code>{url}</code>\n\nUpdate: <code>/set_url https://new.address</code>",
        "set_url_done": "✅ Platform address updated:\n<code>{url}</code>\n\nUsers now land on this address.\nDeep link: <code>t.me/{bot}?start=platforma</code>",
        "qr_error": "⚠️ School not found.",
        "admin_cmds": (
            "🛠️ <b>Admin commands</b>\n\n"
            "/add_school — add a school\n"
            "/list_schools — list\n"
            "/edit_school — edit\n"
            "/set_status — activity\n"
            "/remove_school — delete (alias: /delete_school)\n"
            "/set_url <https://...> — update platform address\n"
            "/stats — statistics\n"
            "/qr &lt;id|slug&gt; — QR code (deep link)\n"
            "/cancel — cancel current action"
        ),
        "field_nomi": "Name",
        "field_login_url": "Login URL",
        "field_tuman": "District",
        "field_manzil": "Address",
        "field_telefon": "Phone",
        "field_logotip_url": "Logo URL",
    },
}

LANG_NAMES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}


def t(code: str, key: str, **kw) -> str:
    """Tarjima olish: t('uz', 'saved', id=1, ...)

    DIQQAT: birinchi parametr `code` deb nomlangan (emas `lang`) — aks holda
    `t(lang, "lang_saved", lang="🇺🇿 O'zbekcha")` kabi chaqiruvlarda
    "got multiple values for argument" xatosi chiqardi.
    """
    table = STRINGS.get(code) or STRINGS["uz"]
    s = table.get(key) or STRINGS["uz"].get(key) or key
    if kw:
        for k, v in kw.items():
            s = s.replace("{%s}" % k, str(v))
    return s