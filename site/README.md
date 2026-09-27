site: GitHub Pages uchun statik landing sahifa

Bu papka GitHub Pages ga joylashtiriladigan mustaqil, tashqi faylsiz
statik sahifa (`index.html`, ~8.5 KB).

Nima uchun alohida: platformaning o'zi — `server.py` (Python `http.server`
+ `sqlite3`). Frontend `/api/*` so'rovlarini shu serverga yuboradi
(`web/js/api.js:12`), GitHub Pages esa faqat statik fayllarni beradi va
Python'ni ishga tushirmaydi. Shuning uchun github.io da faqat
ko'rsatish/landing sahifasi yashaydi, kirish esa haqiqiy serverda
bo'lishi kerak.

Yaytirish (bepul, asosiy repo maxfiy qoladi):

    git init site-repo && cd site-repo
    cp -r <bu-repo>/site/. .
    touch .nojekyll
    git add -A && git commit -m "site: landing sahifa"
    gh repo create AvtomaktabSite --public --source=. --push
    gh api -X POST repos/<user>/AvtomaktabSite/pages \
      -f "source[branch]=main" -f "source[path]=/"

Manzil: `https://<user>.github.io/AvtomaktabSite/`

Asosiy repo (`AvtomaktabPlatforma`) maxfiy qoladi — undan faqat bitta
statik fayl ochiq repoga ko'chiriladi.
