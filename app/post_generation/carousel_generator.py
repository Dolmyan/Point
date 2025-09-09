import concurrent.futures
import logging
import os
import uuid
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple

import multiprocessing
import io
import gc

from config import AI_TOKEN
from database import BotDB

db = BotDB('point.db')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(
        api_key=AI_TOKEN  # вставь свой ключ
)

# ---------- Настройки оптимизации ----------
# Включить "лёгкий режим" (уменьшает размеры шаблонов)
# По умолчанию включён; для отключения установите env POINT_LIGHTWEIGHT=0
LIGHTWEIGHT_MODE = os.environ.get("POINT_LIGHTWEIGHT", "1") != "0"
# Целевой размер (вертикальный ориентир). Длинная сторона не будет превышать max(LIGHTWEIGHT_TARGET).
LIGHTWEIGHT_TARGET = (1080, 1350)
LIGHTWEIGHT_MAX_SIDE = max(LIGHTWEIGHT_TARGET)

# Максимальное число процессов для multiprocessing (min 1)
MAX_WORKERS = max(1, min(4, (os.cpu_count() or 1)))

# Кеш шрифтов (font_path, size) -> ImageFont
FONT_CACHE = {}

def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, int(size))
    f = FONT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(path, int(size))
        FONT_CACHE[key] = f
    return f


def scale_config_for_lightweight(config: dict) -> dict:
    """Сжимает конфиг пропорционально, чтобы ни одна сторона не превышала LIGHTWEIGHT_MAX_SIDE.
    Сохраняет ориентацию (вертикальную/горизонтальную)."""
    if not LIGHTWEIGHT_MODE:
        return config
    w, h = config.get("size", (0, 0))
    long_side = max(w, h)
    if long_side <= LIGHTWEIGHT_MAX_SIDE:
        return config
    s = LIGHTWEIGHT_MAX_SIDE / float(long_side)
    new = dict(config)
    new["size"] = (max(1, int(round(w * s))), max(1, int(round(h * s))))
    # Масштабируем числовые параметры кроме коэффициентов (title_line/body_line)
    for key in ("padding_x", "top_y", "bottom_y", "title_size", "body_size",
                "title_body_gap", "sig_size"):
        if key in config and isinstance(config[key], (int, float)):
            new[key] = max(1, int(round(config[key] * s)))
    # tracking_px — маленькое значение, не масштабируем сильно, но округлим
    if "tracking_px" in config:
        new["tracking_px"] = int(round(config["tracking_px"]))
    # sig_offset — tuple
    if "sig_offset" in config and isinstance(config["sig_offset"], (list, tuple)):
        new["sig_offset"] = (int(round(config["sig_offset"][0] * s)),
                             int(round(config["sig_offset"][1] * s)))
    return new

