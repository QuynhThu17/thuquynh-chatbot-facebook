import os
import base64
import requests
import re
import json
from datetime import datetime

# from controllers.socials.facebook.chatbot import bot_post

from controllers.socials.facebook import _facebook_pages

from configs import constant


########################################################################################
def get_facebook_accounts(access_token):
    """
    Hàm lấy thông tin các send_facebook_messenger của người dùng thông qua API của Facebook.

    :param access_token: Access Token của người dùng
    :return: JSON response từ API nếu thành công, None nếu thất bại
    """
    url = f"https://graph.facebook.com/v20.0/me/accounts"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


def extract_account_info(data):
    """
    Hàm trích xuất các thông tin từ JSON trả về: access_token, name, id.

    :param data: Dữ liệu JSON trả về từ API Facebook
    :return: Danh sách các tài khoản với access_token, name và id
    """
    account_list = []

    if "data" in data:
        for account in data["data"]:
            account_info = {
                "access_token": account.get("access_token", ""),
                "name": account.get("name", ""),
                "id": account.get("id", ""),
            }
            account_list.append(account_info)

    return account_list


# Sử dụng hàm
# access_token = 'EAAOZCGoDpkUwBO9ah9ZCuhksq2nNtaQZCp3rrccZCSqZCowoO21jZBnZAKMvUmrBY25KcYvZCdH6fBGrhQWueJWPXG1YoiyDRSQdpZBOB23QCbXtA5aDaIwTWPUMSFrNOzrdldY3VWmYYFIZCl3eesHwlqPan9Plz6jX1hTIOZCOPDnKdb5ZAGliW5ySd3SZA1Ceyq8tqiO1LQZARF7ZBL1sYylVnHANZBizCk6RF3vhekF0KwzW5MiMXBdsXPcTHchHIGknEAIcDAZDZD'
# response_data = get_facebook_accounts(access_token)
#
# if response_data:
#     account_info_list = extract_account_info(response_data)
#     print("\n[LOG SYSTEM]\nAccount Information Extracted:")
#     for account in account_info_list:
#         print(f"\n[LOG SYSTEM]\nName: {account['name']}, ID: {account['id']}, Access Token: {account['access_token']}")
# else:
#     print("\n[LOG SYSTEM]\nFailed to retrieve account information.")


