"""Pydantic 请求/响应模型"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ParamsInput(BaseModel):
    """13 个工艺特征输入"""
    melt_temp: float = Field(..., description="熔体温度 °C")
    mold_temp: float = Field(..., description="模具温度 °C")
    time_to_fill: float = Field(..., description="填充时间 s")
    plasticizing_time: float = Field(..., description="塑化时间 s")
    cycle_time: float = Field(..., description="循环时间 s")
    closing_force: float = Field(..., description="合模力 kN")
    clamp_force_peak: float = Field(..., description="合模力峰值 kN")
    torque_peak: float = Field(..., description="扭矩峰值 Nm")
    torque_mean: float = Field(..., description="扭矩均值 Nm")
    back_pressure_peak: float = Field(..., description="背压峰值 bar")
    injection_pressure_peak: float = Field(..., description="注射压力峰值 bar")
    screw_pos_end_hold: float = Field(..., description="保压结束螺杆位置 mm")
    shot_volume: float = Field(..., description="射胶量 cm³")

    def dict_params(self) -> dict:
        return self.model_dump()


class RecommendRequest(BaseModel):
    product_type: str = "汽车内饰件"
    material: str = "ABS"
    equipment: str = "海天MA1200"


class PredictRequest(BaseModel):
    material: str = "ABS"
    params: ParamsInput


class RecordCreate(ParamsInput):
    product_type: str = ""
    material: str = "ABS"
    equipment: str = ""
    operator: str = ""
    quality: int = Field(0, ge=0, le=1)
    defect_type: str = ""
    source: str = "manual"
    note: str = ""


class FeedbackCreate(BaseModel):
    material: str
    operator: str = ""
    original_params: dict[str, Any]
    corrected_params: dict[str, Any]
    quality_after: int = Field(1, ge=0, le=1)
    defect_after: str = ""
    reason: str = ""


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class DiagnoseRequest(BaseModel):
    material: str = "ABS"
    params: ParamsInput
