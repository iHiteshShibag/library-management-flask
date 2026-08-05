// Chart.js instances for the dashboard. Colors are read fresh on init and
// on the `themechange` event (dispatched by base.html's theme toggle) so
// charts stay in sync with light/dark mode without a page reload.
(function () {
  if (typeof Chart === 'undefined') return;

  const PALETTE = ['#0d9488', '#38bdf8', '#f59e0b', '#fb7185', '#a78bfa'];

  function theme() {
    const dark = document.documentElement.classList.contains('dark');
    return {
      dark,
      text: dark ? '#94a3b8' : '#64748b',
      grid: dark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.12)',
      surface: dark ? '#0f172a' : '#ffffff',
    };
  }

  const instances = [];

  function baseOptions(extra) {
    const t = theme();
    return Object.assign({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: t.surface,
          titleColor: t.dark ? '#f1f5f9' : '#0f172a',
          bodyColor: t.text,
          borderColor: t.grid,
          borderWidth: 1,
          padding: 10,
          boxPadding: 4,
        },
      },
    }, extra || {});
  }

  function donut(canvas, labels, data) {
    if (!canvas) return;
    const t = theme();
    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{ data, backgroundColor: PALETTE, borderWidth: 0, hoverOffset: 4 }],
      },
      options: baseOptions({
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { color: t.text, boxWidth: 10, padding: 12, font: { size: 11 } } } },
      }),
    });
    instances.push({ chart, recolor: () => {
      const nt = theme();
      chart.options.plugins.legend.labels.color = nt.text;
      chart.options.plugins.tooltip.backgroundColor = nt.surface;
      chart.options.plugins.tooltip.titleColor = nt.dark ? '#f1f5f9' : '#0f172a';
      chart.options.plugins.tooltip.bodyColor = nt.text;
      chart.options.plugins.tooltip.borderColor = nt.grid;
      chart.update();
    }});
    return chart;
  }

  function line(canvas, labels, series) {
    if (!canvas) return;
    const t = theme();
    const chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: series.map((s, i) => ({
          label: s.label,
          data: s.data,
          borderColor: PALETTE[i % PALETTE.length],
          backgroundColor: PALETTE[i % PALETTE.length] + '22',
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        })),
      },
      options: baseOptions({
        plugins: { legend: { display: series.length > 1, position: 'bottom', labels: { color: t.text, boxWidth: 10, padding: 12, font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text, font: { size: 11 } } },
          y: { beginAtZero: true, grid: { color: t.grid }, ticks: { color: t.text, font: { size: 11 }, precision: 0 } },
        },
      }),
    });
    instances.push({ chart, recolor: () => {
      const nt = theme();
      if (chart.options.plugins.legend.labels) chart.options.plugins.legend.labels.color = nt.text;
      chart.options.scales.x.ticks.color = nt.text;
      chart.options.scales.y.ticks.color = nt.text;
      chart.options.scales.y.grid.color = nt.grid;
      chart.update();
    }});
    return chart;
  }

  function bar(canvas, labels, data) {
    if (!canvas) return;
    const t = theme();
    const chart = new Chart(canvas, {
      type: 'bar',
      data: { labels, datasets: [{ data, backgroundColor: '#0d9488', borderRadius: 6, maxBarThickness: 28 }] },
      options: baseOptions({
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text, font: { size: 11 } } },
          y: { beginAtZero: true, grid: { color: t.grid }, ticks: { color: t.text, font: { size: 11 } } },
        },
      }),
    });
    instances.push({ chart, recolor: () => {
      const nt = theme();
      chart.options.scales.x.ticks.color = nt.text;
      chart.options.scales.y.ticks.color = nt.text;
      chart.options.scales.y.grid.color = nt.grid;
      chart.update();
    }});
    return chart;
  }

  window.initDashboardCharts = function (data) {
    donut(document.getElementById('chart-books-by-author'), data.booksByAuthor.labels, data.booksByAuthor.counts);
    line(document.getElementById('chart-borrow-trend'), data.borrowTrend.labels, [
      { label: 'Issued', data: data.borrowTrend.issued },
      { label: 'Returned', data: data.borrowTrend.returned },
    ]);
    bar(document.getElementById('chart-fines-trend'), data.finesTrend.labels, data.finesTrend.amounts);
    donut(document.getElementById('chart-stock-overview'), ['Available', 'Issued'], [data.stockOverview.available, data.stockOverview.issued]);

    document.addEventListener('themechange', () => {
      instances.forEach((i) => i.recolor());
    });
  };
})();
