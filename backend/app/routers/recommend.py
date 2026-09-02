"""参数推荐 API"""
import sys
from pathlib import Path

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.schemas import RecommendRequest
from app.services.recommend_service import recommend as run_recommend

router = APIRouter(prefix="/api/recommend", tags=["参数推荐"])


@router.post("")
def recommend(req: RecommendRequest):
    """参数推荐: 输入产品类型/材料牌号/设备型号 -> 推荐工艺参数(Pareto 最优)"""
    return run_recommend(req.product_type, req.material, req.equipment)
