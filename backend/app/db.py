"""数据库统一入口。

- 本地开发默认使用 SQLite 文件数据库（零依赖，无需 Docker / WSL / PostgreSQL）。
- 团队开发或部署时在 backend/app/.env 中设置 DATABASE_URL 指向 PostgreSQL 即可切换。
- Base 是所有 ORM 模型的公共基类，模型定义见 app/models/ 目录（12 张表）。

两种模式示例：
    # 本地开发（默认，无需任何配置）
    DATABASE_URL=sqlite:///./security_bayes.db

    # 团队 / 部署（在 .env 中配置）
    DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
"""
import os

import dotenv
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# 跨数据库主键/外键类型
# PostgreSQL: BigInteger (8 字节, 兼容原设计)
# SQLite:      Integer   (4 字节, INTEGER PRIMARY KEY 才支持自增)
# ---------------------------------------------------------------------------
PkType = BigInteger().with_variant(Integer(), 'sqlite')

dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # 本地开发默认：SQLite 文件数据库（零配置开箱即用）
    "sqlite:///./security_bayes.db",
)

# SQLite 需要 check_same_thread=False 才能在 FastAPI 多线程下正常工作
_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类（SQLAlchemy 2.x 声明式）。"""


def get_db():
    """FastAPI 依赖注入用：每次请求一个会话，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
