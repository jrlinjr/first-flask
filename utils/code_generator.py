"""驗證碼、隨機密碼、好友邀請碼的產生"""
import random
import string


def generate_verification_code() -> str:
    """6 位數字驗證碼"""
    return str(random.randint(100000, 999999))


def generate_random_password(length: int = 8) -> str:
    """隨機密碼（大小寫英文 + 數字）

    choices() 會從字元池中隨機抽 k 個（可重複）
    """
    pool = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return "".join(random.choices(pool, k=length))


def generate_invite_code(user_id) -> str:
    """用 user id 算出固定的 8 碼好友邀請碼

    前 4 碼 = user id 補零；後 4 碼 = (id * 7 + 1000) % 9000 + 1000
    例：id 1 → "0001" + "2007" = "00012007"
    """
    try:
        user_id_int = int(user_id)
        suffix = (user_id_int * 7 + 1000) % 9000 + 1000
        return f"{user_id_int:04d}" + f"{suffix:04d}"
    except Exception:
        return f"{int(user_id):08d}"
