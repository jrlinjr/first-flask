"""
migration 守門：確保 migrations/versions 建出來的資料表，跟 models 定義的一模一樣

改了 models/ 卻忘了產生 migration（flask --app main db migrate -m "..."），這裡就會失敗。
"""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect, text

from conftest import ROOT
from utils.extensions import db

MIGRATIONS_DIR = str(ROOT / "migrations")


def _drop_everything():
    db.drop_all()
    with db.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_migrations_match_models(app):
    with app.app_context():
        db.session.remove()
        try:
            # 1. 從空資料庫套用全部 migration
            _drop_everything()
            upgrade(directory=MIGRATIONS_DIR)

            # 2. 跟 models 比對，不能有任何差異
            with db.engine.connect() as conn:
                context = MigrationContext.configure(conn, opts={"compare_type": True})
                diffs = compare_metadata(context, db.metadata)
            assert diffs == [], f"models 跟 migration 不一致，請產生新的 migration：{diffs}"

            # 3. 全部退回去，只剩 alembic_version
            downgrade(directory=MIGRATIONS_DIR, revision="base")
            assert inspect(db.engine).get_table_names() == ["alembic_version"]
        finally:
            # 還原成其他測試用的狀態（create_all 建的表）
            _drop_everything()
            db.create_all()
