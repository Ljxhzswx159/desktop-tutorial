"""FastAPI 主应用:面向注塑成型过程的智能工艺参数优化与质量预测系统

启动: cd backend && py -3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
文档: http://localhost:8000/docs
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
from app.db import init_db
from app.routers import dashboard, feedback, knowledge, predict, recommend, records

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="注塑成型智能工艺参数优化与质量预测系统",
    description="功能模块: 参数推荐 | 质量预测 | 知识检索 | 数据记录 | 反馈修正 | 数据看板",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- API 路由 ----------
app.include_router(recommend.router)
app.include_router(predict.router)
app.include_router(knowledge.router)
app.include_router(records.router)
app.include_router(feedback.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "injection-molding-ai", "version": "1.0.0"}


@app.get("/api/meta")
def meta():
    """前端下拉框选项等静态元信息"""
    from app.config import EQUIPMENTS, MATERIALS, PRODUCT_TYPES
    from app.services.model_service import ModelService
    return {
        "materials": [{"key": k, "label": v["label"]} for k, v in MATERIALS.items()],
        "product_types": PRODUCT_TYPES,
        "equipments": EQUIPMENTS,
        "model_name": ModelService.get().meta["quality_model"],
    }


# ---------- 前端静态页面 ----------
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"),
              name="assets")
    app.mount("/libs", StaticFiles(directory=FRONTEND_DIR / "libs"), name="libs")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
