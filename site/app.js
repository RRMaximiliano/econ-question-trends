(function () {
  const data = window.EQT_TREND_DATA;
  if (!data) {
    document.body.innerHTML = "<main class='main'><h1>Missing site/data.js</h1></main>";
    return;
  }

  const categories = ["causal", "predictive", "other", "insufficient_text"];
  const categoryColors = {
    causal: "var(--green)",
    predictive: "var(--blue)",
    other: "var(--gold)",
    insufficient_text: "var(--rose)",
  };
  const categoryLabels = {
    causal: "causal",
    predictive: "predictive",
    other: "other",
    insufficient_text: "insufficient text",
  };
  const journalLabels = {
    aer: "AER",
    qje: "QJE",
    jpe: "JPE",
    ecta: "ECTA",
    restud: "ReStud",
  };

  const state = {
    fullScenario: "baseline",
    recentScenario: "baseline",
    journalCategory: "causal",
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const num = (value) => Number.parseFloat(value || "0") || 0;
  const int = (value) => Number.parseInt(value || "0", 10) || 0;
  const pct = (value, digits = 1) => `${(num(value) * 100).toFixed(digits)}%`;
  const pp = (value, digits = 1) => {
    const parsed = num(value) * 100;
    const sign = parsed > 0 ? "+" : "";
    return `${sign}${parsed.toFixed(digits)} pp`;
  };
  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[char]);

  function init() {
    hydrateShell();
    bindControls();
    renderAll();
    bindNav();
  }

  function hydrateShell() {
    const gate = data.validationGate.validation_gate || "unknown";
    $("#sidebarGate").textContent = gate;
    $("#sidebarGenerated").textContent = `updated ${new Date(data.generatedAt).toLocaleDateString()}`;

    const storedTheme = localStorage.getItem("eqt-theme");
    if (storedTheme === "dark" || storedTheme === "light") {
      document.documentElement.setAttribute("data-theme", storedTheme);
    }

    $("#themeToggle").addEventListener("click", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("eqt-theme", next);
    });
  }

  function bindControls() {
    $$("[data-full-scenario]").forEach((button) => {
      button.addEventListener("click", () => {
        state.fullScenario = button.dataset.fullScenario;
        setActive("[data-full-scenario]", button);
        renderFullTrend();
      });
    });

    $$("[data-recent-scenario]").forEach((button) => {
      button.addEventListener("click", () => {
        state.recentScenario = button.dataset.recentScenario;
        setActive("[data-recent-scenario]", button);
        renderRecent();
      });
    });

    $$("[data-journal-category]").forEach((button) => {
      button.addEventListener("click", () => {
        state.journalCategory = button.dataset.journalCategory;
        setActive("[data-journal-category]", button);
        renderJournalMoves();
      });
    });
  }

  function setActive(selector, activeButton) {
    $$(selector).forEach((button) => button.classList.toggle("active", button === activeButton));
  }

  function bindNav() {
    const main = $(".main");
    const sections = $$("section[id]");
    const links = $$("[data-nav-link]");
    if (!main || sections.length === 0) return;

    function topbarHeight() {
      return $(".topbar")?.offsetHeight || 0;
    }

    function setActiveLink(sectionId) {
      links.forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === `#${sectionId}`);
      });
    }

    function updateActiveLink() {
      const atBottom = main.scrollTop + main.clientHeight >= main.scrollHeight - 2;
      if (atBottom) {
        setActiveLink(sections[sections.length - 1].id);
        return;
      }

      const marker = main.scrollTop + topbarHeight() + 24;
      let current = sections[0].id;
      sections.forEach((section) => {
        if (section.offsetTop <= marker) {
          current = section.id;
        }
      });
      setActiveLink(current);
    }

    links.forEach((link) => {
      link.addEventListener("click", (event) => {
        const targetId = link.getAttribute("href")?.slice(1);
        const target = targetId ? document.getElementById(targetId) : null;
        if (!target) return;

        event.preventDefault();
        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        main.scrollTo({
          top: Math.max(0, target.offsetTop - topbarHeight()),
          behavior: reduceMotion ? "auto" : "smooth",
        });
        window.history.pushState(null, "", `#${targetId}`);
        setActiveLink(targetId);
      });
    });

    let ticking = false;
    main.addEventListener("scroll", () => {
      if (ticking) return;
      window.requestAnimationFrame(() => {
        updateActiveLink();
        ticking = false;
      });
      ticking = true;
    });
    window.addEventListener("resize", updateActiveLink);
    updateActiveLink();
  }

  function renderAll() {
    renderMetrics();
    renderHeadline();
    renderCoverage();
    renderFullTrend();
    renderRecent();
    renderJournalMoves();
    renderValidation();
  }

  function rowsFor(records, filters) {
    return records.filter((row) =>
      Object.entries(filters).every(([key, value]) => String(row[key] ?? "") === String(value)),
    );
  }

  function latestRecentChange(category) {
    return data.recentCategoryTrendChanges.find(
      (row) => row.scenario === "baseline" && row.category === category,
    );
  }

  function renderMetrics() {
    const gate = data.validationGate;
    const causal = latestRecentChange("causal");
    const predictive = latestRecentChange("predictive");
    const other = latestRecentChange("other");
    const validation = data.validationMetrics || {};
    const metrics = [
      {
        label: "Validation gate",
        value: gate.validation_gate || "unknown",
        note: gate.next_action || "No gate note available.",
      },
      {
        label: "Causal share change",
        value: pp(causal?.share_change || 0),
        note: `2023 ${pct(causal?.start_share)} → 2025 ${pct(causal?.end_share)}`,
      },
      {
        label: "Predictive share change",
        value: pp(predictive?.share_change || 0),
        note: `2023 ${pct(predictive?.start_share)} → 2025 ${pct(predictive?.end_share)}`,
      },
      {
        label: "Agreement rate",
        value: pct(validation.agreement_rate || 0),
        note: `${validation.labeled_count || 0} validation rows; other share moved ${pp(other?.share_change || 0)}.`,
      },
    ];

    $("#metricGrid").innerHTML = metrics
      .map(
        (metric) => `
          <article class="metric">
            <div class="metric-label">${escapeHtml(metric.label)}</div>
            <div class="metric-value">${escapeHtml(metric.value)}</div>
            <div class="metric-note">${escapeHtml(metric.note)}</div>
          </article>
        `,
      )
      .join("");
  }

  function renderHeadline() {
    const rows = ["causal", "predictive", "other"].map((category) => latestRecentChange(category));
    $("#headlineList").innerHTML = rows
      .filter(Boolean)
      .map((row) => {
        const change = num(row.share_change);
        return `
          <div class="headline-item">
            <div class="headline-name">${escapeHtml(categoryLabels[row.category])}</div>
            <div>${pct(row.start_share)} → ${pct(row.end_share)}</div>
            <div class="delta ${change >= 0 ? "up" : "down"}">${pp(row.share_change)}</div>
          </div>
        `;
      })
      .join("");
  }

  function renderCoverage() {
    const rows = [...data.insufficientTextRates].sort(
      (a, b) => num(b.insufficient_text_share) - num(a.insufficient_text_share),
    );
    $("#coverageBars").innerHTML = rows
      .map(
        (row) => `
          <div class="bar-row">
            <div class="row-name">${escapeHtml(journalLabels[row.journal_short] || row.journal_short)}</div>
            <div class="bar-track">
              <div class="bar-fill" style="width:${Math.min(100, num(row.insufficient_text_share) * 100)}%"></div>
            </div>
            <div>${pct(row.insufficient_text_share)}</div>
          </div>
        `,
      )
      .join("");
  }

  function renderFullTrend() {
    const records = rowsFor(data.categorySensitivityByYear, { scenario: state.fullScenario });
    const presentCategories = categories.filter((category) =>
      records.some((row) => row.category === category),
    );
    $("#fullLegend").innerHTML = renderLegend(presentCategories);
    drawLineChart($("#fullTrendChart"), records, presentCategories, {
      xKey: "publication_year",
      yKey: "category_share",
      groupKey: "category",
      minYear: 1975,
      maxYear: 2025,
    });
  }

  function renderRecent() {
    const records = rowsFor(data.recentCategoryTrends, { scenario: state.recentScenario });
    const presentCategories = ["causal", "predictive", "other"].filter((category) =>
      records.some((row) => row.category === category),
    );
    $("#recentLegend").innerHTML = renderLegend(presentCategories);
    drawStackedBars($("#recentStackedChart"), records, presentCategories);

    const changeRows = rowsFor(data.recentCategoryTrendChanges, { scenario: state.recentScenario })
      .filter((row) => ["causal", "predictive", "other"].includes(row.category))
      .sort((a, b) => Math.abs(num(b.share_change)) - Math.abs(num(a.share_change)));
    $("#recentChangeTable").innerHTML = changeRows
      .map((row) => {
        const change = num(row.share_change);
        return `
          <div class="table-row">
            <div class="headline-name">${escapeHtml(categoryLabels[row.category])}</div>
            <div>${pct(row.start_share)} → ${pct(row.end_share)}</div>
            <div class="delta ${change >= 0 ? "up" : "down"}">${pp(row.share_change)}</div>
          </div>
        `;
      })
      .join("");
  }

  function renderJournalMoves() {
    const rows = rowsFor(data.recentJournalCategoryTrendChanges, {
      scenario: "baseline",
      category: state.journalCategory,
    }).sort((a, b) => num(b.share_change) - num(a.share_change));
    const maxAbs = Math.max(0.01, ...rows.map((row) => Math.abs(num(row.share_change))));
    $("#journalMoves").innerHTML = rows
      .map((row) => {
        const change = num(row.share_change);
        const width = (Math.abs(change) / maxAbs) * 50;
        const direction = change >= 0 ? "positive" : "negative";
        return `
          <div class="journal-row">
            <div class="journal-name">${escapeHtml(journalLabels[row.journal_short] || row.journal_short)}</div>
            <div class="journal-track">
              <div class="journal-zero"></div>
              <div class="journal-delta ${direction}" style="width:${width}%"></div>
            </div>
            <div>${pct(row.start_share)}</div>
            <div>${pct(row.end_share)}</div>
            <div class="delta ${change >= 0 ? "up" : "down"}">${pp(row.share_change)}</div>
          </div>
        `;
      })
      .join("");
  }

  function renderValidation() {
    $("#validationMetrics").innerHTML = data.validationCategoryMetrics
      .map(
        (row) => `
          <div class="validation-row">
            <div class="row-name">${escapeHtml(categoryLabels[row.label] || row.label)}</div>
            <div class="bar-track">
              <div class="bar-fill" style="width:${Math.min(100, num(row.f1) * 100)}%; background:${categoryColors[row.label] || "var(--accent)"}"></div>
            </div>
            <div>F1 ${row.f1 ? pct(row.f1) : "n/a"}</div>
            <div>P ${row.precision ? pct(row.precision) : "n/a"}</div>
            <div>R ${row.recall ? pct(row.recall) : "n/a"}</div>
          </div>
        `,
      )
      .join("");

    const gateRows = [
      ["validation gate", data.validationGate.validation_gate],
      ["manual labels", `${data.validationGate.completed_manual_labels || 0} / ${data.validationGate.manual_validation_total_rows || 0}`],
      ["overlap labels", `${data.validationGate.completed_overlap_labels || 0} / ${data.validationGate.overlap_rows || 0}`],
      ["adjudications", `${data.validationGate.completed_adjudications || 0} / ${data.validationGate.pending_adjudication_rows || 0}`],
      ["recommendation", data.validationGate.classification_recommendation],
    ];
    $("#gateDetails").innerHTML = gateRows
      .map(
        ([label, value]) => `
          <div class="gate-row">
            <div>${escapeHtml(label)}</div>
            <strong>${escapeHtml(value || "")}</strong>
          </div>
        `,
      )
      .join("");
  }

  function renderLegend(categoryList) {
    return categoryList
      .map(
        (category) => `
          <span class="legend-item">
            <span class="legend-dot" style="background:${categoryColors[category]}"></span>
            ${escapeHtml(categoryLabels[category] || category)}
          </span>
        `,
      )
      .join("");
  }

  function drawLineChart(container, records, categoryList, options) {
    const width = 920;
    const height = 360;
    const margin = { top: 22, right: 26, bottom: 34, left: 44 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;
    const minYear = options.minYear;
    const maxYear = options.maxYear;
    const yMax = 1;
    const xScale = (year) => margin.left + ((year - minYear) / (maxYear - minYear)) * innerW;
    const yScale = (value) => margin.top + (1 - value / yMax) * innerH;
    const byCategory = new Map(categoryList.map((category) => [category, []]));
    records.forEach((row) => {
      if (byCategory.has(row.category)) {
        byCategory.get(row.category).push(row);
      }
    });

    const yTicks = [0, 0.25, 0.5, 0.75, 1];
    const xTicks = [1975, 1985, 1995, 2005, 2015, 2025];
    const grid = [
      ...yTicks.map((tick) => {
        const y = yScale(tick);
        return `<line class="grid-line" x1="${margin.left}" x2="${width - margin.right}" y1="${y}" y2="${y}"></line>
          <text class="axis-text" x="${margin.left - 8}" y="${y + 3}" text-anchor="end">${Math.round(tick * 100)}%</text>`;
      }),
      ...xTicks.map((tick) => {
        const x = xScale(tick);
        return `<text class="axis-text" x="${x}" y="${height - 8}" text-anchor="middle">${tick}</text>`;
      }),
    ].join("");

    const lines = categoryList
      .map((category) => {
        const rows = byCategory.get(category).sort((a, b) => int(a.publication_year) - int(b.publication_year));
        const points = rows.map((row) => `${xScale(int(row.publication_year))},${yScale(num(row.category_share))}`).join(" ");
        const circles = rows
          .map((row) => {
            const x = xScale(int(row.publication_year));
            const y = yScale(num(row.category_share));
            return `<circle class="chart-point" cx="${x}" cy="${y}" r="5" fill="transparent" stroke="transparent"
              data-tooltip="${escapeHtml(`${row.publication_year} · ${categoryLabels[category]} · ${pct(row.category_share)} (${row.article_count}/${row.group_total})`)}"></circle>`;
          })
          .join("");
        return `<polyline class="chart-line" points="${points}" stroke="${categoryColors[category]}"></polyline>${circles}`;
      })
      .join("");

    container.innerHTML = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" aria-hidden="true">${grid}${lines}</svg>`;
    bindTooltips(container);
  }

  function drawStackedBars(container, records, categoryList) {
    const width = 560;
    const height = 290;
    const margin = { top: 18, right: 24, bottom: 34, left: 58 };
    const barH = 42;
    const years = Array.from(new Set(records.map((row) => row.publication_year))).sort();
    const yStep = (height - margin.top - margin.bottom) / Math.max(1, years.length);
    const xScale = (value) => margin.left + value * (width - margin.left - margin.right);
    const bars = years
      .map((year, index) => {
        let x = margin.left;
        const y = margin.top + index * yStep + (yStep - barH) / 2;
        const yearRows = rowsFor(records, { publication_year: year });
        const segments = categoryList
          .map((category) => {
            const row = yearRows.find((item) => item.category === category);
            const share = num(row?.category_share);
            const w = (width - margin.left - margin.right) * share;
            const segment = `<rect x="${x}" y="${y}" width="${w}" height="${barH}" fill="${categoryColors[category]}"
              data-tooltip="${escapeHtml(`${year} · ${categoryLabels[category]} · ${pct(share)} (${row?.article_count || 0}/${row?.group_total || 0})`)}"></rect>`;
            x += w;
            return segment;
          })
          .join("");
        return `<text class="axis-text" x="${margin.left - 10}" y="${y + barH / 2 + 4}" text-anchor="end">${year}</text>${segments}`;
      })
      .join("");
    const ticks = [0, 0.25, 0.5, 0.75, 1]
      .map((tick) => {
        const x = xScale(tick);
        return `<line class="grid-line" x1="${x}" x2="${x}" y1="${margin.top}" y2="${height - margin.bottom}"></line>
          <text class="axis-text" x="${x}" y="${height - 8}" text-anchor="middle">${Math.round(tick * 100)}%</text>`;
      })
      .join("");
    container.innerHTML = `<svg class="chart-svg" viewBox="0 0 ${width} ${height}" aria-hidden="true">${ticks}${bars}</svg>`;
    bindTooltips(container);
  }

  function bindTooltips(container) {
    const tooltip = $("#tooltip");
    container.querySelectorAll("[data-tooltip]").forEach((el) => {
      el.addEventListener("pointermove", (event) => {
        tooltip.hidden = false;
        tooltip.innerHTML = `<strong>${escapeHtml(el.dataset.tooltip)}</strong>`;
        tooltip.style.left = `${Math.min(window.innerWidth - 280, event.clientX + 14)}px`;
        tooltip.style.top = `${event.clientY + 14}px`;
      });
      el.addEventListener("pointerleave", () => {
        tooltip.hidden = true;
      });
    });
  }

  init();
})();
