from datetime import datetime, timezone, timedelta

vn_timezone = timezone(timedelta(hours=7))


def get_current_vn_time():
    # Lấy thời gian hiện tại theo múi giờ VN
    current_time = datetime.now(vn_timezone)

    # Định dạng thời gian theo định dạng mong muốn
    formatted_time = current_time.strftime("%d-%m-%Y %H:%M:%S")

    return formatted_time



