import os
import openai
from dotenv import load_dotenv

load_dotenv()

# Cấu hình API key (bạn có thể set biến môi trường OPENAI_API_KEY trước)
openai.api_key = os.getenv("OPENAI_API_KEY")

def test_openai_api(query):
    try:
        # Gửi request tới OpenAI API (sử dụng Chat Completions - GPT-4 hoặc GPT-3.5)
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # hoặc "gpt-4"
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query}
            ],
            max_tokens=150
        )
        # Lấy text phản hồi từ API
        answer = response.choices[0].message.content
        return answer
    except Exception as e:
        return f"Lỗi khi gọi API: {e}"

if __name__ == "__main__":
    user_query = "viết văn tả mẹ"
    result = test_openai_api(user_query)
    print("Phản hồi từ OpenAI API:")
    print(result)