# --- Текстовые слайды ---
def generate_carousel_text(prompt: str, style):
    logger.info(f"Генерируем текст для промпта")

    response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "user",
                    "content": f"""
    Сделай 6 коротких блоков текста для Instagram-карусели. Моя деятельность: {prompt}.

    === НАЧАЛО БЛОКА СТИЛЯ (используй ЕГО ДОСЛОВНО) ===
    {style}
    === КОНЕЦ БЛОКА СТИЛЯ ===

    Требования:
    1. Каждый блок состоит из цепляющего заголовка (1–2 предложения), затем символ-разделитель "::", затем основной текст (2–3 предложения).
    2. Только текст. Без подписей "Слайд", "Текст", "Изображение", без скобок, без кавычек.  
    3. Не нумеруй. Заголовки нельзя начинать с цифр или «1.» и т. п.  
    4. Каждый блок — отдельная строка. Ровно 6 строк (6 блоков).  
    5. Стиль строго как в блоке «НАЧАЛО БЛОКА СТИЛЯ»: сохраняй пунктуацию, эмодзи, длину предложений, ритм, оформление.  
    6. Если стиль пуст или содержит «[без подписи]» — используй нейтральный экспертный тон.  
    7. Никаких пояснений, комментариев или альтернативных вариантов. Выведи только готовый текст.
    8. Строгое правило. Не используй эмоджи,смайлики, не используй кавычки, особенно для заголовков

    Выведи результат: ровно 6 строк — 6 блоков для карусели.
    """
                }
            ]
    )

    text = response.choices[0].message.content


    # Пример: пока фиксированный текст, можно включить GPT позже
    #     text = '''Стань репетитором супергероем! :: Я эксперт по математике и информатике, который готов передать вам знания об успешном преподавании и заработке.
    # Заработай 100 тыс. рублей в месяц на репетиторстве :: Я покажу вам, как выйти на стабильный доход от 100 тыс. рублей в месяц, преподавая математику и информатику.
    # Вырасти как преподаватель :: Этот контент создан для вас, учитель, который стремится к совершенству и готов посвятить себя обучению других.
    # Стратегии и схемы для успешного преподавания :: Узнайте, как эффективно преподавать, чтобы ученики были довольны и возвращались.
    # Переходите от теории к практике :: Я научу вас использовать знания на практике, чтобы мотивировать и вдохновлять учеников.
    # Давайте начнем приключение вместе :: Готов поделиться опытом и знаниями, чтобы помочь вам стать успешным репетитором.'''
    logger.info(f"Сгенерированный текст {text}")
    slides = [line.strip() for line in text.split("\n") if line.strip()]
    if len(slides) != 6:
        slides = slides[:6]
        while len(slides) < 6:
            slides.append("Заголовок::...")
    return slides


BASE_DIR = os.path.dirname(__file__)
POINT_TEMPLATES_DIR = os.path.join(BASE_DIR, "point_templates")

INTER_REGULAR = os.path.join(BASE_DIR, "Inter-Regular.otf")
INTER_BOLDITALIC = os.path.join(BASE_DIR, "Inter-BoldItalic.otf")
INTER_LIGHT = os.path.join(BASE_DIR, "Inter-Light.otf")

if not os.path.exists(INTER_REGULAR) or not os.path.exists(INTER_LIGHT):
    raise FileNotFoundError("Файлы шрифтов Inter-Regular.otf и Inter-Light.otf должны лежать рядом со скриптом.")


# ----- Утилиты для шаблонов и размеров -----
def find_template_folders(root_dir):
    folders = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        pngs = [f for f in filenames if f.lower().endswith(".png")]
        if pngs:
            folders.append(dirpath)
    folders.sort()
    return folders


def load_sorted_pngs_from_folder(folder: str) -> List[str]:
    pngs = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
    pngs.sort()
    return [os.path.join(folder, p) for p in pngs]


def default_slide_colors():
    # по умолчанию: 1,2,4,5 -> черный; 3,6 -> белый
    return [
        (0, 0, 0),  # slide 1
        (0, 0, 0),  # slide 2
        (255, 255, 255),  # slide 3
        (0, 0, 0),  # slide 4
        (0, 0, 0),  # slide 5
        (255, 255, 255),  # slide 6
    ]


def setup_template_1():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 140,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 170,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-60, 130),
        "title_font": INTER_BOLDITALIC,
        "body_font": INTER_LIGHT,
        "title_align": "center",
        "body_align": "center",
        "slide_colors": default_slide_colors(),
    }


def setup_template_2():
    return {
        "size": (2560, 2160),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 140,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 170,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-100, 80),
        "title_font": INTER_BOLDITALIC,
        "body_font": INTER_LIGHT,
        "title_align": "center",
        "body_align": "center",
        "slide_colors": default_slide_colors(),
    }


