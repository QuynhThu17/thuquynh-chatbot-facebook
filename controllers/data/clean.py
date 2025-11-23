import re
import uuid
from unidecode import unidecode


# Fix mấy ngoặc nhọn với đồ trong string
def clean_special_characters(text):
    text = str(text)
    # Định nghĩa các ký tự đặc biệt cần escape
    special_characters = {"{": "(", "}": ")", '"': "'"}

    # Thay thế từng ký tự đặc biệt trong chuỗi đầu vào
    for char, escape_char in special_characters.items():
        text = text.replace(char, escape_char)

    return text


def convert_string_to_id(s):
    # Chuyển về chữ thường
    s = s.lower()
    # Bỏ dấu tiếng Việt
    s = unidecode(s)
    # Thay thế khoảng trắng bằng dấu '-'
    s = re.sub(r'\s+', '-', s)

    new_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, s))

    return new_id

