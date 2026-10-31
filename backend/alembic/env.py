import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 保证可以从 backend/ 目录导入 app 包（无论从哪个目录启动 alembic）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 接入本项目 ORM 模型与数据库连接（backend/app/db.py）
# 导入 app.models 会把全部 12 张表注册到 Base.metadata，供 autogenerate / create_all 使用
from app import models  # noqa: F401,E402
from app.db import Base, DATABASE_URL  # noqa: E402

target_metadata = Base.metadata

# 数据库连接以 app/db.py 的 DATABASE_URL 为准（.env 未配置时回落 docker-compose 默认值）
# DATABASE_URL 来自环境变量 / .env，可能含 URL 编码字符（如口令里的 %40）。
# ConfigParser 默认启用 % 插值，直接把裸 % 交给 set_main_option 会抛
# ValueError: invalid interpolation syntax；转义成 %% 后读回仍是原值。
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    """以离线模式跑迁移。

    这种模式下 context 只配一个 URL、不建 Engine（其实给 Engine 也行）。
    既然跳过了 Engine 创建，连 DBAPI 都不需要有。这里调 context.execute() 会把
    SQL 字符串直接打到脚本输出。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式跑迁移。

    这种模式要建 Engine，并把连接关联到 context。
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
