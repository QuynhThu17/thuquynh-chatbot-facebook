from dotenv import load_dotenv
import threading
import json
import os
import re
from datetime import datetime
import pytz
import time
import mysql.connector
from contextlib import contextmanager
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.callbacks import get_openai_callback
from langchain_core.tools import BaseTool, tool
from langchain.agents import AgentExecutor, create_openai_tools_agent

from configs import environment, constant, _prompts

from controllers.ultils._log import log_function
from controllers.socials.facebook import connect, _facebook_pages
from controllers.databases.vector_databases import _qdrant
from controllers.databases.mysql import _mysql_mekongai
from controllers.configs import _manager
from controllers.socials.facebook._messenger_tmp import (
    save_message_to_file,
    get_messages_from_file,
    clear_messages_from_file,
)
from controllers.rag import _summary, _upload_files, _clean_data, _history
from controllers.ultils import _token_count, _ultils

from configs.prompts.school import prompt_school
from controllers.agent.tool import tool_school

load_dotenv()
vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")


# Pydantic Models for structured outputs
class BotResponse(BaseModel):
    response: str = Field(description="The bot's response message")
    page: str = Field(
        description="Page numbers for related product images (comma-separated)"
    )


class OrderInfo(BaseModel):
    product_name: str = Field(
        description="Thông tin của tất cả sản phẩm trong đơn hàng hiện tại (các sản phẩm mà khách hàng đã xác nhận mua hàng)"
    )
    unit_price: float = Field(
        description="Đơn giá của sản phẩm (tính bằng tiền Việt Nam đồng)"
    )
    quantity: int = Field(description="Số lượng")
    total_price: float = Field(
        description="Tổng giá trị đơn hàng (tính bằng giá đơn vị nhân với số lượng)"
    )
    delivery_address: str = Field(description="Địa chỉ giao hàng")
    recipient_name: str = Field(description="Tên người nhận")
    recipient_phone: str = Field(description="Số điện thoại người nhận")
    customer_note: str = Field(
        description="Ghi chú của khách hàng (nếu có)", default=""
    )


class MessageData(BaseModel):
    type: str = Field(description="Message type (text, image_url, etc.)")
    content: Union[str, List[str]] = Field(description="Message content")
    page_id: str = Field(description="Facebook page ID")
    sender_id: str = Field(description="Sender ID")


# Database Connection Functions
def connect_mysql():
    try:
        return mysql.connector.connect(
            host=constant.DB_HOST,
            user=constant.DB_USER,
            password=constant.DB_PASSWORD,
            database=constant.DB_NAME,
            autocommit=True,
        )
    except mysql.connector.Error as err:
        print(f"\n[LOG SYSTEM]\nLỗi kết nối MySQL: {err}")
        return None


@contextmanager
def get_cursor():
    connection = connect_mysql()
    if connection is None:
        raise ConnectionError("Không thể kết nối đến MySQL.")
    cursor = connection.cursor(dictionary=True)
    try:
        yield cursor
    except mysql.connector.Error as err:
        print(f"\n[LOG SYSTEM]\nLỗi MySQL: {err}")
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        cursor.close()
        connection.close()


# Tool Functions for Agents
class InformationConsultingTool(BaseModel):
    list_collections: List[str] = Field(
        description="Danh sách các collection để truy xuất thông tin"
    )
    query_retriever_content: str = Field(
        description="Truy vấn được viết lại để phục vụ cho việc truy xuất thông tin từ vector databases. (Nên là câu hỏi hoặc từ khóa liên quan đến thông tin cần tìm kiếm như mô tả đặc điểm, tên hoặc mã sản phẩm,...)"
    )
    query_retriever_image: str = Field(
        default="",
        description="Truy vấn được viết lại để phục vụ cho việc truy xuất hình ảnh từ vector databases. (Nên là câu hỏi hoặc từ khóa tìm kiếm hình ảnh cần tìm kiếm như mô tả đặc điểm, tên hoặc mã sản phẩm,...)",
    )


@tool("information_consulting_tool", args_schema=InformationConsultingTool)
def information_consulting_tool(
    list_collections: List[str] = [],
    query_retriever_content: str = "",
    query_retriever_image: str = "",
) -> str:
    """
    🔍 CÔNG CỤ TÌM KIẾM THÔNG TIN SẢN PHẨM/DỊCH VỤ
    
    Sử dụng tool này khi khách hàng:
    - Hỏi về sản phẩm/dịch vụ cụ thể
    - Muốn biết giá cả, thông số kỹ thuật
    - Yêu cầu xem hình ảnh sản phẩm
    - So sánh các sản phẩm
    - Tìm hiểu về tính năng, chức năng
    
    LUÔN LUÔN sử dụng tool này TRƯỚC KHI trả lời về bất kỳ sản phẩm/dịch vụ nào.
    
    Args:
        list_collections (List[str]): Danh sách collection để tìm kiếm
        query_retriever_content (str): Từ khóa tìm kiếm nội dung
        query_retriever_image (str): Từ khóa tìm kiếm hình ảnh (optional)
    
    Returns:
        str: Thông tin chi tiết về sản phẩm/dịch vụ từ database
    """

    return retrieve_context_information(
        collections=list_collections,
        query_retriever_content=query_retriever_content,
        query_retriever_image=query_retriever_image,
    )


class OrderInfoTool(BaseModel):
    order_info: OrderInfo = Field(
        description="Thông tin đơn hàng chi tiết bao gồm thông tin khách hàng và thông tin đơn hàng:tên sản phẩm, giá đơn vị, số lượng, địa chỉ giao hàng, tên người nhận, số điện thoại người nhận và ghi chú của khách hàng."
    )
    sender_id: str = Field(
        description="ID của người gửi tin nhắn (sender ID) từ Facebook Messenger."
    )
    page_id: str = Field(
        description="ID của trang Facebook (page ID) nơi tin nhắn được gửi."
    )
    user_id: str = Field(
        description="ID của người dùng (user ID) từ Facebook Messenger."
    )


