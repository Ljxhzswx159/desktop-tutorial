/* 共享命名空间与组件(参数推荐 / 质量预测 / 知识检索)
   注: 必须挂到 window, Vue 运行时模板编译器(new Function + with)无法访问顶层 const */
window.Inj = window.Inj || {};

/* ---------- 常量(与后端 config.py 一致) ---------- */
Inj.FEATURES = [
  'melt_temp', 'mold_temp', 'time_to_fill', 'plasticizing_time', 'cycle_time',
  'closing_force', 'clamp_force_peak', 'torque_peak', 'torque_mean',
  'back_pressure_peak', 'injection_pressure_peak', 'screw_pos_end_hold', 'shot_volume',
];
Inj.FEATURE_LABELS = {
  melt_temp: '熔体温度 (°C)', mold_temp: '模具温度 (°C)',
  time_to_fill: '填充时间 (s)', plasticizing_time: '塑化时间 (s)',
  cycle_time: '循环时间 (s)', closing_force: '合模力 (kN)',
  clamp_force_peak: '合模力峰值 (kN)', torque_peak: '扭矩峰值 (Nm)',
  torque_mean: '扭矩均值 (Nm)', back_pressure_peak: '背压峰值 (bar)',
  injection_pressure_peak: '注射压力峰值 (bar)', screw_pos_end_hold: '保压结束螺杆位置 (mm)',
  shot_volume: '射胶量 (cm³)',
};
Inj.DEFECT_TYPES = ['合格', '翘曲变形', '缩痕', '飞边', '银纹', '熔接线', '缺料', '烧焦'];

/* 图表色板(已验证 CVD 安全) */
Inj.COLORS = {
  s1: '#2a78d6', s2: '#eb6834', s3: '#1baf7a', s4: '#eda100',
  s5: '#e87ba4', s6: '#008300', s7: '#4a3aa7', s8: '#e34948',
  good: '#0ca30c', critical: '#d03b3b', warning: '#fab219',
  ink: '#0b0b0b', ink2: '#52514e', muted: '#898781',
  grid: '#e1e0d9', axis: '#c3c2b7', surface: '#fcfcfb',
};

/* 页面切换总线 */
Inj.bus = Vue.reactive({
  page: 'recommend',
  goto(p) { this.page = p; },
  // 推荐结果 -> 预测页
  applyParams: null, applyMaterial: null,
  useRecommended(params, material) {
    this.applyParams = { ...params };
    this.applyMaterial = material;
    this.goto('predict');
  },
});

/* ---------- API 封装 ---------- */
Inj.api = {
  get(url) { return axios.get(url).then(r => r.data); },
  post(url, body) { return axios.post(url, body).then(r => r.data); },
};

/* 加载材料元信息(推荐范围) */
Inj.materialsMeta = Vue.reactive({ loaded: false, data: {} });
Inj.loadMaterials = function () {
  return Inj.api.get('/api/knowledge/materials').then(d => {
    Inj.materialsMeta.data = d.materials;
    Inj.materialsMeta.loaded = true;
  });
};

/* 默认参数: 取推荐范围中值 */
Inj.defaultParams = function (material) {
  const p = {};
  const m = Inj.materialsMeta.data[material] || {};
  Inj.FEATURES.forEach(f => {
    const cfg = m[f];
    if (cfg && cfg.rec) {
      p[f] = Math.round(((cfg.rec[0] + cfg.rec[1]) / 2) * 100) / 100;
    } else {
      const fallback = { plasticizing_time: [2.8, 5.0], closing_force: [870, 930],
        clamp_force_peak: [890, 950], torque_peak: [95, 140], torque_mean: [80, 120],
        back_pressure_peak: [140, 160], screw_pos_end_hold: [8.3, 9.2] };
      const r = fallback[f] || [0, 100];
      p[f] = Math.round(((r[0] + r[1]) / 2) * 100) / 100;
    }
  });
  return p;
};

/* 参数范围提示(输入框 placeholder) */
Inj.rangeHint = function (material, f) {
  const m = Inj.materialsMeta.data[material];
  const cfg = m && m[f];
  if (cfg && cfg.rec) return `推荐 ${cfg.rec[0]} ~ ${cfg.rec[1]}`;
  return '';
};

