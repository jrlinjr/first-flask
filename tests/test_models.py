"""model 的預設值"""
import time
from datetime import date


def test_time_defaults_are_evaluated_per_record(alice, M, db_session):
    # 時間預設值要在每次寫入時才算，不能是程式啟動那一刻的固定值
    # MySQL DATETIME 只到秒，所以中間隔 1 秒
    first = M.A1cRecord(user_id=alice.id, a1cs=6.5, record_date=date(2025, 1, 1))
    db_session.add(first)
    db_session.commit()

    time.sleep(1)
    second = M.A1cRecord(user_id=alice.id, a1cs=7.0, record_date=date(2025, 1, 2))
    db_session.add(second)
    db_session.commit()

    assert second.created_at > first.created_at
    assert second.updated_at > first.updated_at

    # 更新時 updated_at 也要跟著變
    time.sleep(1)
    first.a1cs = 6.8
    db_session.commit()
    assert first.updated_at > first.created_at
