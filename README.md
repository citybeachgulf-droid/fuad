# تثمين عمان - الصفحة الرئيسية (Flask + Bootstrap 5 RTL)

## التشغيل

- خيار آمن (ينصح به إذا كانت بيئة النظام تمنع التثبيت العام):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

- خيار سريع (إذا تعذّر إنشاء بيئة افتراضية):
```bash
pip3 install --break-system-packages -r requirements.txt
python3 app.py
```

- الواجهة: `http://localhost:5000`
- Wireframe: `http://localhost:5000/wireframe`

## الملفات
- `templates/base.html`: قالب أساسي + Bootstrap RTL + AOS + Animate.css + Bootstrap Icons
- `templates/index.html`: الصفحة الرئيسية (CTA، الأخبار، المميزات، الشهادات + نموذج، تواصل)
- `templates/wireframe.html`: Wireframe منخفض الدقة
- `static/css/main.css`: الألوان والهوية والتأثيرات
- `static/js/main.js`: سلوكيات (إرسال الشهادات، اختيار نوع العقار، تحسين تفاعل الأزرار)
- `static/mockups/homepage-wireframe.svg`: Wireframe SVG قابل للتعديل (يمكن استيراده في Figma/Illustrator)
- `static/mockups/homepage-mock.svg`: Mockup عالي الدقة (SVG قابل للتصدير PNG)

## ملاحظات للمطورين (أنيميشن وتفاعلات)
- التمرير: استخدمنا AOS عبر `data-aos` (fade-up, fade-left, zoom-in). التهيئة في `base.html` بمدة 700ms و`once: true`.
- CTA: زر "ابدأ التثمين الآن" يحوي `animate__pulse animate__infinite` مع تأثير hover (رفع بسيط وظل).
- البطاقات: صنف `.card-hover` يرفع الظل ويترجم العنصر للأعلى قليلًا عند hover.
- المميزات: Carousel من Bootstrap. عنصر `.feature-icon` يتلوّن ويكبر عند hover.
- الشهادات: Carousel + نموذج إرسال. عند الإرسال يظهر سبينر ويستبدل النص بـ "تم الإرسال ✓" ثم يعود للحالة الأصلية.
- الأيقونات: Bootstrap Icons مستخدمة في الأقسام.

## RTL والتجاوب
- الاتجاه RTL مفعّل عالميًا (`<html dir="rtl">`) مع Bootstrap RTL.
- التخطيطات مبنية على Grid من Bootstrap ومختبرة من موبايل إلى ديسكتوب.

## تخصيص سريع
- يمكن تعديل ألوان الهوية في `static/css/main.css` داخل `:root`:
  - `--brand-dark` (الأزرق الداكن)
  - `--brand-accent` (الأزرق البارز)
- ربط زر "ابدأ التثمين الآن" بواجهة التثمين الفعلية أو نموذج متعدد الخطوات لاحقًا.