/* ---------- ECharts 工具 ---------- */
Inj.charts = [];
Inj.initChart = function (el, option) {
  const c = echarts.init(el);
  c.setOption(option);
  Inj.charts.push(c);
  return c;
};
window.addEventListener('resize', () => Inj.charts.forEach(c => c.resize()));

Inj.baseText = { color: Inj.COLORS.ink2 };
Inj.baseAxis = {
  axisLine: { lineStyle: { color: Inj.COLORS.axis } },
  axisLabel: { color: Inj.COLORS.muted },
  splitLine: { lineStyle: { color: Inj.COLORS.grid, width: 1 } },
};

/* ---------- 参数输入组件(13 字段网格) ---------- */
Inj.ParamInputs = {
  name: 'ParamInputs',
  props: { modelValue: Object, material: { type: String, default: 'ABS' } },
  emits: ['update:modelValue'],
  template: `
  <div class="param-grid">
    <div class="param-item" v-for="f in Inj.FEATURES" :key="f">
      <div class="label"><span>{{ Inj.FEATURE_LABELS[f] }}</span></div>
      <el-input-number :model-value="modelValue[f]" @update:model-value="set(f, $event)"
        :step="stepOf(f)" :min="0" :precision="2" size="small" controls-position="right"
        style="width:100%" />
      <div class="hint">{{ Inj.rangeHint(material, f) }}</div>
    </div>
  </div>`,
  methods: {
    set(f, v) {
      const next = { ...this.modelValue, [f]: v == null ? 0 : v };
      this.$emit('update:modelValue', next);
    },
    stepOf(f) {
      return ['melt_temp', 'mold_temp'].includes(f) ? 1 : 0.1;
    },
  },
};

/* ---------- 缺陷分布图组件 ---------- */
Inj.DefectChart = {
  name: 'DefectChart',
  props: { distribution: Array },
  mounted() { this.render(); },
  watch: { distribution: { handler() { this.render(); }, deep: true } },
  methods: {
    render() {
      if (!this.$refs.box || !this.distribution) return;
      if (this.chart) this.chart.dispose();
      const d = [...this.distribution].reverse();
      this.chart = Inj.initChart(this.$refs.box, {
        grid: { left: 8, right: 46, top: 8, bottom: 4, containLabel: true },
        xAxis: { type: 'value', ...Inj.baseAxis, splitLine: { lineStyle: { color: Inj.COLORS.grid } } },
        yAxis: { type: 'category', data: d.map(x => x.defect), ...Inj.baseAxis },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
          formatter: p => `${p[0].name}<br/>概率: ${(p[0].value * 100).toFixed(1)}%` },
        series: [{
          type: 'bar', data: d.map(x => x.prob),
          barMaxWidth: 24, color: Inj.COLORS.s1,
          itemStyle: { borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: Inj.COLORS.ink2,
            fontSize: 11, formatter: p => (p.value * 100).toFixed(1) + '%' },
        }],
      });
    },
  },
  template: `<div ref="box" class="chart-box-sm"></div>`,
};

