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
    "nav.dashboard": { uz: "Dashboard", ru: "Дашборд", en: "Dashboard" },
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
    "nav.calendar": { uz: "Kalendar", ru: "Календарь", en: "Calendar" },
    "nav.backup": { uz: "Backup", ru: "Резервная копия", en: "Backup" },
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
    "common.filter": { uz: "Filter", ru: "Фильтр", en: "Filter" },
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
    "err.auth.password_short": { uz: "Parol kamida 5 belgi bo'lsin", ru: "Пароль должен быть не менее 5 символов", en: "Password must be at least 5 characters" },
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
    "err.user.bulk_role": { uz: "Bulk yaratish faqat talabalar uchun", ru: "Массовое создание только для учеников", en: "Bulk creation is for students only" },
    "err.user.bulk_count": { uz: "Soni 1–1000 orasida bo'lsin", ru: "Количество от 1 до 1000", en: "Count must be 1–1000" },
    "err.user.not_found": { uz: "Foydalanuvchi topilmadi", ru: "Пользователь не найден", en: "User not found" },
    "err.user.cannot_modify_admin": { uz: "Admin hisobini o'zgartirish mumkin emas", ru: "Нельзя изменять учётную запись админа", en: "Cannot modify admin account" },
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
    "err.backup.disabled": { uz: "Backup o'chirilgan", ru: "Резервное копирование отключено", en: "Backup is disabled" },
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
    "lesson.pickup_edit": { uz: "Qayerdan olib ketilsin?", ru: "Откуда забрать?", en: "Where should you be picked up?" },
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
    "student.bulk": { uz: "Bulk yaratish", ru: "Массовое создание", en: "Bulk create" },
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

    // ---- audit
    "audit.title": { uz: "Audit jurnali", ru: "Журнал аудита", en: "Audit log" },

    // ---- backup
    "backup.title": { uz: "Backup", ru: "Резервная копия", en: "Backup" },
    "backup.create": { uz: "Backup yaratish", ru: "Создать резервную копию", en: "Create backup" },
    "backup.created": { uz: "Backup yaratildi", ru: "Резервная копия создана", en: "Backup created" },

    // ---- settings
    "settings.title": { uz: "Sozlamalar", ru: "Настройки", en: "Settings" },
    "settings.allow_requests": { uz: "Talabalar mashg'ulot so'rashi mumkin", ru: "Ученики могут запрашивать занятия", en: "Students may request lessons" },

    // ---- profile
    "profile.title": { uz: "Profilim", ru: "Мой профиль", en: "My profile" },
    "profile.edit": { uz: "Profilni tahrirlash", ru: "Редактировать профиль", en: "Edit profile" },
    "profile.credentials": { uz: "Hisob", ru: "Аккаунт", en: "Account" },
    "profile.change_pass": { uz: "Parolni o'zgartirish", ru: "Сменить пароль", en: "Change password" },
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

  function errorText(key) {
    if (!key) return t("err.generic");
    const k = key.startsWith("err.") || key.includes(".") ? key : "err." + key;
    const direct = DICT["err." + key];
    if (direct) return direct[current] || direct.uz || key;
    const entry = DICT[k];
    if (entry) return entry[current] || entry.uz || k;
    return key;
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