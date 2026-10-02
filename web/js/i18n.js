/* Ko'p tillilik: UZ (default) / RU / EN. Tanlangan til localStorage'da saqlanadi. */
const I18N = (function () {
  const DICT = {
    // ---- auth
    "auth.login_title": { uz: "Avtomaktab amaliy mashg'ulotlari", ru: "Автомобильные практические занятия", en: "Driving practical lessons" },
    "auth.login_subtitle": { uz: "Amaliy mashg'ulotlarni boshqarish platformasi", ru: "Платформа управления практическими занятиями", en: "Practical training management platform" },
    "auth.role_student": { uz: "Talaba", ru: "Ученик", en: "Student" },
    "auth.role_instructor": { uz: "Instruktor", ru: "Инструктор", en: "Instructor" },
    "auth.role_admin": { uz: "Admin", ru: "Админ", en: "Admin" },
    "auth.role_switch": { uz: "Rolni tanlang", ru: "Выберите роль", en: "Select your role" },
    "auth.role_required": { uz: "Rolni tanlash shart", ru: "Роль обязательна", en: "Role is required" },
    "auth.login": { uz: "Login", ru: "Логин", en: "Login" },
    "auth.password": { uz: "Parol", ru: "Пароль", en: "Password" },
    "auth.show_password": { uz: "Parolni ko'rsatish", ru: "Показать пароль", en: "Show password" },
    "auth.remember": { uz: "Meni eslab qolish", ru: "Запомнить меня", en: "Remember me" },
    "auth.signin": { uz: "Kirish", ru: "Войти", en: "Sign in" },
    "auth.forgot": { uz: "Parolni unutdingizmi?", ru: "Забыли пароль?", en: "Forgot password?" },
    "auth.no_registration": { uz: "Ochiq ro'yxatdan o'tish mavjud emas. Hisob ma'lumotlarini admin beradi.", ru: "Открытой регистрации нет. Учётные данные выдаёт администратор.", en: "No public registration. Credentials are issued by the administrator." },
    "auth.welcome_back": { uz: "Xush kelibsiz!", ru: "Добро пожаловать!", en: "Welcome back!" },
    "auth.change_password_title": { uz: "Parolni yangilash", ru: "Смена пароля", en: "Change password" },
    "auth.must_change": { uz: "Xavfsizlik uchun parolingizni o'zgartiring. Vaqtinchalik parol sizga berilgan.", ru: "В целях безопасности смените пароль. Вам был выдан временный пароль.", en: "For security, change your password. You were given a temporary one." },
    "auth.old_password": { uz: "Eski parol", ru: "Старый пароль", en: "Old password" },
    "auth.new_password": { uz: "Yangi parol", ru: "Новый пароль", en: "New password" },
    "auth.confirm_password": { uz: "Parolni tasdiqlash", ru: "Подтвердите пароль", en: "Confirm password" },
    "auth.save": { uz: "Saqlash", ru: "Сохранить", en: "Save" },
    "auth.logout": { uz: "Chiqish", ru: "Выйти", en: "Logout" },
    "auth.reset_requested": { uz: "Agar hisob mavjud bo'lsa, tiklash tokeni bildirishnoma sifatida yuborildi", ru: "Если аккаунт существует, токен восстановления отправлен как уведомление", en: "If the account exists, a reset token was sent as a notification" },
    "auth.reset_token": { uz: "Tiklash kodi (token)", ru: "Код восстановления (токен)", en: "Reset token" },
    "auth.reset_password": { uz: "Parolni tiklash", ru: "Восстановление пароля", en: "Reset password" },

    // ---- login sahifasi (tungi shahar dizayni)
    "auth.card_title": { uz: "Platformaga kirish", ru: "Вход в платформу", en: "Sign in to the platform" },
    "auth.card_sub": { uz: "Avtomaktab amaliy mashg'ulotlarini boshqarish platformasiga xush kelibsiz", ru: "Добро пожаловать в платформу управления практическими занятиями", en: "Welcome to the practical training management platform" },
    "auth.slogan": { uz: "Xavfsiz yo'l — ishonchli ta'lim", ru: "Безопасная дорога — надёжное обучение", en: "Safe road — trusted training" },
    "auth.signing_in": { uz: "Kirilmoqda...", ru: "Вход...", en: "Signing in..." },
    "auth.err.empty_login": { uz: "Loginni kiriting.", ru: "Введите логин.", en: "Enter your login." },
    "auth.err.empty_password": { uz: "Parolni kiriting.", ru: "Введите пароль.", en: "Enter your password." },
    "auth.err.empty_role": { uz: "Rolni tanlang.", ru: "Выберите роль.", en: "Please select your role." },
    "auth.err.role_retry": { uz: "Tanlagan rolingizni tekshirib, qayta urinib ko'ring.", ru: "Проверьте выбранную роль и попробуйте снова.", en: "Check the role you selected and try again." },
    "auth.err.blocked": { uz: "Hisobingiz vaqtincha bloklangan. Administrator bilan bog'laning.", ru: "Ваша учётная запись временно заблокирована. Обратитесь к администратору.", en: "Your account is temporarily blocked. Contact the administrator." },
    "auth.err.network": { uz: "Server bilan bog'lanib bo'lmadi. Iltimos, qayta urinib ko'ring.", ru: "Не удалось связаться с сервером. Пожалуйста, попробуйте ещё раз.", en: "Could not reach the server. Please try again." },
    "auth.reset_hint": { uz: "Tasdiqlash kodi SMS orqali yuboriladi. Hozircha kodni administrator beradi.", ru: "Код подтверждения будет отправлен по SMS. Пока код выдаёт администратор.", en: "A verification code will be sent by SMS. For now, the admin provides the code." },
    "auth.reset_done": { uz: "Parol muvaffaqiyatli tiklandi. Endi yangi parol bilan kiring.", ru: "Пароль успешно восстановлен. Войдите с новым паролем.", en: "Password reset successfully. Sign in with the new password." },
    "auth.reset_mismatch": { uz: "Parollar mos kelmadi", ru: "Пароли не совпадают", en: "Passwords do not match" },
    "stat.students_value": { uz: "500+", ru: "500+", en: "500+" },
    "stat.students_label": { uz: "Talaba ta'lim olmoqda", ru: "Учеников обучается", en: "Students enrolled" },
    "stat.success_value": { uz: "98%", ru: "98%", en: "98%" },
    "stat.success_label": { uz: "Muvaffaqiyat darajasi", ru: "Уровень успеха", en: "Success rate" },

    // ---- app / nav
    "nav.home": { uz: "Bosh sahifa", ru: "Главная", en: "Home" },
    "nav.dashboard": { uz: "Bosh sahifa", ru: "Главная", en: "Dashboard" },
    "nav.base": { uz: "Yangi baza", ru: "Новая база", en: "User base" },
    "nav.today": { uz: "Bugun", ru: "Сегодня", en: "Today" },
    "nav.schedule": { uz: "Jadval", ru: "Расписание", en: "Schedule" },
    "nav.requests": { uz: "So'rovlar", ru: "Заявки", en: "Requests" },
    "nav.students": { uz: "Talabalar", ru: "Ученики", en: "Students" },
    "nav.instructors": { uz: "Instruktorlar", ru: "Инструкторы", en: "Instructors" },
    /* MODUL 6: foydalanuvchilar bo'limi — uchta alohida tab */
    "nav.users": { uz: "Foydalanuvchilar", ru: "Пользователи", en: "Users" },
    "nav.admins": { uz: "Adminlar", ru: "Администраторы", en: "Administrators" },
    "users.instructor": { uz: "Instruktor", ru: "Инструктор", en: "Instructor" },
    "users.progress": { uz: "Progress", ru: "Прогресс", en: "Progress" },
    "users.students_count": { uz: "Talabalar soni", ru: "Кол-во учеников", en: "Students" },
    "users.car": { uz: "Avtomobil", ru: "Автомобиль", en: "Vehicle" },
    "users.work_hours": { uz: "Ish vaqti", ru: "Рабочие часы", en: "Working hours" },
    "users.perms": { uz: "Huquqlar", ru: "Права", en: "Permissions" },
    "users.last_login": { uz: "Oxirgi kirish", ru: "Последний вход", en: "Last sign-in" },
    "users.admins_hint": { uz: "Admin hisobini faqat boshqa admin yaratadi.", ru: "Учётную запись администратора создаёт только другой администратор.", en: "Only another administrator can create an admin account." },
    "users.search_student": { uz: "Talaba qidirish (ism, login, telefon)...", ru: "Поиск ученика (имя, логин, телефон)...", en: "Search student (name, login, phone)..." },
    "users.search_instructor": { uz: "Instruktor qidirish (ism, login, telefon)...", ru: "Поиск инструктора (имя, логин, телефон)...", en: "Search instructor (name, login, phone)..." },
    "users.search_admin": { uz: "Admin qidirish (ism, login)...", ru: "Поиск администратора (имя, логин)...", en: "Search administrator (name, login)..." },
    "users.empty_student": { uz: "Talabalar topilmadi", ru: "Ученики не найдены", en: "No students found" },
    "users.empty_instructor": { uz: "Instruktorlar topilmadi", ru: "Инструкторы не найдены", en: "No instructors found" },
    "users.empty_admin": { uz: "Adminlar topilmadi", ru: "Администраторы не найдены", en: "No administrators found" },
    "users.delete_confirm": { uz: "{name} hisobini o'chirishni tasdiqlaysizmi?", ru: "Подтвердите удаление учётной записи {name}?", en: "Delete the account of {name}?" },
    "nav.cars": { uz: "Avtomobillar", ru: "Автомобили", en: "Cars" },
    "nav.lessons": { uz: "Mashg'ulotlar", ru: "Занятия", en: "Lessons" },
    "nav.reports": { uz: "Hisobotlar", ru: "Отчёты", en: "Reports" },
    "nav.analytics": { uz: "Analitika", ru: "Аналитика", en: "Analytics" },
    "nav.notifications": { uz: "Bildirishnomalar", ru: "Уведомления", en: "Notifications" },
    "nav.languages": { uz: "Tillar", ru: "Языки", en: "Languages" },
    "nav.settings": { uz: "Sozlamalar", ru: "Настройки", en: "Settings" },
    "nav.profile": { uz: "Profilim", ru: "Мой профиль", en: "My profile" },
    "nav.my_schedule": { uz: "Mening jadvalim", ru: "Моё расписание", en: "My schedule" },
    "nav.my_lessons": { uz: "Amaliy mashg'ulotlarim", ru: "Мои практические занятия", en: "My practical lessons" },
    "nav.history": { uz: "Mashg'ulotlar tarixi", ru: "История занятий", en: "Lesson history" },
    "nav.today_lessons": { uz: "Bugungi mashg'ulotlar", ru: "Сегодняшние занятия", en: "Today's lessons" },
    "nav.my_students": { uz: "Talabalarim", ru: "Мои ученики", en: "My students" },
    "nav.my_car": { uz: "Mening avtomobilim", ru: "Мой автомобиль", en: "My car" },
    "nav.messages": { uz: "Xabarlar", ru: "Сообщения", en: "Messages" },
    "nav.audit": { uz: "Audit jurnali", ru: "Журнал аудита", en: "Audit log" },
    /* MODUL 2/3: talaba va admin boshqaruvi (bloklash/arxiv/yangi admin). */
    "users.add_admin": { uz: "Yangi admin", ru: "Новый админ", en: "New admin" },
    "users.admin_role_hint": { uz: "Admin roli avtomatik beriladi. Login va parol tizim tomonidan tasodifiy yaratiladi va faqat bir marta ko'rsatiladi.", ru: "Роль админа назначается автоматически. Логин и пароль создаются системой случайно и показываются только один раз.", en: "Admin role is assigned automatically. Login and password are randomly generated by the system and shown only once." },
    "users.view_profile": { uz: "Profilni ko'rish", ru: "Открыть профиль", en: "View profile" },
    "users.block": { uz: "Bloklash", ru: "Заблокировать", en: "Block" },
    "users.unblock": { uz: "Blokdan chiqarish", ru: "Разблокировать", en: "Unblock" },
    "users.archive": { uz: "Arxivlash", ru: "Архивировать", en: "Archive" },
    "users.unarchive": { uz: "Arxivdan chiqarish", ru: "Из архива", en: "Unarchive" },
    "users.block_confirm": { uz: "Ushbu foydalanuvchi tizimga kira olmaydi. Bloklashni tasdiqlaysizmi?", ru: "Этот пользователь не сможет входить в систему. Подтверждаете блокировку?", en: "This user will not be able to log in. Confirm block?" },
    "users.unblock_confirm": { uz: "Foydalanuvchini faollashtirishni tasdiqlaysizmi?", ru: "Подтверждаете разблокировку пользователя?", en: "Confirm activating the user?" },
    "users.archive_confirm": { uz: "Ushbu foydalanuvchi faol ro'yxatdan chiqariladi, ammo ma'lumotlari saqlanadi. Arxivlashni tasdiqlaysizmi?", ru: "Этот пользователь будет убран из активного списка, но его данные сохранятся. Подтверждаете архивирование?", en: "This user will be removed from the active list, but data is preserved. Confirm archive?" },
    "users.unarchive_confirm": { uz: "Foydalanuvchini arxivdan faol ro'yxatga qaytarishni tasdiqlaysizmi?", ru: "Подтверждаете возврат пользователя из архива в активный список?", en: "Confirm returning the user from archive to the active list?" },
    "profile.login_changing": { uz: "Login o'zgartirilmoqda", ru: "Логин изменяется", en: "Login is being changed" },
    "profile.login_format_ok": { uz: "Login formati to'g'ri", ru: "Формат логина верный", en: "Login format is valid" },
    "profile.pw_changing": { uz: "Parol o'zgartirilmoqda", ru: "Пароль изменяется", en: "Password is being changed" },
    "audit.act.admin_created": { uz: "Yangi admin yaratildi", ru: "Создан новый админ", en: "New admin created" },
    "audit.act.user_blocked": { uz: "Foydalanuvchi bloklandi", ru: "Пользователь заблокирован", en: "User blocked" },
    "audit.act.user_archived": { uz: "Foydalanuvchi arxivlandi", ru: "Пользователь архивирован", en: "User archived" },
    "nav.calendar": { uz: "Kalendar", ru: "Календарь", en: "Calendar" },
    // MODUL 7: avval "Backup" (inglizcha) — UZ da ham tarjima qilindi.
    "nav.backup": { uz: "Zaxira nusxa", ru: "Резервная копия", en: "Backup" },
    "nav.import_export": { uz: "Import / Eksport", ru: "Импорт / Экспорт", en: "Import / Export" },

    // ---- dashboard stats
    "stat.students": { uz: "Jami talabalar", ru: "Всего учеников", en: "Total students" },
    "stat.instructors": { uz: "Instruktorlar", ru: "Инструкторы", en: "Instructors" },
    "stat.cars": { uz: "Avtomobillar", ru: "Автомобили", en: "Cars" },
    "stat.today_sessions": { uz: "Bugungi mashg'ulotlar", ru: "Занятия сегодня", en: "Today's lessons" },
    "stat.pending_requests": { uz: "Kutilayotgan so'rovlar", ru: "Ожидающие заявки", en: "Pending requests" },
    "stat.active_instructors": { uz: "Faol instruktorlar", ru: "Активные инструкторы", en: "Active instructors" },
    "stat.cars_repair": { uz: "Ta'mirdagi avtomobillar", ru: "Автомобили в ремонте", en: "Cars in repair" },
    "stat.total_users": { uz: "Jami foydalanuvchilar", ru: "Всего пользователей", en: "Total users" },
    "analytics.month": { uz: "Oy", ru: "Месяц", en: "Month" },
    "analytics.total": { uz: "Jami mashg'ulotlar", ru: "Всего занятий", en: "Total lessons" },
    "analytics.completed": { uz: "O'tkazilgan", ru: "Проведено", en: "Completed" },
    "analytics.cancelled": { uz: "Bekor qilingan", ru: "Отменено", en: "Cancelled" },
    "analytics.cancel_rate": { uz: "Bekor ulushi", ru: "Доля отмен", en: "Cancel rate" },
    "analytics.hours": { uz: "Soatlar", ru: "Часы", en: "Hours" },
    "analytics.students": { uz: "Talabalar", ru: "Ученики", en: "Students" },
    "analytics.daily_chart": { uz: "Kunlik faollik", ru: "Дневная активность", en: "Daily activity" },
    "analytics.cancel_mark": { uz: "qizil ustunlar — bekor qilingan kunlar", ru: "красные столбцы — дни с отменами", en: "red bars mark days with cancels" },
    "analytics.monthly_chart": { uz: "Oylik tendentsiya (12 oy)", ru: "Месячная тенденция (12 мес.)", en: "Monthly trend (12 mo)" },
    "analytics.top_instructors": { uz: "Eng band instruktorlar", ru: "Самые занятые инструкторы", en: "Busiest instructors" },
    "analytics.no_data": { uz: "Bu oyda hali ma'lumot yo'q", ru: "В этом месяце пока нет данных", en: "No data this month yet" },
    "stat.blocked": { uz: "Bloklanganlar", ru: "Заблокированные", en: "Blocked" },
    "stat.archived": { uz: "Arxivlanganlar", ru: "Архивированные", en: "Archived" },

    // ---- M6: Bosh sahifa va Bugun
    "home.weekly_stats": { uz: "Haftalik statistika", ru: "Статистика недели", en: "Weekly stats" },
    "home.overall_progress": { uz: "Umumiy progress", ru: "Общий прогресс", en: "Overall progress" },
    "home.recent_notifications": { uz: "So'nggi bildirishnomalar", ru: "Последние уведомления", en: "Recent notifications" },
    "home.quick_links": { uz: "Tezkor havolalar", ru: "Быстрые ссылки", en: "Quick links" },
    "home.mark_read": { uz: "Barchasini o'qilgan deb belgilash", ru: "Отметить все прочитанными", en: "Mark all read" },
    "week.sessions": { uz: "Haftadagi darslar", ru: "Занятий за неделю", en: "Lessons this week" },
    "week.done": { uz: "Bajarilgan", ru: "Выполнено", en: "Completed" },
    "week.hours": { uz: "Amaliy soatlar", ru: "Практических часов", en: "Hours" },
    /* MODUL 5: "Haftadagi darslar" -> "Jami darslar" (kurst maqsadi bo'yicha).
       "Amaliy soatlar" kartasi talaba bosh sahifasidan olib tashlandi. */
    "week.total_lessons": { uz: "Jami darslar", ru: "Всего занятий", en: "Total lessons" },
    "week.done_lessons": { uz: "Bajarilgan darslar", ru: "Выполнено занятий", en: "Completed lessons" },
    "week.remaining_lessons": { uz: "Qolgan: {n}", ru: "Осталось: {n}", en: "Remaining: {n}" },
    "users.mode_group": { uz: "Umumiy sozlama", ru: "Общая настройка", en: "Platform setting" },
    "users.mode_individual": { uz: "Individual reja", ru: "Индивидуальный план", en: "Individual plan" },
    "users.total_lessons": { uz: "Jami darslar (individual)", ru: "Всего занятий (индивидуально)", en: "Total lessons (individual)" },
    "users.total_lessons_hint": { uz: "Bo'sh qoldirilsa — platformaning umumiy sozlamasi qo'llaniladi.", ru: "Если оставить пустым — применяется общая настройка платформы.", en: "Leave empty to use the platform-wide setting." },
    "users.total_lessons_group_placeholder": { uz: "Umumiy sozlamadan", ru: "Из общей настройки", en: "From platform setting" },
    "week.students": { uz: "Talabalar", ru: "Ученики", en: "Students" },
    "week.requests": { uz: "Yangi so'rovlar", ru: "Новых заявок", en: "New requests" },
    "week.new_users": { uz: "Yangi foydalanuvchilar", ru: "Новых пользователей", en: "New users" },
    "week.today": { uz: "Bugun", ru: "Сегодня", en: "Today" },
    "week.chart_title": { uz: "Haftalik faollik", ru: "Активность за неделю", en: "Weekly activity" },
    "week.day_mon": { uz: "Du", ru: "Пн", en: "Mo" },
    "week.day_tue": { uz: "Se", ru: "Вт", en: "Tu" },
    "week.day_wed": { uz: "Cho", ru: "Ср", en: "We" },
    "week.day_thu": { uz: "Pa", ru: "Чт", en: "Th" },
    "week.day_fri": { uz: "Ju", ru: "Пт", en: "Fr" },
    "week.day_sat": { uz: "Sha", ru: "Сб", en: "Sa" },
    "week.day_sun": { uz: "Ya", ru: "Вс", en: "Su" },
    "dash.today_sessions_title": { uz: "Bugungi mashg'ulotlar", ru: "Занятия сегодня", en: "Today's lessons" },
    "today.now": { uz: "Hozir", ru: "Сейчас", en: "Now" },
    "today.timeline_title": { uz: "Bugungi soatlik jadval", ru: "Сегодняшнее расписание", en: "Today's timetable" },
    "today.checklist_title": { uz: "Bugun bajarish kerak", ru: "Нужно сделать сегодня", en: "To-do today" },
    "today.no_sessions": { uz: "Bugun mashg'ulotlar rejalashtirilmagan.", ru: "На сегодня занятий нет.", en: "No lessons scheduled today." },
    "today.nothing": { uz: "Bugungi reja bo'sh", ru: "План на сегодня пуст", en: "Nothing planned today" },
    "today.nothing_sub": { uz: "Kristal toza kun 😊", ru: "Свободный день 😊", en: "A free day 😊" },
    "chk.start": { uz: "Mashg'ulotni boshlash", ru: "Начать занятие", en: "Start the lesson" },
    "chk.finish": { uz: "Mashg'ulotni yakunlash", ru: "Завершить занятие", en: "Finish the lesson" },
    "chk.attendance": { uz: "Davomatni belgilash", ru: "Отметить посещаемость", en: "Mark attendance" },
    "chk.car_repair": { uz: "Avtomobil ta'mirda — bugun dars o'tkazib bo'lmaydi", ru: "Автомобиль в ремонте — сегодня занятия невозможны", en: "Car in repair — no lessons today" },
    "chk.car_inactive": { uz: "Avtomobil faol emas — admin bilan bog'laning", ru: "Автомобиль неактивен — свяжитесь с админом", en: "Car is inactive — contact admin" },
    "chk.car_checkup": { uz: "Avtomobil tekshiruvda", ru: "Автомобиль на техосмотре", en: "Car is under checkup" },
    "chk.pending_requests": { uz: "Kutilayotgan so'rovlar", ru: "Ожидающие заявки", en: "Pending requests" },
    "chk.review_requests": { uz: "Yangilarni ko'rib chiqish", ru: "Рассмотреть новые заявки", en: "Review new requests" },
    "chk.upcoming": { uz: "Boshlanmagan", ru: "Не начато", en: "Upcoming" },
    "chk.ongoing": { uz: "Davom etmoqda", ru: "Идёт", en: "Ongoing" },
    "progress.total": { uz: "Jami darslar", ru: "Всего занятий", en: "Total lessons" },
    "progress.done": { uz: "Bajarilgan", ru: "Выполнено", en: "Completed" },
    "progress.hours": { uz: "Soatlar", ru: "Часы", en: "Hours" },
    "progress.remaining": { uz: "Qolgan", ru: "Осталось", en: "Remaining" },
    "progress.my_stats": { uz: "Mening statistikam", ru: "Моя статистика", en: "My statistics" },

    // ---- common
    "common.add": { uz: "Qo'shish", ru: "Добавить", en: "Add" },
    "common.create": { uz: "Yaratish", ru: "Создать", en: "Create" },
    "common.save": { uz: "Saqlash", ru: "Сохранить", en: "Save" },
    "common.cancel": { uz: "Bekor qilish", ru: "Отмена", en: "Cancel" },
    "common.edit": { uz: "Tahrirlash", ru: "Редактировать", en: "Edit" },
    "common.delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
    "common.search": { uz: "Qidiruv...", ru: "Поиск...", en: "Search..." },
    "common.filter": { uz: "Saralash", ru: "Фильтр", en: "Filter" },
    "common.status": { uz: "Holat", ru: "Статус", en: "Status" },
    "common.phone": { uz: "Telefon", ru: "Телефон", en: "Phone" },
    "common.date": { uz: "Sana", ru: "Дата", en: "Date" },
    "common.time": { uz: "Vaqt", ru: "Время", en: "Time" },
    "common.actions": { uz: "Amallar", ru: "Действия", en: "Actions" },
    "common.all": { uz: "Barchasi", ru: "Все", en: "All" },
    "common.name": { uz: "Ism", ru: "Имя", en: "First name" },
    "common.last_name": { uz: "Familiya", ru: "Фамилия", en: "Last name" },
    "common.first_name": { uz: "Ism", ru: "Имя", en: "First name" },
    "common.middle_name": { uz: "Otasining ismi", ru: "Отчество", en: "Middle name" },
    "common.login": { uz: "Login", ru: "Логин", en: "Login" },
    "common.loading": { uz: "Yuklanmoqda...", ru: "Загрузка...", en: "Loading..." },
    "common.no_data": { uz: "Ma'lumot yo'q", ru: "Нет данных", en: "No data" },
    "common.confirm": { uz: "Tasdiqlash", ru: "Подтвердить", en: "Confirm" },
    "common.close": { uz: "Yopish", ru: "Закрыть", en: "Close" },
    "common.retry": { uz: "Qayta urinish", ru: "Повторить", en: "Retry" },
    "common.back": { uz: "Orqaga", ru: "Назад", en: "Back" },
    "common.download": { uz: "Yuklab olish", ru: "Скачать", en: "Download" },
    "common.yes": { uz: "Ha", ru: "Да", en: "Yes" },
    "common.no": { uz: "Yo'q", ru: "Нет", en: "No" },
    "common.notes": { uz: "Izoh", ru: "Примечание", en: "Notes" },
    "common.copy": { uz: "Nusxalash", ru: "Копировать", en: "Copy" },
    "common.other": { uz: "Boshqa", ru: "Другое", en: "Other" },

    // ---- errors
    "err.generic": { uz: "Xatolik yuz berdi", ru: "Произошла ошибка", en: "An error occurred" },
    "err.auth.missing_fields": { uz: "Login va parolni kiriting", ru: "Введите логин и пароль", en: "Enter login and password" },
    "err.auth.wrong_credentials": { uz: "Login yoki parol noto'g'ri", ru: "Неверный логин или пароль", en: "Wrong login or password" },
    "err.auth.try_later": { uz: "Judа ko'p urinish. Bir ozdan so'ng qayta urinib ko'ring.", ru: "Слишком много попыток. Попробуйте позже.", en: "Too many attempts. Try again later." },
    "err.auth.too_many_attempts": { uz: "Judа ko'p urinish. Bir ozdan so'ng qayta urinib ko'ring.", ru: "Слишком много попыток. Попробуйте позже.", en: "Too many attempts. Try again later." },
    "err.auth.user_blocked": { uz: "Foydalanuvchi bloklangan", ru: "Пользователь заблокирован", en: "User is blocked" },
    "err.auth.wrong_role": { uz: "Login yoki parol noto'g'ri", ru: "Неверный логин или пароль", en: "Wrong login or password" },
    "err.auth.required": { uz: "Tizimga kirish kerak", ru: "Необходимо войти", en: "Login required" },
    "err.auth.password_short": { uz: "Parol kamida 10 belgidan iborat bo'lishi kerak", ru: "Пароль должен содержать не менее 10 символов", en: "Password must be at least 10 characters" },
    "err.auth.wrong_old": { uz: "Eski parol noto'g'ri", ru: "Старый пароль неверен", en: "Old password is wrong" },
    "err.auth.wrong_old_password": { uz: "Eski parol noto'g'ri", ru: "Старый пароль неверен", en: "Old password is wrong" },
    "err.auth.otp_required": { uz: "Bu hisobda 2FA yoqilgan. SMS'dan 6 raqamli kodni kiriting.", ru: "На этом аккаунте включена 2FA. Введите 6-значный код из SMS.", en: "2FA is enabled on this account. Enter the 6-digit SMS code." },
    "err.auth.otp_invalid": { uz: "2FA kod noto'g'ri yoki eskirgan", ru: "Код 2FA неверен или устарел", en: "2FA code is invalid or expired" },
    "err.img.format": { uz: "Faqat JPG, PNG yoki WebP rasm yuklash mumkin", ru: "Можно загружать только JPG, PNG или WebP", en: "Only JPG, PNG or WebP images are allowed" },
    "err.img.size": { uz: "Rasm hajmi 5MB dan oshib ketdi", ru: "Фото превышает 5 МБ", en: "Photo exceeds 5 MB" },
    "err.auth.invalid_token": { uz: "Tiklash kodi noto'g'ri yoki eskirgan", ru: "Код восстановления неверен или истёк", en: "Reset code is invalid or has expired" },
    "err.forbidden": { uz: "Ruxsat yo'q", ru: "Доступ запрещён", en: "Access denied" },
    "err.invalid_date": { uz: "Sana noto'g'ri", ru: "Неверная дата", en: "Invalid date" },
    "err.invalid_time": { uz: "Vaqt noto'g'ri (boshlanishi tugashidan oldin bo'lsin)", ru: "Неверное время (начало должно быть раньше конца)", en: "Invalid time (start must be before end)" },
    "err.not_found": { uz: "Topilmadi", ru: "Не найдено", en: "Not found" },
    "err.bad_request": { uz: "So'rov ma'lumotlari noto'g'ri", ru: "Некорректные данные запроса", en: "Invalid request data" },
    "err.user.name_required": { uz: "Ism va familiya majburiy", ru: "Имя и фамилия обязательны", en: "First and last name are required" },
    "err.user.invalid_role": { uz: "Noto'g'ri rol", ru: "Неверная роль", en: "Invalid role" },
    "err.user.bulk_role": { uz: "Tezkor yaratish faqat talabalar uchun", ru: "Быстрое создание только для учеников", en: "Quick create is for students only" },
    "err.user.bulk_count": { uz: "Soni 1–1000 orasida bo'lsin", ru: "Количество от 1 до 1000", en: "Count must be 1–1000" },
    "err.user.not_found": { uz: "Foydalanuvchi topilmadi", ru: "Пользователь не найден", en: "User not found" },
    /* MODUL 4 — kenglik/uzunlik validatsiyasi xatolari */
    "err.coord.bad_lat": { uz: "Kenglik noto'g'ri: -90 dan 90 gacha son kiriting", ru: "Неверная широта: введите число от -90 до 90", en: "Invalid latitude: enter a number from -90 to 90" },
    "err.coord.bad_lng": { uz: "Uzunlik noto'g'ri: -180 dan 180 gacha son kiriting", ru: "Неверная долгота: введите число от -180 до 180", en: "Invalid longitude: enter a number from -180 to 180" },
    "err.coord.pair_incomplete": { uz: "Kenglik va uzunlikni ikkalasini ham kiriting yoki ikkalasini ham tozalang", ru: "Укажите широту и долготу вместе или очистите оба поля", en: "Provide both latitude and longitude, or clear both" },
    "err.user.cannot_modify_admin": { uz: "Admin hisobini o'zgartirish mumkin emas", ru: "Нельзя изменять учётную запись админа", en: "Cannot modify admin account" },
    /* MODUL 3 — adminga nisbatan bloklash/arxivlash himoyasi */
    "err.user.cannot_block_self": { uz: "O'z hisobingizni bloklay yoki arxivlay olmaysiz", ru: "Нельзя заблокировать или архивировать свою учётную запись", en: "You cannot block or archive your own account" },
    "err.user.last_admin_protected": { uz: "Oxirgi faol adminni bloklash yoki arxivlash mumkin emas", ru: "Нельзя заблокировать или архивировать последнего активного администратора", en: "Cannot block or archive the last active admin" },
    "err.user.bad_status": { uz: "Noto'g'ri holat", ru: "Неверный статус", en: "Invalid status" },
    "err.car.bad_plate": { uz: "Davlat raqami formati noto'g'ri", ru: "Неверный формат гос. номера", en: "Invalid plate number format" },
    "err.car.plate_exists": { uz: "Bu davlat raqamli avtomobil allaqachon mavjud", ru: "Автомобиль с этим номером уже существует", en: "A car with this plate already exists" },
    "err.car.bad_capacity": { uz: "Sig'im 1–20 orasida bo'lsin", ru: "Вместимость от 1 до 20", en: "Capacity must be 1–20" },
    "err.car.bad_status": { uz: "Noto'g'ri holat", ru: "Неверный статус", en: "Invalid status" },
    "err.car.not_found": { uz: "Avtomobil topilmadi", ru: "Автомобиль не найден", en: "Car not found" },
    "err.car.assigned": { uz: "Avtomobil instruktorga biriktirilgan. Avval biriktiruvni olib tashlang.", ru: "Автомобиль привязан к инструктору. Сначала отвяжите.", en: "Car is assigned to an instructor. Unassign it first." },
    "err.session.not_found": { uz: "Mashg'ulot topilmadi", ru: "Занятие не найдено", en: "Lesson not found" },
    "err.session.rules_violated": { uz: "Mashg'ulot yaratib bo'lmaydi", ru: "Не удалось создать занятие", en: "Cannot create the lesson" },
    "err.session.duplicate_student": { uz: "Talaba allaqachon bu sessionda", ru: "Ученик уже в этой сессии", en: "Student already in this session" },
    "err.session.student_not_found": { uz: "Talaba sessionda topilmadi", ru: "Ученик не найден в сессии", en: "Student not found in session" },
    "err.session.wrong_status": { uz: "Mashg'ulot holati bu amalga mos emas", ru: "Статус занятия не подходит для этого действия", en: "Lesson status doesn't allow this action" },
    "err.session.not_today": { uz: "Mashg'ulot bugun emas. Faqat bugungi mashg'ulotni boshlash mumkin.", ru: "Занятие не сегодня. Начать можно только сегодняшнее.", en: "Lesson is not today. Only today's can be started." },
    "err.request.not_found": { uz: "So'rov topilmadi", ru: "Заявка не найдена", en: "Request not found" },
    "err.request.not_pending": { uz: "So'rov kutilayotgan holatda emas", ru: "Заявка не в ожидании", en: "Request is not pending" },
    "err.request.no_instructor": { uz: "Instruktor tanlanmagan", ru: "Инструктор не выбран", en: "Instructor not selected" },
    "err.attendance.bad_status": { uz: "Noto'g'ri davomat holati", ru: "Неверный статус посещаемости", en: "Invalid attendance status" },
    "err.notif.empty": { uz: "Xabar matni bo'sh", ru: "Текст сообщения пуст", en: "Message text is empty" },
    "err.msg.empty": { uz: "Xabar matni bo'sh", ru: "Текст сообщения пуст", en: "Message text is empty" },
    "err.backup.disabled": { uz: "Zaxira nusxa o'chirilgan", ru: "Резервное копирование отключено", en: "Backup is disabled" },
    "err.backup.bad": { uz: "Fayl nomi noto'g'ri", ru: "Неверное имя файла", en: "Invalid file name" },
    "err.backup.not_found": { uz: "Bunday zaxira nusxa topilmadi", ru: "Такой резервной копии не найдено", en: "No such backup" },
    "err.backup.delete_failed": { uz: "Faylni o'chirib bo'lmadi", ru: "Не удалось удалить файл", en: "Failed to delete file" },
    "err.capacity_full": { uz: "Avtomobilning amaliy mashg'ulot sig'imi to'lgan", ru: "Вместимость автомобиля заполнена", en: "Car practice capacity is full" },
    "err.student_busy": { uz: "Talaba shu vaqtda boshqa mashg'ulotga yozilgan", ru: "Ученик записан на другое занятие в это время", en: "Student is booked in another lesson at this time" },
    "err.instructor_busy": { uz: "Instruktor shu vaqtda boshqa mashg'ulot bilan band", ru: "Инструктор занят в это время", en: "Instructor is busy at this time" },
    "err.car_busy": { uz: "Avtomobil shu vaqtda boshqa mashg'ulotda", ru: "Автомобиль занят в это время", en: "Car is busy at this time" },
    "err.car_not_assigned": { uz: "Ushbu instruktor uchun avtomobil biriktirilmagan", ru: "Для этого инструктора не привязан автомобиль", en: "No car assigned to this instructor" },
    "err.car_not_found": { uz: "Instruktorning avtomobili bazada topilmadi", ru: "Автомобиль инструктора не найден в базе", en: "Instructor's car was not found in the database" },
    "err.duplicate_student_in_session": { uz: "Bitta talaba mashg'ulotda bir necha marta kiritilgan", ru: "Один ученик указан в занятии несколько раз", en: "The same student is listed several times in the lesson" },
    "err.student_not_found": { uz: "Talaba topilmadi", ru: "Ученик не найден", en: "Student not found" },
    "err.time_order": { uz: "Boshlanish vaqti tugash vaqtidan keyin bo'lmasligi kerak", ru: "Время начала должно быть раньше времени окончания", en: "Start time must be before end time" },
    "err.car_in_repair": { uz: "Instruktorning avtomobili hozir ta'mirda. Yangi mashg'ulot yaratib bo'lmaydi.", ru: "Автомобиль инструктора в ремонте. Создание занятия невозможно.", en: "The instructor's car is in repair. Cannot create a lesson." },
    "err.car_in_checkup": { uz: "Avtomobil tekshiruvda", ru: "Автомобиль на проверке", en: "Car is under inspection" },
    "err.car_inactive": { uz: "Avtomobil faol emas", ru: "Автомобиль неактивен", en: "Car is inactive" },
    "err.instructor_not_found": { uz: "Instruktor topilmadi", ru: "Инструктор не найден", en: "Instructor not found" },
    "err.instructor_blocked": { uz: "Instruktor bloklangan", ru: "Инструктор заблокирован", en: "Instructor is blocked" },
    "err.instructor_inactive": { uz: "Instruktor faol emas", ru: "Инструктор неактивен", en: "Instructor is inactive" },
    "err.not_work_day": { uz: "Bu kun instruktorning ish jadvaliga kirmaydi", ru: "Этот день не входит в график инструктора", en: "This day is not in the instructor's schedule" },
    "err.outside_work_hours": { uz: "Bu vaqt instruktorning ish jadvaliga kirmaydi", ru: "Это время не входит в рабочие часы", en: "This time is outside working hours" },
    "err.intersects_break": { uz: "Bu vaqt instruktorning tanaffus vaqtiga to'g'ri keladi", ru: "Это время совпадает с перерывом", en: "This time intersects the instructor's break" },
    "err.session_too_long": { uz: "Mashg'ulot juda uzoq", ru: "Занятие слишком длинное", en: "Lesson is too long" },
    "err.invalid_input": { uz: "Ma'lumot formati noto'g'ri", ru: "Неверный формат данных", en: "Invalid input" },
    "err.server_error": { uz: "Server xatosi", ru: "Ошибка сервера", en: "Server error" },

    // ---- car status
    "car.status.active": { uz: "🟢 Faol", ru: "🟢 Активен", en: "🟢 Active" },
    "car.status.repair": { uz: "🔧 Ta'mirda", ru: "🔧 В ремонте", en: "🔧 In repair" },
    "car.status.checkup": { uz: "🟡 Tekshiruvda", ru: "🟡 На проверке", en: "🟡 Under inspection" },
    "car.status.inactive": { uz: "🔴 Faol emas", ru: "🔴 Неактивен", en: "🔴 Inactive" },
    "car.brand": { uz: "Marka", ru: "Марка", en: "Brand" },
    "car.model": { uz: "Model", ru: "Модель", en: "Model" },
    "car.plate": { uz: "Davlat raqami", ru: "Гос. номер", en: "Plate number" },
    "car.year": { uz: "Ishlab chiqarilgan yil", ru: "Год выпуска", en: "Year" },
    "car.color": { uz: "Rang", ru: "Цвет", en: "Color" },
    "car.seats": { uz: "O'rindiqlar", ru: "Места", en: "Seats" },
    "car.capacity": { uz: "Amaliy mashg'ulot sig'imi", ru: "Вместимость занятий", en: "Practice capacity" },
    "car.inspection": { uz: "Texnik ko'rik sanasi", ru: "Дата техосмотра", en: "Inspection date" },
    "car.insurance": { uz: "Sug'urta muddati", ru: "Срок страховки", en: "Insurance expiry" },
    "car.assigned_to": { uz: "Biriktirilgan instruktor", ru: "Привязан к инструктору", en: "Assigned instructor" },
    "car.not_assigned": { uz: "Biriktirilmagan", ru: "Не привязан", en: "Not assigned" },
    "car.add": { uz: "Yangi avtomobil", ru: "Новый автомобиль", en: "New car" },
    "car.automatic": { uz: "Avtomatik (instruktordan)", ru: "Автоматически (от инструктора)", en: "Automatic (from instructor)" },
    "car.reassign": { uz: "Avtomobilni almashtirish", ru: "Сменить автомобиль", en: "Replace car" },
    "car.status": { uz: "Holati", ru: "Статус", en: "Status" },
    "car.status_changed": { uz: "Status yangilandi", ru: "Статус обновлён", en: "Status updated" },
    "car.confirm_status": { uz: "Holatni '{s}'ga o'zgartirasizmi?", ru: "Изменить статус на '{s}'?", en: "Change status to '{s}'?" },
    "car.photos": { uz: "Fotosuratlar", ru: "Фотографии", en: "Photos" },
    "car.add_photo": { uz: "Fotosurat qo'shish", ru: "Добавить фото", en: "Add photo" },
    "car.remove_photo": { uz: "Fotosuratni o'chirish", ru: "Удалить фото", en: "Remove photo" },
    "car.photo_added": { uz: "Fotosurat qo'shildi", ru: "Фото добавлено", en: "Photo added" },
    "car.photo_removed": { uz: "Fotosurat o'chirildi", ru: "Фото удалено", en: "Photo removed" },
    "car.no_photos": { uz: "Fotosuratlar yo'q", ru: "Нет фотографий", en: "No photos" },
    "car.photo_hint": { uz: "JPG/PNG/WebP, har biri ≤5MB. Bitta avtomobilga ko'pi bilan 8 ta.", ru: "JPG/PNG/WebP, каждый ≤5MB. До 8 фото на автомобиль.", en: "JPG/PNG/WebP, each ≤5MB. Up to 8 photos per car." },
    "car.photo_count": { uz: "foto", ru: "фото", en: "photos" },
    "car.photo_limit": { uz: "Bitta avtomobilga ko'pi bilan 8 ta fotosurat qo'shish mumkin", ru: "Можно добавить не более 8 фото на автомобиль", en: "Maximum 8 photos per car" },
    "car.photo_not_found": { uz: "Fotosurat topilmadi", ru: "Фото не найдено", en: "Photo not found" },

    // ---- lesson
    "lesson.add": { uz: "Yangi mashg'ulot", ru: "Новое занятие", en: "New lesson" },
    "lesson.create_title": { uz: "Yangi amaliy mashg'ulot", ru: "Новое практическое занятие", en: "New practical lesson" },
    "lesson.date": { uz: "Sana", ru: "Дата", en: "Date" },
    "lesson.time": { uz: "Vaqt", ru: "Время", en: "Time" },
    "lesson.start": { uz: "Boshlanish", ru: "Начало", en: "Start" },
    "lesson.end": { uz: "Tugash", ru: "Конец", en: "End" },
    "lesson.instructor": { uz: "Instruktor", ru: "Инструктор", en: "Instructor" },
    "lesson.car": { uz: "Avtomobil", ru: "Автомобиль", en: "Car" },
    "lesson.capacity": { uz: "Sig'im", ru: "Вместимость", en: "Capacity" },
    "lesson.students": { uz: "Talabalar", ru: "Ученики", en: "Students" },
    "lesson.search_student": { uz: "Talaba qo'shish... (ism yoki familiya)", ru: "Добавить ученика... (имя или фамилия)", en: "Add student... (name or surname)" },
    "lesson.add_student": { uz: "Talaba qo'shish", ru: "Добавить ученика", en: "Add student" },
    "lesson.start_btn": { uz: "Mashg'ulotni boshlash", ru: "Начать занятие", en: "Start lesson" },
    "lesson.finish_btn": { uz: "Mashg'ulotni yakunlash", ru: "Завершить занятие", en: "Finish lesson" },
    "lesson.cancel_btn": { uz: "Bekor qilish", ru: "Отменить", en: "Cancel lesson" },
    "lesson.cancel_reason": { uz: "Bekor qilish sababi", ru: "Причина отмены", en: "Cancel reason" },
    "lesson.reschedule_btn": { uz: "Ko'chirish", ru: "Перенести", en: "Reschedule" },
    "lesson.reschedule_title": { uz: "Mashg'ulotni ko'chirish", ru: "Перенос занятия", en: "Reschedule lesson" },
    "lesson.reschedule_info": { uz: "Qayta rejalashtirildi (avval → hozir)", ru: "Перенесено (было → стало)", en: "Rescheduled (was → now)" },
    "lesson.error": { uz: "Mashg'ulot yaratib bo'lmaydi", ru: "Не удалось создать занятие", en: "Cannot create lesson" },
    "lesson.status.scheduled": { uz: "🟡 Kutilmoqda", ru: "🟡 Ожидается", en: "🟡 Scheduled" },
    "lesson.status.ongoing": { uz: "🔵 Davom etmoqda", ru: "🔵 Идёт", en: "🔵 Ongoing" },
    "lesson.status.completed": { uz: "✅ Yakunlangan", ru: "✅ Завершено", en: "✅ Completed" },
    "lesson.status.cancelled": { uz: "❌ Bekor qilingan", ru: "❌ Отменено", en: "❌ Cancelled" },
    // ---- ESKI nomlar ("Olib ketish joyi"). Endi ishlatilMAYdi — faqat
    //      xarita qaytadiganda kerak bo'ladi. O'chirilmadi (i18n QA ogohlantirish
    //      bermasligi uchun ham saqlanib qoldi).
    "lesson.pickup": { uz: "Olib ketish joyi", ru: "Место забора", en: "Pickup location" },
    "lesson.map": { uz: "Xaritada ko'rish", ru: "Смотреть на карте", en: "View on map" },
    "lesson.call": { uz: "Qo'ng'iroq", ru: "Звонок", en: "Call" },
    "lesson.message": { uz: "Xabar", ru: "Сообщение", en: "Message" },
    "messages.empty": { uz: "Xabarlar tarixi bo'sh", ru: "История сообщений пуста", en: "No message history yet" },
    "lesson.attendance": { uz: "Davomat", ru: "Посещаемость", en: "Attendance" },
    "lesson.present": { uz: "Qatnashdi", ru: "Участвовал", en: "Present" },
    "lesson.late": { uz: "Kechikdi", ru: "Опоздал", en: "Late" },
    "lesson.absent": { uz: "Kelmagan", ru: "Не пришёл", en: "Absent" },
    "lesson.unmarked": { uz: "Belgilanmagan", ru: "Не отмечено", en: "Unmarked" },
    // ---- ESKI (xarita rejimi uchun saqlangan).
    "lesson.pickup_edit": { uz: "Qayerdan olib ketilsin?", ru: "Откуда забрать?", en: "Where should you be picked up?" },
    /* MODUL 4 — XARITA (Yandex Maps). Avval "lat"/"lng" yozuvlari ko'rinmasdi. */
    "map.open": { uz: "Xaritada ko'rish", ru: "Открыть на карте", en: "View on map" },
    "map.lat": { uz: "Kenglik", ru: "Широта", en: "Latitude" },
    "map.lng": { uz: "Uzunlik", ru: "Долгота", en: "Longitude" },
    "map.lat_hint": { uz: "Shimoldan janubga — masalan 41.311081", ru: "С севера на юг — например 41.311081", en: "North to south — e.g. 41.311081" },
    "map.lng_hint": { uz: "G'arbdan sharqqa — masalan 69.240562", ru: "С запада на восток — например 69.240562", en: "West to east — e.g. 69.240562" },
    "map.pick_hint": { uz: "Xaritada kerakli nuqtani bosing (yoki belgini suring) — kenglik va uzunlik avtomatik to'ldiriladi.", ru: "Нажмите нужную точку на карте (или перетащите метку) — широта и долгота заполнятся сами.", en: "Click the right spot on the map (or drag the pin) — latitude and longitude fill in automatically." },
    "map.loading": { uz: "Xarita yuklanmoqda…", ru: "Загрузка карты…", en: "Loading map…" },
    "map.no_key": { uz: "Xarita sozlanmagan: Yandex Maps API kaliti topilmadi.", ru: "Карта не настроена: не найден ключ Yandex Maps API.", en: "Map is not configured: Yandex Maps API key not found." },
    "map.no_key_fix": { uz: "Administrator `.env` fayliga Yandex Maps JS API kalitini qo'yishi kerak, keyin server qayta ishga tushiriladi.", ru: "Администратор должен добавить ключ Yandex Maps JS API в файл `.env` и перезапустить сервер.", en: "The administrator must add a Yandex Maps JS API key to `.env` and restart the server." },
    "map.config_error": { uz: "Xarita sozlamalari yuklanmadi. Serverga ulanib bo'lmadi.", ru: "Не удалось загрузить настройки карты. Нет связи с сервером.", en: "Could not load map settings. Cannot reach the server." },
    "map.load_error": { uz: "Xarita yuklanmadi. Internetni tekshirib, qayta urinib ko'ring.", ru: "Карта не загрузилась. Проверьте интернет и повторите попытку.", en: "The map failed to load. Check your internet connection and try again." },
    "map.init_error": { uz: "Xarita ishga tushmadi. Sahifani yangilang va qayta urinib ko'ring.", ru: "Не удалось запустить карту. Обновите страницу и повторите попытку.", en: "The map could not start. Refresh the page and try again." },
    "lesson.move_student": { uz: "Talabani ko'chirish", ru: "Переместить ученика", en: "Move student" },
    "lesson.request_btn": { uz: "Mashg'ulot so'rash", ru: "Запросить занятие", en: "Request a lesson" },
    "lesson.request_form": { uz: "Mashg'ulot so'rovi", ru: "Заявка на занятие", en: "Lesson request" },
    "lesson.next": { uz: "Keyingi mashg'ulot", ru: "Следующее занятие", en: "Next lesson" },
    "lesson.no_upcoming": { uz: "Rejalashtirilgan mashg'ulotlar yo'q", ru: "Нет запланированных занятий", en: "No upcoming lessons" },
    "lesson.teacher_phone": { uz: "Instruktor telefoni", ru: "Телефон инструктора", en: "Instructor's phone" },
    "lesson.students_count": { uz: "Guruhdagi talabalar", ru: "Учеников в группе", en: "Students in group" },
    "lesson.empty_today": { uz: "Bugun mashg'ulotlar mavjud emas.", ru: "Сегодня занятий нет.", en: "No lessons today." },
    "lesson.view_calendar": { uz: "Kalendarda ko'rish", ru: "Смотреть в календаре", en: "View in calendar" },
    "lesson.capacity_full_warn": { uz: "Sig'im to'lgan", ru: "Вместимость заполнена", en: "Capacity full" },
    "lesson.history_empty": { uz: "Mashg'ulotlar tarixi bo'sh", ru: "История занятий пуста", en: "Lesson history is empty" },
    "lesson.lesson": { uz: "Mashg'ulot", ru: "Занятие", en: "Lesson" },

    // ---- M4/M5: tarix va so'rovlarni tozalash / o'chirish (soft-delete)
    "history.clear_all": { uz: "Barchasini tozalash", ru: "Очистить всё", en: "Clear all" },
    "history.delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
    "history.clear_all_confirm": { uz: "Rostdan ham barcha tarixni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi", ru: "Вы действительно хотите удалить всю историю? Это действие нельзя отменить", en: "Really delete all history? This cannot be undone" },
    "requests.clear_all": { uz: "Barchasini tozalash", ru: "Очистить всё", en: "Clear all" },
    "requests.delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
    "requests.clear_all_confirm": { uz: "Rostdan ham barcha so'rovlarni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi", ru: "Вы действительно хотите удалить все заявки? Это действие нельзя отменить", en: "Really delete all requests? This cannot be undone" },

    // ---- student
    "student.full_name": { uz: "Ism familiya", ru: "Имя фамилия", en: "Full name" },
    "student.group": { uz: "Guruh", ru: "Группа", en: "Group" },
    "student.category": { uz: "Haydovchilik toifasi", ru: "Категория", en: "License category" },
    "student.enrolled": { uz: "Ro'yxatga olingan sana", ru: "Дата регистрации", en: "Enrolled on" },
    "student.address": { uz: "Manzil", ru: "Адрес", en: "Address" },
    "student.birth_date": { uz: "Tug'ilgan sana", ru: "Дата рождения", en: "Birth date" },
    "student.gender": { uz: "Jinsi", ru: "Пол", en: "Gender" },
    "student.phone2": { uz: "Qo'shimcha telefon", ru: "Доп. телефон", en: "Secondary phone" },
    "student.add": { uz: "Yangi talaba", ru: "Новый ученик", en: "New student" },
    "student.with_car": { uz: "Talaba avtomobilni tanlamaydi. Avtomobil instruktor orqali aniqlanadi.", ru: "Ученик не выбирает автомобиль. Автомобиль определяется инструктором.", en: "The student does not choose the car. It is determined by the instructor." },
    "student.status.active": { uz: "Faol", ru: "Активен", en: "Active" },
    "student.status.paused": { uz: "Tanaffusda", ru: "Пауза", en: "Paused" },
    "student.status.graduated": { uz: "Bitirgan", ru: "Выпущен", en: "Graduated" },
    "student.status.expelled": { uz: "Chiqarilgan", ru: "Отчислен", en: "Expelled" },
    "student.credentials": { uz: "Vaqtinchalik login/parol", ru: "Временные логин/пароль", en: "Temporary login/password" },

    // ---- CSV import natijalari (views-admin import results)
    "import.created": { uz: "Yaratildi:", ru: "Создано:", en: "Created:" },
    "import.duplicates": { uz: "Dublikat:", ru: "Дубликаты:", en: "Duplicates:" },
    "import.errors": { uz: "Xatolar:", ru: "Ошибки:", en: "Errors:" },
    "import.success": { uz: "Muvaffaqiyatli", ru: "Успешно", en: "Successful" },
    "import.no_errors": { uz: "Xatosiz", ru: "Без ошибок", en: "No errors" },
    "student.import": { uz: "Import (CSV)", ru: "Импорт (CSV)", en: "Import (CSV)" },
    // MODUL 3: "Bulk yaratish" -> "Tezkor yaratish".
    "student.bulk": { uz: "Tezkor yaratish", ru: "Быстрое создание", en: "Quick create" },
    "common.count": { uz: "Soni", ru: "Количество", en: "Count" },
    "common.send": { uz: "Yuborish", ru: "Отправить", en: "Send" },

    // ---- instructor
    "instructor.experience": { uz: "Ish tajribasi (yil)", ru: "Опыт (лет)", en: "Experience (years)" },
    "instructor.license_categories": { uz: "Haydovchilik toifalari", ru: "Категории", en: "License categories" },
    "instructor.work_days": { uz: "Ish kunlari", ru: "Рабочие дни", en: "Working days" },
    "instructor.schedule": { uz: "Ish jadvali", ru: "График работы", en: "Work schedule" },
    "instructor.break": { uz: "Tanaffus", ru: "Перерыв", en: "Break" },
    "instructor.bio": { uz: "Bio", ru: "Био", en: "Bio" },
    "instructor.add": { uz: "Yangi instruktor", ru: "Новый инструктор", en: "New instructor" },
    "instructor.assign_car": { uz: "Avtomobil biriktirish", ru: "Привязать автомобиль", en: "Assign car" },
    "instructor.no_car": { uz: "Sizga avtomobil biriktirilmagan", ru: "Вам не привязан автомобиль", en: "No car assigned to you" },
    "instructor.car_note": { uz: "Avtomobilni faqat admin o'zgartira oladi.", ru: "Автомобиль может менять только администратор.", en: "Only the admin can change the car." },
    "instructor.my_students": { uz: "Talabalarim", ru: "Мои ученики", en: "My students" },
    "instructor.students_empty": { uz: "Hozircha talabalar yo'q", ru: "Пока нет учеников", en: "No students yet" },
    "instructor.send_msg": { uz: "Xabar yuborish", ru: "Отправить сообщение", en: "Send message" },
    "instructor.attend_mark": { uz: "Davomatni belgilash", ru: "Отметить посещаемость", en: "Mark attendance" },
    "instructor.notes_about_stud": { uz: "Izoh", ru: "Заметка", en: "Note" },

    // ---- request
    "req.title": { uz: "Mashg'ulot so'rovlari", ru: "Заявки на занятия", en: "Lesson requests" },
    "req.pending": { uz: "🟡 Kutilmoqda", ru: "🟡 Ожидает", en: "🟡 Pending" },
    "req.approved": { uz: "🟢 Tasdiqlandi", ru: "🟢 Одобрено", en: "🟢 Approved" },
    "req.rejected": { uz: "🔴 Rad etildi", ru: "🔴 Отклонено", en: "🔴 Rejected" },
    "req.cancelled": { uz: "⚪ Bekor qilindi", ru: "⚪ Отменено", en: "⚪ Cancelled" },
    "req.rescheduled": { uz: "🔄 Ko'chirildi", ru: "🔄 Перенесено", en: "🔄 Rescheduled" },
    "req.approve": { uz: "Tasdiqlash", ru: "Одобрить", en: "Approve" },
    "req.reject": { uz: "Rad etish", ru: "Отклонить", en: "Reject" },
    "req.preferred": { uz: "Kutilgan vaqt", ru: "Желаемое время", en: "Preferred time" },
    "req.message": { uz: "Xabar", ru: "Сообщение", en: "Message" },
    "req.choose_schedule": { uz: "So'rovni tasdiqlash — sana/vaqt/instruktor", ru: "Одобрение заявки — дата/время/инструктор", en: "Approve request — date/time/instructor" },

    // ---- notifications
    "notif.title": { uz: "Bildirishnomalar", ru: "Уведомления", en: "Notifications" },
    "notif.all": { uz: "Barchasi", ru: "Все", en: "All" },
    "notif.delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
    "notif.clear_all": { uz: "Barchasini tozalash", ru: "Очистить все", en: "Clear all" },
    "notif.clear_all_confirm": { uz: "Rostdan ham barcha bildirishnomalarni o'chirmoqchimisiz? Bu amalni qaytarib bo'lmaydi.", ru: "Удалить все уведомления? Это действие нельзя отменить.", en: "Delete all notifications? This action cannot be undone." },
    "notif.read_all": { uz: "Barchasini o'qilgan deb belgilash", ru: "Отметить все прочитанными", en: "Mark all read" },
    "notif.send": { uz: "Xabar yuborish", ru: "Отправить уведомление", en: "Send notification" },
    "notif.to_role": { uz: "Kimga", ru: "Кому", en: "To" },
    "notif.empty": { uz: "Bildirishnomalar yo'q", ru: "Нет уведомлений", en: "No notifications" },
    "notif.unread": { uz: "O'qilmagan", ru: "Непрочитанные", en: "Unread" },
    "notif.system": { uz: "Tizim", ru: "Система", en: "System" },
    "notif.unknown": { uz: "Noma'lum foydalanuvchi", ru: "Неизвестный пользователь", en: "Unknown user" },
    "notif.reason": { uz: "Sabab", ru: "Причина", en: "Reason" },

    // ---- T2/M2: bildirishnoma sarlavhalari (kod -> til bo'yicha)
    "notif.t.lesson.created": { uz: "Mashg'ulot yaratildi", ru: "Занятие создано", en: "Lesson created" },
    "notif.t.lesson.assigned": { uz: "Sizga mashg'ulot biriktirildi", ru: "Вам назначено занятие", en: "Lesson assigned to you" },
    "notif.t.lesson.cancelled": { uz: "Mashg'ulot bekor qilindi", ru: "Занятие отменено", en: "Lesson cancelled" },
    "notif.t.lesson.rescheduled": { uz: "Mashg'ulot vaqti o'zgartirildi", ru: "Занятие перенесено", en: "Lesson rescheduled" },
    "notif.t.lesson.reminder": { uz: "Mashg'ulot eslatmasi", ru: "Напоминание о занятии", en: "Lesson reminder" },
    "notif.t.msg.new": { uz: "Yangi xabar", ru: "Новое сообщение", en: "New message" },
    "notif.t.request.new": { uz: "Yangi so'rov", ru: "Новая заявка", en: "New request" },
    "notif.t.2fa.code": { uz: "Xavfsizlik kodi", ru: "Код безопасности", en: "Security code" },
    "notif.t.auth.reset_token": { uz: "Parolni tiklash", ru: "Сброс пароля", en: "Password reset" },
    "notif.t.message": { uz: "Xabar", ru: "Сообщение", en: "Message" },
    "notif.t.admin": { uz: "Admin xabari", ru: "Сообщение администратора", en: "Admin message" },

    // ---- T2/M2: bildirishnoma matnlari (template, {param} almashtiriladi)
    "notif.m.lesson.created": { uz: "{date} {start_time}-{end_time} · {student_count} nafar talaba",
                                 ru: "{date} {start_time}-{end_time} · {student_count} учащихся",
                                 en: "{date} {start_time}-{end_time} · {student_count} students" },
    "notif.m.lesson.assigned": { uz: "{date} {start_time}-{end_time} · {instructor_name}",
                                 ru: "{date} {start_time}-{end_time} · {instructor_name}",
                                 en: "{date} {start_time}-{end_time} · {instructor_name}" },
    "notif.m.lesson.cancelled": { uz: "{date} {start_time}-{end_time}",
                                  ru: "{date} {start_time}-{end_time}",
                                  en: "{date} {start_time}-{end_time}" },
    "notif.m.lesson.rescheduled": { uz: "{date} {start_time}-{end_time}",
                                    ru: "{date} {start_time}-{end_time}",
                                    en: "{date} {start_time}-{end_time}" },
    "notif.m.lesson.reminder": { uz: "{date} {start_time}-{end_time}",
                                 ru: "{date} {start_time}-{end_time}",
                                 en: "{date} {start_time}-{end_time}" },
    "notif.m.msg.new": { uz: "{text}", ru: "{text}", en: "{text}" },
    "notif.m.request.new": { uz: "{student_name} amaliy mashg'ulot so'radi",
                             ru: "{student_name} запросил занятие",
                             en: "{student_name} requested a lesson" },
    "notif.m.2fa.code": { uz: "{code} — telefonni tasdiqlash kodi. Kod 5 daqiqa amal qiladi.",
                          ru: "{code} — код подтверждения телефона. Действует 5 минут.",
                          en: "{code} — phone verification code. Valid for 5 minutes." },
    "notif.m.auth.reset_token": { uz: "Parolni tiklash kodi: {token}", ru: "Код сброса пароля: {token}", en: "Password reset token: {token}" },
    "notif.m.message": { uz: "{text}", ru: "{text}", en: "{text}" },

    // ---- reports
    "report.title": { uz: "Hisobotlar", ru: "Отчёты", en: "Reports" },
    "report.period.daily": { uz: "Kunlik", ru: "Дневной", en: "Daily" },
    "report.period.weekly": { uz: "Haftalik", ru: "Недельный", en: "Weekly" },
    "report.period.monthly": { uz: "Oylik", ru: "Месячный", en: "Monthly" },
    "report.sessions": { uz: "Mashg'ulotlar", ru: "Занятия", en: "Lessons" },
    "report.completed": { uz: "Yakunlangan", ru: "Завершено", en: "Completed" },
    "report.cancelled": { uz: "Bekor qilingan", ru: "Отменено", en: "Cancelled" },
    "report.present": { uz: "Qatnashdi", ru: "Участвовали", en: "Present" },
    "report.late": { uz: "Kechikdi", ru: "Опоздали", en: "Late" },
    "report.absent": { uz: "Kelmagan", ru: "Не пришли", en: "Absent" },
    "report.export": { uz: "Eksport", ru: "Экспорт", en: "Export" },
    "report.per_instructor": { uz: "Instruktorlar faoliyati", ru: "Активность инструкторов", en: "Instructor activity" },
    "report.per_car": { uz: "Avtomobillardan foydalanish", ru: "Использование автомобилей", en: "Car usage" },

    // ====================================================================
    // MODUL 2 — Baza bo'limida toifa ichidagi foydalanuvchilar soni
    // ====================================================================
    "base.count": { uz: "Jami: {n} ta {what}", ru: "Всего: {n} {what}", en: "Total: {n} {what}" },
    "base.unit.student": { uz: "talaba", ru: "ученик(а/ов)", en: "student(s)" },
    "base.unit.instructor": { uz: "instruktor", ru: "инструктор(а/ов)", en: "instructor(s)" },
    "base.unit.admin": { uz: "admin", ru: "админ(а/ов)", en: "admin(s)" },
    "base.count_filtered": { uz: "(filtr bo'yicha {n} ta natija)", ru: "(по фильтру {n} результатов)", en: "({n} results by filter)" },

    // ====================================================================
    // MODUL 3 — Tugmalar: "Tezkor yaratish", Import ko'chirilgani
    // ====================================================================
    "base.go_reports": { uz: "Hisobot", ru: "Отчёт", en: "Report" },
    "base.go_reports_hint": { uz: "Hisobotlar bo'limiga o'tish", ru: "Перейти в раздел Отчёты", en: "Go to Reports section" },

    // ====================================================================
    // MODUL 5 — Eskirgan so'rovlar (so'ralgan mashg'ulot sanasidan +1 KUN)
    // ====================================================================
    "req.expired": { uz: "Muddati o'tgan", ru: "Срок истёк", en: "Expired" },
    "req.expired_hint": { uz: "So'ralgan mashg'ulot sanasidan 1 kun o'tib ketgan, lekin hali tasdiqlanmagan", ru: "С указанной даты занятия прошёл 1 день, заявка не подтверждена", en: "1 day has passed since the requested lesson date and it is still unconfirmed" },
    "req.filter_active": { uz: "Faol", ru: "Активные", en: "Active" },
    "req.filter_expired": { uz: "Eskirgan", ru: "Просроченные", en: "Expired" },
    "req.filter_history": { uz: "Tarix", ru: "История", en: "History" },
    "req.auto_hidden": { uz: "Muddati o'tgan so'rovlar asosiy ro'yxatdan avtomatik yashiriladi va \"Eskirgan\" bo'limiga o'tadi", ru: "Просроченные заявки автоматически скрываются из основного списка и переходят в раздел «Просроченные»", en: "Expired requests are automatically hidden from the main list and move to the Expired tab" },

    // ====================================================================
    // MODUL 5 — TO'LIQ HISOBOTLAR TIZIMI
    // ====================================================================
    "rep.tab.data": { uz: "Ma'lumot", ru: "Данные", en: "Data" },
    "rep.tab.creds": { uz: "Login va parollar", ru: "Логины и пароли", en: "Logins and passwords" },
    "rep.tab.import": { uz: "Import", ru: "Импорт", en: "Import" },
    "rep.pick_types": { uz: "Toifani tanlang", ru: "Выберите категорию", en: "Select categories" },
    "rep.pick_types_hint": { uz: "Bir nechtasini bir vaqtda tanlashingiz mumkin", ru: "Можно выбрать несколько одновременно", en: "You may select several at once" },
    "rep.cred_toggle": { uz: "Login va parollarni hisobotga qo'shish", ru: "Добавить логины и пароли в отчёт", en: "Include logins and passwords in the report" },
    "rep.cred_toggle_hint": { uz: "Yoqilgan holda hisiborat FAQAT: Ism, Familiya, Guruh, Login, Parol. Boshqa ma'lumot (statistika, jadval) QO'SHILMAYDI.", ru: "Когда выключено, отчёт содержит ТОЛЬКО: Имя, Фамилия, Группа, Логин, Пароль. Другие данные (статистика, расписание) НЕ добавляются.", en: "When ON, the report contains ONLY: First name, Last name, Group, Login, Password. Other data (statistics, schedule) is NOT included." },
    "rep.cred_toggle_warn": { uz: "Diqqat: bu hisobotda parollar ochiq matn ko'rinishida bo'ladi. Faylni xavfsiz saqlang va ishonchli bo'lmagan kanallar orqali yubormang.", ru: "Внимание: в этом отчёте пароли будут видны открытым текстом. Сохраните файл в безопасном месте и не отправляйте по ненадёжным каналам.", en: "Warning: passwords will appear in plain text in this report. Store the file securely and do not send it over untrusted channels." },
    "rep.wrong_mode": { uz: "Ikkala rejim aralashmaydi: login/parol yoqilgan — to'liq ma'lumot, o'chirilgan — maxfiy ma'lumot", ru: "Режимы не смешиваются: с логинами/паролями — полные данные, без — конфиденциальные", en: "Modes never mix: with credentials — full data, without — confidential data" },
    "rep.exported": { uz: "Hisobot yuklab olindi", ru: "Отчёт скачан", en: "Report downloaded" },
    "rep.type.students": { uz: "Talabalar", ru: "Ученики", en: "Students" },
    "rep.type.instructors": { uz: "Instruktorlar", ru: "Инструкторы", en: "Instructors" },
    "rep.type.admins": { uz: "Adminlar", ru: "Админы", en: "Admins" },
    "rep.fmt.csv": { uz: "CSV", ru: "CSV", en: "CSV" },
    "rep.fmt.xlsx": { uz: "XLSX", ru: "XLSX", en: "XLSX" },
    "rep.fmt.pdf": { uz: "PDF", ru: "PDF", en: "PDF" },
    "rep.no_types": { uz: "Kamida bitta toifa tanlang", ru: "Выберите хотя бы одну категорию", en: "Select at least one category" },
    "rep.col.name": { uz: "Ism", ru: "Имя", en: "First name" },
    "rep.col.lastname": { uz: "Familiya", ru: "Фамилия", en: "Last name" },
    "rep.col.group": { uz: "Guruh", ru: "Группа", en: "Group" },
    "rep.col.login": { uz: "Login", ru: "Логин", en: "Login" },
    "rep.col.password": { uz: "Parol", ru: "Пароль", en: "Password" },
    "rep.col.progress": { uz: "Progress", ru: "Прогресс", en: "Progress" },
    "rep.col.done": { uz: "O'tilgan mashg'ulotlar", ru: "Проведённые занятия", en: "Lessons taken" },
    "rep.col.total": { uz: "Jami belgilangan", ru: "Всего назначено", en: "Total assigned" },
    "rep.col.status": { uz: "Holat", ru: "Статус", en: "Status" },
    "rep.col.phone": { uz: "Telefon", ru: "Телефон", en: "Phone" },
    "rep.col.cat": { uz: "Toifa", ru: "Категория", en: "License category" },
    "rep.col.birth": { uz: "Tug'ilgan sana", ru: "Дата рождения", en: "Date of birth" },
    "rep.col.enrolled": { uz: "Qabul sanasi", ru: "Дата зачисления", en: "Enrolled" },
    "rep.creds_title": { uz: "LOGIN VA PAROLLAR", ru: "ЛОГИНЫ И ПАРОЛИ", en: "LOGINS AND PASSWORDS" },
    "rep.creds_sub": { uz: "{n} ta yozuv", ru: "{n} записей", en: "{n} record(s)" },

    // ====================================================================
    // MODUL 6 — Ommaviy (bulk) amallar
    // ====================================================================
    "bulk.pick": { uz: "Tanlangan foydalanuvchilar", ru: "Выбранные пользователи", en: "Selected users" },
    "bulk.count": { uz: "{n} ta tanlangan", ru: "{n} выбрано", en: "{n} selected" },
    "bulk.none": { uz: "Hech kim tanlanmagan", ru: "Ничего не выбрано", en: "None selected" },
    "bulk.select_all": { uz: "Hammasini tanlash", ru: "Выбрать все", en: "Select all" },
    "bulk.deselect_all": { uz: "Tanlashni bekor qilish", ru: "Снять выделение", en: "Clear selection" },
    "bulk.delete": { uz: "Ommaviy o'chirish", ru: "Удалить выбранных", en: "Bulk delete" },
    "bulk.edit": { uz: "Ommaviy tahrirlash", ru: "Изменить выбранных", en: "Bulk edit" },
    "bulk.confirm_delete": { uz: "{n} ta foydalanuvchini o'chirmoqchimisiz?\n\nBu amalni qaytarib bo'lmaydi: ularning ma'lumotlari, mashg'ulotlari va tarixi butunlay o'chib ketadi.", ru: "Удалить {n} пользователей?\n\nЭто действие необратимо: их данные, занятия и история будут полностью удалены.", en: "Delete {n} user(s)?\n\nThis cannot be undone: their data, lessons and history will be permanently removed." },
    "bulk.edit_title": { uz: "Ommaviy tahrirlash", ru: "Массовое изменение", en: "Bulk edit" },
    "bulk.edit_hint": { uz: "Bo'sh qoldirilgan maydonlar O'ZGARTIRILMAYDI — faqat to'ldirilganlar barcha tanlanganlarga qo'llaniladi.", ru: "Пустые поля НЕ ИЗМЕНЯЮТСЯ — заполненные применяются ко всем выбранным.", en: "Empty fields are NOT changed — only filled ones apply to all selected." },
    "bulk.edit_group": { uz: "Guruh", ru: "Группа", en: "Group" },
    "bulk.edit_category": { uz: "Haydovchilik toifasi", ru: "Категория прав", en: "License category" },
    "bulk.edit_status": { uz: "Holat", ru: "Статус", en: "Status" },
    "bulk.edit_notes": { uz: "Izoh", ru: "备注", en: "Notes" },
    "bulk.done": { uz: "{n} ta foydalanuvchi yangilandi", ru: "{n} пользователей обновлено", en: "{n} user(s) updated" },
    "bulk.deleted": { uz: "{n} ta foydalanuvchi o'chirildi", ru: "{n} пользователей удалено", en: "{n} user(s) deleted" },
    "bulk.confirm_all": { uz: "Filtr bo'yicha topilgan BARCHA {n} ta natisani tanlamoqchimisiz? (joriy sahifadagilar emas)", ru: "Выбрать ВСЕ {n} результатов по фильтру? (не только на текущей странице)", en: "Select ALL {n} results by filter? (not just the current page)" },
    "err.bulk.none": { uz: "Kamida bitta foydalanuvchini tanlang", ru: "Выберите хотя бы одного пользователя", en: "Select at least one user" },
    "err.bulk.too_many": { uz: "Bir vaqtda ko'p foydalanuvchini tahrirlab bo'lmaydi (maksimum {n})", ru: "Слишком много пользователей за раз (максимум {n})", en: "Too many users at once (max {n})" },
    "err.bulk.bad_id": { uz: "Foydalanuvchi identifikatori noto'g'ri", ru: "Некорректный идентификатор пользователя", en: "Invalid user identifier" },
    "err.bulk.self_protected": { uz: "O'z akkauntingizni o'chira yoki arxivlaya olmaysiz", ru: "Нельзя удалить или архивировать собственную учётную запись", en: "You cannot delete or archive your own account" },
    "err.bulk.nothing_to_change": { uz: "O'zgartiriladigan maydon kiritilmadi", ru: "Не указано ни одно поле для изменения", en: "No fields to change were provided" },
    "err.bulk.mixed_roles": { uz: "Turli rolli foydalanuvchilarni birga tahrirlab bo'lmaydi — avval bittasini tanlang", ru: "Нельзя изменять пользователей разных ролей вместе — выберите одну роль", en: "Cannot bulk-edit mixed roles at once — pick a single role" },
    // ---- VAZIFA 1: hisobot yaratish
    "err.export.bad_format": { uz: "Format noto'g'ri (CSV, XLSX yoki PDF)", ru: "Неверный формат (CSV, XLSX или PDF)", en: "Invalid format (CSV, XLSX or PDF)" },
    "err.export.bad_role": { uz: "Noma'lum rol: {role}", ru: "Неизвестная роль: {role}", en: "Unknown role: {role}" },
    "err.export.bad_roles": { uz: "Ro'yxatlar noto'g'ri", ru: "Некорректный список категорий", en: "Invalid category list" },
    "err.export.xlsx_unavailable": { uz: "XLSX uchun 'openpyxl' kutubxonasi o'rnatilmagan. Serverga: pip install openpyxl", ru: "Для XLSX не установлена библиотека 'openpyxl'. На сервере: pip install openpyxl", en: "The 'openpyxl' library is not installed for XLSX. On the server: pip install openpyxl" },
    "err.export.pdf_unavailable": { uz: "PDF uchun 'reportlab' kutubxonasi o'rnatilmagan. Serverga: pip install reportlab", ru: "Для PDF не установлена библиотека 'reportlab'. На сервере: pip install reportlab", en: "The 'reportlab' library is not installed for PDF. On the server: pip install reportlab" },
    "err.export.pdf_broken": { uz: "PDF yaratilishida xatolik (fayl to'g'ri shakllanmagan)", ru: "Ошибка создания PDF (файл сформирован неверно)", en: "PDF generation error (file malformed)" },
    "err.export.failed": { uz: "Hisobot yaratishda xatolik", ru: "Ошибка при создании отчёта", en: "Failed to generate report" },
    "err.rep.no_rows": { uz: "Tanlangan toifada foydalanuvchi topilmadi", ru: "В выбранных категориях нет пользователей", en: "No users found in the selected categories" },
    "rep.pw_new_needed": { uz: "YANGI_KERAK", ru: "НУЖЕН НОВЫЙ", en: "NEW_REQUIRED" },
    "rep.pw_new_needed_hint": { uz: "Parollar platformada scrypt bilan saqlanadi (xom ko'rinishda saqlanmaydi), shuning uchun tiklanmaydi. 'Parolni tiklash' orqali YENGI parol bering — eskisi o'chadi.", ru: "Пароли хранятся в виде scrypt-хеша (в открытом виде не сохраняются), поэтому их нельзя восстановить. Сбросьте НОВЫЙ пароль — старый станет недействителен.", en: "Passwords are stored as scrypt hashes (never in plain text) and cannot be recovered. Reset to issue a NEW password — the old one stops working." },
    "rep.audit_note": { uz: "Har bir yuklanish audit jurnalida qayd etiladi.", ru: "Каждое скачивание записывается в журнал аудита.", en: "Every download is recorded in the audit log." },
    "rep.generating": { uz: "Yaratilmoqda...", ru: "Создание...", en: "Generating..." },
    // ---- MODUL 4: eskirgan so'rovlar
    "err.req.expired_not_editable": { uz: "Muddati o'tgan so'rovni tahrirlab bo'lmaydi", ru: "Нельзя изменить заявку с истёкшим сроком", en: "An expired request cannot be edited" },

    // ---- audit
    "audit.title": { uz: "Audit jurnali", ru: "Журнал аудита", en: "Audit log" },

    // ---- backup
    // MODUL 7: UZ da "Backup" -> "Zaxira nusxa" (inglizcha so'z qolmasin).
    "backup.title": { uz: "Zaxira nusxa", ru: "Резервная копия", en: "Backup" },
    "backup.create": { uz: "Zaxira nusxa yaratish", ru: "Создать резервную копию", en: "Create backup" },
    /* ---- MODUL 1: Audit jurnali */
    "audit.time": { uz: "Vaqt", ru: "Время", en: "Time" },
    "audit.who": { uz: "Kim", ru: "Кто", en: "Who" },
    "audit.did": { uz: "Nima qildi", ru: "Что сделал", en: "Action" },
    "audit.target": { uz: "Kimga / nimaga", ru: "Кому / чему", en: "Target" },
    "audit.from": { uz: "Dan", ru: "С", en: "From" },
    "audit.to": { uz: "Gacha", ru: "По", en: "To" },
    "audit.user": { uz: "Foydalanuvchi", ru: "Пользователь", en: "User" },
    "audit.action": { uz: "Amal turi", ru: "Тип действия", en: "Action type" },
    "audit.all_users": { uz: "Barcha foydalanuvchilar", ru: "Все пользователи", en: "All users" },
    "audit.all_actions": { uz: "Barcha amallar", ru: "Все действия", en: "All actions" },
    "audit.search_ph": { uz: "Ism yoki amal matni bo'yicha qidirish...", ru: "Поиск по имени или тексту...", en: "Search by name or action text..." },
    "audit.immutable_hint": { uz: "Jurnal yozuvlari o'chirilmaydi va tahrirlanmaydi - bu butunlik kafolati.", ru: "Записи не удаляются и не редактируются.", en: "Journal entries cannot be deleted or edited - integrity guarantee." },
    "audit.empty": { uz: "Hozircha yozuv yo'q", ru: "Пока записей нет", en: "No entries yet" },
    "audit.system": { uz: "Tizim", ru: "Система", en: "System" },
    "audit.act.login": { uz: "Tizimga kirdi", ru: "Вошёл в систему", en: "Logged in" },
    "audit.act.logout": { uz: "Tizimdan chiqdi", ru: "Вышел из системы", en: "Logged out" },
    "audit.act.user_created": { uz: "Foydalanuvchi qo'shdi", ru: "Добавил пользователя", en: "Added user" },
    "audit.act.user_updated": { uz: "Foydalanuvchini tahrirladi", ru: "Изменил пользователя", en: "Edited user" },
    "audit.act.user_deleted": { uz: "Foydalanuvchini o'chirdi", ru: "Удалил пользователя", en: "Deleted user" },
    "audit.act.password_changed": { uz: "Parolni o'zgartirdi", ru: "Изменил пароль", en: "Changed password" },
    "audit.act.password_reset": { uz: "Parolni tikladi", ru: "Сбросил пароль", en: "Reset password" },
    "audit.act.session_created": { uz: "Mashg'ulot yaratdi", ru: "Создал занятие", en: "Created lesson" },
    "audit.act.session_cancelled": { uz: "Mashg'ulotni bekor qildi", ru: "Отменил занятие", en: "Cancelled lesson" },
    "audit.act.session_rescheduled": { uz: "Mashg'ulot vaqtini o'zgartirdi", ru: "Изменил время занятия", en: "Rescheduled lesson" },
    "audit.act.request_approved": { uz: "So'rovni tasdiqladi", ru: "Одобрил запрос", en: "Approved request" },
    "audit.act.request_rejected": { uz: "So'rovni rad etdi", ru: "Отказал запрос", en: "Rejected request" },
    "audit.act.backup_created": { uz: "Zaxira nusxa yaratdi", ru: "Создал резервную копию", en: "Created backup" },
    "audit.act.backup_restored": { uz: "Zaxira nusxani tikladi", ru: "Восстановил из резервной копии", en: "Restored backup" },
    "audit.act.backup_deleted": { uz: "Zaxira nusxani o'chirdi", ru: "Удалил резервную копию", en: "Deleted backup" },
    "audit.act.login_changed": { uz: "Loginni o'zgartirdi", ru: "Изменил логин", en: "Changed login" },

    /* ---- MODUL 1: Zaxira nusxa */
    "backup.empty": { uz: "Hozircha zaxira nusxa yo'q", ru: "Копий есь нет", en: "No backups yet" },
    "backup.file": { uz: "Fayl", ru: "Файл", en: "File" },
    "backup.size": { uz: "Hajmi", ru: "Размер", en: "Size" },
    "backup.download": { uz: "Yuklab olish", ru: "Скачать", en: "Download" },
    "backup.restore": { uz: "Tiklash", ru: "Восстановить", en: "Restore" },
    "backup.restored": { uz: "Zaxira nusxa tiklandi", ru: "Копия восстановлена", en: "Backup restored" },
    "backup.restore_title": { uz: "Zaxira nusxani tiklash", ru: "Восстановление копии", en: "Restore backup" },
    "backup.restore_warn": { uz: "DIQQAT: hozirgi barcha ma'lumotlar shu zaxira nusxa bilan ALMASHTIRILADI. Bu amalni qaytarib bo'lmaydi.", ru: "ВНИМАНИЯ: все текущие данные будут заменены этой копией заменена. Откатить неле.", en: "WARNING: all current data will be REPLACED by this backup. This cannot be undone." },
    "backup.restore_type": { uz: "Tasdiqlash uchun quyidagi so'zni yozing:", ru: "Для подтверждения напишите слово:", en: "Type the following word to confirm:" },
    "backup.restore_word": { uz: "TASDIQLASH", ru: "ПОДТВЕРЖДЕНИЯ", en: "TASDIQLASH" },
    "backup.restore_go": { uz: "Ha, tiklashni tasdiqlayman", ru: "Да, восстановить", en: "Yes, restore" },
    "backup.restore_wrong": { uz: "So'z noto'g'ri - tasdiqlash uchun TASDIQLASH deb yozish shart", ru: "Неверное слово", en: "Wrong word - type TASDIQLASH" },
    "backup.download_failed": { uz: "Faylni yuklab olib bo'lmadi", ru: "Не удалось скачать", en: "Download failed" },
    "backup.created": { uz: "Zaxira nusxa yaratildi", ru: "Резервная копия создана", en: "Backup created" },
    "backup.delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
    "backup.delete_confirm": { uz: "Bu zahira nusxani o'chirmoqchisiz? Bu amalni qaytarib bo'lmaydi.", ru: "Удалить эту резервную копию? Это действие необратимо.", en: "Delete this backup? This action cannot be undone." },
    "backup.deleted": { uz: "Zaxira nusxa o'chirildi", ru: "Резервная копия удалена", en: "Backup deleted" },

    // ---- settings
    "settings.title": { uz: "Sozlamalar", ru: "Настройки", en: "Settings" },
    "settings.allow_requests": { uz: "Talabalar mashg'ulot so'rashi mumkin", ru: "Ученики могут запрашивать занятия", en: "Students may request lessons" },

    // ---- profile
    "profile.title": { uz: "Profilim", ru: "Мой профиль", en: "My profile" },
    "profile.edit": { uz: "Profilni tahrirlash", ru: "Редактировать профиль", en: "Edit profile" },
    "profile.credentials": { uz: "Hisob", ru: "Аккаунт", en: "Account" },
    "profile.change_pass": { uz: "Parolni o'zgartirish", ru: "Сменить пароль", en: "Change password" },
    /* MODUL 4: parol VA login bir xil, alohida xavfsiz oqimda o'zgaradi. */
    "profile.change_credentials": { uz: "Parol va login o'zgartirish", ru: "Смена пароля и логина", en: "Change password and login" },
    "profile.change_credentials_hint": { uz: "Joriy parol bilan tasdiqlanadi. Kamida bittasi — login yoki parol — o'zgarishi shart.", ru: "Подтверждается текущим паролем. Нужно изменить хотя бы одно: логин или пароль.", en: "Confirmed with the current password. At least one of login or password must change." },
    "profile.new_login": { uz: "Yangi login (ixtiyoriy)", ru: "Новый логин (необязательно)", en: "New login (optional)" },
    "profile.new_password": { uz: "Yangi parol (ixtiyoriy)", ru: "Новый пароль (необязательно)", en: "New password (optional)" },
    "profile.confirm_new_password": { uz: "Yangi parolni takrorlang", ru: "Повторите новый пароль", en: "Repeat the new password" },
    "profile.current_password": { uz: "Joriy parol", ru: "Текущий пароль", en: "Current password" },
    "profile.credentials_saved": { uz: "Parol va login yangilandi. Boshqa qurilmalardagi sessiyalar bekor qilindi.", ru: "Пароль и логин обновлены. Сессии на других устройствах завершены.", en: "Password and login updated. Sessions on other devices were revoked." },
    "auth.pw_rules": { uz: "Parol talablari", ru: "Требования к паролю", en: "Password requirements" },
    "auth.pw_rule_len": { uz: "Kamida 10 ta belgi", ru: "Не менее 10 символов", en: "At least 10 characters" },
    "auth.pw_rule_lower": { uz: "Kamida bitta kichik harf (a-z)", ru: "Строчная буква (a-z)", en: "A lowercase letter (a-z)" },
    "auth.pw_rule_upper": { uz: "Kamida bitta bosh harf (A-Z)", ru: "Заглавная буква (A-Z)", en: "An uppercase letter (A-Z)" },
    "auth.pw_rule_digit": { uz: "Kamida bitta raqam (0-9)", ru: "Цифра (0-9)", en: "A digit (0-9)" },
    "auth.pw_rule_special": { uz: "Maxsus belgi (!@#$%^&*) — tavsiya etiladi", ru: "Спецсимвол (!@#$%^&*) — рекомендуется", en: "A special character (!@#$%^&*) — recommended" },
    "auth.pw_match_ok": { uz: "Parollar mos keldi", ru: "Пароли совпадают", en: "Passwords match" },
    "auth.pw_match_bad": { uz: "Parollar mos emas", ru: "Пароли не совпадают", en: "Passwords do not match" },
    "profile.my_car": { uz: "Mening avtomobilim", ru: "Мой автомобиль", en: "My car" },
    "profile.upload_photo": { uz: "Rasm yuklash", ru: "Загрузить фото", en: "Upload photo" },
    "profile.change_photo": { uz: "Rasmini o'zgartirish", ru: "Изменить фото", en: "Change photo" },
    "profile.crop": { uz: "Kesish", ru: "Обрезать", en: "Crop" },
    "profile.crop_help": { uz: "Kvadratni kerakli joyga suring va \"Kesish\" tugmasini bosing", ru: "Переместите квадрат в нужное место и нажмите «Обрезать»", en: "Drag the square to position and press Crop" },
    "profile.photo_saved": { uz: "Rasm saqlandi", ru: "Фото сохранено", en: "Photo saved" },
    "profile.photo_size": { uz: "Rasm 5MB dan katta bo'lmasin", ru: "Фото не более 5 МБ", en: "Photo must not exceed 5 MB" },
    "auth.otp": { uz: "2FA kod (SMS)", ru: "Код 2FA (SMS)", en: "2FA code (SMS)" },
    "profile.twofa": { uz: "Ikki bosqichli tasdiqlash (2FA)", ru: "Двухфакторная аутентификация (2FA)", en: "Two-factor authentication (2FA)" },
    "profile.twofa_enable": { uz: "Yoqish", ru: "Включить", en: "Enable" },
    "profile.twofa_disable": { uz: "O'chirish", ru: "Отключить", en: "Disable" },
    "profile.twofa_enabled": { uz: "2FA yoqilgan — tizimga kirishda kod talab qilinadi", ru: "2FA включена — при входе требуется код", en: "2FA enabled — a code is required on login" },
    "profile.twofa_disabled": { uz: "2FA o'chirilgan", ru: "2FA отключена", en: "2FA disabled" },
    "profile.twofa_scan": { uz: "Authenticator ilovasida QRni skanerlang yoki kalitni qo'lda kiriting:", ru: "Отсканируйте QR в приложении-аутентификаторе или введите ключ вручную:", en: "Scan the QR in your authenticator app or type the key manually:" },
    "profile.twofa_secret": { uz: "Maxfiy kalit", ru: "Секретный ключ", en: "Secret key" },
    "profile.twofa_code": { uz: "SMS'dan 6 raqamli kod", ru: "6-значный код из SMS", en: "6-digit SMS code" },
    "profile.twofa_confirm": { uz: "Kodni kiritib tasdiqlang", ru: "Подтвердите кодом", en: "Confirm with the code" },
    "profile.twofa_password_hint": { uz: "Xavfsizlik uchun joriy parolingizni kiriting:", ru: "Для безопасности введите текущий пароль:", en: "Enter your current password for security:" },
    "profile.twofa_phone_hint": { uz: "Kod yuboriladigan telefon raqamingiz:", ru: "Ваш номер телефона для отправки кода:", en: "Your phone number to receive the code:" },
    "profile.twofa_sms_sent": { uz: "SMS kod yuborildi. 6 raqamli kodni kiriting:", ru: "SMS-код отправлен. Введите 6-значный код:", en: "An SMS code was sent. Type the 6-digit code:" },
    "profile.twofa_sms_note": { uz: "Kod bildirishnoma sifatida ham yuboriladi (demo)", ru: "Код также отправляется как уведомление (демо)", en: "The code is also delivered as a notification (demo)" },
    "profile.edit_phone_hint": { uz: "Telefon so'zma-so'z: +998 90 123 45 67 yoki pastki qismidagi qo'ng'iroq havolalari shunga moslanadi", ru: "Телефон в формате: +998 90 123 45 67", en: "Phone format: +998 90 123 45 67" },

    // ---- misc
    "misc.today": { uz: "Bugun", ru: "Сегодня", en: "Today" },
    "misc.yes": { uz: "Ha", ru: "Да", en: "Yes" },
    "misc.monday": { uz: "Dushanba", ru: "Понедельник", en: "Monday" },
    "misc.tuesday": { uz: "Seshanba", ru: "Вторник", en: "Tuesday" },
    "misc.wednesday": { uz: "Chorshanba", ru: "Среда", en: "Wednesday" },
    "misc.thursday": { uz: "Payshanba", ru: "Четверг", en: "Thursday" },
    "misc.friday": { uz: "Juma", ru: "Пятница", en: "Friday" },
    "misc.saturday": { uz: "Shanba", ru: "Суббота", en: "Saturday" },
    "misc.sunday": { uz: "Yakshanba", ru: "Воскресенье", en: "Sunday" },
    "misc.success": { uz: "Bajarildi", ru: "Выполнено", en: "Done" },
    "misc.saved": { uz: "Saqlanib o'zlashtirildi", ru: "Сохранено", en: "Saved" },

    // ---- M12: sozlamalar
    "settings.lang_title": { uz: "Til va mintaqa", ru: "Язык и регион", en: "Language & region" },
    "settings.region_info": { uz: "Mintaqa: O'zbekiston (Toshkent, UTC+5)", ru: "Регион: Узбекистан (Ташкент, UTC+5)", en: "Region: Uzbekistan (Tashkent, UTC+5)" },
    "settings.theme_title": { uz: "Tema (mavzu)", ru: "Тема", en: "Theme" },
    "settings.theme_hint": { uz: "Kunduzgi yoki tungi ko'rinishni tanlang", ru: "Выберите светлый или тёмный вид", en: "Pick light or dark appearance" },
    "settings.theme_light": { uz: "☀️ Kunduzgi", ru: "☀️ Светлая", en: "☀️ Light" },
    "settings.theme_dark": { uz: "🌙 Tungi", ru: "🌙 Тёмная", en: "🌙 Dark" },
    "settings.notif_title": { uz: "Bildirishnoma sozlamalari", ru: "Настройки уведомлений", en: "Notification settings" },
    "settings.notif_hint": { uz: "Qaysi hodisalar uchun bildirishnoma kelishini belgilang", ru: "Выберите события, для которых нужны уведомления", en: "Choose which events notify you" },
    "settings.notif_lesson": { uz: "Mashg'ulotlar (yaratish/bekor qilish/ko'chirish)", ru: "Занятия (создание/отмена/перенос)", en: "Lessons (created/cancelled/rescheduled)" },
    "settings.notif_request": { uz: "So'rovlar (mashg'ulot so'rash)", ru: "Заявки (запрос занятия)", en: "Requests (lesson requests)" },
    "settings.notif_message": { uz: "Xabarlar (chat)", ru: "Сообщения (чат)", en: "Messages (chat)" },
    "settings.notif_security": { uz: "Xavfsizlik hodisalari", ru: "События безопасности", en: "Security events" },
    "settings.notif_reminder": { uz: "Mashg'ulot eslatmalari", ru: "Напоминания о занятии", en: "Lesson reminders" },
    "settings.notif_lesson_title": { uz: "Mashg'ulotlar", ru: "Занятия", en: "Lessons" },
    "settings.notif_lesson_desc": { uz: "Yaratish/bekor qilish/ko'chirish", ru: "Создание, отмена, перенос", en: "Created, cancelled, rescheduled" },
    "settings.notif_request_title": { uz: "So'rovlar", ru: "Заявки", en: "Requests" },
    "settings.notif_request_desc": { uz: "Mashg'ulot so'rash", ru: "Запрос занятия", en: "Lesson requests" },
    "settings.notif_message_title": { uz: "Xabarlar", ru: "Сообщения", en: "Messages" },
    "settings.notif_message_desc": { uz: "Chat xabarlari", ru: "Сообщения чата", en: "Chat messages" },
    "settings.notif_security_title": { uz: "Xavfsizlik hodisalari", ru: "События безопасности", en: "Security events" },
    "settings.notif_security_desc": { uz: "Kirish va xavfsizlik o'zgarishlari", ru: "Вход и изменения безопасности", en: "Logins and security changes" },
    "settings.notif_reminder_title": { uz: "Mashg'ulot eslatmalari", ru: "Напоминания о занятии", en: "Lesson reminders" },
    "settings.notif_reminder_desc": { uz: "Mashg'ulot boshlanishidan oldin eslatma", ru: "Напоминание перед занятием", en: "Reminder before the lesson" },
    "settings.allow_requests_desc": { uz: "Talabalar o'zlari mashg'ulot vaqtini so'rashi mumkin", ru: "Ученики могут сами запрашивать время занятия", en: "Students may request lesson slots themselves" },
    "settings.security_title": { uz: "Maxfiylik va xavfsizlik", ru: "Конфиденциальность и безопасность", en: "Privacy & security" },
    "settings.sessions_title": { uz: "Faol sessiyalar", ru: "Активные сессии", en: "Active sessions" },
    "settings.sessions_empty": { uz: "Faol sessiya yo'q", ru: "Нет активных сессий", en: "No active sessions" },
    "settings.sessions_current": { uz: "Joriy qurilma", ru: "Текущее устройство", en: "Current device" },
    "settings.sessions_created": { uz: "Boshlangan", ru: "Начата", en: "Started" },
    "settings.sessions_last_seen": { uz: "Oxirgi faollik", ru: "Последняя активность", en: "Last active" },
    "settings.sessions_expires": { uz: "Amal qilish muddati", ru: "Срок действия", en: "Expires" },
    "settings.revoke": { uz: "O'chirish", ru: "Завершить", en: "End" },
    "settings.revoke_all": { uz: "Barcha qurilmalardan chiqish", ru: "Выйти со всех устройств", en: "Log out of all devices" },
    "settings.revoke_all_confirm": { uz: "Barcha qurilmalardan chiqishni tasdiqlaysizmi? Joriy sessiya ham tugatiladi.", ru: "Выйти со всех устройств? Текущая сессия также будет завершена.", en: "Log out of all devices? The current session will end too." },
    "settings.sessions_current_revoked": { uz: "Joriy sessiya tugatildi — qayta kiring", ru: "Текущая сессия завершена — войдите снова", en: "Current session ended — sign in again" },
    "settings.change_password": { uz: "Parolni o'zgartirish", ru: "Сменить пароль", en: "Change password" },
    "settings.platform_title": { uz: "Platforma sozlamalari", ru: "Настройки платформы", en: "Platform settings" },
    "settings.platform_hint": { uz: "Yangi mashg'ulotlar va eslatmalar uchun standart qiymatlar", ru: "Значения по умолчанию для новых занятий и напоминаний", en: "Defaults for new lessons and reminders" },
    "settings.lesson_duration": { uz: "Mashg'ulot davomiyligi standarti (daqiqa)", ru: "Стандартная длительность занятия (мин)", en: "Default lesson duration (minutes)" },
    "settings.work_start": { uz: "Ish vaqti boshlanishi", ru: "Начало рабочего времени", en: "Work start" },
    "settings.work_end": { uz: "Ish vaqti tugashi", ru: "Конец рабочего времени", en: "Work end" },
    "settings.reminder_minutes": { uz: "Avtomatik eslatma vaqti (daqiqa oldin)", ru: "Время напоминания (за N минут)", en: "Auto reminder (minutes before)" },
    "settings.reminder_hint": { uz: "Mashg'ulot boshlanishidan necha daqiqa oldin ishtirokchilarga eslatma yuboriladi", ru: "За сколько минут до занятия отправлять напоминание участникам", en: "How many minutes before the lesson to remind participants" },
    /* MODUL 5: ommaviy (platforma) jami-darslar maqsadi */
    "settings.total_lessons": { uz: "Jami darslar (barcha talabalar uchun)", ru: "Всего занятий (для всех учеников)", en: "Total lessons (all students)" },
    "settings.total_lessons_hint": { uz: "Talabada individual qiymat belgilangan bo'lsa, u shu yer ustun keladi", ru: "Если у ученика задан индивидуальный план, он имеет приоритет", en: "An individual student plan overrides this value" },
    "err.user.bad_total_lessons": { uz: "Jami darslar soni 1 dan 999 gacha bo'lishi kerak (yoki bo'sh qoldiring)", ru: "Количество занятий — от 1 до 999 (или оставьте пустым)", en: "Total lessons must be 1–999 (or leave empty)" },
    /* Chiqish (logout) — Admin, Instruktor va Talaba uchun umumiy */
    "settings.logout_title": { uz: "Sessiya va chiqish", ru: "Сессия и выход", en: "Session & sign out" },
    "settings.logout_hint": { uz: "Hisobingizdan xavfsiz chiqing. Joriy sessiya serverda ham yakunlanadi.", ru: "Безопасно выйдите из аккаунта. Текущая сессия завершится и на сервере.", en: "Sign out safely. The current session is ended on the server too." },
    "settings.logout_btn": { uz: "Hisobdan chiqish", ru: "Выйти из аккаунта", en: "Sign out of account" },
    "settings.logout_desc": { uz: "Bu amaldan keyin qayta kirish uchun login va parol kerak bo'ladi.", ru: "После этого действия для повторного входа понадобятся логин и пароль.", en: "After this you will need your login and password to sign in again." },
    "logout.confirm_title": { uz: "Hisobdan chiqmoqchimisiz?", ru: "Выйти из аккаунта?", en: "Sign out of your account?" },
    "logout.confirm_text": { uz: "Tasdiqlasangiz, sessiya yakunlanadi va login sahifasiga qaytasiz.", ru: "После подтверждения сессия завершится, и вы вернётесь на страницу входа.", en: "Once confirmed, the session ends and you return to the sign-in page." },
    "logout.confirm_yes": { uz: "Ha, chiqish", ru: "Да, выйти", en: "Yes, sign out" },
    "logout.done": { uz: "Hisobdan chiqdingiz", ru: "Вы вышли из аккаунта", en: "You have signed out" },
    "logout.sidebar": { uz: "Chiqish", ru: "Выйти", en: "Sign out" },
    "logout.server_error": { uz: "Serverga ulanib bo'lmadi — sessiya yopilmagan bo'lishi mumkin. Brauzerni yopib qayta oching.", ru: "Не удалось связаться с сервером — сессия могла не завершиться. Закройте и снова откройте браузер.", en: "Could not reach the server — the session may not have ended. Close and reopen your browser." },
    /* Sessiya almashib qolgan holat (tab'ga xos sessiya himoyasi) */
    "session.switched": { uz: "Sessiya boshqa foydalanuvchiga o'tdi. Xavfsizlik uchun ma'lumotlar yashirildi — qayta kiring.", ru: "Сессия перешла к другому пользователю. Данные скрыты в целях безопасности — войдите снова.", en: "This session now belongs to another user. Your data was hidden for safety — please sign in again." },
    "err.auth.ip_blocked": { uz: "Juda ko'p urinish. {seconds} soniya kutib, qayta urinib ko'ring.", ru: "Слишком много попыток. Подождите {seconds} секунд и повторите.", en: "Too many attempts. Wait {seconds} seconds and try again." },
    "err.auth.password_same": { uz: "Yangi parol eskisidan farq qilishi kerak.", ru: "Новый пароль должен отличаться от старого.", en: "The new password must be different from the old one." },
    "err.auth.password_used": { uz: "Bu parol allaqachon ishlatilgan - boshqasini tanlang.", ru: "Этот пароль уже использовался - выберите другой.", en: "This password was already used - choose another one." },
    "err.auth.password_weak": { uz: "Parol kamida 10 belgidan, bosh harf va raqamdan iborat bo'lishi kerak", ru: "Пароль должен содержать не менее 10 символов, заглавную букву и цифру", en: "Password must be at least 10 characters and contain an uppercase letter and a digit" },
    "err.auth.nothing_to_change": { uz: "Yangi login yoki yangi parol kiritish shart", ru: "Укажите новый логин или новый пароль", en: "Enter a new login or a new password" },
    "err.auth.password_mismatch": { uz: "Yangi parol va uning takrori bir-biriga mos kelmadi", ru: "Новый пароль и его повтор не совпадают", en: "The new password and its repeat do not match" },
    "err.auth.confirm_required": { uz: "Yangi parolni takrorlash shart", ru: "Необходимо повторить новый пароль", en: "Please repeat the new password" },
    "err.csrf_invalid": { uz: "Xavfsizlik tokeni yaroqli emas. Sahifani yangilang va qayta urinib ko'ring.", ru: "Недействительный токен безопасности. Обновите страницу и повторите.", en: "Invalid security token. Refresh the page and try again." },
    "err.csrf_origin": { uz: "So'rov manzili mos kelmadi. Sahifani yangilang va qayta urinib ko'ring.", ru: "Адрес запроса не совпадает. Обновите страницу и повторите.", en: "The request origin does not match. Refresh the page and try again." },
    "err.map.address_too_long": { uz: "Manzil juda uzun (maksimum 400 belgi).", ru: "Адрес слишком длинный (максимум 400 символов).", en: "The address is too long (maximum 400 characters)." },
    "err.notif.too_long": { uz: "Xabar juda uzun (maksimum 2000 belgi).", ru: "Сообщение слишком длинное (максимум 2000 символов).", en: "The message is too long (maximum 2000 characters)." },
    "err.profile.birth_date_invalid": { uz: "Tug'ilgan sana noto'g'ri yoki kelajakda bo'lishi mumkin emas.", ru: "Неверная дата рождения или дата в будущем.", en: "Invalid date of birth or the date is in the future." },
    "err.profile.login_format": { uz: "Login `usrL_` bilan boshlanishi va 14-32 ta harf/raqamdan iborat bo'lishi kerak.", ru: "Логин должен начинаться с `usrL_` и содержать 14-32 буквы/цифры.", en: "The login must start with `usrL_` and contain 14-32 letters/digits." },
    "err.profile.login_taken": { uz: "Bu login band. Boshqasini tanlang.", ru: "Этот логин занят. Выберите другой.", en: "This login is taken. Choose another one." },
    "err.profile.phone_invalid": { uz: "Telefon raqam noto'g'ri (masalan: +998901234567).", ru: "Неверный номер телефона (например: +998901234567).", en: "Invalid phone number (e.g. +998901234567)." },
    "err.rate_limited": { uz: "Juda ko'p so'rov. Biroz kutib, qayta urinib ko'ring.", ru: "Слишком много запросов. Подождите немного и повторите.", en: "Too many requests. Wait a moment and try again." },
    "err.user.not_a_student": { uz: "Bu foydalanuvchi talaba emas.", ru: "Этот пользователь не студент.", en: "This user is not a student." },
    "err.user.total_lessons_below_done": { uz: "Jami darslar soni bajarilganlardan kam bo'lishi mumkin emas (bajarilgan: {done}).", ru: "Общее число занятий не может быть меньше выполненных (выполнено: {done}).", en: "The total cannot be lower than completed lessons ({done} completed)." },
    "home.overdue_count": { uz: "O'tib ketgan: {n}", ru: "Пропущено: {n}", en: "Overdue: {n}" },
    "home.sessions_count": { uz: "Jami mashg'ulot: {n}", ru: "Всего занятий: {n}", en: "Total lessons: {n}" },
    "home.upcoming_count": { uz: "Kelayotgan: {n}", ru: "Предстоит: {n}", en: "Upcoming: {n}" },
    "map.address": { uz: "Manzil", ru: "Адрес", en: "Address" },
    "map.address_hint": { uz: "Manzil tanlang yoki xaritada nuqtani bosing - koordinatani kiritish shart emas.", ru: "Выберите адрес или нажмите точку на карте - вводить координаты не нужно.", en: "Pick an address or click a point on the map - no coordinates needed." },
    "map.address_ph": { uz: "Manzilni yozing (masalan: Beshariq tumani)", ru: "Введите адрес (например: Бекaryкский район)", en: "Type an address (e.g. Beshariq district)" },
    "map.address_required": { uz: "Manzilni kiritish shart", ru: "Укажите адрес", en: "Address is required" },
    "map.autocomplete_hint": { uz: "Manzilni yozing - variantlar paydo bo'ladi. Tanlangandan so'ng xaritada nuqta avtomatik qo'yiladi.", ru: "Введите адрес - появятся варианты. После выбора точка появится на карте автоматически.", en: "Type an address - suggestions will appear. After you pick one, the map pin is set automatically." },
    "map.geocoder_failed": { uz: "Manzilni aniqlab bo'lmadi. Boshqa shaklda yozib ko'ring (masalan: ko'cha, uy raqami).", ru: "Не удалось определить адрес. Попробуйте написать иначе (например: улица, номер дома).", en: "Could not resolve the address. Try a different format (e.g. street, house number)." },
    "map.geocoder_no_key": { uz: "Manzil avtomatik to'ldirilmaydi: Yandex geocoder kaliti serverga o'rnatilmagan. Xaritada nuqtani bosing yoki manzilni qo'lda yozing. Administrator `.env` fayliga `YANDEX_GEOCODER_API_KEY` qo'yishi kerak.", ru: "Автозаполнение адреса недоступно: на сервере не задан ключ Yandex geocoder. Нажмите точку на карте или введите адрес вручную. Администратор должен добавить `YANDEX_GEOCODER_API_KEY` в `.env`.", en: "Address autocomplete is unavailable: the Yandex geocoder key is not configured on the server. Click a point on the map or type the address manually. The administrator must set `YANDEX_GEOCODER_API_KEY` in `.env`." },
    "map.no_result": { uz: "Bunday manzil topilmadi. Xaritada nuqtani bosing yoki ko'proq ma'lumot qo'shing.", ru: "Такой адрес не найден. Нажмите точку на карте или добавьте больше данных.", en: "No such address found. Click a point on the map or add more detail." },
    "map.reverse_fail": { uz: "Bu nuqta uchun aniq manzil topilmadi - manzilni qo'lda to'ldiring.", ru: "Для этой точки точный адрес не найден - заполните адрес вручную.", en: "No exact address found for this point - fill the address manually." },
    "map.reverse_ok": { uz: "Nuqtani manzilga aylantirildi", ru: "Координаты преобразованы в адрес", en: "Point converted to an address" },
    // ---- "Olib ketish joyi" -> "Uchrashuv joyi" (xarita vaqtincha o'chirilgan).
    //      `meeting.*` — oddiy MATN maydoni (xaritasiz). `map.*` esa xarita
    //      qaytadiganda kerak bo'ladi va o'chirilmagan.
    "meeting.place": { uz: "Uchrashuv joyi", ru: "Место встречи", en: "Meeting place" },
    "meeting.place_edit": { uz: "Uchrashuv joyini tahrirlash", ru: "Изменить место встречи", en: "Edit meeting place" },
    "meeting.place_hint": { uz: "Instruktor sizni shu yerdan kutadi. Yozib qo'ying \u2014 masalan: Beshariq, Mustaqillik maydoni yonida.", ru: "Инструктор ждёт вас здесь. Напишите \u2014 например: Бекарык, рядом с площадью Независимости.", en: "The instructor will meet you here. Type it \u2014 e.g.: Beshariq, next to Independence Square." },
    "meeting.place_ph": { uz: "Masalan: Beshariq, Mustaqillik maydoni yonida", ru: "Например: Бекарык, рядом с площадью Независимости", en: "E.g.: Beshariq, next to Independence Square" },
    "notif.cat_lesson": { uz: "Mashg'ulotlar", ru: "Занятия", en: "Lessons" },
    "notif.cat_message": { uz: "Xabarlar", ru: "Сообщения", en: "Messages" },
    "notif.cat_reminder": { uz: "Mashg'ulot eslatmalari", ru: "Напоминания о занятиях", en: "Lesson reminders" },
    "notif.reminder_2h": { uz: "Sizning amaliy mashg'ulotingizga 2 soat qoldi.", ru: "До вашего практического занятия осталось 2 часа.", en: "2 hours left until your practical lesson." },
    "profile.login_changed": { uz: "Login o'zgartirildi. Boshqa qurilmalardagi sessiyalar xavfsizlik uchun bekor qilindi.", ru: "Логин изменён. Сессии на других устройствах завершены из соображений безопасности.", en: "Login changed. Sessions on other devices were revoked for security." },
    "profile.login_hint": { uz: "Login `usrL_` bilan boshlanadi va 14-32 ta harf/raqamdan iborat bo'lishi shart. Boshqa foydalanuvchida bo'lmasligi kerak.", ru: "Логин должен начинаться с `usrL_` и содержать 14-32 буквы/цифры. Он должен быть уникальным.", en: "The login must start with `usrL_` and contain 14-32 letters/digits and must be unique." },
    "profile.password_not_here": { uz: "Parol bu oynada ko'rsatilmaydi va tahrirlanmaydi. Uni faqat «Parolni o'zgartirish» orqali almashtirasiz.", ru: "Пароль здесь не отображается и не изменяется. Смените его только через «Изменить пароль».", en: "The password is not shown or changed here. Use “Change password” instead." },
    "settings.notif_admin": { uz: "admin_messages", ru: "admin_messages", en: "admin_messages" },
    "settings.notif_admin_desc": { uz: "Administrator yuborgan xabarlar", ru: "Сообщения от администратора", en: "Messages sent by the administrator" },
    "settings.notif_admin_title": { uz: "Admin xabarlari", ru: "Сообщения администратора", en: "Admin messages" },
    "st.cancelled": { uz: "Bekor qilingan", ru: "Отменено", en: "Cancelled" },
    "st.completed": { uz: "Bajarilgan", ru: "Выполнено", en: "Completed" },
    "st.confirmed": { uz: "Tasdiqlangan", ru: "Подтверждено", en: "Confirmed" },
    "st.ongoing": { uz: "Jarayonda", ru: "Идёт", en: "Ongoing" },
    "st.overdue": { uz: "O'tib ketgan", ru: "Просрочено", en: "Overdue" },
    "st.pending": { uz: "Kutilmoqda", ru: "Ожидает", en: "Pending" },
    "st.rejected": { uz: "Rad etilgan", ru: "Отклонено", en: "Rejected" },
    "student.category_ph": { uz: "Masalan: B", ru: "Например: B", en: "e.g. B" },
    "student.group_ph": { uz: "Masalan: 2024-A", ru: "Например: 2024-A", en: "e.g. 2024-A" },
    "users.edit_btn": { uz: "Ma'lumotni tahrirlash", ru: "Изменить данные", en: "Edit details" },
    "users.field_name": { uz: "Talaba", ru: "Студент", en: "Student" },
    "users.new_password": { uz: "Yangi parol yaratish", ru: "Создать новый пароль", en: "Generate new password" },
    "users.new_password_confirm": { uz: "Ushbu foydalanuvchi uchun yangi parol yaratilsinmi? Eski parol darhol bekor qilinadi.", ru: "Создать новый пароль для этого пользователя? Старый пароль будет отменён немедленно.", en: "Generate a new password for this user? The old password is revoked immediately." },
    "users.password_shown_once": { uz: "Bu parol faqat BIR MARTA ko'rsatiladi. Admin uni qayta ko'ra olmaydi - uni darhol foydalanuvchiga yetkazing.", ru: "Этот пароль показывается ОДИН раз. Администратор не сможет увидеть его снова - передайте его пользователю сразу.", en: "This password is shown ONCE. The admin cannot see it again - pass it to the user immediately." },
    "users.profile_title": { uz: "Foydalanuvchi profili", ru: "Профиль пользователя", en: "User profile" },
    "users.scope_all": { uz: "Barcha talabalar", ru: "Все студенты", en: "All students" },
    "users.scope_single": { uz: "Bitta talaba", ru: "Один студент", en: "Single student" },
    "users.total_all_hint": { uz: "BARCHA talabalar uchun jami son bir xil qilinadi. Bitta talabaning bajarilgan darslari soni bu qiymatdan ko'p bo'lsa — saqlanmaydi.", ru: "Общее число будет одинаковым для ВСЕХ студентов. Если у студента больше выполненных занятий - значение не сохранится.", en: "The same total will be set for ALL students. If a student has more completed lessons, the value will be rejected." },
    "users.total_below_done": { uz: "Bajarilgan darslardan kam qilib bo'lmaydi (hozir {n} ta bajarilgan).", ru: "Нельзя меньше выполненных занятий (уже выполнено {n}).", en: "Cannot be lower than completed lessons ({n} completed)." },
    "users.total_btn": { uz: "Jami dars sonini o'zgartirish", ru: "Изменить число занятий", en: "Change total lessons" },
    "users.total_btn_all": { uz: "Barcha talabalar uchun", ru: "Для всех студентов", en: "For all students" },
    "users.total_clear": { uz: "O'chirish (umumiy songa qaytarish)", ru: "Очистить (вернуть общему значению)", en: "Clear (revert to the group default)" },
    "users.total_hint": { uz: "Bajarilgan mashg'ulotlar: {n}. Yangi son bundan kam bo'lishi mumkin emas. Bajarilgan mashg'ulotlar va tarix o'chirilmaydi.", ru: "Выполнено занятий: {n}. Новое число не может быть меньше. Выполненные занятия и история не удаляются.", en: "Completed lessons: {n}. The new value cannot be lower. Completed lessons and history are not deleted." },
    "users.total_one_hint": { uz: "Faqat tanlangan talabaning jami soni o'zgaradi (bajarilgan: {n}).", ru: "Изменится только выбранного студента (выполнено: {n}).", en: "Only the selected student's total changes (completed: {n})." },
    "users.total_saved_all": { uz: "Barcha talabalar uchun yangi jami saqlandi ({n} ta talaba)", ru: "Новое общее число сохранено для всех студентов ({n} студентов)", en: "New total saved for all students ({n} students)" },
    "users.total_saved_one": { uz: "Talabaning jami mashg'ulotlar soni saqlandi", ru: "Общее количество занятий для студента сохранено", en: "The student's total number of lessons was saved" },
    "users.total_scope": { uz: "Qaysi talabalar uchun?", ru: "Для каких студентов?", en: "For which students?" },
    "users.total_title": { uz: "Jami amaliy mashg'ulotlar sonini o'zgartirish", ru: "Изменение общего количества практических занятий", en: "Change the total number of practical lessons" },
    "week.done_share": { uz: "{n}% bajarilgan", ru: "{n}% выполнено", en: "{n}% completed" },
    "week.remaining_note": { uz: "hali bajarilmagan", ru: "ещё не выполнено", en: "not completed yet" },
    "err.auth.password_need_digit": { uz: "Parolda kamida bitta raqam bo'lsin", ru: "Пароль должен содержать цифру", en: "The password must contain a digit" },
    "err.auth.password_need_lower": { uz: "Parolda kamida bitta kichik harf (a-z) bo'lsin", ru: "Пароль должен содержать строчную букву (a-z)", en: "The password must contain a lowercase letter (a-z)" },
    "err.auth.password_need_upper": { uz: "Parolda kamida bitta katta harf (A-Z) bo'lsin", ru: "Пароль должен содержать заглавную букву (A-Z)", en: "The password must contain an uppercase letter (A-Z)" },
  };

  const LANGS = { uz: "O'zbek", ru: "Русский", en: "English" };

  /* Xavfsiz storage yordamchilari: agar brauzer localStorage'ni bloklasa
     (maxfiy rejim, himoyalangan sozlamalar) ilova ishdan chiqmasligi uchun. */
  function lsGet(k) {
    try { return localStorage.getItem(k); } catch (e) { return null; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(k, v); } catch (e) {}
  }

  let current = lsGet("lang") || "uz";

  /* Tarjima kaliti. `params` berilsa, matndagi {nom} kabi joylar almashtiriladi:
     t("users.delete_confirm", { name: "Ali" }) -> "...Ali..." */
  function t(key, params) {
    const entry = DICT[key];
    if (!entry) return key;
    let s = entry[current] || entry.uz || key;
    if (params && typeof params === "object") {
      Object.keys(params).forEach((k) => {
        s = s.split("{" + k + "}").join(String(params[k]));
      });
    }
    return s;
  }

  function setLang(l) {
    if (DICT && l && LANGS[l]) {
      current = l;
      lsSet("lang", l);
      document.documentElement.lang = l;
      document.dispatchEvent(new CustomEvent("langchange"));
    }
  }

  // Oy nomlari (qisqa) — brauzerning uz-UZ lokali "M09" kabi g'alati nom berishi
  // mumkin, shuning uchun oy nomlari qo'lda beriladi (uz/ru/en).
  const MONTHS = {
    uz: ["yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek"],
    ru: ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
    en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  };

  function toDate(v) {
    if (!v) return null;
    const d = new Date(v.length === 10 ? v + "T00:00:00" : v.replace(" ", "T"));
    return isNaN(d) ? null : d;
  }

  function fmtDate(dateStr) {
    const d = toDate(dateStr);
    if (!d) return dateStr ? String(dateStr) : "—";
    const m = MONTHS[current] || MONTHS.uz;
    return d.getDate() + " " + m[d.getMonth()] + " " + d.getFullYear();
  }

  function fmtDateTime(dt) {
    const d = toDate(dt);
    if (!d) return dt ? String(dt) : "—";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return fmtDate(dt) + ", " + hh + ":" + mm;
  }

  /* BAND 23 — xato matni. `params` berilsa, matndagi {nom} joylari
     almashtiriladi: errorText("err.user.total_lessons_below_done", { done: 8 })
       -> "Jami darslar soni bajarilganlardan kam bo'lishi mumkin emas (bajarilgan: 8)".
     Noma'lum kod qaytariladi — lekin TEXNIK xato matni (Python traceback
     va h.k.) hech qachon foydalanuvchiga ko'rsatilmaydi. */
  function errorText(key, params) {
    if (!key) return t("err.generic");
    const k = key.startsWith("err.") || key.includes(".") ? key : "err." + key;
    let v = "";
    const direct = DICT["err." + key];
    if (direct) v = direct[current] || direct.uz || key;
    else {
      const entry = DICT[k];
      v = entry ? (entry[current] || entry.uz || k) : key;
    }
    if (params) {
      v = String(v).replace(/\{(\w+)\}/g, (m0, name) => {
        const val = params[name];
        return val !== undefined && val !== null ? String(val) : m0;
      });
    }
    return v;
  }

  // T2:M2 — bildirishnoma kod (title) -> qisqa sarlavha (foydalanuvchi tilida)
  function notifLabel(code) {
    if (!code) return "";
    const entry = DICT["notif.t." + code];
    if (entry) return entry[current] || entry.uz || code;
    // noma'lum kodli eski bildirishnomalar uchun kodni o'zi ko'rsatiladi
    return code;
  }

  // T2:M2 — bildirishnoma to'liq matni: i18n template + data, yo'q bo'lsa legacy body
  function notifText(n, data) {
    const code = n.title || "";
    const d = data || {};
    const entry = DICT["notif.m." + code];
    if (entry) {
      let v = entry[current] || entry.uz || code;
      v = v.replace(/\{(\w+)\}/g, (_, k) => {
        const val = d[k];
        return val !== undefined && val !== null ? String(val) : "";
      });
      if (code === "lesson.cancelled" && d.cancel_reason) {
        v += " · " + t("notif.reason") + ": " + d.cancel_reason;
      }
      return v;
    }
    // Legacy / kontent-bildirishnomalar (admin, msg.new, eski satrlar)
    return n.body || n.title || "";
  }

  // til almashtirish tugmalariga bosilganda barcha [data-i18n] elementlar yangilanadi
  document.addEventListener("langchange", () => {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      const text = t(key);
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") el.placeholder = text;
      else el.textContent = text;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(el.getAttribute("data-i18n-placeholder"));
    });
  });

  return { t, setLang, getLang: () => current, LANGS, fmtDate, fmtDateTime, errorText,
    notifLabel, notifText,
    monthShort: (mi) => (MONTHS[current] || MONTHS.uz)[((mi % 12) + 12) % 12] };
})();