def setup_template_3():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 140,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 170,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-60, 130),
        "title_font": INTER_BOLDITALIC,
        "body_font": INTER_LIGHT,
        "title_align": "center",
        "body_align": "center",
        "slide_colors": [
            (0, 0, 0),  # slide 1
            (0, 0, 0),  # slide 2
            (0, 0, 0),  # slide 3 → черный
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 6 → черный
        ],
    }


def setup_template_4():
    return {
        "size": (2560, 2160),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 140,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 170,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-100, 80),
        "title_font": INTER_BOLDITALIC,
        "body_font": INTER_LIGHT,
        "title_align": "center",
        "body_align": "center",
        "slide_colors": [
            (0, 0, 0),  # slide 1
            (0, 0, 0),  # slide 2
            (0, 0, 0),  # slide 3 → черный
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 6 → черный
        ],
    }


def setup_template_5():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 140,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 400,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (5, 130),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 1
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 1
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ],
    }


def setup_template_6():
    return {
        "size": (2560, 2160),
        "padding_x": 200,
        "top_y": 300,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 180,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-1, 100),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 1
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 1
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ], }


def setup_template_7():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 350,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (5, 130),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (255, 255, 255),  # slide 3
            (255, 255, 255),  # slide 3
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ],
    }


def setup_template_8():
    return {
        "size": (2560, 2160),
        "padding_x": 200,
        "top_y": 300,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 180,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-1, 100),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (255, 255, 255),  # slide 3
            (255, 255, 255),  # slide 3
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ], }


def setup_template_9():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 350,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (5, 130),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ],
    }


def setup_template_10():
    return {
        "size": (2560, 2160),
        "padding_x": 350,
        "top_y": 300,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 180,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-1, 100),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (255, 255, 255),  # slide 3
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (255, 255, 255),  # slide 6
        ], }


def setup_template_11():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 500,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 350,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (5, 130),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 5
        ],
    }


def setup_template_12():
    return {
        "size": (2560, 2160),
        "padding_x": 350,
        "top_y": 300,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 180,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-1, 100),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 5
        ],
    }


def setup_template_13():
    return {
        "size": (2160, 2700),
        "padding_x": 200,
        "top_y": 550,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 350,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (5, 130),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (256, 256, 256),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 5
        ],
    }


def setup_template_14():
    return {
        "size": (2560, 2160),
        "padding_x": 350,
        "top_y": 300,
        "bottom_y": 1850,
        "title_size": 150,
        "body_size": 120,
        "title_line": 0.95,
        "body_line": 0.97,
        "title_body_gap": 180,
        "tracking_px": -4,
        "sig_size": 70,
        "sig_offset": (-1, 100),
        "title_font": INTER_REGULAR,
        "body_font": INTER_LIGHT,
        "title_align": "left",
        "body_align": "left",
        "slide_colors": [
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 4
            (256, 256, 256),  # slide 4
            (0, 0, 0),  # slide 4
            (0, 0, 0),  # slide 5
            (0, 0, 0),  # slide 5
        ],
    }


TEMPLATE_SETUP_FUNCS = {
    1: setup_template_1,
    2: setup_template_2,
    3: setup_template_3,
    4: setup_template_4,
    5: setup_template_5,
    6: setup_template_6,
    7: setup_template_7,
    8: setup_template_8,
    9: setup_template_9,
    10: setup_template_10,
    11: setup_template_11,
    12: setup_template_12,
    13: setup_template_13,
    14: setup_template_14,
}


