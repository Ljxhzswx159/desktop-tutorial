/* 数据看板 / 数据记录 / 反馈修正 页面 */

/* ==================== 4. 数据看板页 ==================== */
Inj.DashboardPage = {
  name: 'DashboardPage',
  data() {
    return { loading: true, data: null };
  },
  methods: {
    async load() {
      try {
        this.data = await Inj.api.get('/api/dashboard');
        this.$nextTick(() => { this.renderTrend(); this.renderDefects(); this.renderMaterials(); this.renderImportance(); this.renderModelTrend(); });
      } finally { this.loading = false; }
    },
    /* 质量趋势: 每日合格/不合格(状态色 + 图例 + 端点标签) */
    renderTrend() {
      const s = this.data.record_stats;
      const days = Object.keys(s.by_day || {});
      const total = days.map(d => s.by_day[d]);
      const ok = (s.by_day_ok || {});
      const ng = days.map((d, i) => total[i] - (ok[d] || 0));
      // by_day_ok 由后端补充(见下),若缺失则仅显示总数
      const hasOk = days.length && Object.keys(ok).length;
      const series = hasOk ? [
        { name: '合格', type: 'line', data: days.map(d => ok[d] || 0),
          color: Inj.COLORS.good, symbolSize: 8, lineStyle: { width: 2 },
          itemStyle: { borderColor: Inj.COLORS.surface, borderWidth: 2 },
          endLabel: { show: true, formatter: '{c}', color: Inj.COLORS.ink2 } },
        { name: '不合格', type: 'line', data: ng,
          color: Inj.COLORS.critical, symbolSize: 8, lineStyle: { width: 2 },
          itemStyle: { borderColor: Inj.COLORS.surface, borderWidth: 2 },
          endLabel: { show: true, formatter: '{c}', color: Inj.COLORS.ink2 } },
      ] : [
        { name: '记录数', type: 'line', data: total,
          color: Inj.COLORS.s1, symbolSize: 8, lineStyle: { width: 2 },
          itemStyle: { borderColor: Inj.COLORS.surface, borderWidth: 2 },
          endLabel: { show: true, formatter: '{c}', color: Inj.COLORS.ink2 } },
      ];
      Inj.initChart(this.$refs.trendBox, {
        grid: { left: 8, right: 24, top: 30, bottom: 8, containLabel: true },
        legend: { top: 0, textStyle: { color: Inj.COLORS.ink2, fontSize: 12 } },
        xAxis: { type: 'category', data: days, ...Inj.baseAxis,
                 splitLine: { show: false } },
        yAxis: { type: 'value', ...Inj.baseAxis, minInterval: 1 },
        tooltip: { trigger: 'axis',
          axisPointer: { type: 'cross', lineStyle: { color: Inj.COLORS.muted } } },
        series,
      });
    },
    /* 缺陷分布: 单序列柱图(单一蓝色) + 顶部数值 */
    renderDefects() {
      const s = this.data.record_stats;
      const items = Object.entries(s.by_defect || {}).sort((a, b) => b[1] - a[1]);
      Inj.initChart(this.$refs.defectBox, {
        grid: { left: 8, right: 8, top: 30, bottom: 8, containLabel: true },
        xAxis: { type: 'category', data: items.map(x => x[0]),
                 ...Inj.baseAxis, splitLine: { show: false },
                 axisLabel: { color: Inj.COLORS.muted, fontSize: 11, interval: 0, rotate: items.length > 5 ? 20 : 0 } },
        yAxis: { type: 'value', ...Inj.baseAxis, minInterval: 1 },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        series: [{
          type: 'bar', data: items.map(x => x[1]),
          barMaxWidth: 24, color: Inj.COLORS.s1,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: 'top', color: Inj.COLORS.ink2, fontSize: 11 },
        }],
      });
    },
    /* 各材料合格率 */
    renderMaterials() {
      const s = this.data.record_stats;
      const mat = Object.entries(this.data.materials || {});
      const rates = mat.map(([k]) => {
        const m = (s.by_material || {})[k] || 0;
        const ok = (s.by_material_ok || {})[k] || 0;
        return m ? +(ok / m).toFixed(3) : 0;
      });
      Inj.initChart(this.$refs.matBox, {
        grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
        xAxis: { type: 'category', data: mat.map(x => x[0]), ...Inj.baseAxis,
                 splitLine: { show: false } },
        yAxis: { type: 'value', max: 1, ...Inj.baseAxis,
                 axisLabel: { color: Inj.COLORS.muted, formatter: v => (v * 100) + '%' } },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
                   formatter: p => `${p[0].name}: ${(p[0].value * 100).toFixed(1)}%` },
        series: [{
          type: 'bar', data: rates, barMaxWidth: 24, color: Inj.COLORS.s3,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: 'top', color: Inj.COLORS.ink2, fontSize: 11,
                   formatter: p => (p.value * 100).toFixed(1) + '%' },
        }],
      });
    },
    /* 特征重要性(横向柱) */
    renderImportance() {
      const fi = this.data.model.feature_importance || [];
      const labels = fi.map(x => Inj.FEATURE_LABELS[x[0]] || x[0]);
      Inj.initChart(this.$refs.impBox, {
        grid: { left: 8, right: 40, top: 8, bottom: 8, containLabel: true },
        xAxis: { type: 'value', ...Inj.baseAxis },
        yAxis: { type: 'category', data: labels.reverse(), ...Inj.baseAxis,
                 axisLabel: { color: Inj.COLORS.muted, fontSize: 11 } },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
                   formatter: p => `${p[0].name}: ${(p[0].value * 100).toFixed(2)}%` },
        series: [{
          type: 'bar', data: [...fi].reverse().map(x => +(x[1] * 100).toFixed(2)),
          barMaxWidth: 16, color: Inj.COLORS.s5,
          itemStyle: { borderRadius: [0, 4, 4, 0] },
          label: { show: true, position: 'right', color: Inj.COLORS.ink2, fontSize: 10,
                   formatter: p => p.value + '%' },
        }],
      });
    },
    /* 模型版本趋势 */
    renderModelTrend() {
      const t = this.data.model.model_trend || [];
      if (!t.length) return;
      Inj.initChart(this.$refs.modelBox, {
        grid: { left: 8, right: 24, top: 30, bottom: 8, containLabel: true },
        xAxis: { type: 'category', data: t.map(x => x.trained_at), ...Inj.baseAxis,
                 splitLine: { show: false } },
        yAxis: { type: 'value', ...Inj.baseAxis },
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' },
                   formatter: p => `${p[0].name}<br/>准确率: ${(p[0].value * 100).toFixed(1)}%` },
        series: [{
          name: '准确率', type: 'line', data: t.map(x => +(x.accuracy * 100).toFixed(1)),
          color: Inj.COLORS.s7, symbolSize: 8, lineStyle: { width: 2 },
          itemStyle: { borderColor: Inj.COLORS.surface, borderWidth: 2 },
          endLabel: { show: true, formatter: p => p.value + '%', color: Inj.COLORS.ink2 },
        }],
      });
    },
  },
  mounted() {
    if (!Inj.materialsMeta.loaded) Inj.loadMaterials();
    this.load();
  },
  template: `
  <div v-if="data">
    <div class="page-title">数据看板</div>
    <div class="page-desc">生产统计、质量趋势与模型运行状态总览</div>

    <!-- 统计磁贴 -->
    <div class="stat-tiles">
      <div class="stat-tile">
        <div class="label">生产记录总数</div>
        <div class="value">{{ data.record_stats.total }}</div>
        <div class="delta" style="color:var(--ink-muted)">近 30 天录入</div>
      </div>
      <div class="stat-tile">
        <div class="label">生产合格率</div>
        <div class="value" :style="{color: data.record_stats.ok_rate >= 0.9 ? 'var(--status-good)' : 'var(--status-warning)'}">
          {{ (data.record_stats.ok_rate * 100).toFixed(1) }}%
        </div>
        <div class="delta" style="color:var(--ink-muted)">目标 ≥ 95%</div>
      </div>
      <div class="stat-tile">
        <div class="label">质量预测模型 AUC</div>
        <div class="value">{{ data.model.metrics.roc_auc }}</div>
        <div class="delta" style="color:var(--ink-muted)">{{ data.model.name }} · 5 折交叉验证</div>
      </div>
      <div class="stat-tile">
        <div class="label">缺陷分类准确率</div>
        <div class="value">{{ (data.model.defect_accuracy * 100).toFixed(1) }}%</div>
        <div class="delta" style="color:var(--ink-muted)">macro-F1 {{ data.model.defect_macro_f1 }}</div>
      </div>
      <div class="stat-tile">
        <div class="label">训练样本数</div>
        <div class="value">{{ data.model.trained_samples }}</div>
        <div class="delta" style="color:var(--ink-muted)">真实 1451 + 领域知识合成</div>
      </div>
    </div>

    <div class="page-card">
      <div class="card-title">每日生产质量趋势</div>
      <div ref="trendBox" class="chart-box"></div>
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <div class="page-card">
          <div class="card-title">缺陷分布(生产记录)</div>
          <div ref="defectBox" class="chart-box-sm"></div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="page-card">
          <div class="card-title">各材料生产合格率</div>
          <div ref="matBox" class="chart-box-sm"></div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <div class="page-card">
          <div class="card-title">模型特征重要性 Top10</div>
          <div ref="impBox" class="chart-box"></div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="page-card">
          <div class="card-title">模型版本准确率趋势(含在线学习)</div>
          <div ref="modelBox" class="chart-box"></div>
        </div>
      </el-col>
    </el-row>
  </div>
  <div v-else class="page-card" v-loading="loading" style="height:200px"></div>`,
};

