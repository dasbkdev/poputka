import re
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from datetime import datetime
import dateutil.parser as dtparser

# --- OCR универсальный ---
def ocr_text_from_any(path: str) -> str:
    text = ""
    if path.lower().endswith(".pdf"):
        pages = convert_from_path(path, dpi=200)
        for p in pages:
            text += pytesseract.image_to_string(p, lang="rus+eng+kaz+kir+osd") + "\n"
    else:
        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang="rus+eng+kaz+kir+osd")
    return text


# --- Извлечение суммы ---
def extract_amount(text: str):
    """
    Достаём сумму даже если: '- 20,00 c', '20.00 сом', '20,05 KGS'.
    Игнорируем длинные числа (счета, ID).
    """
    t = re.sub(r'\s+', ' ', text).lower()
    CUR_RE = r'(?:сом|kgs|кгс|с|s)'
    MONEY_RE = re.compile(r'(?<!\d)(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:' + CUR_RE + r')?', re.IGNORECASE)

    candidates = []
    for m in MONEY_RE.finditer(t):
        raw = m.group(1).replace(',', '.')
        try:
            val = float(raw)
        except:
            continue
        if not (0.01 <= val <= 100000):
            continue

        start, end = m.start(), m.end()
        window = t[max(0, start - 30): min(len(t), end + 30)]

        score = 0
        if any(k in window for k in ['итого', 'итог', 'сумма', 'платеж', 'оплата', 'перевод']):
            score += 2
        if re.search(CUR_RE, window):
            score += 1
        if '-' in t[max(0, start - 3): start + 1]:
            score += 1

        candidates.append((score, val))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return round(candidates[0][1], 2)


# --- Извлечение даты/времени ---
DATE_REGEXES = [
    r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}[,\s]+\d{1,2}:\d{2}\b',
    r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b',
]

def extract_datetime(text: str):
    t = re.sub(r'\s+', ' ', text)
    for pat in DATE_REGEXES:
        m = re.search(pat, t)
        if m:
            s = m.group(0)
            try:
                return dtparser.parse(s, dayfirst=True, fuzzy=True)
            except:
                pass
    try:
        return dtparser.parse(t, dayfirst=True, fuzzy=True)
    except:
        return None


# --- Извлечение номера телефона (последние 9 цифр) ---
def extract_phone(text: str):
    m = re.search(r'(\d{9})', text)
    return m.group(1) if m else None