# -----------------------------
# Текстовые хелперы
# -----------------------------
def wrap_paragraph(draw: ImageDraw.ImageDraw, paragraph: str, font: ImageFont.FreeTypeFont, max_w: int,
                   tracking_px: int) -> List[str]:
    words = paragraph.split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + " " + w
        total_width = draw.textlength(test, font=font) + max(0, (len(test) - 1)) * tracking_px
        if total_width <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def rewrap_and_measure(draw, title_raw: str, body_raw: str, t_font: ImageFont.FreeTypeFont,
                       b_font: ImageFont.FreeTypeFont,
                       available_width: int, config: dict):
    tracking = config["tracking_px"]
    t_lines = wrap_paragraph(draw, title_raw.strip(), t_font, available_width, tracking)
    b_paragraphs = []
    for para in body_raw.split("\n"):
        para = para.strip()
        if para:
            b_paragraphs.append(wrap_paragraph(draw, para, b_font, available_width, tracking))

    title_line_px = max(1, int(round(t_font.size * config["title_line"])))
    body_line_px = max(1, int(round(b_font.size * config["body_line"])))
    title_body_gap = config.get("title_body_gap", max(36, int(available_width * 0.02)))

    t_h = len(t_lines) * title_line_px
    b_h = sum(len(p) * body_line_px for p in b_paragraphs)
    total_h = t_h + title_body_gap + b_h
    return t_lines, b_paragraphs, total_h, title_line_px, body_line_px, title_body_gap


def draw_text_with_tracking(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.FreeTypeFont,
                            fill: Tuple[int, int, int], tracking_px: int):
    cur_x = x
    for ch in text:
        draw.text((cur_x, y), ch, font=font, fill=fill)
        adv = draw.textlength(ch, font=font)
        cur_x += adv + tracking_px


