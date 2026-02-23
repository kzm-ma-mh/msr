# 📤 راهنمای آپلود به Google Colab

## قدم ۱: باز کردن Colab

1. برو به [Google Colab](https://colab.research.google.com/)
2. یک Notebook جدید بساز
3. از منوی Runtime → Change runtime type → GPU انتخاب کن

## قدم ۲: آپلود دیتاست

1. پنل سمت چپ → آیکون 📁 (Files)
2. کلیک روی آیکون آپلود
3. فایل `datasets.zip` رو انتخاب کن
4. صبر کن تا آپلود کامل بشه

## قدم ۳: اجرای کد

کد `colab_notebook/finetune_qwen.py` رو در ۵ سل جدا کپی کن و اجرا کن.

## قدم ۴: دانلود مدل

بعد از اتمام:
1. پنل سمت چپ → Files
2. روی `my_finetuned_model.gguf` راست کلیک
3. Download

## ⚠️ نکات مهم

- Colab رایگان: حدود ۱۲ ساعت محدودیت
- GPU T4: حدود ۱۵GB VRAM
- اگه disconnect شد، از فاز ۳ به بعد رو دوباره اجرا کن