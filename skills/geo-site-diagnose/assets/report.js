(() => {
  "use strict";

  const D = GEO_REPORT_DATA;
  const L = D.labels;
  const COLORS = {
    ink: "#17243a",
    blue: "#1b365d",
    blue2: "#496b96",
    muted: "#5f6b7a",
    line: "#dce1e7",
    strongLine: "#bec6d0",
    good: "#23846b",
    warn: "#a96613",
    risk: "#ad4938",
    white: "#ffffff",
    missing: "#e8ebef",
  };
  const FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif';
  const charts = [];
  const pages = D.pages.filter((page) => page.status === "observed");
  const numeric = (value) => typeof value === "number" && Number.isFinite(value);
  const scoreColor = (score) => !numeric(score) ? COLORS.missing : score >= 70 ? COLORS.good : score >= 55 ? COLORS.warn : COLORS.risk;
  const empty = (value) => value === null || value === undefined || value === "";
  const short = (value, length = 18) => String(value || "").length > length ? `${String(value).slice(0, length - 1)}…` : String(value || "");
  const check = (page, id) => page.checks && page.checks[id] ? page.checks[id] : null;
  const checkScore = (page, id) => {
    const item = check(page, id);
    return item && numeric(item.score) ? item.score : -1;
  };
  const base = {
    animation: false,
    textStyle: { fontFamily: FONT, color: COLORS.ink },
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: "item", renderMode: "richText", confine: true },
  };

  function gap(name, reason) {
    const id = `chart-${name.replaceAll("_", "-")}`;
    const element = document.getElementById(id);
    const gapElement = document.querySelector(`[data-chart-gap="${name}"]`);
    if (element) {
      element.hidden = true;
      element.dataset.chartStatus = "gap";
    }
    if (gapElement) {
      gapElement.hidden = false;
      gapElement.textContent = reason || (D.locale === "en-US" ? "Evidence is insufficient, so this chart was not generated" : "当前证据不足，图表未生成");
    }
  }

  function insight(name, message) {
    const element = document.querySelector(`[data-chart-insight="${name}"]`);
    if (element && message) element.textContent = message;
  }

  function mount(name, option, eligible = true, reason = "") {
    if (!eligible) {
      gap(name, reason);
      return null;
    }
    const id = `chart-${name.replaceAll("_", "-")}`;
    const element = document.getElementById(id);
    if (!element) return null;
    const chart = echarts.init(element, null, { renderer: "canvas" });
    chart.setOption({ ...base, ...option });
    element.dataset.chartStatus = "rendered";
    charts.push(chart);
    return chart;
  }

  const dimensionValues = D.dimensions.filter((dimension) => numeric(dimension.score));
  const radarReady = dimensionValues.length === D.dimensions.length && D.dimensions.length > 0;
  mount("radar", {
    radar: {
      indicator: D.dimensions.map((dimension) => ({ name: dimension.label, max: 100 })),
      radius: "61%",
      center: ["50%", "53%"],
      splitNumber: 4,
      axisName: { color: COLORS.muted, fontSize: 11 },
      axisLine: { lineStyle: { color: COLORS.line } },
      splitLine: { lineStyle: { color: COLORS.line } },
      splitArea: { show: false },
    },
    series: [{
      type: "radar",
      data: [{ value: D.dimensions.map((dimension) => dimension.score), name: L.score }],
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { color: COLORS.blue, width: 2 },
      itemStyle: { color: COLORS.blue },
      areaStyle: { color: "rgba(27,54,93,.12)" },
      label: { show: true, formatter: (params) => params.value, color: COLORS.ink, fontSize: 10 },
    }],
  }, radarReady, D.locale === "en-US" ? "One or more dimensions lack evidence, so the radar is withheld" : "一个或多个维度缺少证据，雷达图暂不生成");
  if (radarReady) {
    const weakest = [...D.dimensions].sort((a, b) => a.score - b.score)[0];
    insight("radar", `${weakest.label} ${weakest.score} / 100`);
  }

  mount("dimensions", {
    grid: { left: 126, right: 42, top: 24, bottom: 28 },
    xAxis: { type: "value", min: 0, max: 100, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "category", data: dimensionValues.map((dimension) => dimension.label).reverse(), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 10 } },
    series: [{
      type: "bar",
      data: dimensionValues.map((dimension) => ({ value: dimension.score, weight: dimension.weight, itemStyle: { color: scoreColor(dimension.score) } })).reverse(),
      barWidth: 13,
      label: { show: true, position: "right", formatter: (params) => `${params.value} · ${params.data.weight}%`, color: COLORS.ink, fontSize: 10 },
    }],
  }, dimensionValues.length > 0);

  const crawlerHeat = [];
  D.crawlerMatrix.forEach((crawler, y) => D.pages.forEach((page, x) => {
    const access = crawler.page_access.find((item) => item.url === page.url);
    crawlerHeat.push([x, y, !access || access.allowed === null ? -1 : access.allowed ? 1 : 0]);
  }));
  mount("crawlers", {
    grid: { left: 110, right: 18, top: 22, bottom: 76 },
    xAxis: { type: "category", data: D.pages.map((page) => page.label), axisTick: { show: false }, axisLine: { lineStyle: { color: COLORS.line } }, axisLabel: { rotate: 32, fontSize: 9, color: COLORS.muted } },
    yAxis: { type: "category", data: D.crawlerMatrix.map((crawler) => crawler.agent), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: COLORS.muted } },
    visualMap: { show: false, type: "piecewise", pieces: [{ value: -1, color: COLORS.missing }, { value: 0, color: COLORS.risk }, { value: 1, color: COLORS.good }] },
    series: [{
      type: "heatmap",
      data: crawlerHeat,
      label: { show: true, formatter: (params) => params.value[2] === 1 ? L.allowed : params.value[2] === 0 ? L.blocked : L.unknown, color: COLORS.ink, fontSize: 9 },
      itemStyle: { borderColor: COLORS.white, borderWidth: 3 },
    }],
  }, D.crawlerMatrix.length > 0 && D.pages.length > 0);

  const funnelData = [
    { name: L.discovered, value: D.inventoryCount },
    { name: L.selected, value: D.selectedCount },
    { name: L.observed, value: D.observedCount },
    { name: L.ready, value: D.evidenceReadyCount },
  ];
  mount("funnel", {
    series: [{
      type: "funnel",
      left: "8%", right: "8%", top: 22, bottom: 18,
      minSize: "24%", maxSize: "96%", sort: "descending", gap: 4,
      label: { show: true, formatter: "{b}  {c}", color: COLORS.ink, fontSize: 10 },
      itemStyle: { borderColor: COLORS.white, borderWidth: 2 },
      data: funnelData.map((item, index) => ({ ...item, itemStyle: { color: [COLORS.blue, COLORS.blue2, COLORS.good, COLORS.warn][index] } })),
    }],
  }, funnelData.every((item) => numeric(item.value)));

  mount("types", {
    series: [{
      type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false },
      label: { show: true, formatter: (params) => `${params.name}\n${params.data.status}`, color: COLORS.white, fontSize: 10 },
      itemStyle: { borderColor: COLORS.white, borderWidth: 4, gapWidth: 2 },
      data: D.pages.map((page) => ({ name: page.label, value: 1, status: page.status === "observed" ? L.observedStatus : L.sourceGap, itemStyle: { color: page.status === "observed" ? COLORS.blue : COLORS.risk } })),
    }],
  }, D.pages.length > 0);

  const representativePages = D.pages.filter((page) => numeric(page.selection && page.selection.representativeness));
  mount("representativeness", {
    grid: { left: 104, right: 36, top: 20, bottom: 26 },
    xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: "category", data: representativePages.map((page) => page.label).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 10 } },
    series: [{ type: "bar", data: representativePages.map((page) => page.selection.representativeness).reverse(), barWidth: 3, itemStyle: { color: COLORS.line } }, { type: "scatter", data: representativePages.map((page) => page.selection.representativeness).reverse(), symbolSize: 11, itemStyle: { color: COLORS.blue }, label: { show: true, position: "right", formatter: "{c}", color: COLORS.ink, fontSize: 9 } }],
  }, representativePages.length > 0);

  const graphReady = D.graph.nodes.length >= 2 && D.graph.links.length >= 1;
  mount("links", {
    series: [{
      type: "graph", layout: "force", roam: true,
      force: { repulsion: 130, edgeLength: 72 },
      data: D.graph.nodes.map((node) => ({ ...node, symbolSize: numeric(node.value) ? 27 + node.value * .18 : 30, itemStyle: { color: scoreColor(node.value) }, label: { show: true, formatter: short(node.name, 10), color: COLORS.ink, fontSize: 9, position: "bottom" } })),
      links: D.graph.links,
      lineStyle: { color: COLORS.strongLine, width: 1.2, curveness: .08 },
      emphasis: { focus: "adjacency" },
    }],
  }, graphReady, D.locale === "en-US" ? "At least two pages and one observed link are required" : "至少需要两个页面和一条可观察内链");

  function matrix(name, checkIds, labels) {
    const data = [];
    D.pages.forEach((page, y) => checkIds.forEach((id, x) => data.push([x, y, checkScore(page, id)])));
    mount(name, {
      grid: { left: 104, right: 18, top: 18, bottom: 68 },
      xAxis: { type: "category", data: labels, axisTick: { show: false }, axisLine: { lineStyle: { color: COLORS.line } }, axisLabel: { rotate: labels.length > 2 ? 25 : 0, fontSize: 9, color: COLORS.muted } },
      yAxis: { type: "category", data: D.pages.map((page) => page.label), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: COLORS.muted } },
      visualMap: { type: "piecewise", orient: "horizontal", left: "center", bottom: 2, pieces: [{ value: -1, label: L.missing, color: COLORS.missing }, { min: 0, max: 39, label: "0–39", color: COLORS.risk }, { min: 40, max: 69, label: "40–69", color: COLORS.warn }, { min: 70, max: 100, label: "70–100", color: COLORS.good }], textStyle: { fontSize: 9, color: COLORS.muted } },
      series: [{ type: "heatmap", data, label: { show: true, formatter: (params) => params.value[2] < 0 ? "–" : params.value[2], color: COLORS.ink, fontSize: 9 }, itemStyle: { borderColor: COLORS.white, borderWidth: 3 } }],
    }, D.pages.length > 0);
  }

  function ranking(name, dimension) {
    const ranked = pages.filter((page) => numeric(page.dimensions[dimension])).sort((a, b) => a.dimensions[dimension] - b.dimensions[dimension]);
    mount(name, {
      grid: { left: 104, right: 34, top: 18, bottom: 26 },
      xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: "category", data: ranked.map((page) => page.label), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 9 } },
      series: [{ type: "bar", data: ranked.map((page) => ({ value: page.dimensions[dimension], itemStyle: { color: scoreColor(page.dimensions[dimension]) } })), barWidth: 12, label: { show: true, position: "right", color: COLORS.ink, fontSize: 9 } }],
    }, ranked.length > 0);
    if (ranked.length) insight(name, `${ranked[0].label} ${ranked[0].dimensions[dimension]} / 100`);
  }

  matrix("entity_matrix", ["entity-heading", "entity-schema"], D.locale === "en-US" ? ["Entity heading", "Entity Schema"] : ["实体标题", "实体 Schema"]);
  ranking("entity_ranking", "entity_clarity");
  ranking("answer_ranking", "answerability");

  const answerPoints = pages.filter((page) => numeric(page.metrics.visible_text_length)).map((page) => {
    const structure = (page.metrics.h2_count || 0) + (page.metrics.h3_count || 0) + (page.metrics.list_count || 0) + (page.metrics.table_count || 0);
    return { name: page.label, value: [page.metrics.visible_text_length, structure, page.dimensions.answerability], symbolSize: 10 + Math.min(18, (page.metrics.faq_like_count || 0) * 4), itemStyle: { color: scoreColor(page.dimensions.answerability) } };
  });
  mount("answer_scatter", {
    grid: { left: 64, right: 24, top: 25, bottom: 46 },
    xAxis: { type: "value", name: L.contentDepth, nameLocation: "middle", nameGap: 30, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "value", name: L.structureDensity, nameGap: 36, splitLine: { lineStyle: { color: COLORS.line } } },
    series: [{ type: "scatter", data: answerPoints, label: { show: true, formatter: (params) => params.data.name, position: "top", color: COLORS.muted, fontSize: 9 } }],
  }, answerPoints.length > 0);

  matrix("evidence_matrix", ["evidence-language", "external-sources", "numeric-proof"], D.locale === "en-US" ? ["Source language", "External sources", "Numeric proof"] : ["来源语言", "外部来源", "数字证明"]);
  ranking("evidence_ranking", "evidence_citation");
  matrix("authority_matrix", ["authorship", "trust-contact"], D.locale === "en-US" ? ["Authorship", "Trust contact"] : ["作者归属", "信任联系"]);
  ranking("authority_ranking", "authority_trust");

  mount("schema", {
    series: [{
      type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false },
      data: D.schemas.map((item, index) => ({ ...item, itemStyle: { color: [COLORS.blue, COLORS.blue2, COLORS.good, COLORS.warn, COLORS.risk][index % 5] } })),
      label: { show: true, formatter: "{b}\n{c}", color: COLORS.white, fontSize: 10 },
      itemStyle: { borderColor: COLORS.white, borderWidth: 4, gapWidth: 2 },
    }],
  }, D.schemas.length > 0, D.locale === "en-US" ? "No structured data types were observed" : "代表页面中未观察到结构化数据类型");
  matrix("structured_matrix", ["semantic-landmarks", "structured-data"], D.locale === "en-US" ? ["Semantic landmarks", "Structured data"] : ["语义地标", "结构化数据"]);

  const freshness = pages.map((page) => ({ page, value: page.selection && page.selection.lastmod, date: page.selection && page.selection.lastmod ? Date.parse(page.selection.lastmod) : NaN })).filter((item) => Number.isFinite(item.date));
  mount("freshness", {
    grid: { left: 104, right: 24, top: 24, bottom: 42 },
    xAxis: { type: "time", splitLine: { lineStyle: { color: COLORS.line } }, axisLabel: { fontSize: 9, color: COLORS.muted } },
    yAxis: { type: "category", data: freshness.map((item) => item.page.label), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: COLORS.muted } },
    series: [{ type: "scatter", symbolSize: 12, data: freshness.map((item, index) => ({ name: item.page.label, value: [item.value, index], itemStyle: { color: scoreColor(item.page.dimensions.freshness) } })), label: { show: true, formatter: (params) => String(params.value[0]).slice(0, 10), position: "right", color: COLORS.muted, fontSize: 8 } }],
  }, freshness.length > 0, D.locale === "en-US" ? "No valid sitemap lastmod dates were observed" : "未观察到有效的站点地图 lastmod 日期");

  const pageHeat = [];
  pages.forEach((page, y) => D.dimensions.forEach((dimension, x) => pageHeat.push([x, y, numeric(page.dimensions[dimension.id]) ? page.dimensions[dimension.id] : -1])));
  mount("page_heatmap", {
    grid: { left: 106, right: 18, top: 18, bottom: 82 },
    xAxis: { type: "category", data: D.dimensions.map((dimension) => dimension.label), axisTick: { show: false }, axisLabel: { rotate: 34, fontSize: 9, color: COLORS.muted } },
    yAxis: { type: "category", data: pages.map((page) => page.label), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: COLORS.muted } },
    visualMap: { type: "piecewise", orient: "horizontal", left: "center", bottom: 2, pieces: [{ value: -1, label: L.missing, color: COLORS.missing }, { min: 0, max: 39, label: "0–39", color: COLORS.risk }, { min: 40, max: 69, label: "40–69", color: COLORS.warn }, { min: 70, max: 100, label: "70–100", color: COLORS.good }], textStyle: { fontSize: 9, color: COLORS.muted } },
    series: [{ type: "heatmap", data: pageHeat, label: { show: true, formatter: (params) => params.value[2] < 0 ? "–" : params.value[2], color: COLORS.ink, fontSize: 8 }, itemStyle: { borderColor: COLORS.white, borderWidth: 2 } }],
  }, pages.length > 0);

  if (pages.length >= 3) {
    mount("distribution", {
      grid: { left: 42, right: 16, top: 20, bottom: 38 },
      xAxis: { type: "category", data: Object.keys(D.scoreBins), axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 9 } },
      yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false } },
      series: [{ type: "bar", data: Object.values(D.scoreBins), barWidth: "55%", itemStyle: { color: COLORS.blue }, label: { show: true, position: "top", color: COLORS.ink } }],
    });
  } else {
    const ranked = [...pages].sort((a, b) => a.score - b.score);
    mount("distribution", {
      grid: { left: 104, right: 34, top: 20, bottom: 26 },
      xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: COLORS.line } } },
      yAxis: { type: "category", data: ranked.map((page) => page.label), axisLine: { show: false }, axisTick: { show: false } },
      series: [{ type: "bar", data: ranked.map((page) => ({ value: page.score, itemStyle: { color: scoreColor(page.score) } })), label: { show: true, position: "right" } }],
    }, ranked.length > 0);
    insight("distribution", D.locale === "en-US" ? "Small samples use a page ranking fallback" : "小样本已切换为页面排序视图");
  }

  const severityOrder = ["critical", "high", "medium", "low"];
  const issueGroups = new Map();
  D.issues.forEach((issue) => {
    if (!issueGroups.has(issue.dimension)) issueGroups.set(issue.dimension, new CounterShim());
    issueGroups.get(issue.dimension).add(issue.severity);
  });
  const severityData = [...issueGroups.entries()].map(([dimension, counts]) => ({
    name: (D.dimensions.find((item) => item.id === dimension) || { label: dimension }).label,
    value: counts.total,
    children: severityOrder.filter((severity) => counts.get(severity) > 0).map((severity) => ({ name: severity, value: counts.get(severity), itemStyle: { color: severity === "critical" || severity === "high" ? COLORS.risk : severity === "medium" ? COLORS.warn : COLORS.good } })),
    itemStyle: { color: COLORS.blue },
  }));
  mount("severity", {
    series: [{ type: "sunburst", radius: ["14%", "83%"], data: severityData, label: { rotate: "radial", formatter: "{b}\n{c}", fontSize: 9 }, itemStyle: { borderColor: COLORS.white, borderWidth: 3 } }],
  }, severityData.length > 0, D.locale === "en-US" ? "No failed checks were observed" : "当前快照未观察到失败检查项");

  const actions = D.actions.filter((action) => numeric(action.impact) && numeric(action.effort) && numeric(action.priority));
  mount("priority", {
    grid: { left: 48, right: 20, top: 22, bottom: 44 },
    xAxis: { type: "value", name: L.effort, min: .5, max: 5.5, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "value", name: L.impact, min: .5, max: 5.5, splitLine: { lineStyle: { color: COLORS.line } } },
    series: [{ type: "scatter", data: actions.map((action) => ({ name: action.title, value: [action.effort, action.impact, action.priority], symbolSize: 10 + Math.min(24, action.priority / 7), symbol: action.severity === "critical" ? "diamond" : action.severity === "high" ? "triangle" : "circle", itemStyle: { color: action.severity === "critical" || action.severity === "high" ? COLORS.risk : action.severity === "medium" ? COLORS.warn : COLORS.good } })), label: { show: false } }],
  }, actions.length > 0);

  const rankedActions = [...actions].sort((a, b) => b.priority - a.priority).slice(0, 10).reverse();
  mount("priority_ranking", {
    grid: { left: 110, right: 38, top: 18, bottom: 26 },
    xAxis: { type: "value", min: 0, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false } },
    yAxis: { type: "category", data: rankedActions.map((action) => short(action.title, 12)), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: COLORS.muted } },
    series: [{ type: "bar", data: rankedActions.map((action) => ({ value: action.priority, itemStyle: { color: action.severity === "critical" || action.severity === "high" ? COLORS.risk : action.severity === "medium" ? COLORS.warn : COLORS.good } })), barWidth: 12, label: { show: true, position: "right", color: COLORS.ink, fontSize: 9 } }],
  }, rankedActions.length > 0);

  function CounterShim() {
    this.values = new Map();
    this.total = 0;
    this.add = (key) => { this.values.set(key, (this.values.get(key) || 0) + 1); this.total += 1; };
    this.get = (key) => this.values.get(key) || 0;
  }

  const navLinks = [...document.querySelectorAll(".nav-links a, .nav-mobile a")];
  const sections = [...document.querySelectorAll("main > section.module")];
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      navLinks.forEach((link) => link.setAttribute("aria-current", link.getAttribute("href") === `#${visible.target.id}` ? "true" : "false"));
    }, { rootMargin: "-18% 0px -68% 0px", threshold: [0, .1, .35] });
    sections.forEach((section) => observer.observe(section));
  }
  navLinks.forEach((link) => link.addEventListener("click", () => {
    const details = link.closest("details");
    if (details) details.removeAttribute("open");
  }));

  const resize = () => charts.forEach((chart) => chart.resize());
  window.addEventListener("resize", resize, { passive: true });
  window.addEventListener("beforeprint", () => {
    document.querySelectorAll("details").forEach((details) => { details.dataset.printOpen = details.open ? "1" : "0"; details.open = true; });
    resize();
  });
  window.addEventListener("afterprint", () => {
    document.querySelectorAll("details").forEach((details) => { details.open = details.dataset.printOpen === "1"; delete details.dataset.printOpen; });
    resize();
  });
  window.__GEO_REPORT_READY__ = Promise.resolve({ charts: charts.length, figures: document.querySelectorAll("[data-chart]").length });
})();