# -----------------------------
# Рендер одного слайда (полный)
# -----------------------------
def make_image_from_bg(slide_text: str, bg_path: str, config: dict, sig: str = "", slide_index: int = 1) -> Image.Image:
    if not os.path.exists(bg_path):
        raise FileNotFoundError(f"Фон не найден: {bg_path}")

    width, height = config["size"]
    bg = Image.open(bg_path).convert("RGBA")
    if bg.size != (width, height):
        bg = bg.resize((width, height), Image.LANCZOS)

    txt_layer = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Fonts
    title_font = ImageFont.truetype(INTER_REGULAR, config["title_size"])
    body_font = ImageFont.truetype(INTER_LIGHT, config["body_size"])
    sig_font = ImageFont.truetype(INTER_LIGHT, config["sig_size"])

    # Parse text
    if "::" in slide_text:
        title_raw, body_raw = slide_text.split("::", 1)
    else:
        parts = slide_text.split("\n", 1)
        title_raw = parts[0].strip() if parts else ""
        body_raw = parts[1].strip() if len(parts) > 1 else ""

    padding_x = config["padding_x"]
    available_width = width - 2 * padding_x
    top_y = config["top_y"]
    bottom_y = config["bottom_y"]
    available_height = bottom_y - top_y - int(height * 0.02)

    cur_title_size = title_font.size
    cur_body_size = body_font.size

    # переиспользуем get_font, но для изменения размера требуется новый объект — поэтому будем запрашивать вновь
    t_font = get_font(INTER_REGULAR, cur_title_size)
    b_font = get_font(INTER_LIGHT, cur_body_size)

    t_lines, b_paragraphs, total_h, title_line_px, body_line_px, title_body_gap = rewrap_and_measure(
            draw, title_raw, body_raw, t_font, b_font, available_width, config
    )

    MIN_TITLE = max(22, int(round(config["title_size"] * 0.3)))
    MIN_BODY = max(12, int(round(config["body_size"] * 0.3)))

    while total_h > available_height and cur_title_size > MIN_TITLE:
        cur_title_size -= max(2, int(cur_title_size * 0.03))
        cur_body_size = max(MIN_BODY, cur_body_size - max(1, int(cur_body_size * 0.02)))
        t_font = ImageFont.truetype(INTER_REGULAR, cur_title_size)
        b_font = ImageFont.truetype(INTER_LIGHT, cur_body_size)
        t_lines, b_paragraphs, total_h, title_line_px, body_line_px, title_body_gap = rewrap_and_measure(
                draw, title_raw, body_raw, t_font, b_font, available_width, config
        )

    text_block_top = max(0, top_y)
    y_start = int(text_block_top + (available_height - total_h) / 2)
    if y_start < text_block_top:
        y_start = text_block_top + 6

    slide_colors = config.get("slide_colors", default_slide_colors())
    if not isinstance(slide_colors, (list, tuple)) or len(slide_colors) < slide_index:
        # если цветов меньше, чем номер слайда, используем fallback
        sig_color = (30, 30, 30)
    else:
        sig_color = slide_colors[slide_index - 1]

    if not isinstance(slide_colors, (list, tuple)) or len(slide_colors) < 6:
        raise ValueError("config['slide_colors'] должен быть список/tuple из 6 элементов (RGB кортежей).")
    text_color = slide_colors[slide_index - 1]

    tracking_px = config.get("tracking_px", -4)

    # --- Title ---
    y = y_start
    title_align = config.get("title_align", "left")
    for line in t_lines:
        glyphs_width = draw.textlength(line, font=t_font) + tracking_px * (len(line) - 1)

        if title_align == "center":
            # центрируем внутри области от padding_x до width - padding_x
            x = padding_x + (available_width - glyphs_width) // 2
        elif title_align == "right":
            # правый край внутри доступной области
            x = padding_x + available_width - glyphs_width
        else:  # left
            x = padding_x

        draw_text_with_tracking(draw, int(x), y, line, t_font, text_color, tracking_px)
        y += title_line_px

    y += title_body_gap

    # --- Body ---
    body_align = config.get("body_align", "left")
    for para_lines in b_paragraphs:
        for line in para_lines:
            glyphs_width = draw.textlength(line, font=b_font) + tracking_px * (len(line) - 1)

            if body_align == "center":
                x = padding_x + (available_width - glyphs_width) // 2
            elif body_align == "right":
                x = padding_x + available_width - glyphs_width
            else:  # left
                x = padding_x

            draw_text_with_tracking(draw, int(x), y, line, b_font, text_color, tracking_px)
            y += body_line_px

    # --- Signature ---
    if sig:
        sig_offset_x, sig_offset_y = config.get("sig_offset", (80, 40))
        sig_x = padding_x + sig_offset_x
        sig_y = sig_offset_y  # или можно добавить padding_y при необходимости

        # берем цвет подписи из slide_colors по текущему слайду
        slide_colors = config.get("slide_colors", default_slide_colors())
        if isinstance(slide_colors, (list, tuple)) and len(slide_colors) >= slide_index:
            sig_color = slide_colors[slide_index - 1]
        else:
            sig_color = (30, 30, 30)  # fallback

        draw.text((sig_x, sig_y), sig, font=sig_font, fill=sig_color)
    out = Image.alpha_composite(bg, txt_layer).convert("RGB")
    try:
        del draw
        del txt_layer
        bg.close()
    except Exception:
        pass
    return out


# -----------------------------
import io


# ---------- multiprocessing worker (top-level, чтобы можно было форкать) ----------
def _worker_generate_slide_bytes(args):
    """
    args = (slide_text, bg_path, config, sig, slide_index)
    Возвращает байты JPEG оптимизированного изображения или None при ошибке.
    """
    slide_text, bg_path, config, sig, slide_index = args
    try:
        img = make_image_from_bg(slide_text, bg_path, config, sig=sig, slide_index=slide_index)
        bio = io.BytesIO()
        # JPEG сжатие — значительно меньше памяти и веса, чем PNG
        img.save(bio, format="JPEG", optimize=True, quality=85)
        bio.seek(0)
        data = bio.read()
        bio.close()
        img.close()
        del img
        gc.collect()
        return data
    except Exception as e:
        logger.exception("Ошибка в worker при генерации слайда: %s", e)
        return None


# -----------------------------
from aiogram.types import BufferedInputFile