@tool("save_order_to_database", args_schema=OrderInfoTool)
def save_order_to_database(
    order_info: OrderInfo, sender_id: str, page_id: str, user_id: str
) -> str:
    """
    💾 CÔNG CỤ LƯU ĐƠN HÀNG ĐÃ XÁC NHẬN
    
    ⚠️ CHỈ SỬ DỤNG KHI:
    ✅ Khách hàng đã XÁC NHẬN muốn mua hàng (nói rõ "mua", "đặt hàng", "xác nhận", "chốt đơn")
    ✅ Có đầy đủ thông tin: tên sản phẩm, giá, số lượng, địa chỉ giao hàng, tên người nhận, SĐT
    ✅ Khách hàng đã đồng ý với tổng tiền và điều kiện
    
    ❌ KHÔNG SỬ DỤNG KHI:
    ❌ Khách hàng chỉ hỏi thông tin, chưa quyết định mua
    ❌ Thiếu thông tin giao hàng hoặc liên hệ
    ❌ Khách hàng còn đang cân nhắc, so sánh
    
    Args:
        order_info (OrderInfo): Thông tin đơn hàng chi tiết đã được xác nhận
        sender_id (str): Facebook Messenger sender ID
        page_id (str): Facebook Page ID  
        user_id (str): Facebook User ID
        
    Returns:
        str: Thông báo kết quả lưu đơn hàng vào database
    """
    try:
        order_id = _mysql_mekongai.add_order(
            order_info.product_name,
            order_info.unit_price,
            order_info.quantity,
            order_info.delivery_address,
            order_info.recipient_name,
            order_info.recipient_phone,
            sender_id,
            page_id,
            user_id,
            order_info.customer_note,
        )

        # Save order timestamp
        file_path = f"{constant.DATAS_PUBLIC_PATH}/{constant.NAME_BOT_FACEBOOK}/{sender_id}/history_order_{sender_id}_{page_id}.txt"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        order_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        with open(file_path, "a") as file:
            file.write(f"{order_id} - {order_time}\n")

        return f"✅ Đã lưu đơn hàng thành công với mã: {order_id}"
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nError saving order: {e}")
        return "❌ Lỗi khi lưu đơn hàng, vui lòng thử lại"


class CustomerInfoTool(BaseModel):
    customer_name: str = Field(
        default="",
        description="Tên khách hàng (họ và tên đầy đủ nếu có). Nếu không có thông tin thì để trống."
    )
    gender: str = Field(
        default="",
        description="Giới tính của khách hàng (nam/nữ/khác). Nếu không có thông tin thì để trống."
    )
    phone_number: str = Field(
        default="",
        description="Số điện thoại của khách hàng. Nếu không có thông tin thì để trống."
    )
    address: str = Field(
        default="",
        description="Địa chỉ của khách hàng (có thể là địa chỉ nhà, địa chỉ công ty, hoặc khu vực sinh sống). Nếu không có thông tin thì để trống."
    )
    interested_products: str = Field(
        default="",
        description="Các sản phẩm hoặc dịch vụ mà khách hàng quan tâm, đang hỏi, hoặc có ý định mua. Nếu không có thông tin thì để trống."
    )
    additional_info: str = Field(
        default="",
        description="Thông tin bổ sung khác về khách hàng như sở thích, nhu cầu đặc biệt, ghi chú quan trọng. Nếu không có thông tin thì để trống."
    )
    sender_id: str = Field(
        description="ID của người gửi tin nhắn (sender ID) từ Facebook Messenger."
    )
    page_id: str = Field(
        description="ID của trang Facebook (page ID) nơi tin nhắn được gửi."
    )
    user_id: str = Field(
        description="ID của người dùng (user ID) từ Facebook Messenger."
    )


@tool("save_customer_info_to_database", args_schema=CustomerInfoTool)
def save_customer_info_to_database(
    customer_name: str = "",
    gender: str = "",
    phone_number: str = "",
    address: str = "",
    interested_products: str = "",
    additional_info: str = "",
    sender_id: str = "",
    page_id: str = "",
    user_id: str = ""
) -> str:
    """
    👤 CÔNG CỤ LƯU THÔNG TIN KHÁCH HÀNG (LEAD GENERATION)
    
    Sử dụng tool này khi khách hàng:
    ✅ Cung cấp thông tin cá nhân (tên, SĐT, địa chỉ)
    ✅ Chia sẻ sở thích, nhu cầu về sản phẩm
    ✅ Thể hiện quan tâm đến sản phẩm/dịch vụ cụ thể
    ✅ Đưa ra thông tin bổ sung về bản thân
    
    Tool này giúp xây dựng cơ sở dữ liệu khách hàng tiềm năng để hỗ trợ marketing và bán hàng.
    
    Args:
        customer_name (str): Họ tên khách hàng
        gender (str): Giới tính (nam/nữ/khác)
        phone_number (str): Số điện thoại liên hệ
        address (str): Địa chỉ của khách hàng
        interested_products (str): Sản phẩm/dịch vụ quan tâm
        additional_info (str): Thông tin bổ sung khác
        sender_id (str): Facebook Messenger sender ID
        page_id (str): Facebook Page ID
        user_id (str): Facebook User ID
        
    Returns:
        str: Thông báo kết quả lưu thông tin khách hàng
    """
    try:
        # Tạo unique ID cho khách hàng
        customer_unique_id = f"{user_id}{page_id}{sender_id}"
        
        # Gộp tất cả thông tin thành một chuỗi để lưu vào trường all_info
        all_info_parts = []
        
        if customer_name:
            all_info_parts.append(f"Tên: {customer_name}")
        if gender:
            all_info_parts.append(f"Giới tính: {gender}")
        if phone_number:
            all_info_parts.append(f"Số điện thoại: {phone_number}")
        if address:
            all_info_parts.append(f"Địa chỉ: {address}")
        if interested_products:
            all_info_parts.append(f"Sản phẩm quan tâm: {interested_products}")
        if additional_info:
            all_info_parts.append(f"Thông tin bổ sung: {additional_info}")
            
        if not all_info_parts:
            return "⚠️ Không có thông tin khách hàng để lưu"
            
        all_info_combined = " | ".join(all_info_parts)
        
        # Lưu thông tin khách hàng vào database
        customer_id = _mysql_mekongai.add_customer_info(
            user_id=user_id,
            sender_id=sender_id,
            page_id=page_id,
            id=customer_unique_id,
            name=customer_name,
            gender=gender,
            phone_number=phone_number,
            address=address,
            interested_products=interested_products,
            all_info=all_info_combined
        )
        
        # Lưu thông tin vào memory để sử dụng sau này
        try:
            memory_messages = []
            if customer_name:
                memory_messages.append({"role": "system", "content": f"Tên khách hàng: {customer_name}"})
            if gender:
                memory_messages.append({"role": "system", "content": f"Giới tính: {gender}"})
            if phone_number:
                memory_messages.append({"role": "system", "content": f"Số điện thoại: {phone_number}"})
            if address:
                memory_messages.append({"role": "system", "content": f"Địa chỉ: {address}"})
            if interested_products:
                memory_messages.append({"role": "system", "content": f"Sản phẩm quan tâm: {interested_products}"})
            if additional_info:
                memory_messages.append({"role": "system", "content": f"Thông tin bổ sung: {additional_info}"})
            
            if memory_messages:
                environment.memory.add(memory_messages, user_id=customer_unique_id)
            
        except Exception as memory_error:
            print(f"\n[LOG SYSTEM]\nWarning - Error saving to memory: {memory_error}")
        
        return f"✅ Đã lưu thông tin khách hàng với ID: {customer_id}\n📝 Thông tin: {all_info_combined}"
        
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nError saving customer info: {e}")
        return f"❌ Lỗi khi lưu thông tin khách hàng: {str(e)}"


