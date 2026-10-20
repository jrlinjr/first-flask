"""寄信"""
from flask_mail import Message

from shared import env
from utils.extensions import mail
from utils.logger import logger


def send_mail(subject: str, recipient: str, body: str) -> None:
    """寄一封純文字信。寄失敗會丟例外，由呼叫端決定怎麼處理

    MAIL_SUPPRESS_SEND=1 時不會真的寄出，信件內容改寫進 log（看得到驗證碼，方便開發測試）。
    正式環境不要開，不然驗證碼、新密碼會留在 log 裡。
    """
    if env.mail_suppress_send:
        body_one_line = body.replace("\n", " ")
        logger.info(f"[不寄信模式] 收件者：{recipient}｜主旨：{subject}｜內容：{body_one_line}")

    # 建立一個 Flask-Mail 的郵件物件，再交給 mail 寄出（不寄信模式下 Flask-Mail 會略過實際寄送）
    message = Message(subject=subject, recipients=[recipient], body=body)
    mail.send(message)


def send_verification_code(email: str, code: str) -> None:
    """寄註冊 / 重寄用的驗證碼信"""
    send_mail("帳號驗證", email, f"您的驗證碼是: {code}，15分鐘內有效。")


def send_new_password(email: str, new_password: str) -> None:
    """寄忘記密碼產生的新密碼"""
    send_mail("忘記密碼 - 新密碼", email, f"您的新密碼是: {new_password}\n\n請登入後立即修改密碼。")
