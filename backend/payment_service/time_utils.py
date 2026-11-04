from datetime import datetime
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def now_vn():
    return datetime.now(VN_TZ).replace(tzinfo=None)