/* ==================== 5. 数据记录页 ==================== */
Inj.RecordsPage = {
  name: 'RecordsPage',
  data() {
    return {
      form: {
        product_type: '汽车内饰件', material: 'ABS', equipment: '海天MA1200',
        operator: '操作员1', params: {}, quality: 1, defect_type: '合格', note: '',
      },
      productTypes: ['汽车内饰件', '电子外壳', '精密齿轮', '医疗耗材', '日用壳体'],
      equipments: ['海天MA1200', '海天MA2500', '震雄SM120', '伊之密UN260'],
      submitting: false,
      list: { items: [], total: 0, page: 1, page_size: 10 },
      filterMaterial: '',
    };
  },
  computed: {
    materialOptions() {
      return Object.entries(Inj.materialsMeta.data).map(([k, v]) => ({ key: k, label: v.label || k }));
    },
  },
  methods: {
    fillDefaults() { this.form.params = Inj.defaultParams(this.form.material); },
    async submit() {
      this.submitting = true;
      try {
        await Inj.api.post('/api/records', {
          ...this.form.params, product_type: this.form.product_type,
          material: this.form.material, equipment: this.form.equipment,
          operator: this.form.operator, quality: this.form.quality,
          defect_type: this.form.quality ? '合格' : this.form.defect_type,
          source: 'manual', note: this.form.note,
        });
        this.$message.success('生产记录已保存');
        this.load();
      } catch (e) {
        this.$message.error('保存失败: ' + (e.response?.data?.detail || e.message));
      } finally { this.submitting = false; }
    },
    async load() {
      const p = { page: this.list.page, page_size: this.list.page_size };
      if (this.filterMaterial) p.material = this.filterMaterial;
      const r = await Inj.api.get('/api/records?' + new URLSearchParams(p).toString());
      this.list = { ...this.list, items: r.items, total: r.total };
    },
    paramSummary(p) {
      return `熔温 ${p.melt_temp} · 模温 ${p.mold_temp} · 射压 ${p.injection_pressure_peak} · 周期 ${p.cycle_time}s`;
    },
  },
  mounted() {
    if (!Inj.materialsMeta.loaded) Inj.loadMaterials().then(() => this.fillDefaults());
    else this.fillDefaults();
    this.load();
  },
  template: `
  <div>
    <div class="page-title">数据记录</div>
    <div class="page-desc">操作员录入实际工艺参数与质量检测结果,形成「推荐 → 执行 → 检测 → 反馈」闭环</div>

    <div class="page-card">
      <div class="card-title">生产数据录入</div>
      <div class="flex" style="margin-bottom:12px">
        <el-select v-model="form.product_type" style="width:150px">
          <el-option v-for="t in productTypes" :key="t" :label="t" :value="t"/>
        </el-select>
        <el-select v-model="form.material" style="width:200px">
          <el-option v-for="m in materialOptions" :key="m.key" :label="m.label" :value="m.key"/>
        </el-select>
        <el-select v-model="form.equipment" style="width:150px">
          <el-option v-for="e in equipments" :key="e" :label="e" :value="e"/>
        </el-select>
        <el-input v-model="form.operator" placeholder="操作员" style="width:110px"/>
        <el-button size="small" @click="fillDefaults">填充推荐中值</el-button>
      </div>
      <Inj.ParamInputs v-model="form.params" :material="form.material"/>
      <div class="flex mt16">
        <span style="font-size:13px">检测结果</span>
        <el-radio-group v-model="form.quality">
          <el-radio-button :value="1">合格</el-radio-button>
          <el-radio-button :value="0">不合格</el-radio-button>
        </el-radio-group>
        <el-select v-if="!form.quality" v-model="form.defect_type" style="width:130px" placeholder="缺陷类型">
          <el-option v-for="d in Inj.DEFECT_TYPES.slice(1)" :key="d" :label="d" :value="d"/>
        </el-select>
        <el-input v-model="form.note" placeholder="备注(可选)" style="width:200px"/>
        <el-button type="primary" :loading="submitting" @click="submit">保存记录</el-button>
      </div>
    </div>

    <div class="page-card">
      <div class="flex-between">
        <div class="card-title">历史记录(共 {{ list.total }} 条)</div>
        <div class="flex">
          <el-select v-model="filterMaterial" placeholder="按材料筛选" clearable style="width:160px" @change="load">
            <el-option v-for="m in materialOptions" :key="m.key" :label="m.key" :value="m.key"/>
          </el-select>
          <el-button size="small" @click="load">刷新</el-button>
        </div>
      </div>
      <el-table :data="list.items" size="small">
        <el-table-column prop="id" label="ID" width="55"/>
        <el-table-column prop="created_at" label="时间" width="130"/>
        <el-table-column prop="product_type" label="产品" width="110"/>
        <el-table-column prop="material" label="材料" width="70"/>
        <el-table-column prop="equipment" label="设备" width="110"/>
        <el-table-column label="关键参数" min-width="220">
          <template #default="s">
            <span style="font-size:12px;color:var(--ink-secondary)">{{ paramSummary(s.row.params) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="质量" width="90">
          <template #default="s">
            <el-tag :type="s.row.quality ? 'success' : 'danger'" size="small">
              {{ s.row.quality ? '合格' : s.row.defect_type || '不合格' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作员" width="80"/>
        <el-table-column label="参数" width="80">
          <template #default="s">
            <el-popover placement="left" width="360" trigger="click">
              <template #reference><el-button size="small" link type="primary">查看</el-button></template>
              <div class="param-pop">
                <div class="row" v-for="f in Inj.FEATURES" :key="f">
                  <span>{{ Inj.FEATURE_LABELS[f] }}</span><b>{{ s.row.params[f] }}</b>
                </div>
              </div>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
      <div class="mt16" style="text-align:right">
        <el-pagination layout="prev, pager, next, total" :total="list.total"
          v-model:current-page="list.page" :page-size="list.page_size" @current-change="load"/>
      </div>
    </div>
  </div>`,
};