/* ==================== 1. 参数推荐页 ==================== */
Inj.RecommendPage = {
  name: 'RecommendPage',
  data() {
    return {
      form: { product_type: '汽车内饰件', material: 'ABS', equipment: '海天MA1200' },
      productTypes: ['汽车内饰件', '电子外壳', '精密齿轮', '医疗耗材', '日用壳体'],
      equipments: ['海天MA1200', '海天MA2500', '震雄SM120', '伊之密UN260'],
      loading: false, result: null, selected: null,
    };
  },
  computed: {
    materialOptions() {
      return Object.entries(Inj.materialsMeta.data).map(([k, v]) => ({ key: k, label: v.label || k }));
    },
    recParams() {
      if (!this.result) return null;
      return this.result.recommended.params;
    },
  },
  methods: {
    async run() {
      this.loading = true;
      this.result = null;
      try {
        this.result = await Inj.api.post('/api/recommend', this.form);
        this.selected = this.result.recommended;
        this.$message.success('推荐完成: 已生成 Pareto 最优参数');
      } catch (e) {
        this.$message.error('推荐失败: ' + (e.response?.data?.detail || e.message));
      } finally {
        this.loading = false;
      }
    },
    fmtProb(p) { return (p * 100).toFixed(1) + '%'; },
    inRec(f, v) {
      const m = Inj.materialsMeta.data[this.form.material];
      const cfg = m && m[f];
      if (!cfg || !cfg.rec) return null;
      return v >= cfg.rec[0] && v <= cfg.rec[1];
    },
    applyToPredict() {
      if (!this.selected) return;
      Inj.bus.useRecommended(this.selected.params, this.form.material);
    },
  },
  mounted() {
    if (!Inj.materialsMeta.loaded) Inj.loadMaterials();
  },
  template: `
  <div>
    <div class="page-title">参数推荐</div>
    <div class="page-desc">输入产品类型、材料牌号与设备型号,系统通过「知识图谱历史案例 + NSGA-II 多目标优化 + 质量预测模型评估」协同推荐最优工艺参数</div>

    <div class="page-card">
      <div class="flex">
        <el-select v-model="form.product_type" style="width:170px">
          <el-option v-for="t in productTypes" :key="t" :label="t" :value="t"/>
        </el-select>
        <el-select v-model="form.material" style="width:240px">
          <el-option v-for="m in materialOptions" :key="m.key" :label="m.label" :value="m.key"/>
        </el-select>
        <el-select v-model="form.equipment" style="width:170px">
          <el-option v-for="e in equipments" :key="e" :label="e" :value="e"/>
        </el-select>
        <el-button type="primary" :loading="loading" @click="run">
          <span v-if="!loading">智能推荐</span><span v-else>NSGA-II 优化中…(约 2-3 秒)</span>
        </el-button>
      </div>
      <div style="font-size:12px;color:var(--ink-muted);margin-top:8px">
        优化目标: 最大化合格概率 × 最小化能耗(循环时间 + 0.3×熔体温度)
      </div>
    </div>

    <template v-if="result">
      <!-- 推荐结果 -->
      <div class="page-card">
        <div class="flex-between">
          <div class="card-title">最优推荐参数({{ result.inputs.material }})</div>
          <div class="flex">
            <span style="font-size:13px">合格概率</span>
            <b class="big-prob prob-ok" style="font-size:28px">{{ fmtProb(result.recommended.quality_prob) }}</b>
            <el-tag type="success" effect="light">规则检查: {{ result.recommended.rule_check }}</el-tag>
            <el-button size="small" type="primary" @click="applyToPredict">应用到质量预测</el-button>
          </div>
        </div>
        <div class="param-grid">
          <div class="param-item" v-for="f in Inj.FEATURES" :key="f">
            <div class="label"><span>{{ Inj.FEATURE_LABELS[f] }}</span>
              <el-tag v-if="inRec(f, selected.params[f]) === true" size="small" type="success" effect="plain">推荐区</el-tag>
              <el-tag v-else-if="inRec(f, selected.params[f]) === false" size="small" type="warning" effect="plain">边界区</el-tag>
            </div>
            <div style="font-weight:600;font-size:16px">{{ selected.params[f] }}</div>
            <div class="hint">{{ Inj.rangeHint(result.inputs.material, f) }}</div>
          </div>
        </div>
        <div class="mt16" style="font-size:13px;color:var(--ink-secondary)">
          能耗代理: <b>{{ result.recommended.energy_proxy }}</b> ·
          模型 AUC: <b>{{ result.confidence.model_auc }}</b> ·
          {{ result.confidence.note }}
        </div>
      </div>

      <!-- Pareto 前沿 -->
      <div class="page-card">
        <div class="card-title">Pareto 前沿候选方案(质量 × 能耗双目标)</div>
        <el-table :data="result.pareto_front" size="small" highlight-current-row
                  @current-change="selected = $event">
          <el-table-column type="index" label="#" width="45"/>
          <el-table-column label="熔体温度" width="90">
            <template #default="s">{{ s.row.params.melt_temp }}</template>
          </el-table-column>
          <el-table-column label="模具温度" width="90">
            <template #default="s">{{ s.row.params.mold_temp }}</template>
          </el-table-column>
          <el-table-column label="注射压力峰值" width="110">
            <template #default="s">{{ s.row.params.injection_pressure_peak }}</template>
          </el-table-column>
          <el-table-column label="循环时间" width="90">
            <template #default="s">{{ s.row.params.cycle_time }}</template>
          </el-table-column>
          <el-table-column label="合格概率" width="90">
            <template #default="s"><b style="color:var(--status-good)">{{ fmtProb(s.row.quality_prob) }}</b></template>
          </el-table-column>
          <el-table-column label="能耗代理" width="90">
            <template #default="s">{{ s.row.energy }}</template>
          </el-table-column>
          <el-table-column label="规则检查" width="90">
            <template #default="s">{{ s.row.rule_check }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="s">
              <el-button size="small" link type="primary" @click="selected = s.row">选用</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div style="font-size:12px;color:var(--ink-muted);margin-top:6px">点击行选用方案;「选用」后可通过上方按钮应用到质量预测页</div>
      </div>

      <!-- 历史相似案例 -->
      <div class="page-card">
        <div class="card-title">知识图谱 · 历史相似案例({{ result.history_cases.length }} 条)</div>
        <el-table :data="result.history_cases" size="small">
          <el-table-column prop="source" label="来源" width="130"/>
          <el-table-column label="关键参数">
            <template #default="s">
              <span style="font-size:12px;color:var(--ink-secondary)">
                熔温 {{ s.row.params.melt_temp }} · 模温 {{ s.row.params.mold_temp }} ·
                射压 {{ s.row.params.injection_pressure_peak }} · 周期 {{ s.row.params.cycle_time }}s
              </span>
            </template>
          </el-table-column>
          <el-table-column label="质量" width="80">
            <template #default="s">
              <el-tag :type="s.row.quality ? 'success' : 'danger'" size="small">{{ s.row.quality ? '合格' : '不合格' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 材料画像 -->
      <div class="page-card">
        <div class="card-title">材料工艺画像</div>
        <p style="font-size:13px;margin:0 0 6px">{{ result.material_profile.label }}</p>
        <div style="font-size:13px;color:var(--ink-secondary);margin-bottom:8px">
          适用设备: {{ result.material_profile.equipments.join('、') || '—' }}
        </div>
        <el-collapse>
          <el-collapse-item title="相关工艺规则(知识图谱约束)">
            <div v-for="(r, i) in result.material_profile.rules" :key="i" style="font-size:13px;padding:3px 0">
              <b>{{ i + 1 }}. {{ r.name }}</b>: {{ r.props['规则内容'] }}
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>
  </div>`,
};