def generate_carousel(slides_or_prompt, template_index: int, sig: str = "", style=None) -> List[BufferedInputFile]:
    # slides_or_prompt может быть либо список из 6 строк, либо строкой prompt
    if isinstance(slides_or_prompt, str):
        slides = generate_carousel_text(slides_or_prompt, style)
    else:
        slides = slides_or_prompt

    if not isinstance(slides, (list, tuple)):
        raise RuntimeError("slides должен быть списком строк или строкой-проомптом.")
    if len(slides) < 6:
        while len(slides) < 6:
            slides.append("Заголовок::...")
    slides = slides[:6]

    if template_index not in TEMPLATE_SETUP_FUNCS:
        raise ValueError(f"Нет настроек для template_index={template_index}")

    # Получаем конфиг (без папки)
    config = TEMPLATE_SETUP_FUNCS[template_index]()
    # масштабируем конфиг под лёгкий режим (если включён)
    scaled_config = scale_config_for_lightweight(config)

    # Находим все папки и выбираем N-ю (1-based)
    folders = find_template_folders(POINT_TEMPLATES_DIR)
    if not folders:
        raise RuntimeError(f"Нет папок с png в {POINT_TEMPLATES_DIR}")
    if template_index < 1 or template_index > len(folders):
        raise ValueError(
            f"template_index={template_index} больше числа найденных папок ({len(folders)}). "
            f"Передайте корректный номер папки (1..{len(folders)})."
        )

    folder = folders[template_index - 1]  # выбираем N-ю папку
    logger.info(f"Используется шаблон {template_index} (настройки) и папка #{template_index}: {folder}")
    print(f"✅ Использован шаблон №{template_index} из папки: {folder}")

    pngs = load_sorted_pngs_from_folder(folder)
    if not pngs:
        raise RuntimeError(f"В шаблоне {folder} нет png-файлов.")
    if len(pngs) < 6:
        pngs = (pngs * (6 // len(pngs) + 1))[:6]
    else:
        pngs = pngs[:6]

    # Подготовим аргументы для воркеров
    args_list = []
    for i in range(6):
        slide_index = i + 1
        text = slides[i]
        bg = pngs[i]
        args_list.append((text, bg, scaled_config, sig, slide_index))

    data_results = [None] * 6

    # Попытка использовать ProcessPoolExecutor с mp_context=spawn (устойчивее в daemon окружениях)
    if MAX_WORKERS > 1:
        try:
            workers = min(MAX_WORKERS, 6)
            logger.info(f"Запускаем ProcessPoolExecutor из {workers} воркеров для генерации слайдов")
            mp_ctx = multiprocessing.get_context("spawn")
            with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=mp_ctx) as executor:
                # executor.map вернёт в том же порядке, в котором передали args_list
                futures = list(executor.map(_worker_generate_slide_bytes, args_list))
            data_results = futures
            if any(r is None for r in data_results):
                logger.warning("В пуле некоторые слайды не сгенерировались, пробуем последовательную генерацию (fallback).")
                data_results = [None] * 6
        except Exception as e:
            logger.exception("ProcessPoolExecutor упал: %s. Будем генерировать последовательно.", e)
            data_results = [None] * 6

    # Если пул не сработал или отключён — последовательно вызвать воркер-функцию (локально)
    if any(r is None for r in data_results):
        for idx, args in enumerate(args_list):
            logger.info("Последовательная генерация слайда %d", idx + 1)
            data = _worker_generate_slide_bytes(args)
            if data is None:
                raise RuntimeError(f"Ошибка генерации слайда {idx + 1}")
            data_results[idx] = data

    # Сформируем BufferedInputFile-список
    files = []
    for i, data in enumerate(data_results):
        if data is None:
            raise RuntimeError(f"Слайд {i + 1} не сгенерирован")
        filename = f"slide_{i+1}.jpg"
        files.append(BufferedInputFile(data, filename=filename))
        logger.info(f"Создан слайд {i+1}")

    gc.collect()
    return files

