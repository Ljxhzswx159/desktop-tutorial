/* 根应用: 页面切换 + 组件注册 */
(function () {
  const app = Vue.createApp({
    computed: {
      page() { return Inj.bus.page; },
    },
    methods: {
      switchPage(p) { Inj.bus.goto(p); },
    },
  });

  app.use(ElementPlus);
  // prod 构建模板编译为 _ctx.Inj 访问,需挂到 globalProperties
  app.config.globalProperties.Inj = Inj;
  app.component('recommend-page', Inj.RecommendPage);
  app.component('predict-page', Inj.PredictPage);
  app.component('knowledge-page', Inj.KnowledgePage);
  app.component('dashboard-page', Inj.DashboardPage);
  app.component('records-page', Inj.RecordsPage);
  app.component('feedback-page', Inj.FeedbackPage);

  app.mount('#app');
})();