########################################################################################
def post_to_facebook_page(user_id, page_id, image_url, scheduled_publish_time, topic):
    """
    Hàm post bài viết lên trang Facebook.

    :param user_id:
    :param scheduled_publish_time:
    :param published:
    :param image_url:
    :param page_id: ID của trang mà bạn muốn lấy bài viết
    :return: JSON response từ API nếu thành công, None nếu thất bại
    """

    message = bot_post.chatbot(user_id, page_id, topic)

    if image_url == "none" or image_url == "":
        url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
        if scheduled_publish_time == "" or scheduled_publish_time == "now":
            data = {
                "message": message,
                "published": "true",
            }
        else:
            data = {
                "message": message,
                "published": "false",
                "scheduled_publish_time": scheduled_publish_time,
            }
    else:
        url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
        if scheduled_publish_time == "" or scheduled_publish_time == "now":
            data = {"message": message, "published": "true", "url": image_url}
        else:
            data = {
                "message": message,
                "published": "false",
                "scheduled_publish_time": scheduled_publish_time,
                "url": image_url,
            }

    access_token, user_id_ = _facebook_pages.get_access_token_from_page_id(page_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


def post_to_facebook_page_with_content(
    user_id, page_id, content, image_url, scheduled_publish_time
):
    # Xử lý DB gọi vào hàm post_now_to_facebook

    pass


def post_now_to_facebook(user_id, page_id, content, image_urls):
    """
    Hàm post bài viết lên trang Facebook với danh sách hình ảnh.

    :param page_id: ID của trang mà bạn muốn đăng bài
    :param content: Nội dung bài viết
    :param image_urls: Danh sách URL hình ảnh
    :return: JSON response từ API nếu thành công, None nếu thất bại
    """
    access_token, user_id_ = _facebook_pages.get_access_token_from_page_id(page_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    if content == "":
        content = bot_post.chatbot(user_id, page_id, "")

    try:
        # Case 1: No images provided
        if not image_urls or len(image_urls) == 0:
            print("\n[LOG SYSTEM]\nchạy trường hợp không có ảnh")
            url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
            data = {
                "message": content,
                "published": "true",
            }
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                post_id = response.json().get("id")
                link_post = f"https://www.facebook.com/{post_id}"
                return response.json(), link_post
            else:
                print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
                return None

        # Case 2: Images are provided
        else:
            print("\n[LOG SYSTEM]\nchạy trường hợp có ảnh")
            # Post each image to the /photos endpoint
            photo_ids = []
            for image_url in image_urls:
                url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
                data = {"message": "", "published": "false", "url": image_url}
                response = requests.post(url, headers=headers, json=data, timeout=120)
                if response.status_code == 200:
                    photo_ids.append(response.json().get("id"))
                else:
                    print(
                        f"Error uploading image: {image_url}, {response.status_code}, {response.text}"
                    )

            # Once images are uploaded, create the post with attached media
            if photo_ids:
                url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
                data = {
                    "message": content,
                    "published": "true",
                    "attached_media": [
                        {"media_fbid": photo_id} for photo_id in photo_ids
                    ],
                }
                response = requests.post(url, headers=headers, json=data, timeout=120)
                if response.status_code == 200:
                    post_id = response.json().get("id")
                    link_post = f"https://www.facebook.com/{post_id}"
                    return response.json(), link_post
                else:
                    print(
                        f"Error creating post: {response.status_code}, {response.text}"
                    )
                    return None

    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


def get_facebook_posts(access_token, page_id):
    """
    Hàm lấy danh sách các bài viết từ một trang Facebook.

    :param access_token: Access Token của người dùng
    :param page_id: ID của trang mà bạn muốn lấy bài viết
    :return: JSON response từ API nếu thành công, None nếu thất bại
    """
    url = f"https://graph.facebook.com/v20.0/{page_id}/posts?fields=id,message,full_picture,created_time,attachments"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


def extract_post_info(data):
    """
    Hàm trích xuất các thông tin từ JSON trả về: id, message, created_time, full_picture.

    :param data: Dữ liệu JSON trả về từ API Facebook
    :return: Danh sách các bài viết với các trường id, message, created_time và full_picture (nếu có)
    """
    post_list = []

    if "data" in data:
        for post in data["data"]:
            post_info = {
                "id": post.get("id", ""),
                "message": post.get("message", ""),
                "created_time": post.get("created_time", ""),
                "full_picture": post.get(
                    "full_picture", None
                ),  # Sử dụng None nếu không có
            }
            post_list.append(post_info)

    return post_list


# Sử dụng hàm
# access_token = 'EAAOZCGoDpkUwBOyQU02odnh3RMx1SK119NILdaijHvZAa1c0YlwQopSUyoW0JWEsBb2vZB7pV2P7mzF629B8l3uKH8BUK9oBwjuuvwsVZARX3swCpHNXgWrIy6l0HcBCh8eCneQrKZBZAQ5ljXxHlr0gShI2gpmucXeym530NKVKgVLSzqOG6NoSn5bhKHKp9x8CDBMb77RZBS4N9sZD'
# page_id = '108844705633926'
#
# response_data = get_facebook_posts(access_token, page_id)
#
# if response_data:
#     post_info_list = extract_post_info(response_data)
#     print("\n[LOG SYSTEM]\nPost Information Extracted:")
#     for post in post_info_list:
#         print(f"\n[LOG SYSTEM]\nID: {post['id']}, Message: {post['message']}, Created Time: {post['created_time']}, Full Picture: {post['full_picture']}")
# else:
#     print("\n[LOG SYSTEM]\nFailed to retrieve posts information.")


########################################################################################
def get_facebook_comments(access_token, post_id):
    """
    Hàm lấy danh sách các bình luận từ một bài viết trên Facebook.

    :param access_token: Access Token của người dùng
    :param post_id: ID của bài viết mà bạn muốn lấy bình luận
    :return: JSON response từ API nếu thành công, None nếu thất bại
    """
    url = f"https://graph.facebook.com/v20.0/{post_id}/comments?fields=id,message,created_time,from{{id,name,picture}},attachment"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


def extract_comment_info(data):
    """
    Hàm trích xuất các thông tin từ JSON trả về: id, message, created_time, from{id, name}, attachment (nếu có).

    :param data: Dữ liệu JSON trả về từ API Facebook
    :return: Danh sách các bình luận với các trường id, message, created_time, from{id, name} và attachment (nếu có)
    """
    comment_list = []

    if "data" in data:
        for comment in data["data"]:
            comment_info = {
                "id": comment.get("id", ""),
                "message": comment.get("message", ""),
                "created_time": comment.get("created_time", ""),
                "from": {
                    "id": comment.get("from", {}).get("id", ""),
                    "name": comment.get("from", {}).get("name", ""),
                },
                "attachment": comment.get(
                    "attachment", None
                ),  # Sử dụng None nếu không có
            }
            comment_list.append(comment_info)

    return comment_list


# Sử dụng hàm
# access_token = 'EAAOZCGoDpkUwBOyQU02odnh3RMx1SK119NILdaijHvZAa1c0YlwQopSUyoW0JWEsBb2vZB7pV2P7mzF629B8l3uKH8BUK9oBwjuuvwsVZARX3swCpHNXgWrIy6l0HcBCh8eCneQrKZBZAQ5ljXxHlr0gShI2gpmucXeym530NKVKgVLSzqOG6NoSn5bhKHKp9x8CDBMb77RZBS4N9sZD'
# post_id = '108844705633926_160927007083914'
#
# response_data = get_facebook_comments(access_token, post_id)
#
# if response_data:
#     comment_info_list = extract_comment_info(response_data)
#     print("\n[LOG SYSTEM]\nComment Information Extracted:")
#     for comment in comment_info_list:
#         print(f"\n[LOG SYSTEM]\nID: {comment['id']}, Message: {comment['message']}, Created Time: {comment['created_time']}, "
#               f"From: {comment['from']['id']} - {comment['from']['name']}, Attachment: {comment['attachment']}")
# else:
#     print("\n[LOG SYSTEM]\nFailed to retrieve comments information.")


########################################################################################
def reply_to_comment(access_token, parent_comment_id, message):
    """
    Hàm tạo bình luận con (reply) vào một bình luận trên Facebook.

    :param access_token: Access Token của người dùng
    :param parent_comment_id: ID của bình luận cha mà bạn muốn bình luận vào
    :param message: Nội dung của bình luận
    :return: ID của bình luận vừa được tạo nếu thành công, None nếu thất bại
    """
    url = f"https://graph.facebook.com/v20.0/{parent_comment_id}/comments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {"message": message}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        if response.status_code == 200:
            return response.json().get("id", None)
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred: {str(e)}")
        return None


# Sử dụng hàm
# access_token = 'EAAOZCGoDpkUwBOyQU02odnh3RMx1SK119NILdaijHvZAa1c0YlwQopSUyoW0JWEsBb2vZB7pV2P7mzF629B8l3uKH8BUK9oBwjuuvwsVZARX3swCpHNXgWrIy6l0HcBCh8eCneQrKZBZAQ5ljXxHlr0gShI2gpmucXeym530NKVKgVLSzqOG6NoSn5bhKHKp9x8CDBMb77RZBS4N9sZD'
# parent_comment_id = '160927007083914_654176506858230'
# message = 'Cảm ơn bạn đã bình luận!'
#
# # Gọi hàm để tạo bình luận
# new_comment_id = reply_to_comment(access_token, parent_comment_id, message)
#
# if new_comment_id:
#     print(f"\n[LOG SYSTEM]\nSuccessfully created a reply comment with ID: {new_comment_id}")
# else:
#     print("\n[LOG SYSTEM]\nFailed to create a reply comment.")


# ============================================== FACEBOOK CONNECT ==============================================
################################################################################################################
def send_action_facebook_messenger(page_id, page_access_token, sender_id, status):
    """
    Hàm gửi tin nhắn Facebook.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    if status:
        action = "typing_on"
    else:
        action = "typing_off"

    data = {"recipient": {"id": sender_id}, "sender_action": action}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"\n[LOG SYSTEM]\nError: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred send_action: {str(e)}")
        return None


def split_sentences_(text):
    """
    Tách câu từ văn bản cho trước.
    """
    # Bước 1: Thay thế nhiều dấu '*' liên tiếp thành 1 dấu '*'
    text = re.sub(r"\*\*+", "*", text, flags=re.UNICODE)

    # Bước 2: Sử dụng regex để tách câu dựa trên dấu chấm, dấu chấm than, dấu chấm hỏi.
    # Cẩn thận không tách khi dấu chấm nằm sau chữ số (ví dụ: số thứ tự)
    pattern = re.compile(r"(?<!\b\d)\.(?=\s|$)|(?<=[!?])\s*", flags=re.UNICODE)
    sentences = pattern.split(text)

    # Loại bỏ khoảng trắng thừa và các câu rỗng
    cleaned_sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

    # Nếu phần tử cuối cùng chỉ chứa ký tự không phải chữ hoặc số, gộp vào câu trước
    if len(cleaned_sentences) > 1:
        last_part = cleaned_sentences[-1]
        if re.match(r"^[^\w\s]+$", last_part, flags=re.UNICODE):
            cleaned_sentences[-2] += f" {last_part}"
            cleaned_sentences.pop()

    # Nếu câu có chứa danh sách (số thứ tự hoặc dấu '-' dùng trong liệt kê) thì tách riêng theo dòng
    final_sentences = []
    for sentence in cleaned_sentences:
        if re.search(r"^\d+\.\s|-\s", sentence, flags=re.MULTILINE):
            items = sentence.split("\n")
            final_sentences.extend([item.strip() for item in items if item.strip()])
        else:
            final_sentences.append(sentence)

    # Gộp lại các dòng bắt đầu bằng '-' hoặc '+' với câu phía trên
    processed_sentences = []
    for sentence in final_sentences:
        if processed_sentences and (
            sentence.startswith("-") or sentence.startswith("+")
        ):
            processed_sentences[-1] += "\n" + sentence
        else:
            processed_sentences.append(sentence)

    return processed_sentences


# # Hàm gửi tin nhắn Facebook Messenger
# def send_facebook_messenger(page_id, page_access_token, sender_id, message, is_button=False):
#     """
#     Hàm gửi tin nhắn đến Facebook Messenger với văn bản và ảnh base64.
#     """

#     # URL gửi tin nhắn
#     global image_path
#     url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

#     # Header cần thiết cho yêu cầu
#     headers = {
#         'Authorization': f'Bearer {page_access_token}',
#     }

#     def split_sentences(text):
#         """
#         Tách câu từ văn bản cho trước, đồng thời bảo vệ các liên kết (URL) không bị tách riêng.
#         """

#         # Bước 0: Bảo vệ các URL bằng cách thay thế tạm thời bằng placeholder
#         url_regex = re.compile(r'\b(?:https?://|www\.)\S+\b', flags=re.UNICODE)
#         placeholders = {}

#         def replacer(match):
#             placeholder = f"__URL_PLACEHOLDER_{len(placeholders)}__"
#             placeholders[placeholder] = match.group(0)
#             return placeholder

#         text = url_regex.sub(replacer, text)

#         # Bước 1: Thay thế nhiều dấu '*' liên tiếp thành 1 dấu '*'
#         text = re.sub(r'\*\*+', '*', text, flags=re.UNICODE)

#         # Bước 2: Sử dụng regex để tách câu dựa trên dấu chấm, dấu chấm than, dấu chấm hỏi.
#         # Chú ý: Không tách khi dấu chấm nằm sau chữ số (ví dụ: số thứ tự)
#         pattern = re.compile(r'(?<!\b\d)\.(?=\s|$)|(?<=[!?])\s*', flags=re.UNICODE)
#         sentences = pattern.split(text)

#         # Loại bỏ khoảng trắng thừa và các câu rỗng
#         cleaned_sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

#         # Nếu phần tử cuối cùng chỉ chứa ký tự không phải chữ hoặc số, gộp vào câu trước
#         if len(cleaned_sentences) > 1:
#             last_part = cleaned_sentences[-1]
#             if re.match(r'^[^\w\s]+$', last_part, flags=re.UNICODE):
#                 cleaned_sentences[-2] += f" {last_part}"
#                 cleaned_sentences.pop()

#         # Nếu câu có chứa danh sách (số thứ tự hoặc dấu '-' dùng trong liệt kê) thì tách riêng theo dòng
#         final_sentences = []
#         for sentence in cleaned_sentences:
#             if re.search(r'^\d+\.\s|-\s', sentence, flags=re.MULTILINE):
#                 items = sentence.split('\n')
#                 final_sentences.extend([item.strip() for item in items if item.strip()])
#             else:
#                 final_sentences.append(sentence)

#         # Gộp lại các dòng bắt đầu bằng '-' hoặc '+' với câu phía trên
#         processed_sentences = []
#         for sentence in final_sentences:
#             if processed_sentences and (sentence.startswith('-') or sentence.startswith('+')):
#                 processed_sentences[-1] += "\n" + sentence
#             else:
#                 processed_sentences.append(sentence)

#         # Cuối cùng, khôi phục lại các URL từ placeholder
#         def restore_placeholders(sentence):
#             for placeholder, url in placeholders.items():
#                 sentence = sentence.replace(placeholder, url)
#             return sentence

#         processed_sentences = [restore_placeholders(sentence) for sentence in processed_sentences]

#         return processed_sentences

#     # Tách message thành các câu nhỏ
#     messages = split_sentences(message)
#     # print("\n[LOG SYSTEM]\nMessages split:", messages)

#     # Gửi từng câu nhỏ
#     for msg in messages:
#         if not msg:
#             continue

#         msg = msg.replace("\\n", "\n").replace("\"", "'")
#         send_action_facebook_messenger(page_id, page_access_token, sender_id, True)
#         msg = clean_response(msg)

#         data = {
#             "recipient": {
#                 "id": sender_id
#             },
#             "messaging_type": "RESPONSE",
#             "message": {
#                 "text": msg
#             }
#         }

#         try:
#             response = requests.post(url, headers=headers, json=data)
#             if response.status_code != 200:
#                 print(f"\n[LOG SYSTEM]\nFailed to send message. Status code: {response.status_code}, Response: {response.text}")
#         except Exception as e:
#             print(f"\n[LOG SYSTEM]\nAn exception occurred message: {str(e)}")
#         finally:
#             send_action_facebook_messenger(page_id, page_access_token, sender_id, False)

#     return


# Hàm trả về option button tùy chỉnh
def button_option_facebook_messenger():
    buttons_1 = [
        {
            "type": "postback",
            "title": "Thông tin về sản phẩm",
            "payload": "CONSULT_PRODUCT",
        },
        {"type": "postback", "title": "Tình trạng đơn hàng", "payload": "CHECK_ORDER"},
        {"type": "postback", "title": "Chính sách bảo hành", "payload": "WARRANTYY_POLICY"},
    ]
    buttons_2 = [
        {
            "type": "postback",
            "title": "Tình trạng đơn hàng",
            "payload": "CHECK_ORDER",
        },
        {
            "type": "postback",
            "title": "Nhóm khách hàng thân thiết",
            "payload": "KAT_GROUP",
        },
        {"type": "postback", "title": "Khác", "payload": "DIFFERENT"},
    ]
    return buttons_1, buttons_2


def send_facebook_button(
    page_id, page_access_token, sender_id, *button_groups_with_text
):
    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    # Header cần thiết cho yêu cầu
    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }
    send_action_facebook_messenger(page_id, page_access_token, sender_id, True)

    for idx, (text, button_group) in enumerate(button_groups_with_text):
        payload = {
            "recipient": {"id": sender_id},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": text,  # có thể cho message ở payload đầu tiên nếu muốn
                        "buttons": button_group,
                    },
                }
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code != 200:
                print(
                    f"[{idx+1}] Failed to send message. Status code: {response.status_code}, Response: {response.text}"
                )
        except Exception as e:
            print(f"\n[LOG SYSTEM]\n[{idx+1}] Exception occurred while sending button group: {str(e)}")
        finally:
            send_action_facebook_messenger(page_id, page_access_token, sender_id, False)


