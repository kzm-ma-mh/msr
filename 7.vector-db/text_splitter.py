"""
تقسیم متن به قطعات کوچکتر (Chunking)
با حفظ ساختار معنایی
"""

import re
from config import Config


class TextSplitter:
    def __init__(self, chunk_size=None, chunk_overlap=None):
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

    def split_text(self, text):
        """
        تقسیم عمومی متن بر اساس پاراگراف و خطوط

        Returns:
            list[str]: لیست قطعات
        """
        if not text or len(text.strip()) < 20:
            return []

        if len(text) <= self.chunk_size:
            return [text.strip()]

        # اول سعی کن با جداکننده‌های طبیعی تقسیم کنی
        separators = ["\n\n", "\n", ". ", " "]

        for sep in separators:
            chunks = self._split_by_separator(text, sep)
            if chunks:
                return chunks

        # اگه هیچکدوم نشد → brute force
        return self._split_fixed(text)

    def split_code(self, text, language="python"):
        """
        تقسیم هوشمند کد با حفظ ساختار توابع و کلاس‌ها
        """
        if not text or len(text.strip()) < 20:
            return []

        if len(text) <= self.chunk_size:
            return [text.strip()]

        if language == "python":
            return self._split_python(text)

        # زبان‌های دیگه → تقسیم معمولی
        return self.split_text(text)

    def _split_python(self, text):
        """
        تقسیم کد پایتون بر اساس ساختار (class, def)
        """
        chunks = []
        lines = text.split("\n")
        current_chunk = []
        current_size = 0

        for line in lines:
            stripped = line.strip()
            line_len = len(line) + 1  # +1 for newline

            # اگه به تعریف تابع/کلاس جدید رسیدیم
            is_boundary = (
                stripped.startswith("def ") or
                stripped.startswith("async def ") or
                stripped.startswith("class ") or
                stripped.startswith("# ===") or
                stripped.startswith("# ---")
            )

            # اگه مرز جدیده و chunk فعلی بزرگ شده
            if is_boundary and current_size > self.chunk_size // 2:
                chunk_text = "\n".join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)

                # شروع chunk جدید با overlap
                overlap_lines = current_chunk[-3:] if len(current_chunk) > 3 else []
                current_chunk = overlap_lines + [line]
                current_size = sum(len(l) + 1 for l in current_chunk)
                continue

            current_chunk.append(line)
            current_size += line_len

            # اگه chunk خیلی بزرگ شد
            if current_size >= self.chunk_size:
                chunk_text = "\n".join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)

                overlap_lines = current_chunk[-3:] if len(current_chunk) > 3 else []
                current_chunk = overlap_lines
                current_size = sum(len(l) + 1 for l in current_chunk)

        # آخرین chunk
        if current_chunk:
            chunk_text = "\n".join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

        return chunks

    def _split_by_separator(self, text, separator):
        """تقسیم بر اساس جداکننده"""
        parts = text.split(separator)
        chunks = []
        current_chunk = ""

        for part in parts:
            test_chunk = current_chunk + separator + part if current_chunk else part

            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                if len(part) > self.chunk_size:
                    # قطعه خودش بزرگتره → بیشتر تقسیم کن
                    sub_chunks = self._split_fixed(part)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = part

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [c for c in chunks if c.strip()]

    def _split_fixed(self, text):
        """تقسیم ثابت با overlap"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    def split_markdown(self, text):
        """
        تقسیم markdown بر اساس هدرها
        """
        if not text or len(text.strip()) < 20:
            return []

        if len(text) <= self.chunk_size:
            return [text.strip()]

        # تقسیم بر اساس هدرهای markdown
        sections = re.split(r'\n(?=#{1,3} )', text)

        chunks = []
        current_chunk = ""

        for section in sections:
            if len(current_chunk) + len(section) <= self.chunk_size:
                current_chunk += "\n" + section if current_chunk else section
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                if len(section) > self.chunk_size:
                    sub_chunks = self.split_text(section)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = section

        if current_chunk:
            chunks.append(current_chunk.strip())

        return [c for c in chunks if c.strip()]