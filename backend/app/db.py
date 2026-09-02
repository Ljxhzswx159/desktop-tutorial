"""数据访问层:SQLAlchemy(SQLite 默认, 可切换到 PostgreSQL)

表:
  production_records - 生产数据记录(操作员录入/推荐参数实际执行结果)
  feedback_records   - 人工修正反馈(老师傅手动调整, 用于模型在线学习)
  model_versions     - 模型版本与训练历史

说明: 方案设计中的 PostgreSQL 可通过修改 config.DB_URL 切换,
如 "postgresql+psycopg://user:pwd@localhost/injection"。
"""
import datetime as dt
import sys
from pathlib import Path

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            sessionmaker)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
from app.config import DB_URL, PROCESSED_DIR

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ProductionRecord(Base):
    __tablename__ = "production_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    product_type: Mapped[str] = mapped_column(String(50), default="")
    material: Mapped[str] = mapped_column(String(20))
    equipment: Mapped[str] = mapped_column(String(50), default="")
    operator: Mapped[str] = mapped_column(String(50), default="")
    # 13 个工艺特征
    melt_temp: Mapped[float] = mapped_column(Float)
    mold_temp: Mapped[float] = mapped_column(Float)
    time_to_fill: Mapped[float] = mapped_column(Float)
    plasticizing_time: Mapped[float] = mapped_column(Float)
    cycle_time: Mapped[float] = mapped_column(Float)
    closing_force: Mapped[float] = mapped_column(Float)
    clamp_force_peak: Mapped[float] = mapped_column(Float)
    torque_peak: Mapped[float] = mapped_column(Float)
    torque_mean: Mapped[float] = mapped_column(Float)
    back_pressure_peak: Mapped[float] = mapped_column(Float)
    injection_pressure_peak: Mapped[float] = mapped_column(Float)
    screw_pos_end_hold: Mapped[float] = mapped_column(Float)
    shot_volume: Mapped[float] = mapped_column(Float)
    # 检测结果
    quality: Mapped[int] = mapped_column(Integer, default=0)   # 0/1
    defect_type: Mapped[str] = mapped_column(String(20), default="")
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # manual=人工录入 recommended=执行推荐参数 corrected=修正后执行
    note: Mapped[str] = mapped_column(String(200), default="")


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    material: Mapped[str] = mapped_column(String(20))
    operator: Mapped[str] = mapped_column(String(50), default="")
    original_params: Mapped[str] = mapped_column(Text)   # JSON
    corrected_params: Mapped[str] = mapped_column(Text)  # JSON
    quality_after: Mapped[int] = mapped_column(Integer, default=1)  # 修正后是否合格
    defect_after: Mapped[str] = mapped_column(String(20), default="")
    reason: Mapped[str] = mapped_column(String(200), default="")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否已用于再训练


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trained_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    samples: Mapped[int] = mapped_column(Integer, default=0)
    feedback_used: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    note: Mapped[str] = mapped_column(String(200), default="")


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
