"""驗證碼、隨機密碼的產生（utils/code_generator.py）"""
import random
import string

from utils.code_generator import generate_verification_code, generate_random_password


def test_verification_code_format():
    for _ in range(200):
        code = generate_verification_code()
        assert len(code) == 6
        assert code.isdigit()
        assert 100000 <= int(code) <= 999999


def test_random_password_format():
    pool = set(string.ascii_letters + string.digits)
    for _ in range(200):
        password = generate_random_password()
        assert len(password) == 8
        assert set(password) <= pool
    assert len(generate_random_password(12)) == 12


def test_codes_cannot_be_reproduced_by_seeding_random():
    # random 是可預測的偽亂數，同一個 seed 會產生同一串結果；secrets 不受 random.seed 影響
    random.seed(1234)
    first = [generate_verification_code() for _ in range(5)] + [generate_random_password() for _ in range(5)]
    random.seed(1234)
    second = [generate_verification_code() for _ in range(5)] + [generate_random_password() for _ in range(5)]
    assert first != second
