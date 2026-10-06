# VIP.BOT · Glass Edition

بوت تداول XAUUSD احترافي يعتمد **الشموع اليابانية** كمحرك أساسي + لوحة تحكم زجاجية شفافة.

## ✨ المميزات

- 🕯️ **كشف 25+ نمط شمعة يابانية** (مطرقة، ابتلاع، نجمة الصباح/المساء، الجنود البيض، الغربان السود...)
- 📊 لوحة تحكم **Glassmorphism** شفافة تعرض:
  - سعر XAUUSD الحي
  - الصفقات المفتوحة والمغلقة
  - سبب كل صفقة والأنماط المكتشفة
- ⚡ سكالبينج عدواني (حتى 25 صفقة/يوم) بشروط **غير صارمة**
- 🛡️ إدارة مخاطر ذكية
- 📱 إشعارات تليجرام عربية جميلة
- 🚀 جاهز للنشر على **Render** بنقرة واحدة

## 🔑 ضبط التليجرام (بدون متغيرات بيئة)

افتح الملف `config/settings.py` وضع بياناتك مباشرة:

```python
TELEGRAM_BOT_TOKEN = "123456789:ABCdef..."
TELEGRAM_CHANNEL_ID = "@your_channel"   # أو -100xxxxxxxxxx
TELEGRAM_ADMIN_ID = "123456789"
```

## 🚀 التشغيل المحلي

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

ثم افتح: http://localhost:10000

## ☁️ النشر على Render

1. ارفع المستودع على GitHub
2. في Render → New → Web Service
3. اربط المستودع
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python app.py`
6. اضغط Deploy

Render سيستخدم متغير `PORT` تلقائياً.

## 📁 الهيكل

```
VIP.BOT/
├── app.py                 # السيرفر + محرك البوت
├── config/settings.py     # الإعدادات + توكن التليجرام
├── modules/
│   ├── data_fetcher.py
│   ├── pattern_detector.py   # الشموع اليابانية
│   └── technical_analyzer.py
├── strategies/scalping_strategy.py
├── utils/risk_manager.py
├── signals/telegram_sender.py
├── templates/dashboard.html  # الواجهة الزجاجية
└── requirements.txt
```

## ⚠️ تنويه

التداول ينطوي على مخاطر. هذا المشروع تعليمي. لا تستخدم أموالاً حقيقية دون اختبار كافٍ.

---
**VIP.BOT Glass Edition v2.0** · Powered by Japanese Candlesticks