/* ==================== 6. 反馈修正页 ==================== */
Inj.FeedbackPage = {
  name: 'FeedbackPage',
  data() {
    return {
      form: {
        material: 'ABS', operator: '李师傅',
        original: {}, corrected: {}, quality_after: 1, defect_after: '', reason: '',
      },
      fromRecordId: null,
      submitting: false, retraining: false,
      feedbacks: [], versions: [], retrainResult: null,
    };
  },
  computed: {
    materialOptions() {
      return Object.entries(Inj.materialsMeta.data).map(([k, v]) => ({ key: k, label: v.label || k }));
    },
  },
  methods: {
    fillDefaults() { this.form.corrected = Inj.defaultParams(this.form.material); },
    async loadFeedback() { this.feedbacks = await Inj.api.get('/api/feedback'); },
    async loadVersions() { this.versions = await Inj.api.get('/api/feedback/models'); },
    async submit() {
      if (!Object.keys(this.form.original).length) {
        this.$message.warning('请先选择一条生产记录作为原始参数'); return;
      }
      this.submitting = true;
      try {
        await Inj.api.post('/api/feedback', {
          material: this.form.material, operator: this.form.operator,
          original_params: this.form.original, corrected_params: this.form.corrected,
          quality_after: this.form.quality_after, defect_after: this.form.defect_after,
          reason: this.form.reason,
        });
        this.$message.success('修正反馈已提交,待在线学习应用');
        this.loadFeedback();
      } catch (e) {
        this.$message.error('提交失败: ' + (e.response?.data?.detail || e.message));
      } finally { this.submitting = false; }
    },
    async loadRecordToCorrect() {
      if (!this.fromRecordId) return;
      const r = await Inj.api.get('/api/records?page=1&page_size=100');
      const rec = r.items.find(x => x.id === this.fromRecordId);
      if (rec) {
        this.form.material = rec.material;
        this.form.original = { ...rec.params };
        this.form.corrected = { ...rec.params };
      }
    },
    async retrain() {
      this.retraining = true;
      try {
        this.retrainResult = await Inj.api.post('/api/feedback/retrain');
        if (this.retrainResult.retrained) {
          this.$message.success(`在线学习完成: 应用 ${this.retrainResult.feedback_used} 条反馈, AUC ${this.retrainResult.metrics.auc}`);
        } else {
          this.$message.info(this.retrainResult.message);
        }
        this.loadFeedback(); this.loadVersions();
      } catch (e) {
        this.$message.error('重训失败: ' + (e.response?.data?.detail || e.message));
      } finally { this.retraining = false; }
    },
    diffList() {
      const diffs = [];
      for (const f of Inj.FEATURES) {
        const o = this.form.original[f], c = this.form.corrected[f];
        if (o != null && c != null && Math.abs(o - c) > 1e-6) diffs.push({ f, o, c });
      }
      return diffs;
    },
  },
  mounted() {
    if (!Inj.materialsMeta.loaded) Inj.loadMaterials().then(() => this.fillDefaults());
    else this.fillDefaults();
    this.loadFeedback(); this.loadVersions();
  },
  template: `
  <div>
    <div class="page-title">反馈修正</div>
    <div class="page-desc">记录老师傅的手动参数调整,积累足够反馈后触发「在线学习」反哺质量预测模型</div>

    <div class="page-card">
      <div class="card-title">提交人工修正</div>
      <div class="flex" style="margin-bottom:12px">
        <span style="font-size:13px">选择生产记录</span>
        <el-input-number v-model="fromRecordId" :min="1" size="small" style="width:130px"
                         controls-position="right" placeholder="记录 ID"/>
        <el-button size="small" @click="loadRecordToCorrect">载入原始参数</el-button>
        <el-input v-model="form.operator" placeholder="师傅姓名" style="width:110px"/>
        <el-input v-model="form.reason" placeholder="修正原因(如: 料温太低打不满)" style="width:220px"/>
      </div>
      <div class="fb-compare">
        <div>
          <div style="font-weight:600;font-size:13px;margin-bottom:8px">原始参数(推荐/原设定)</div>
          <div class="param-grid" style="grid-template-columns:1fr">
            <div class="param-item" v-for="f in Inj.FEATURES" :key="f">
              <div class="label"><span>{{ Inj.FEATURE_LABELS[f] }}</span>
                <span v-if="diffList().some(d => d.f === f)" style="color:var(--status-warning)">已修正</span>
              </div>
              <div style="font-weight:600">{{ form.original[f] ?? '—' }}</div>
            </div>
          </div>
        </div>
        <div>
          <div class="flex-between" style="margin-bottom:8px">
            <div style="font-weight:600;font-size:13px">修正后参数(老师傅调整)</div>
            <el-button size="small" @click="fillDefaults">重置为推荐中值</el-button>
          </div>
          <Inj.ParamInputs v-model="form.corrected" :material="form.material"/>
        </div>
      </div>
      <div class="flex mt16">
        <span style="font-size:13px">修正后质量</span>
        <el-radio-group v-model="form.quality_after">
          <el-radio-button :value="1">合格</el-radio-button>
          <el-radio-button :value="0">不合格</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="submitting" @click="submit">提交修正反馈</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="14">
        <div class="page-card">
          <div class="flex-between">
            <div class="card-title">待学习反馈({{ feedbacks.filter(f => !f.applied).length }})</div>
            <el-button type="success" :loading="retraining" @click="retrain">
              {{ retraining ? '训练中…(约 5 秒)' : '触发在线学习(重训模型)' }}
            </el-button>
          </div>
          <el-alert v-if="retrainResult" type="success" :closable="false" style="margin-bottom:10px"
            :title="'已应用 ' + retrainResult.feedback_used + ' 条反馈, 样本 ' + retrainResult.samples + ', AUC ' + retrainResult.metrics.auc"/>
          <el-table :data="feedbacks" size="small">
            <el-table-column prop="id" label="ID" width="50"/>
            <el-table-column prop="created_at" label="时间" width="130"/>
            <el-table-column prop="material" label="材料" width="70"/>
            <el-table-column prop="operator" label="师傅" width="80"/>
            <el-table-column prop="reason" label="修正原因" min-width="150"/>
            <el-table-column label="结果" width="80">
              <template #default="s">
                <el-tag :type="s.row.quality_after ? 'success' : 'danger'" size="small">
                  {{ s.row.quality_after ? '合格' : '不合格' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="s">
                <el-tag v-if="s.row.applied" type="info" size="small">已学习</el-tag>
                <el-tag v-else type="warning" size="small">待学习</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="10">
        <div class="page-card">
          <div class="card-title">模型版本历史</div>
          <el-timeline>
            <el-timeline-item v-for="v in versions" :key="v.id"
                              :timestamp="v.trained_at" placement="top">
              <div style="font-size:13px">
                版本 #{{ v.id }} · 样本 {{ v.samples }}
                <el-tag size="small" effect="plain" style="margin-left:6px">{{ v.note }}</el-tag>
              </div>
              <div style="font-size:12px;color:var(--ink-secondary)">
                acc {{ (v.metrics.accuracy * 100).toFixed(1) }}% ·
                f1 {{ (v.metrics.f1 * 100).toFixed(1) }}% ·
                auc {{ v.metrics.auc }}
              </div>
            </el-timeline-item>
          </el-timeline>
          <div v-if="!versions.length" style="font-size:13px;color:var(--ink-muted)">
            尚无在线学习记录(初始模型见数据看板)
          </div>
        </div>
      </el-col>
    </el-row>
  </div>`,
};