/* ==================== 2. 质量预测页 ==================== */
Inj.PredictPage = {
  name: 'PredictPage',
  data() {
    return {
      material: 'ABS',
      params: {},
      loading: false, result: null,
    };
  },
  computed: {
    materialOptions() {
      return Object.entries(Inj.materialsMeta.data).map(([k, v]) => ({ key: k, label: v.label || k }));
    },
    // 跨页面通信: 推荐页"应用到质量预测"
    incomingParams() { return Inj.bus.applyParams; },
  },
  watch: {
    material() {
      if (this.result) this.result = null;
    },
    incomingParams(v) {
      if (v) {
        this.material = Inj.bus.applyMaterial || this.material;
        this.params = { ...v };
        Inj.bus.applyParams = null;
      }
    },
  },
  methods: {
    fillDefaults() { this.params = Inj.defaultParams(this.material); },
    async run() {
      if (!this.params.melt_temp) { this.$message.warning('请先填写参数'); return; }
      this.loading = true;
      try {
        this.result = await Inj.api.post('/api/predict/quality',
          { material: this.material, params: this.params });
      } catch (e) {
        this.$message.error('预测失败: ' + (e.response?.data?.detail || e.message));
      } finally { this.loading = false; }
    },
    async saveRecord() {
      const r = this.result;
      await Inj.api.post('/api/records', {
        ...this.params, material: this.material,
        product_type: '—', equipment: '', operator: '操作员',
        quality: r.quality, defect_type: r.defect_type, source: 'manual', note: '预测验证',
      });
      this.$message.success('已存入生产记录');
    },
    fmtProb(p) { return (p * 100).toFixed(1) + '%'; },
  },
  mounted() {
    if (!Inj.materialsMeta.loaded) Inj.loadMaterials().then(() => this.fillDefaults());
    else this.fillDefaults();
  },
  template: `
  <div>
    <div class="page-title">质量预测</div>
    <div class="page-desc">输入工艺参数组合,XGBoost 模型预测制品质量合格概率,并结合知识图谱给出缺陷根因与对策</div>

    <div class="page-card">
      <div class="flex">
        <span style="font-size:13px">材料牌号</span>
        <el-select v-model="material" style="width:240px">
          <el-option v-for="m in materialOptions" :key="m.key" :label="m.label" :value="m.key"/>
        </el-select>
        <el-button size="small" @click="fillDefaults">填充推荐中值</el-button>
        <el-button type="primary" :loading="loading" @click="run">
          {{ loading ? '预测中…' : '开始预测' }}
        </el-button>
      </div>
      <div class="mt16">
        <Inj.ParamInputs v-model="params" :material="material"/>
      </div>
    </div>

    <template v-if="result">
      <div class="page-card">
        <div class="card-title">预测结果</div>
        <div class="flex" style="align-items:flex-start">
          <div style="min-width:260px">
            <div class="big-prob" :class="result.quality ? 'prob-ok' : 'prob-bad'">
              {{ fmtProb(result.quality_prob) }}
            </div>
            <div style="font-size:13px;color:var(--ink-secondary)">质量合格概率</div>
            <div class="mt16">
              <el-tag :type="result.quality ? 'success' : 'danger'" size="large" effect="dark">
                {{ result.quality ? '判定: 合格' : '判定: 不合格' }}
              </el-tag>
              <el-tag type="info" size="large" effect="plain" style="margin-left:8px">
                缺陷: {{ result.defect_type }}
              </el-tag>
            </div>
            <el-button size="small" style="margin-top:14px" @click="saveRecord">存为生产记录</el-button>
          </div>
          <div style="flex:1;min-width:320px">
            <div class="card-title" style="font-size:13px">缺陷类型概率分布(ML 多分类)</div>
            <Inj.DefectChart :distribution="result.defect_distribution"/>
          </div>
        </div>
      </div>

      <!-- 规则诊断 -->
      <div class="page-card">
        <div class="card-title">知识图谱规则诊断(领域知识双重校验)</div>
        <el-alert v-if="result.rule_diagnosis.defect_type === '合格'"
                  title="参数均在各材料允许范围内,未发现工艺违规" type="success" :closable="false" show-icon/>
        <template v-else>
          <el-alert :title="'诊断缺陷: ' + result.rule_diagnosis.defect_type"
                    type="warning" :closable="false" show-icon/>
          <div class="mt16" style="font-size:13px">
            <div v-for="(v, i) in result.rule_diagnosis.violations" :key="i"
                 style="padding:6px 0;border-bottom:1px dashed #eee">
              <b>{{ Inj.FEATURE_LABELS[v.param] }}</b> — {{ v.rule }}
              <el-tag size="small" type="danger" effect="plain" style="margin-left:8px">{{ v.defect }}</el-tag>
            </div>
          </div>
        </template>
      </div>

      <!-- 图谱对策 -->
      <div class="page-card" v-if="result.defect_analysis">
        <div class="card-title">根因与对策(知识图谱推理)</div>
        <el-row :gutter="16">
          <el-col :span="12">
            <div style="font-weight:600;font-size:13px;margin-bottom:6px">影响参数(原因)</div>
            <div v-for="(c, i) in result.defect_analysis.causes" :key="i"
                 style="font-size:13px;padding:5px 0;border-bottom:1px dashed #eee">
              <el-tag size="small" effect="plain" style="margin-right:6px">{{ c.param }}</el-tag>{{ c.detail }}
            </div>
          </el-col>
          <el-col :span="12">
            <div style="font-weight:600;font-size:13px;margin-bottom:6px">解决对策</div>
            <div v-for="(c, i) in result.defect_analysis.countermeasures" :key="i"
                 style="font-size:13px;padding:5px 0;border-bottom:1px dashed #eee">
              <el-tag size="small" type="success" effect="plain" style="margin-right:6px">{{ c.action }}</el-tag>{{ c.detail }}
            </div>
          </el-col>
        </el-row>
      </div>
    </template>
  </div>`,
};

