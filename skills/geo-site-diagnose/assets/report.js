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
    critical: "#7f3028",
    white: "#ffffff",
    missing: "#e8ebef",
  };
  const FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif';
  const charts = [];
  const pages = D.pages.filter((page) => page.status === "observed");
  const numeric = (value) => typeof value === "number" && Number.isFinite(value);
  const scoreColor = (score) => !numeric(score) ? COLORS.missing : score >= 70 ? COLORS.good : score >= 55 ? COLORS.warn : COLORS.risk;
  const empty = (value) => value === null || value === undefined || value === "";
  const wrapAxisLabel = (value, length = 5) => {
    const label = String(value || "").trim();
    if (!label) return "";
    if (label.includes(" ")) {
      const lines = [];
      label.split(/\s+/).forEach((word) => {
        const last = lines.at(-1);
        if (last && `${last} ${word}`.length <= Math.max(length, 10)) lines[lines.length - 1] = `${last} ${word}`;
        else lines.push(word);
      });
      return lines.join("\n");
    }
    return label.match(new RegExp(`.{1,${length}}`, "g"))?.join("\n") || label;
  };
  const dimensionLabel = (id) => (D.dimensions.find((dimension) => dimension.id === id) || { label: id }).label;
  const check = (page, id) => page.checks && page.checks[id] ? page.checks[id] : null;
  const checkScore = (page, id) => {
    const item = check(page, id);
    return item && numeric(item.score) ? item.score : -1;
  };
  const base = {
    animation: false,
    textStyle: { fontFamily: FONT, color: COLORS.ink },
    aria: { enabled: true, decal: { show: false } },
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
      indicator: D.dimensions.map((dimension) => ({ name: `${wrapAxisLabel(dimension.label, D.locale === "en-US" ? 12 : 5)}\n${dimension.score}`, max: 100 })),
      radius: "54%",
      center: ["50%", "53%"],
      splitNumber: 4,
      axisName: { color: COLORS.muted, fontSize: 10, lineHeight: 13 },
      axisLine: { lineStyle: { color: COLORS.line } },
      splitLine: { lineStyle: { color: COLORS.line } },
      splitArea: { show: false },
    },
    series: [{
      type: "radar",
      data: [{ value: D.dimensions.map((dimension) => dimension.score), name: L.score }],
      symbol: "none",
      lineStyle: { color: COLORS.blue, width: 2 },
      itemStyle: { color: COLORS.blue },
      areaStyle: { color: "rgba(27,54,93,.12)" },
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
    xAxis: { type: "category", data: D.pages.map((page) => page.label), axisTick: { show: false }, axisLine: { lineStyle: { color: COLORS.line } }, axisLabel: { interval: 0, formatter: (value) => wrapAxisLabel(value, D.locale === "en-US" ? 10 : 4), fontSize: 9, lineHeight: 12, color: COLORS.muted } },
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
  const funnelBase = numeric(funnelData[0].value) && funnelData[0].value > 0 ? funnelData[0].value : 1;
  const funnelStages = funnelData.map((item, index) => {
    const previous = index > 0 ? funnelData[index - 1].value : item.value;
    return {
      ...item,
      step: index + 1,
      retention: Math.max(0, Math.min(100, Math.round(item.value / funnelBase * 100))),
      drop: numeric(previous) ? Math.max(0, previous - item.value) : 0,
    };
  });
  const funnelDisplay = [...funnelStages].reverse();
  mount("funnel", {
    grid: { left: 112, right: 78, top: 22, bottom: 28 },
    xAxis: { type: "value", min: 0, max: 100, show: false },
    yAxis: {
      type: "category",
      data: funnelDisplay.map((stage) => `${String(stage.step).padStart(2, "0")}  ${stage.name}`),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: COLORS.muted, fontSize: 10, lineHeight: 13 },
    },
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        const stage = funnelDisplay[params.dataIndex];
        const dropText = stage.drop > 0
          ? `${D.locale === "en-US" ? "Step loss" : "阶段损耗"} ${stage.drop}`
          : (D.locale === "en-US" ? "No step loss" : "本阶段无损耗");
        return `${stage.name}<br>${stage.value} · ${stage.retention}%<br>${dropText}`;
      },
    },
    series: [
      {
        type: "bar",
        silent: true,
        barWidth: 28,
        data: funnelDisplay.map(() => 100),
        itemStyle: { color: "#eef1f4", borderRadius: 2 },
      },
      {
        type: "bar",
        barGap: "-100%",
        barWidth: 28,
        data: funnelDisplay.map((stage) => ({
          value: stage.retention,
          itemStyle: { color: stage.drop > 0 ? COLORS.warn : COLORS.blue, borderRadius: 2 },
        })),
        label: {
          show: true,
          position: "right",
          distance: 10,
          formatter: (params) => {
            const stage = funnelDisplay[params.dataIndex];
            return `${stage.value} · ${stage.retention}%`;
          },
          color: COLORS.ink,
          fontSize: 10,
        },
      },
    ],
  }, funnelData.every((item) => numeric(item.value)));
  if (funnelStages.length > 0) {
    const largestDrop = [...funnelStages].sort((a, b) => b.drop - a.drop)[0];
    insight("funnel", largestDrop.drop > 0
      ? `${largestDrop.name} ${largestDrop.value} / ${funnelBase} · ${D.locale === "en-US" ? "loss" : "损耗"} ${largestDrop.drop}`
      : (D.locale === "en-US" ? "All stages retained the discovered pages" : "各阶段均完整保留已发现页面"));
  }

  const pageTypeData = D.pages.map((page) => ({
    name: page.label,
    status: page.status === "observed" ? L.observedStatus : L.sourceGap,
    color: page.status === "observed" ? COLORS.blue : COLORS.risk,
  })).reverse();
  mount("types", {
    grid: { left: 112, right: 18, top: 18, bottom: 20 },
    xAxis: { type: "value", min: 0, max: 1, show: false },
    yAxis: { type: "category", data: pageTypeData.map((page) => page.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { formatter: (value) => wrapAxisLabel(value, D.locale === "en-US" ? 12 : 6), color: COLORS.muted, fontSize: 9, lineHeight: 11 } },
    series: [{
      type: "bar",
      barWidth: 16,
      data: pageTypeData.map((page) => ({ value: 1, status: page.status, itemStyle: { color: page.color } })),
      label: { show: true, position: "insideRight", formatter: (params) => params.data.status, color: COLORS.white, fontSize: 9 },
    }],
  }, pageTypeData.length > 0);

  const representativePages = D.pages.filter((page) => numeric(page.selection && page.selection.representativeness));
  mount("representativeness", {
    grid: { left: 104, right: 36, top: 20, bottom: 26 },
    xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false }, axisTick: { show: false } },
    yAxis: { type: "category", data: representativePages.map((page) => page.label).reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 10 } },
    series: [{ type: "bar", data: representativePages.map((page) => page.selection.representativeness).reverse(), barWidth: 3, itemStyle: { color: COLORS.line } }, { type: "scatter", data: representativePages.map((page) => page.selection.representativeness).reverse(), symbolSize: 11, itemStyle: { color: COLORS.blue }, label: { show: true, position: "right", formatter: "{c}", color: COLORS.ink, fontSize: 9 } }],
  }, representativePages.length > 0);

  const graphReady = D.graph.nodes.length >= 2 && D.graph.links.length >= 1;
  const graphLinkKeys = new Set(D.graph.links.map((link) => `${link.source}:${link.target}`));
  const linkMatrix = [];
  D.graph.nodes.forEach((source, y) => D.graph.nodes.forEach((target, x) => {
    linkMatrix.push([x, y, graphLinkKeys.has(`${source.id}:${target.id}`) ? 1 : 0]);
  }));
  mount("links", {
    grid: { left: 112, right: 18, top: 18, bottom: 34 },
    xAxis: { type: "category", data: D.graph.nodes.map((_node, index) => index + 1), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 9 } },
    yAxis: { type: "category", data: D.graph.nodes.map((node, index) => `${index + 1}  ${wrapAxisLabel(node.name, D.locale === "en-US" ? 12 : 6)}`), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 8, lineHeight: 10 } },
    visualMap: { show: false, type: "piecewise", pieces: [{ value: 0, color: "#f2f4f6" }, { value: 1, color: COLORS.blue }] },
    tooltip: { formatter: (params) => {
      const source = D.graph.nodes[params.value[1]];
      const target = D.graph.nodes[params.value[0]];
      return `${source.name} → ${target.name}<br>${params.value[2] ? (D.locale === "en-US" ? "Observed link" : "已观察内链") : (D.locale === "en-US" ? "No observed link" : "未观察到内链")}`;
    } },
    series: [{ type: "heatmap", data: linkMatrix, label: { show: true, formatter: (params) => params.value[2] ? "1" : "", color: COLORS.white, fontSize: 8 }, itemStyle: { borderColor: COLORS.white, borderWidth: 2 } }],
  }, graphReady, D.locale === "en-US" ? "At least two pages and one observed link are required" : "至少需要两个页面和一条可观察内链");

  function matrix(name, checkIds, labels) {
    const data = [];
    D.pages.forEach((page, y) => checkIds.forEach((id, x) => data.push([x, y, checkScore(page, id)])));
    mount(name, {
      grid: { left: 104, right: 18, top: 18, bottom: 68 },
      xAxis: { type: "category", data: labels, axisTick: { show: false }, axisLine: { lineStyle: { color: COLORS.line } }, axisLabel: { interval: 0, formatter: (value) => wrapAxisLabel(value, D.locale === "en-US" ? 12 : 5), fontSize: 9, lineHeight: 12, color: COLORS.muted } },
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
    return { name: page.label, value: [page.metrics.visible_text_length, structure, page.dimensions.answerability], symbol: "circle", symbolSize: 10 + Math.min(18, (page.metrics.faq_like_count || 0) * 4), itemStyle: { color: scoreColor(page.dimensions.answerability), borderColor: COLORS.white, borderWidth: 1 } };
  });
  mount("answer_scatter", {
    grid: { left: 64, right: 24, top: 25, bottom: 46 },
    xAxis: { type: "value", name: L.contentDepth, nameLocation: "middle", nameGap: 30, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "value", name: L.structureDensity, nameGap: 36, splitLine: { lineStyle: { color: COLORS.line } } },
    series: [{ type: "scatter", data: answerPoints, label: { show: true, formatter: (params) => params.data.name, position: "top", color: COLORS.muted, fontSize: 9 }, labelLayout: { hideOverlap: true } }],
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
    series: [{ type: "scatter", symbol: "circle", symbolSize: 12, data: freshness.map((item, index) => ({ name: item.page.label, value: [item.value, index], itemStyle: { color: scoreColor(item.page.dimensions.freshness), borderColor: COLORS.white, borderWidth: 1 } })), label: { show: true, formatter: (params) => String(params.value[0]).slice(0, 10), position: "right", color: COLORS.muted, fontSize: 8 }, labelLayout: { hideOverlap: true } }],
  }, freshness.length > 0, D.locale === "en-US" ? "No valid sitemap lastmod dates were observed" : "未观察到有效的站点地图 lastmod 日期");

  const pageHeat = [];
  pages.forEach((page, y) => D.dimensions.forEach((dimension, x) => pageHeat.push([x, y, numeric(page.dimensions[dimension.id]) ? page.dimensions[dimension.id] : -1])));
  mount("page_heatmap", {
    grid: { left: 106, right: 18, top: 18, bottom: 82 },
    xAxis: { type: "category", data: D.dimensions.map((dimension) => dimension.label), axisTick: { show: false }, axisLabel: { interval: 0, formatter: (value) => wrapAxisLabel(value, D.locale === "en-US" ? 12 : 4), fontSize: 9, lineHeight: 12, color: COLORS.muted } },
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
  const severityColors = { critical: COLORS.critical, high: COLORS.risk, medium: COLORS.warn, low: COLORS.good };
  const issueGroups = new Map();
  D.issues.forEach((issue) => {
    if (!issueGroups.has(issue.dimension)) issueGroups.set(issue.dimension, new CounterShim());
    issueGroups.get(issue.dimension).add(issue.severity);
  });
  const severityData = [...issueGroups.entries()].map(([dimension, counts]) => ({
    name: dimensionLabel(dimension),
    value: counts.total,
    counts: Object.fromEntries(severityOrder.map((severity) => [severity, counts.get(severity)])),
  }));
  mount("severity", {
    legend: { top: 4, left: "center", itemWidth: 9, itemHeight: 9, textStyle: { color: COLORS.muted, fontSize: 9 } },
    grid: { left: 88, right: 18, top: 42, bottom: 24 },
    xAxis: { type: "value", minInterval: 1, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "category", data: severityData.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { formatter: (value) => wrapAxisLabel(value, D.locale === "en-US" ? 12 : 5), color: COLORS.muted, fontSize: 9, lineHeight: 11 } },
    series: severityOrder.map((severity) => ({
      name: severity,
      type: "bar",
      stack: "severity",
      barWidth: 16,
      itemStyle: { color: severityColors[severity] },
      data: severityData.map((item) => item.counts[severity]),
      label: { show: true, position: "inside", formatter: (params) => params.value > 0 ? params.value : "", color: COLORS.white, fontSize: 9 },
    })),
  }, severityData.length > 0, D.locale === "en-US" ? "No failed checks were observed" : "当前快照未观察到失败检查项");

  const actions = D.actions.filter((action) => numeric(action.impact) && numeric(action.effort) && numeric(action.priority));
  const actionGroups = new Map();
  actions.forEach((action) => {
    const key = `${action.effort}:${action.impact}`;
    const current = actionGroups.get(key) || { effort: action.effort, impact: action.impact, actions: [], priority: 0, severity: "low" };
    current.actions.push(action);
    current.priority = Math.max(current.priority, action.priority);
    if (severityOrder.indexOf(action.severity) < severityOrder.indexOf(current.severity)) current.severity = action.severity;
    actionGroups.set(key, current);
  });
  const priorityPoints = [...actionGroups.values()];
  mount("priority", {
    grid: { left: 50, right: 22, top: 20, bottom: 52 },
    xAxis: { type: "value", name: L.effort, nameLocation: "middle", nameGap: 30, min: .5, max: 5.5, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: COLORS.line } } },
    yAxis: { type: "value", name: L.impact, nameLocation: "middle", nameGap: 34, min: .5, max: 5.5, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: COLORS.line } } },
    tooltip: { formatter: (params) => `${L.effort} ${params.value[0]} · ${L.impact} ${params.value[1]}<br>${params.data.actionCount} ${D.locale === "en-US" ? "actions" : "项行动"}` },
    series: [{ type: "scatter", symbol: "circle", data: priorityPoints.map((group) => ({ name: group.actions.map((action) => action.title).join("\n"), value: [group.effort, group.impact, group.priority], actionCount: group.actions.length, symbolSize: 16 + Math.min(14, group.actions.length * 2), itemStyle: { color: severityColors[group.severity], borderColor: COLORS.white, borderWidth: 2 } })), label: { show: true, formatter: (params) => params.data.actionCount > 1 ? params.data.actionCount : "", color: COLORS.white, fontSize: 9 } }],
  }, actions.length > 0);

  const rankedActions = [...actions].sort((a, b) => b.priority - a.priority).slice(0, 10).map((action, index) => ({ ...action, rank: index + 1 })).reverse();
  mount("priority_ranking", {
    grid: { left: 112, right: 38, top: 18, bottom: 26 },
    xAxis: { type: "value", min: 0, splitLine: { lineStyle: { color: COLORS.line } }, axisLine: { show: false } },
    yAxis: { type: "category", data: rankedActions.map((action) => `${action.rank}. ${dimensionLabel(action.dimension)}`), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: COLORS.muted } },
    tooltip: { formatter: (params) => rankedActions[params.dataIndex].title },
    series: [{ type: "bar", data: rankedActions.map((action) => ({ value: action.priority, itemStyle: { color: severityColors[action.severity] } })), barWidth: 12, label: { show: true, position: "right", color: COLORS.ink, fontSize: 9 } }],
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
