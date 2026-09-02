# 面向注塑成型过程的智能工艺参数优化与质量预测系统

制造智能技术课程设计。以轻量化、低成本为原则,面向中小企业注塑车间,
将「老师傅的经验」转化为可复用、可优化的数据资产。

## 系统架构

```
keshe/
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口(API + 前端静态托管)
│   │   ├── config.py        # 全局配置: 特征定义、材料参数范围(领域知识)
│   │   ├── db.py            # SQLAlchemy 数据层(SQLite 默认,可切 PostgreSQL)
│   │   ├── schemas.py       # Pydantic 请求/响应模型
│   │   ├── routers/         # 6 个功能模块 API
│   │   │   ├── recommend.py    # 参数推荐
│   │   │   ├── predict.py      # 质量预测
│   │   │   ├── knowledge.py    # 知识检索
│   │   │   ├── records.py      # 数据记录
│   │   │   ├── feedback.py     # 反馈修正(在线学习)
│   │   │   └── dashboard.py    # 数据看板
│   │   └── services/        # 算法服务层
│   │       ├── model_service.py        # 模型加载与推理
│   │       ├── optimizer.py            # NSGA-II 多目标优化(DEAP)
│   │       ├── kg_service.py           # 知识图谱存储与检索
│   │       ├── rule_diagnosis.py       # 工艺规则缺陷诊断
│   │       ├── recommend_service.py    # 三模块协同推荐流程
│   │       └── feedback_service.py     # 反馈在线学习(模型重训)
│   └── scripts/
│       ├── preprocess.py    # 数据预处理(真实数据解析 + 合成数据生成)
│       ├── train.py         # 模型训练(XGBoost/RF 对比 + 缺陷多分类)
│       └── seed_demo_data.py # 演示数据播种
├── frontend/                # Vue3 + Element Plus(CDN 本地化,免构建)
│   ├── index.html           # SPA 骨架(6 个页面)
│   ├── assets/              # components.js / pages2.js / app.js / style.css
│   └── libs/                # vue / element-plus / echarts / axios(本地库,离线可用)
├── knowledge/kg_data.json   # 注塑工艺知识图谱数据(6 类实体、4 类关系)
├── data/
│   ├── raw/                 # 原始数据(UCI 注塑质量预测数据集)
│   └── processed/           # dataset.csv / 模型 / SQLite / Cypher 脚本
└── tests/                   # 后端闭环测试 + 前端挂载测试
```

## 功能模块

| 模块 | 技术实现 | 说明 |
|---|---|---|
| 参数推荐 | NSGA-II 遗传算法(DEAP)+ 质量预测模型 + 知识图谱历史案例 | 输入产品/材料/设备,输出 Pareto 最优参数集 |
| 质量预测 | XGBoost 二分类 + 多分类(8 类缺陷) | 合格概率 + 缺陷类型分布,5 折 CV AUC 0.976 |
| 知识检索 | 轻量图谱存储(实体/关系/别名)+ 自然语言检索 | 缺陷根因分析: 影响参数 + 解决对策 |
| 数据记录 | SQLAlchemy + SQLite | 生产数据录入与历史查询 |
| 反馈修正 | 增量重训 XGBoost(在线学习) | 老师傅修正参数反哺模型 |
| 数据看板 | ECharts | 生产统计、质量趋势、模型指标 |

## 数据说明

- **真实数据**: UCI "Quality Prediction in a Plastic Injection Molding Process"
  公开数据集(1451 条),质量标签 {1,2}→不合格 / {3,4}→合格;
  原数据集未标注材料牌号,按 ABS 工艺归类处理。
- **合成数据**: 依据材料领域知识(推荐/允许参数范围)生成 7 种材料 × 1000 条,
  缺陷标签由工艺规则引擎打标(与在线诊断规则一致,保证「训练-推理」同源)。
  违规区深度覆盖边界外 30%~45% 跨度,决策边界清晰。
- **知识图谱**: 教材知识 + 通用注塑工艺经验整理
  (材料 7、设备 4、参数 7、缺陷 10、对策 9、规则 6,关系 4 类)。

## 快速启动

```bash
# 1. 安装依赖(Python 3.13)
py -3.13 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r backend/requirements.txt

# 2. (首次)数据预处理 + 模型训练
cd backend
py -3.13 scripts/preprocess.py
py -3.13 scripts/train.py
py -3.13 scripts/seed_demo_data.py     # 可选: 生成演示生产记录

# 3. 启动服务(自动托管前端页面)
py -3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. 访问
#    系统页面:  http://localhost:8000
#    API 文档:  http://localhost:8000/docs
```

## 测试

```bash
# 后端端到端闭环测试(需先启动服务)
PYTHONIOENCODING=utf-8 py -3.13 tests/test_api_e2e.py

# 前端挂载测试(jsdom,需先在 tests/ 下 npm install)
node tests/frontend_mount_test.js
```

## 设计要点

- **三模块协同**: 图谱历史案例 → GA 生成候选 → 模型评估 → 最优推荐(方案设计 2.3.5 流程)
- **双重诊断**: ML 缺陷概率 + 知识图谱规则诊断互为校验,极端违规参数不被放行
- **多目标优化**: 质量合格概率(最大化)× 能耗代理 = 循环时间 + 0.3×熔体温度(最小化)
- **在线学习**: 反馈修正参数 + 实际质量结果 → 增量重训 XGBoost → 模型版本可追溯
- **Neo4j 兼容**: 知识图谱以 JSON 存储 + 内存图检索,已生成
  `data/processed/knowledge_graph.cypher` 可一键导入 Neo4j;数据库层经 SQLAlchemy
  配置 `DB_URL` 即可切换 PostgreSQL