# Cập nhật tools_list để bao gồm tool mới với tối ưu hóa
tools_list: List[BaseTool] = [
    information_consulting_tool, 
    save_order_to_database, 
    save_customer_info_to_database
]

BOT_MESSENGER_FACEBOOK_V2 = """\
<|begin_of_text|><|start_header_id|>system<|end_header_id|>

Ignore all previous instructions.

<|Instructions - (Hướng dẫn chung)|>:
- Mục đích chung: Bạn là một con người với `Information (Identity)` cụ thể. Bạn dựa vào `Role`, `Target` và `Mission` để hiểu rõ bạn đang thực hiện nhiệm vụ cụ thể gì.
- Cách hiểu truy vấn của khách hàng: Bạn sẽ sử dụng lịch sử trò chuyện `History` và nội dung truy vấn `Question` để hiểu rõ ngữ cảnh và ý định hiện tại, giúp trả lời mạch lạc, liên kết hơn và tiếp nối một cách tự nhiên tránh nhầm lẫn.
- Bạn phải tuân đủ đúng với action ở hướng dẫn trong `Procedures` để trả lời, không nên tự đưa ra câu trả lời mà không tuân theo hướng dẫn.
- Tư duy, suy luận, suy nghĩ, phân tích tình huống trước khi đưa ra câu trả lời. Đảm bảo rằng câu trả lời của bạn phải liên kết chặt chẽ với câu hỏi trước đó và phải đúng với ngữ cảnh hiện tại.
- Bạn phải có nhận thức cái nhìn bao quát về bối cảnh hiện tại. Để làm được điều đó bạn cần chú ý và suy luận thật kỹ, căn cứ vào `History` (Lịch sử cuộc trò chuyện) và `Customer Information` (Thông tin khách hàng) để biết chắc chắn điều gì đang xảy ra và đã có những thông tin cần thiết nào.
- Nếu có mô tả hình ảnh hoặc hình ảnh được gửi cho bạn ở `Question`, thì hãy tìm kiếm các thông tin liên quan trong `Context` để trả lời một cách chính xác và đầy đủ.
- Nếu khách hàng đính kèm link hoặc hình ảnh, hãy xem xét kỹ và trả lời dựa trên thông tin đã có trong `Context`.
- Xử lý tình huống không có thông tin: Nếu khách hỏi về sản phẩm/dịch vụ mà bạn không tìm thấy thông tin trong `Context` hoặc các nguồn khác được cung cấp, hãy thành thật và khéo léo nói rằng không tìm thấy sản phẩm / dịch vụ đó, đồng thời đề xuất các sản phầm / dịch vụ thay thế khác mà bạn có (không nên hỏi thêm nhiều về sản phầm / dịch vụ không có).

---

<|Role - (Vai trò)|> :
{role}
- Giọng điệu và cách trò chuyện y hệt một con người tự nhiên.

---

<|Target - (Mục tiêu)|> :
{target}

---

<|Mission - (Nhiệm vụ)|> :
{mission}
- Bạn dựa vào thông tin hình ảnh được đính kèm (nếu có) và thông tin trong `Context` để đưa ra câu trả lời phù hợp.
    + Thông tin hình ảnh đính kèm sẽ nằm trong `Query` dưới dạng `#<|Mô tả hình ảnh đính kèm: ...`. (nếu có).

---

<|History - (Lịch sử trò chuyện từ cũ đến mới nhất, sử dụng `History` để trả lời câu hỏi một cách logic và liên kết hơn tạo thành một cuộc trò chuyện hoàn chỉnh, tiếp tục từ câu trả lời gần nhất của bạn)|>:
{history}

---

<|Question - (Truy vấn hiện tại của khách hàng)|>:
{input}

---

<|Information (Identity) - (Bao gồm các thông tin cá nhân chung về bạn)|>.
{information}

---

<|Customer Information - (Thông tin khách hàng)|>:
{long_context}

---

<|Time Now - (Thời gian hiện tại)|>:
{time_now}

---

<|Note - (Lưu ý)|> :
- Tôn trọng khách hàng.
- Nếu thông tin cần thiết để trả lời không có trong `Context`, thì hãy thành thật nói rằng bạn không có thông tin về nó, và đưa ra gợi ý dưa vào thông tin mà bạn được cung cấp.
- Tránh hỏi lại những thông tin đã được cung cấp trong `History`. Sử dụng những thông tin trong `History` để đưa ra câu trả lời tự nhiên và liên kết.
- Đảm bảo thông tin trả lời chính xác và đầy đủ. Đưa ra các ví dụ nếu cần thiết.
- Ngắt câu, xuống dòng, in đậm và viết hoa đúng chỗ, tránh viết tắt và viết sai chính tả. Đưa ra định dạng dễ đọc nhất. 
- Sử dụng icon phù hợp (ví dụ: 😊,👟,👗,v.v.).
- Xưng hô: Dựa vào tên hoặc phong cách trò chuyện của khách hàng, bạn sẽ đoán giới tính của họ để gọi họ là "Anh" hoặc "Chị" hoặc "Anh/Chị" nếu không xác định được.
- Cách bạn nói chuyện y hệt một con người thực sự và không giả tạo.
- Tóm tắt thông tin để trả lời một cách ngắn gọn khoảng 50 đến 200 ký tự.
- Phải tuân thủ theo quy trình `Procedures` và thêm giọng điệu cách về trò chuyện của bạn vào đó. 
- * Luôn sử dụng tool để tìm kiếm thông tin trước khi trả lời.
- Trả lời theo ngôn ngữ của người dùng trong `Question`. 
- Xem xét kỹ những từ viết tắt để cố gắng hiểu ý định.
- Mỗi lần chỉ hỏi 1-2 câu hỏi, không dồn lại hỏi một lần.
- Nhắc đến cụ thể mã, tên sản phẩm/dịch vụ nếu cần thiết.
{note}

---

<|Things to avoid - (Những điều cần tránh)|>:
- Không được tự sáng tạo ra thông tin sản phẩm / dịch vụ.
- Không giới thiệu thông tin sản phẩm / dịch vụ không được cung cấp trong dữ liệu.
- Không hỏi lại thông tin đã được User cung cấp trong `History`.
- Tránh nhắc đến việc bạn nhận được thông tin từ ngữ cảnh.
- Tránh nhầm lẫn giữa bản thân và khách hàng.
- Số trang trong "page" phải là các số trang thông tin mà "response" nhắc đến (tối đa 3 trang liên quan nhất). Và chỉ cho ra số trang khi mà bạn nghĩ rằng lần này cần hình ảnh cho khách hàng xem về sản phẩm hoặc dịch vụ này. Hạn chế gửi trùng hình ảnh với các câu trả lời trước đó.
- Bạn chỉ trả lời những kiến thức có trong `Context` và giao tiếp cơ bản. Không được trả lời những câu hỏi mà không liên quan đến `Role`, `Target`, `Mission` của bạn. Vì nó nằm ngoài kiến thức. Hãy từ chối một cách lịch sự nếu không thể trả lời (ví dụ: Dạ em xin lỗi, nhưng em không thể trả lời câu hỏi này. Em là ... và chỉ trả lời các vấn đề liên quan đến...). (Không cần Things to avoid - (Những điều cần tránh) này nếu có đính kèm ảnh).

---

<|Procedures - (Action là hành động mà bạn sẽ khéo léo thực hiện theo trong bước này và một vài bước tiếp theo, hãy tuân thủ theo nó)|>:
{procedure}

---

<|Output format - (Định dạng câu trả lời)|>:
- Phản hồi theo định dạng JSON gồm 2 trường sau: 
"response": "<string>", "page": "<numbers_string>"
- Trong đó (trong câu trả lời định dạng JSON):
  + Viết "response" là câu trả lời của bạn (định dạng rõ ràng và dễ đọc, tránh các dấu nháy đơn hay nháy đôi trong câu trả lời của bạn). Độ dài của câu trả lời linh hoạt tùy vào tình huống. "response" là luôn luôn phải có trong câu trả lời.
  + Viết "page" là các số trang thông tin tài liệu mà câu trả lời response ở trên nhắc đến (nếu có thì tối đa 3 trang liên quan quan trọng nhất, còn nếu không có thì không cần viết). Được ngăn cách bởi dấu phẩy. Chỉ nên có "page" ở những câu trả lời về thông tin cụ thể từ tài liệu và cần thiết hoặc khách hàng yêu cầu xem sản phẩm hoặc ảnh sản phảm. Và chỉ cho ra số trang khi mà bạn nghĩ rằng lần này cần hình ảnh cho khách hàng xem về sản phẩm hoặc dịch vụ này.

- (Quan trọng) page phải trả về trang thông tin mà câu trả lời của bạn nhắc đến nếu đó là thông tin sản phẩm hoặc dịch vụ (không được nhầm lẫn trang page).

---

<|Ví dụ|>:
- Câu hỏi: "Xin chào"
- Câu trả lời: "response": "Dạ, em chào chị ạ! Em là Lan Anh, nhân viên tư vấn của FM Style. Không biết hôm nay chị đang tìm mẫu nào hay cần em hỗ trợ tư vấn không ạ?", "page": ""

---

<|Context - (Thông tin / sản phẩm / dịch vụ bạn cần tham khảo)|>:
{context}

---

list_collections: {list_collections}
sender_id: {sender_id}
page_id: {page_id}
user_id: {user_id}

---

<|Scratchpad - (Nơi bạn ghi lại quá trình suy nghĩ và xử lý)|>:
- Bạn được cung cấp nhiều tools, bạn có thể sử dụng nhiều tools cùng một lúc để hoàn thành nhiệm vụ của mình.
{agent_scratchpad}

---

<|eot_id|><|start_header_id|>user<|end_header_id|>

{input}

<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

prompt = ChatPromptTemplate.from_template(BOT_MESSENGER_FACEBOOK_V2)

agent = create_openai_tools_agent(environment.llm_4o_05_temperature, tools_list, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools_list,
    verbose=True,
    handle_parsing_errors="Xin lỗi, Hệ thống đang gặp chút sự cố nhỏ trong việc xử lý yêu cầu của bạn. Bạn vui lòng thử lại hoặc diễn đạt khác đi một chút nhé!",
    max_iterations=7,  # Tăng từ 5 lên 7 để agent có thời gian sử dụng tools
    early_stopping_method="generate",  # Tránh loop vô hạn
    return_intermediate_steps=True  # Debug tool calling steps
)


# School Agent
school_tools_list: List[BaseTool] = [
    tool_school.search_school,
]

school_prompt = ChatPromptTemplate.from_template(prompt_school.BOT)

# Tạo streaming agent executor riêng
school_agent = create_openai_tools_agent(
    environment.llm_4o_05_temperature, 
    school_tools_list, 
    school_prompt
)

school_agent_executor = AgentExecutor(
    agent=school_agent,
    tools=school_tools_list,
    verbose=True,
    handle_parsing_errors="Xin lỗi, Hệ thống đang gặp chút sự cố nhỏ trong việc xử lý yêu cầu của bạn. Bạn vui lòng thử lại hoặc diễn đạt khác đi một chút nhé!",
    max_iterations=3,   
)


def retrieve_context_information(
    collections: List[str],
    query_retriever_content: str,
    query_retriever_image: str = "",
) -> str:
    """Retrieve relevant context from vector databases."""
    if not collections:
        return ""

    if not query_retriever_image:
        query_retriever_image = query_retriever_content

    try:

        def get_retriever(collection, query):
            db = _upload_files.load_vector_db(collection)
            retriever = _upload_files.retriever_question(db, query, collection)
            return retriever

        def get_retriever_img(collection, summary_query):
            try:
                parts_img = collection.split("_")
                modified_string_img = f"{parts_img[0]}_{parts_img[2]}"
                img_collection = modified_string_img + "_IMAGES"

                db_images = _upload_files.load_vector_db(img_collection)
                retriever_img = _upload_files.retriever_question_img(
                    db_images,
                    _clean_data.clean_special_characters(summary_query),
                    img_collection,
                )
                return retriever_img
            except Exception as e:
                print(f"\n[LOG SYSTEM]\nError getting image retriever: {e}")
                return ""

        retrievers = []
        with ThreadPoolExecutor() as executor:
            future_to_collection = {
                executor.submit(
                    get_retriever, collection, query_retriever_content
                ): collection
                for collection in collections
            }
            future_to_collection_img = {
                executor.submit(
                    get_retriever_img, collection, query_retriever_image
                ): collection
                for collection in collections
            }

            # Get text retriever results
            retriever_results = {
                future_to_collection[future]: future.result()
                for future in as_completed(future_to_collection)
            }

            # Get image retriever results
            retriever_img_results = {
                future_to_collection_img[future]: future.result()
                for future in as_completed(future_to_collection_img)
            }

            # Combine results
            for collection in collections:
                text_result = retriever_results.get(collection, "")
                img_result = retriever_img_results.get(collection, "")
                retrievers.append(f"{text_result}\n\n{img_result}")

        return "\n\n".join(retrievers)
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nError retrieving context: {e}")
        return ""


def get_conversation_history(
    query: str, sender_id: str, page_id: str, user_id: str
) -> str:
    """Get conversation history and relevant memories."""
    try:
        # Load conversation history
        history = _history.load_history(sender_id, page_id, constant.NAME_BOT_FACEBOOK)

        # Build history context
        history_context = ""

        for item in history:
            if item["answer"] != "":
                history_context += (
                    f"- User: {item['query']}\n- Staff: {item['answer']}\n\n"
                )
            else:
                history_context += f"- User: {item['query']}\n\n"

        history_context += f"\n- User: {query}\n\n"

        try:
            relevant_memories = environment.memory.search(
                query=query, user_id=f"{user_id}{page_id}{sender_id}", limit=5
            )

            history_context_ = "\n".join(
                f"- {entry['memory']}" for entry in relevant_memories["results"]
            )
            history_context += "\n\n⚙️ Relevant Memories: " + str(history_context_)

            print(f"\n[LOG SYSTEM]\n⚙️ Relevant Memories: {history_context_}")

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError Memory: {e}")

        return _clean_data.clean_special_characters(history_context)
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nError getting conversation history: {e}")
        return ""


def get_product_images(
    collections: List[str], pages: List[str], query: str, sender_id: str, page_id: str
) -> List[str]:
    """Get base64 images for specific product pages."""
    base64_images = []

    try:
        for collection in collections:
            print(f"\n[LOG SYSTEM]\nProcessing collection: {collection}")
            parts = collection.split("_")
            modified_string = f"{parts[0]}_{parts[2]}"

            for page in pages:
                result = _qdrant.scroll_qdrant(modified_string + "_IMAGES", page)
                if result:
                    for item in result["result"]["points"]:
                        image_base_64 = item["payload"]["metadata"]["images_base_64"]

                        # Check if image is needed based on query
                        if (
                            "ảnh" in query.lower()
                            or "image" in query.lower()
                            or "gửi hình" in query.lower()
                            or "xem hình" in query.lower()
                        ):
                            check = False
                        else:
                            check = _history.check_base64_image_exists(
                                sender_id,
                                page_id,
                                constant.NAME_BOT_FACEBOOK,
                                image_base_64,
                            )
                            
                            print(f"\n[LOG SYSTEM]\nChecking if image already exists - Check result: {check}")

                        if not check:
                            base64_images.append(image_base_64)

        # print(f"\n[LOG SYSTEM]\nFound {len(base64_images)} base64 images in total.")
        # Clean up base64 images
        base64_images_ = list(dict.fromkeys(base64_images))
        # print(f"\n[LOG SYSTEM]\nFound {len(base64_images_)} unique base64 images after deduplication.")

        # Remove duplicates
        return base64_images_
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nError getting product images: {e}")
        return []


# Agent Classes
class MessageProcessorAgent:
    """Agent for processing incoming messages and managing message flow."""

    def __init__(self):
        self.name = "MessageProcessor"

    def extract_message_data(self, json_data: Dict) -> Optional[MessageData]:
        """Extract message data from Facebook webhook payload."""
        try:
            entry = json_data.get("entry", [])
            if not entry or not isinstance(entry, list):
                print(
                    "\n[LOG SYSTEM]\n| Bot Messenger ERR || Missing or invalid 'entry' field"
                )
                return None

            entry_item = entry[0]
            page_id = entry_item.get("id")

            messaging = entry_item.get("messaging", [])
            if not messaging or not isinstance(messaging, list):
                print(
                    "\n[LOG SYSTEM]\n| Bot Messenger WARN || No 'messaging' field found"
                )
                return None

            messaging_item = messaging[0]
            sender = messaging_item.get("sender", {})
            sender_id = sender.get("id")

            message = messaging_item.get("message", {})

            if not message:
                # Handle postback
                postback = messaging_item.get("postback", {})
                message_text = postback.get("title")
                if message_text:
                    # Fix encoding issue
                    message_text = (
                        message_text.encode("latin1").decode("utf-8")
                        if isinstance(message_text, str)
                        else message_text
                    )
                    return MessageData(
                        type="text",
                        content=message_text,
                        page_id=page_id,
                        sender_id=sender_id,
                    )
                return None
            else:
                # Handle text message
                message_text = message.get("text")
                if message_text:
                    # Fix encoding issue
                    try:
                        message_text = (
                            message_text.encode("latin1").decode("utf-8")
                            if isinstance(message_text, str)
                            else message_text
                        )
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        # If encoding conversion fails, use original text
                        pass

                    return MessageData(
                        type="text",
                        content=message_text,
                        page_id=page_id,
                        sender_id=sender_id,
                    )

                # Handle image attachments
                attachments = message.get("attachments", [])
                if attachments:
                    urls = []
                    for attachment in attachments:
                        if attachment.get("type") == "image":
                            payload = attachment.get("payload", {})
                            sticker_id = payload.get("sticker_id")
                            if not sticker_id:
                                url = payload.get("url")
                                if url:
                                    urls.append(url)
                                    print(f"Found image URL: {url}")

                    if len(urls) == 1:
                        return MessageData(
                            type="image_url",
                            content=urls[0],
                            page_id=page_id,
                            sender_id=sender_id,
                        )
                    elif len(urls) > 1:
                        return MessageData(
                            type="multiple_images",
                            content=urls,
                            page_id=page_id,
                            sender_id=sender_id,
                        )

            return None
        except Exception as e:
            print(
                f"\n[LOG SYSTEM]\n| Bot Messenger ERR || Error in extract_message_data: {e}"
            )
            return None

    def check_last_message(
        self, message_text: str, sender_id: str, page_id: str
    ) -> bool:
        """Check if the current message is still the last message."""
        try:
            all_messages = get_messages_from_file(sender_id, page_id)

            if not all_messages:
                print("\n[LOG SYSTEM]\nNo messages found in file")
                return True

            # Get the last message from file
            last_message = all_messages[-1]["text"]

            # Fix encoding for comparison
            try:
                message_text_fixed = (
                    message_text.encode("latin1").decode("utf-8")
                    if isinstance(message_text, str)
                    else message_text
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                message_text_fixed = message_text

            try:
                last_message_fixed = (
                    last_message.encode("latin1").decode("utf-8")
                    if isinstance(last_message, str)
                    else last_message
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                last_message_fixed = last_message

            # Check if current message matches the last message in file
            if message_text_fixed == last_message_fixed or message_text == last_message:
                return True
            else:
                print("\n[LOG SYSTEM]\nHủy task do có tin nhắn liên tiếp mới được gửi")
                return False

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError in check_last_message: {e}")
            return True  # Default to True if there's an error

    def process_messages(
        self, user_id: str, all_messages: List[Dict], current_message: str
    ) -> tuple:
        """Process and combine messages including image descriptions."""
        string_query = ""
        has_url = False
        summary_string_query = ""  # Fix: Add missing variable

        for msg in all_messages:
            text = msg["text"]

            # Fix encoding for each message
            try:
                text = (
                    text.encode("latin1").decode("utf-8")
                    if isinstance(text, str)
                    else text
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass  # Keep original text if encoding conversion fails

            if self.is_image_url(text):
                has_url = True
                summary = _summary.image_summary_openai_v2(
                    user_id, text, current_message
                )
                string_query += f"{current_message}\n[Sau đây là mô tả hình ảnh được đính kèm theo]: {summary}\n"
                summary_string_query += f"{summary}\n"
            else:
                string_query += f"{text}\n"

        return string_query, has_url

    def is_image_url(self, text: str) -> bool:
        """Check if text is an image URL."""
        image_url_regex = re.compile(
            r"^(http|https)://"
            r"(www\.)?"
            r"[\w\-]+(\.[\w\-]+)+"
            r"(/[^\s]*)?"
            r"\.(jpg|jpeg|png|gif|bmp|webp)"
            r"(\?.*)?$",
            re.IGNORECASE,
        )
        return bool(image_url_regex.match(text))

    def check_last_message(
        self, message_text: str, sender_id: str, page_id: str
    ) -> bool:
        """Check if the current message is still the last message."""
        try:
            all_messages = get_messages_from_file(sender_id, page_id)
            print(
                f"\n[LOG SYSTEM]\n| Bot Messenger INFO || All messages: {all_messages}"
            )

            if not all_messages:
                print("\n[LOG SYSTEM]\nNo messages found in file")
                return True

            # Get the last message from file
            last_message = all_messages[-1]["text"]

            # Fix encoding for comparison
            try:
                message_text_fixed = (
                    message_text.encode("latin1").decode("utf-8")
                    if isinstance(message_text, str)
                    else message_text
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                message_text_fixed = message_text

            try:
                last_message_fixed = (
                    last_message.encode("latin1").decode("utf-8")
                    if isinstance(last_message, str)
                    else last_message
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                last_message_fixed = last_message

            print(
                f"\n[LOG SYSTEM]\nComparing: '{message_text_fixed}' with '{last_message_fixed}'"
            )

            # Check if current message matches the last message in file
            if message_text_fixed == last_message_fixed or message_text == last_message:
                return True
            else:
                print("\n[LOG SYSTEM]\nHủy task do có tin nhắn liên tiếp mới được gửi")
                return False

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError in check_last_message: {e}")
            return True  # Default to True if there's an error

    def run_agent(
        self,
        query: str,
        role: str,
        target: str,
        mission: str,
        contexts: str,
        history_context: str,
        procedure: str,
        info: str,
        long_memory: str,
        current_time: datetime,
        note: str,
        list_collections: List[str],
        sender_id: str,
        page_id: str,
        user_id: str,
    ) -> BotResponse:
        try:
            if page_id == "757245234130314":
                # Special case for school agent
                print("\n[LOG SYSTEM]\nUsing School Agent for query:", query)
                invoke_payload = {
                    "input": str(query),
                    "history": str(history_context),
                    "time_now": str(current_time),
                }

                response = school_agent_executor.invoke(invoke_payload)
                
                # Handle school agent response with same JSON parsing logic
                try:
                    return BotResponse(
                        response=str(response.get("output", "Xin lỗi quý khách, hệ thống đang gặp sự cố kỹ thuật nhỏ. Bên mình sẽ sớm khắc phục. Mong bạn thông cảm và thử lại sau ít phút!")),
                        page="",
                    )
                except Exception as e:
                    return BotResponse(
                        response="Xin lỗi quý khách, hệ thống đang gặp sự cố kỹ thuật nhỏ. Bên mình sẽ sớm khắc phục. Mong bạn thông cảm và thử lại sau ít phút!",
                        page="",
                    )
                
            else:
                invoke_payload = {
                    "input": str(query),
                    "role": str(role),
                    "target": str(target),
                    "mission": str(mission),
                    "context": str(contexts),
                    "history": str(history_context),
                    "procedure": str(procedure),
                    "information": str(info),
                    "long_context": str(long_memory),
                    "time_now": str(current_time),
                    "note": str(note),
                    "list_collections": list_collections,
                    "sender_id": str(sender_id),
                    "page_id": str(page_id),
                    "user_id": str(user_id),
                }

                response = agent_executor.invoke(invoke_payload)
                
                # Debug tool calling steps
                if "intermediate_steps" in response:
                    print(f"\n[TOOL CALLING STEPS]\n{response['intermediate_steps']}")
                    
                # Enhanced logging cho tool calling
                print(f"\n[TOOL CALLING DEBUG]\nQuery: {query}")
                print(f"Collections available: {list_collections}")
                
                if isinstance(response.get("output"), str):
                    try:
                        output_str = response.get("output")
                        
                        # Kiểm tra xem output có phải là JSON hoàn chỉnh không
                        if output_str.strip().startswith('{') and output_str.strip().endswith('}'):
                            # JSON hoàn chỉnh
                            output_json = json.loads(output_str)
                        else:
                            # JSON không hoàn chỉnh - thêm dấu ngoặc nhọn
                            if '"response":' in output_str and '"page":' in output_str:
                                # Đã có format JSON nhưng thiếu dấu ngoặc nhọn
                                fixed_json = '{' + output_str + '}'
                                output_json = json.loads(fixed_json)
                            else:
                                # Không phải JSON, coi như text thuần
                                raise json.JSONDecodeError("Not a JSON format", output_str, 0)
                        
                        return BotResponse(
                            response=output_json.get(
                                "response",
                                "Xin lỗi, mình chưa hiểu rõ ý bạn. Bạn có thể nói rõ hơn được không?",
                            ),
                            page=output_json.get("page", ""),
                        )
                        
                    except json.JSONDecodeError:
                        # Nếu không parse được JSON, kiểm tra xem có chứa pattern response và page không
                        output_str = response.get("output", "")
                        
                        # Extract response và page bằng regex nếu có pattern
                        import re
                        response_match = re.search(r'"response":\s*"([^"]*(?:\\.[^"]*)*)"', output_str)
                        page_match = re.search(r'"page":\s*"([^"]*)"', output_str)
                        
                        if response_match:
                            extracted_response = response_match.group(1)
                            extracted_page = page_match.group(1) if page_match else ""
                            
                            return BotResponse(
                                response=extracted_response,
                                page=extracted_page,
                            )
                        else:
                            # Nếu không có pattern, sử dụng toàn bộ string làm response
                            return BotResponse(
                                response=output_str or "Xin lỗi quý khách, hệ thống đang gặp sự cố kỹ thuật nhỏ. Bên mình sẽ sớm khắc phục. Mong bạn thông cảm và thử lại sau ít phút!",
                                page="",
                            )
                else:
                    # If output is not a string, return a default response
                    return BotResponse(
                        response="Xin lỗi quý khách, hệ thống đang gặp sự cố kỹ thuật nhỏ. Bên mình sẽ sớm khắc phục. Mong bạn thông cảm và thử lại sau ít phút!",
                        page="",
                    )

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError in run_agent: {e}")
            return BotResponse(
                response="Xin lỗi quý khách, hệ thống đang gặp sự cố kỹ thuật nhỏ. Bên mình sẽ sớm khắc phục. Mong bạn thông cảm và thử lại sau ít phút!",
                page="",
            )


class MultiAgentMessengerBot:
    """Main bot class that orchestrates all agents."""

    def __init__(self):
        self.message_processor = MessageProcessorAgent()

    def save_message_to_db(
        self,
        user_id: str,
        sender_id: str,
        page_id: str,
        query: str,
        response: str,
        suggest: List[str],
    ):
        """Save message to database."""
        with get_cursor() as cursor:
            try:
                query_get_id_user_fb = """
                    SELECT uf.id_user_fb
                    FROM pages p
                    JOIN users_facebook uf ON p.access_token_user = uf.access_token_user
                    WHERE p.fb_page_id = %s
                    LIMIT 1
                """
                cursor.execute(query_get_id_user_fb, (page_id,))
                result = cursor.fetchone()
                id_user_fb = result[0] if result else None

                suggest_json = json.dumps(suggest)

                sql_insert = """
                    INSERT INTO messages (user_id, sender_id, page_id, query, response, suggest, id_user_fb)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(
                    sql_insert,
                    (
                        user_id,
                        sender_id,
                        page_id,
                        query,
                        response,
                        suggest_json,
                        id_user_fb,
                    ),
                )

            except mysql.connector.Error as err:
                print(f"\n[LOG SYSTEM]\nLỗi khi thêm dữ liệu vào bảng messages: {err}")

    def save_message_and_context(
        self,
        user_id: str,
        sender_id: str,
        page_id: str,
        query: str,
        response: str,
        base64_images: List[str],
        current_time: datetime,
    ):
        """Save message and update customer context."""
        try:
            # Save to history
            if isinstance(current_time, datetime):
                current_time = current_time.isoformat()

            _upload_files.save_history(
                response,
                sender_id,
                user_id,
                query,
                page_id,
                constant.NAME_BOT_FACEBOOK,
                current_time,
                base64_images,
            )

            # Save to memory
            messages = [{"role": "user", "content": query}]
            environment.memory.add(messages, user_id=f"{user_id}{page_id}{sender_id}")

            # Update customer information
            # self.update_customer_info(user_id, sender_id, page_id)

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError saving message and context: {e}")


    def process_message(self, json_data: Dict):
        """Main method to process incoming Facebook messages."""
        try:
            # Extract message data
            message_data = self.message_processor.extract_message_data(json_data)
            if not message_data:
                return

            print(f"Type: {message_data.type}, Content: {message_data.content}")

            # Get basic info
            page_id = message_data.page_id
            sender_id = message_data.sender_id
            
            if message_data.type == "multiple_images":
                urls = message_data.content
                print(f"Multiple images found: {urls}")
                for url in urls:
                    # Save each image URL to temporary file
                    save_message_to_file(
                        sender_id, page_id, url, int(datetime.now().timestamp())
                    )
            else:
                message_text = message_data.content
            
                # message_text = (
                #     message_data.content
                #     if isinstance(message_data.content, str)
                #     else str(message_data.content)
                # )

                # Save message to temporary file
                save_message_to_file(
                    sender_id, page_id, message_text, int(datetime.now().timestamp())
                )

            # Get page access token and user ID
            page_access_token, user_id = _facebook_pages.get_access_token_from_page_id(
                page_id
            )

            # Process combined messages
            all_messages = get_messages_from_file(sender_id, page_id)
            if all_messages:
                string_query, has_url = self.message_processor.process_messages(
                    user_id, all_messages, message_text
                )
            else:
                string_query = message_text
                has_url = False

            # Send typing indicator
            threading.Thread(
                target=connect.send_action_facebook_messenger,
                args=(page_id, page_access_token, sender_id, True),
            ).start()

            role, target, mission, list_collections, procedure, info, note = (
                _manager.get_info_by_page_id_and_action(page_id, 1)
            )
            
            if not self.message_processor.check_last_message(
                message_text, sender_id, page_id
            ):
                return

            # Generate response using conversation agent
            bot_response = self.message_processor.run_agent(
                query=string_query,
                role=role,
                target=target,
                mission=mission,
                contexts="Được cung cấp bởi các công cụ và thông tin từ vector databases",
                history_context=get_conversation_history(
                    string_query, sender_id, page_id, user_id
                ),
                procedure=procedure,
                info=info,
                long_memory="",
                current_time=datetime.now(vietnam_tz),
                note=note,
                list_collections=list_collections,
                sender_id=sender_id,
                page_id=page_id,
                user_id=user_id,
            )
            
            if not self.message_processor.check_last_message(
                message_text, sender_id, page_id
            ):
                return

            print(
                f"\n[LOG SYSTEM]\n- Query: {string_query}\n- Image: {has_url}\n- Bot Response: {bot_response.response}\n- Page: {bot_response.page}"
            )

            # Send response
            if bot_response.response:
                connect.send_facebook_messenger(
                    page_id, page_access_token, sender_id, bot_response.response
                )

            # Get and send images if needed
            base64_images = []
            if bot_response.page:
                pages = _ultils.extract_pages(bot_response.page)
                print(f"\n[LOG SYSTEM]\nPages: {pages}")
                if pages:
                    base64_images = get_product_images(
                        list_collections, pages, string_query, sender_id, page_id
                    )

            print(f"\n[LOG SYSTEM]\nBase64 Images: {len(base64_images)} found")

            # Save to database
            threading.Thread(
                target=self.save_message_to_db,
                args=(
                    user_id,
                    sender_id,
                    page_id,
                    string_query,
                    bot_response.response,
                    [],
                ),
            ).start()

            # Save message and context
            current_time = datetime.now(vietnam_tz)
            threading.Thread(
                target=self.save_message_and_context,
                args=(
                    user_id,
                    sender_id,
                    page_id,
                    string_query,
                    bot_response.response,
                    base64_images,
                    current_time,
                ),
            ).start()

            # Clear temporary messages
            clear_messages_from_file(sender_id, page_id, all_messages)

            # Send images
            if base64_images:
                connect.send_facebook_messenger_images(
                    page_id, page_access_token, sender_id, base64_images, []
                )

        except Exception as e:
            print(f"\n[LOG SYSTEM]\nError processing message: {e}")