/* ==================== 3. 知识检索页 ==================== */
Inj.KG_TYPES = [
  { name: '材料', color: Inj.COLORS.s1 },
  { name: '设备', color: Inj.COLORS.s2 },
  { name: '参数', color: Inj.COLORS.s3 },
  { name: '缺陷', color: Inj.COLORS.s4 },
  { name: '对策', color: Inj.COLORS.s5 },
  { name: '工艺规则', color: Inj.COLORS.s6 },
];
Inj.KG_TYPE_COLOR = Object.fromEntries(Inj.KG_TYPES.map(t => [t.name, t.color]));
Inj.KG_SIZE = { '材料': 42, '设备': 36, '参数': 30, '缺陷': 32, '对策': 28, '工艺规则': 26 };

Inj.KnowledgePage = {
  name: 'KnowledgePage',
  data() {
    return {
      query: '',
      examples: ['翘曲变形了怎么办', '缩痕', '缺料', 'ABS 工艺', '保压时间', '海天MA1200', '银纹'],
      loading: false,
      results: [],
      analysis: null,
      graphData: null,
      showFullGraph: false,
    };
  },
  methods: {
    async run(q) {
      this.query = q;
      if (!q.trim()) return;
      this.loading = true;
      try {
        const r = await Inj.api.post('/api/knowledge/search', { query: q, limit: 10 });
        this.results = r.results || [];
        this.analysis = r.defect_analysis;
        this.renderGraph();
      } catch (e) {
        this.$message.error('检索失败: ' + (e.response?.data?.detail || e.message));
      } finally { this.loading = false; }
    },
    async loadFullGraph() {
      this.graphData = await Inj.api.get('/api/knowledge/graph');
      this.showFullGraph = true;
      this.renderGraph();
    },
    renderGraph() {
      if (!this.$refs.graphBox) return;
      let g;
      if (this.showFullGraph && this.graphData) {
        g = this.graphData;
      } else {
        // 取得分最高的命中实体的子图
        const top = this.results[0];
        if (!top) return;
        const sub = this._subgraphFrom(top.node);
        g = sub;
      }
      this._drawGraph(g);
    },
    /* 由检索结果(node + neighbors)组装子图 */
    _subgraphFrom(node) {
      const nodes = [node];
      const edges = [];
      const seen = new Set([node.id]);
      (node.neighbors || []).forEach(nb => {
        if (!seen.has(nb.node.id)) { seen.add(nb.node.id); nodes.push(nb.node); }
        edges.push({ source: node.id, target: nb.node.id, rel: nb.rel, props: nb.props || {} });
      });
      return { nodes, edges };
    },
    _drawGraph(g) {
      if (this.chart) this.chart.dispose();
      const nodes = g.nodes.map(n => ({
        id: n.id, name: n.name, category: n.type,
        symbolSize: Inj.KG_SIZE[n.type] || 28,
      }));
      const edges = g.edges.map(e => ({
        source: e.source, target: e.target,
        label: { show: true, formatter: e.rel, fontSize: 10, color: Inj.COLORS.ink2 },
        lineStyle: { color: Inj.COLORS.axis, width: 1, curveness: 0.08 },
      }));
      this.chart = Inj.initChart(this.$refs.graphBox, {
        legend: [{ data: Inj.KG_TYPES.map(t => t.name), bottom: 4,
                   textStyle: { color: Inj.COLORS.ink2, fontSize: 11 } }],
        tooltip: { formatter: p => p.dataType === 'node'
            ? `<b>${p.data.name}</b><br/>类型: ${p.data.category}` : p.data.label?.formatter || '' },
        series: [{
          type: 'graph', layout: 'force', roam: true, draggable: true,
          data: nodes, links: edges,
          categories: Inj.KG_TYPES.map(t => ({ name: t.name })),
          itemStyle: { color: p => Inj.KG_TYPE_COLOR[p.data.category] || Inj.COLORS.s1 },
          label: { show: true, position: 'bottom', fontSize: 11, color: Inj.COLORS.ink },
          force: { repulsion: 420, edgeLength: [70, 130], gravity: 0.08 },
          lineStyle: { color: 'source', opacity: 0.5 },
          emphasis: { focus: 'adjacency' },
        }],
      });
    },
    typeColor(t) { return Inj.KG_TYPE_COLOR[t] || Inj.COLORS.s1; },
  },
  template: `
  <div>
    <div class="page-title">知识检索</div>
    <div class="page-desc">查询注塑工艺知识图谱(材料 / 设备 / 参数 / 缺陷 / 对策 / 工艺规则),支持自然语言描述</div>

    <div class="page-card">
      <div class="flex">
        <el-input v-model="query" placeholder="输入问题,如: 翘曲变形了怎么办 / 缩痕 / ABS 工艺参数"
                  style="max-width:460px" clearable @keyup.enter="run(query)">
          <template #append>
            <el-button :loading="loading" @click="run(query)">检索</el-button>
          </template>
        </el-input>
        <el-button link type="primary" @click="loadFullGraph">浏览全图</el-button>
      </div>
      <div class="flex" style="margin-top:10px">
        <span style="font-size:12px;color:var(--ink-muted)">示例:</span>
        <el-tag v-for="e in examples" :key="e" size="small" effect="plain"
                style="cursor:pointer" @click="run(e)">{{ e }}</el-tag>
      </div>
    </div>

    <div class="page-card" v-if="results.length || showFullGraph">
      <div class="card-title">知识图谱</div>
      <div ref="graphBox" style="width:100%;height:380px"></div>
      <div style="font-size:12px;color:var(--ink-muted)">
        节点可按类型拖拽/缩放;线标签为关系类型(适用于/影响/解决/约束)
      </div>
    </div>

    <!-- 根因分析 -->
    <div class="page-card" v-if="analysis">
      <div class="card-title">缺陷根因分析: {{ analysis.defect }}</div>
      <el-row :gutter="16">
        <el-col :span="12">
          <div style="font-weight:600;font-size:13px;margin-bottom:6px">影响参数(原因)</div>
          <div v-for="(c, i) in analysis.causes" :key="i"
               style="font-size:13px;padding:5px 0;border-bottom:1px dashed #eee">
            <el-tag size="small" effect="plain" style="margin-right:6px">{{ c.param }}</el-tag>{{ c.detail }}
          </div>
        </el-col>
        <el-col :span="12">
          <div style="font-weight:600;font-size:13px;margin-bottom:6px">解决对策</div>
          <div v-for="(c, i) in analysis.countermeasures" :key="i"
               style="font-size:13px;padding:5px 0;border-bottom:1px dashed #eee">
            <el-tag size="small" type="success" effect="plain" style="margin-right:6px">{{ c.action }}</el-tag>{{ c.detail }}
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 检索结果卡片 -->
    <div class="page-card" v-if="results.length">
      <div class="card-title">知识条目({{ results.length }})</div>
      <div class="knowledge-card" v-for="(r, i) in results" :key="i">
        <div class="flex-between">
          <div class="flex" style="gap:8px">
            <span class="name">{{ r.node.name }}</span>
            <el-tag size="small" :style="{background: typeColor(r.node.type), color: '#fff', border: 'none'}">
              {{ r.node.type }}
            </el-tag>
          </div>
          <span style="font-size:11px;color:var(--ink-muted)">匹配度 {{ (r.score * 100) | 0 }}%</span>
        </div>
        <div class="prop" v-for="(v, k) in r.node.props" :key="k"><b>{{ k }}:</b> {{ v }}</div>
        <div v-if="r.neighbors.length" style="margin-top:8px">
          <span style="font-size:12px;color:var(--ink-muted)">关联: </span>
          <el-tag v-for="(nb, j) in r.neighbors.slice(0, 8)" :key="j" size="small" effect="plain"
                  style="margin:2px 4px 2px 0">
            --{{ nb.rel }}→ {{ nb.node.name }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>`,
};