# Hàm gửi tin nhắn Facebook Messenger
def send_facebook_messenger(
    page_id, page_access_token, sender_id, message
):
    """
    Hàm gửi tin nhắn đến Facebook Messenger với văn bản và ảnh base64.
    """

    # URL gửi tin nhắn
    global image_path
    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    # Header cần thiết cho yêu cầu
    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    def split_sentences(text):
        """
        Tách câu từ văn bản cho trước, đồng thời bảo vệ các liên kết (URL) không bị tách riêng.
        """

        # Bước 0: Bảo vệ các URL bằng cách thay thế tạm thời bằng placeholder
        url_regex = re.compile(r"\b(?:https?://|www\.)\S+\b", flags=re.UNICODE)
        placeholders = {}

        def replacer(match):
            placeholder = f"__URL_PLACEHOLDER_{len(placeholders)}__"
            placeholders[placeholder] = match.group(0)
            return placeholder

        text = url_regex.sub(replacer, text)

        # Bước 1: Thay thế nhiều dấu '*' liên tiếp thành 1 dấu '*'
        text = re.sub(r"\*\*+", "*", text, flags=re.UNICODE)

        # Bước 2: Sử dụng regex để tách câu dựa trên dấu chấm, dấu chấm than, dấu chấm hỏi.
        # Chú ý: Không tách khi dấu chấm nằm sau chữ số (ví dụ: số thứ tự)
        pattern = re.compile(r"(?<!\b\d)\.(?=\s|$)|(?<=[!?])\s*", flags=re.UNICODE)
        sentences = pattern.split(text)

        # Loại bỏ khoảng trắng thừa và các câu rỗng
        cleaned_sentences = [
            sentence.strip() for sentence in sentences if sentence.strip()
        ]

        # Nếu phần tử cuối cùng chỉ chứa ký tự không phải chữ hoặc số, gộp vào câu trước
        if len(cleaned_sentences) > 1:
            last_part = cleaned_sentences[-1]
            if re.match(r"^[^\w\s]+$", last_part, flags=re.UNICODE):
                cleaned_sentences[-2] += f" {last_part}"
                cleaned_sentences.pop()

        # Nếu câu có chứa danh sách (số thứ tự hoặc dấu '-' dùng trong liệt kê) thì tách riêng theo dòng
        final_sentences = []
        for sentence in cleaned_sentences:
            if re.search(r"^\d+\.\s|-\s", sentence, flags=re.MULTILINE):
                items = sentence.split("\n")
                final_sentences.extend([item.strip() for item in items if item.strip()])
            else:
                final_sentences.append(sentence)

        # Gộp lại các dòng bắt đầu bằng '-' hoặc '+' với câu phía trên
        processed_sentences = []
        for sentence in final_sentences:
            if processed_sentences and (
                sentence.startswith("-") or sentence.startswith("+")
            ):
                processed_sentences[-1] += "\n" + sentence
            else:
                processed_sentences.append(sentence)

        # Cuối cùng, khôi phục lại các URL từ placeholder
        def restore_placeholders(sentence):
            for placeholder, url in placeholders.items():
                sentence = sentence.replace(placeholder, url)
            return sentence

        processed_sentences = [
            restore_placeholders(sentence) for sentence in processed_sentences
        ]

        return processed_sentences

    # Tách message thành các câu nhỏ
    messages = split_sentences(message)
    # print("\n[LOG SYSTEM]\nMessages split:", messages)

    # Gửi từng câu nhỏ
    for msg in messages:
        if not msg:
            continue

        msg = msg.replace("\\n", "\n").replace('"', "'")
        send_action_facebook_messenger(page_id, page_access_token, sender_id, True)
        msg = clean_response(msg)

        data = {
            "recipient": {"id": sender_id},
            "messaging_type": "RESPONSE",
            "message": {"text": msg},
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code != 200:
                print(
                    f"Failed to send message. Status code: {response.status_code}, Response: {response.text}"
                )
        except Exception as e:
            print(f"\n[LOG SYSTEM]\nAn exception occurred message: {str(e)}")
        finally:
            send_action_facebook_messenger(page_id, page_access_token, sender_id, False)
    return


def clean_response(text):
    # Xóa phần `"response": "` ở đầu chuỗi
    text = re.sub(r'^"response": "', "", text, count=1)

    # Xóa phần `", "mekongai_page": "..."` ở cuối chuỗi (nếu có)
    text = re.sub(r'", "mekongai_page": ".*?"$', "", text, count=1)

    # Nếu chuỗi kết thúc bằng dấu `"`, loại bỏ nó
    text = re.sub(r'"$', "", text, count=1)

    return text


def send_facebook_messenger_images(
    page_id, page_access_token, sender_id, base64_images, suggest
):
    """
    Hàm gửi tin nhắn đến Facebook Messenger với văn bản và ảnh base64.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    # Header cần thiết cho yêu cầu
    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    print(f"\n[LOG SYSTEM]\nLength of base64_images: {len(base64_images)}")

    attachments = []
    image_paths = []

    # Nếu có danh sách ảnh base64, tiến hành xử lý và gửi từng ảnh
    if base64_images:
        local_folder = constant.IMAGE_TMP_PATH  # Thư mục tạm trên VPS

        # Tạo thư mục tạm nếu chưa tồn tại
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        image_filenames = []
        
        for image_base64 in base64_images:
            try:
                send_action_facebook_messenger(
                    page_id, page_access_token, sender_id, True
                )

                # Tạo tên file với thời gian hiện tại
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"image_{timestamp}.png"
                image_path = os.path.join(local_folder, image_filename)

                image_paths.append(image_path)

                # Lưu base64 thành file ảnh tạm thời
                with open(image_path, "wb") as image_file:
                    image_file.write(base64.b64decode(image_base64))

                # Tạo URL cho ảnh
                image_url = f"{constant.PUBLIC_API}/api/v1/facebook/images-tmp/resources/tmp/{image_filename}"
                # print(f"\n[LOG SYSTEM]\nTemporary image URL: {image_url}")

                if image_filename not in image_filenames:
                    attachments.append({
                        "type": "image",
                        "payload": {"is_reusable": True, "url": image_url},
                    })
                    image_filenames.append(image_filename)
                    
            except Exception as e:
                print(f"\n[LOG SYSTEM]\nAn exception occurred while sending image: {str(e)}")

    try:
        if attachments:
            send_action_facebook_messenger(
                page_id, page_access_token, sender_id, True
            )

            # Gửi tin nhắn chứa ảnh lên Facebook Messenger
            data = {
                "recipient": {"id": sender_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachments": attachments
                },
            }

            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                # print(f"\n[LOG SYSTEM]\nSuccessfully sent image: {image_url}")
                pass
            else:
                print(
                    f"Failed to send image. Status code: {response.status_code}, Response: {response.text}"
                )

    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred while sending image: {str(e)}")

    finally:
        send_action_facebook_messenger(
            page_id, page_access_token, sender_id, False
        )

        if image_paths:
            for image_path in image_paths:
                # Xóa ảnh tạm sau khi gửi xong
                try:
                    if os.path.exists(image_path):
                        os.remove(image_path)
                        # print(f"\n[LOG SYSTEM]\nTemporary file {image_path} has been deleted.")
                except Exception as e:
                    print(f"\n[LOG SYSTEM]\nFailed to delete file {image_path}: {str(e)}")

    # if suggest:
    #     try:
    #         send_action_facebook_messenger(page_id, page_access_token, sender_id, True)
    #
    #         buttons = []
    #         for suggest_item in suggest:
    #             button = {
    #                 "type": "postback",
    #                 "title": suggest_item,
    #                 "payload": "POSTBACK_PAYLOAD"
    #             }
    #             buttons.append(button)
    #
    #         data = {
    #             "recipient": {
    #                 "id": sender_id
    #             },
    #             "messaging_type": "RESPONSE",
    #             "message": {
    #                 "attachment": {
    #                     "type": "template",
    #                     "payload": {
    #                         "template_type": "generic",
    #                         "elements": [
    #                             {
    #                                 "title": "Gợi ý",
    #                                 "subtitle": "Một số gợi ý cho bạn",
    #                                 "buttons": buttons
    #                             }
    #
    #                         ]
    #                     }
    #                 }
    #             }
    #         }
    #
    #         try:
    #             response = requests.post(url, headers=headers, json=data)
    #             if response.status_code != 200:
    #                 print(f"\n[LOG SYSTEM]\nFailed to send message. Status code: {response.status_code}, Response: {response.text}")
    #         except Exception as e:
    #             print(f"\n[LOG SYSTEM]\nAn exception occurred suggest: {str(e)}")
    #
    #     except Exception as e:
    #         print(f"\n[LOG SYSTEM]\nAn exception occurred while sending suggest: {str(e)}")
    #
    #     finally:
    #         send_action_facebook_messenger(page_id, page_access_token, sender_id, False)

    return


def subscribed_apps(user_id, page_id, page_access_token, _type, action):
    user_subscribed_file, subscribed = get_subscribed_apps(user_id, page_id)

    # Đảm bảo `type` và `action` là danh sách
    if not isinstance(_type, list):
        _type = [_type]
    if not isinstance(action, list):
        action = [action]

    # Xử lý cập nhật từng mục trong danh sách
    for t, a in zip(_type, action):
        if t == "messages":
            subscribed["messages"] = a
        elif t == "comments":
            subscribed["comments"] = a

    # Trường hợp dữ liệu ban đầu rỗng, thiết lập mặc định
    if not subscribed:
        subscribed = {"messages": 0, "comments": 0}
        for t, a in zip(_type, action):
            if t == "messages":
                subscribed["messages"] = a
            elif t == "comments":
                subscribed["comments"] = a

    # Lưu dữ liệu cập nhật vào file
    with open(user_subscribed_file, "w", encoding="utf-8") as file:
        json.dump(subscribed, file, ensure_ascii=False, indent=4)

    url = f"https://graph.facebook.com/{page_id}/subscribed_apps"

    if subscribed["messages"] == 1 and subscribed["comments"] == 1:
        subscribed_fields = "feed,messages,messaging_postbacks"
    elif subscribed["messages"] == 1:
        subscribed_fields = "messages,messaging_postbacks"
    elif subscribed["comments"] == 1:
        subscribed_fields = "feed"
    else:
        subscribed_fields = "name"

    payload = {
        "subscribed_fields": subscribed_fields,
        "access_token": page_access_token,
    }

    try:
        # Gửi yêu cầu POST
        response = requests.post(url, data=payload, timeout=120)

        if response.status_code == 200:
            return True, response.json(), subscribed
        else:
            return False, response.json(), subscribed
    except Exception as e:
        return False, str(e), subscribed


def get_subscribed_apps(user_id, page_id):
    try:
        path = (
                constant.DATAS_PUBLIC_PATH
                + "/"
                + constant.NAME_BOT_FACEBOOK
                + "/"
                + constant.SUBSCRIBED
        )
        os.makedirs(path, exist_ok=True)

        user_subscribed_file = os.path.join(
            path, f"subscribed_{user_id}_{page_id}.json"
        )

        subscribed = {"messages": 0, "comments": 0}

        if os.path.exists(user_subscribed_file):
            with open(user_subscribed_file, "r", encoding="utf-8") as file:
                try:
                    subscribed = json.load(file)
                except json.JSONDecodeError:
                    pass

        return user_subscribed_file, subscribed
    except Exception as e:
        print(f"\n[LOG SYSTEM]\nAn exception occurred get_subscribed_apps: {str(e)}")
        return {"messages": 0, "comments": 0}, []