# Main function to replace the original chatbot function
def chatbot(json_data: Dict):
    """Main chatbot function using Multi-Agent System."""
    bot = MultiAgentMessengerBot()
    bot.process_message(json_data)


# Legacy utility functions (kept for compatibility)
def get_messages_from_db(sender_id=None, user_id=None, page_id=None, id_user_fb=None):
    """
    Lấy danh sách messages, có thể lọc theo user_id, page_id hoặc cả hai.
    Nếu không truyền tham số nào, trả về tất cả messages.
    """
    try:
        with get_cursor() as cursor:
            # Khởi tạo câu lệnh và danh sách điều kiện
            base_query = "SELECT * FROM messages"
            conditions = []
            params = []

            # Thêm điều kiện nếu có user_id
            if user_id:
                conditions.append("user_id = %s")
                params.append(user_id)

            # Thêm điều kiện nếu có page_id
            if page_id:
                conditions.append("page_id = %s")
                params.append(page_id)

            if sender_id:
                conditions.append("sender_id = %s")
                params.append(sender_id)

            if id_user_fb:
                conditions.append("id_user_fb = %s")
                params.append(id_user_fb)

            # Nối điều kiện vào câu lệnh SQL
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)

            # Thực thi truy vấn
            cursor.execute(base_query, params)
            rows = cursor.fetchall()

            return rows

    except Exception as err:
        # Ném lỗi rõ ràng nếu có vấn đề với DB
        raise Exception(f"Database error: {err}")

