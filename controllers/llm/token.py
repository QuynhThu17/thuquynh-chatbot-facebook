import json
import os
from langchain_community.callbacks.infino_callback import get_num_tokens

from datetime import datetime
from configs import constant
from controllers.ultils import time


def calculate_tokens(text, model="gpt-4o-mini", name=""):
    print(f"======= {name} =======")
    try:
        if "gpt-" in model:
            num_tokens = get_num_tokens(text, "gpt-4o")
            print(f"Model: {model} - Tokens: {num_tokens}")
            return num_tokens
        else:
            num_tokens = get_num_tokens(text, model)
            print(f"Model: {model} - Tokens: {num_tokens}")
            return num_tokens

    except Exception as e:
        return 0


def count_token(user_id, cb, message):
    try:
        return user_id, cb.total_tokens, cb.prompt_tokens, cb.completion_tokens, cb.total_cost, message
    except Exception as e:
        print(f"Error in count_token: {e}")
    return


def save_tokens(user_id, action, token_input, token_output, model, time_request):
    try:
        now = datetime.now(time.vn_timezone)
        time_query = now.strftime("%d/%m/%Y %H:%M:%S")

        folder_path = os.path.join(constant.DATA_TOKEN, user_id)
        user_file = os.path.join(folder_path, "tokens.json")

        # Kiểm tra xem thư mục của user đã tồn tại chưa, nếu chưa thì tạo mới
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)  # Tạo thư mục cho user

        # Khởi tạo danh sách dữ liệu
        data = []

        # Kiểm tra xem file của user đã tồn tại chưa và đọc dữ liệu cũ nếu có
        if os.path.exists(user_file):
            with open(user_file, 'r') as file:
                try:
                    data = json.load(file)  # Đọc dữ liệu JSON từ file
                except json.JSONDecodeError:
                    data = []  # Nếu lỗi, khởi tạo danh sách rỗng

        # Tính id_query tự động dựa trên số lượng query hiện có
        new_query_id = len(data) + 1

        # Tạo entry mới cho query hiện tại
        new_query = {
            "id": str(new_query_id),
            "action": action,
            "model": model,
            "input_token": token_input,
            "output_token": token_output,
            "total_token": token_input + token_output,
            "request_time": time_request,
            "datetime": time_query
        }

        # Thêm entry mới vào danh sách
        data.append(new_query)

        # Ghi lại dữ liệu đã được cập nhật vào file JSON
        with open(user_file, 'w') as file:
            json.dump(data, file, indent=4)

    except Exception as e:
        print(f"Lỗi khi lưu dữ liệu token: {e}")
