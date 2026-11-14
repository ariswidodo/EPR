/* EPR Achievement Dashboard */
(() => {
  const CATS = ["Consumer", "Scanner", "Consumables", "Dotmatrix"];
  const CAT_COLORS = {
    Consumer: "#4f46e5",
    Scanner: "#0ea5e9",
    Consumables: "#10b981",
    Dotmatrix: "#f59e0b",
  };
  const DEFAULT_MONTHS = [
    "Apr 26", "Mei 26", "Jun 26", "Jul 26", "Agu 26", "Sep 26",
    "Okt 26", "Nov 26", "Des 26", "Jan 27", "Feb 27", "Mar 27",
  ];

  let rawData = null;
  let state = {
    period: "fy", // fy | h1 | h2
    search: "",
    tier: "ALL",
    city: "ALL",
    status: "ALL",
    sortKey: "actual",
    sortDir: "desc",
  };

  let charts = {
    monthly: null,
    category: null,
    partner: null,
    drawer: null,
  };

  const $ = (id) => document.getElementById(id);

  // Formatters
  const fmtRp = (v) =>
    "Rp " + Math.round(v || 0).toLocaleString("id-ID");

  const fmtCompact = (v) => {
    const n = Number(v || 0);
    if (n >= 1e9) return `Rp ${(n / 1e9).toFixed(2).replace(".", ",")} M`;
    if (n >= 1e6) return `Rp ${(n / 1e6).toFixed(1).replace(".", ",")} Jt`;
    if (n >= 1e3) return `Rp ${(n / 1e3).toFixed(0)} Rb`;
    return `Rp ${Math.round(n)}`;
  };

  const fmtPct = (v) =>
    v == null || !isFinite(v) ? "-" : `${(v * 100).toFixed(1)}%`;

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
    );

  function achColor(pct) {
    if (pct == null) return "var(--text-3)";
    if (pct >= 1) return "var(--emerald)";
    if (pct >= 0.75) return "var(--indigo)";
    if (pct >= 0.5) return "var(--amber)";
    return "var(--rose)";
  }

  function achBadgeClass(pct) {
    if (pct == null) return "badge-neutral";
    if (pct >= 1) return "badge-emerald";
    if (pct >= 0.75) return "badge-indigo";
    if (pct >= 0.5) return "badge-amber";
    return "badge-rose";
  }

  function achLabel(pct) {
    if (pct == null) return "No Target";
    if (pct >= 1) return "Achieved";
    if (pct >= 0.75) return "On Track";
    if (pct >= 0.5) return "Moderate";
    return "Behind";
  }

  // Theme
  function initTheme() {
    const saved = localStorage.getItem("epr_theme") || "light";
    applyTheme(saved);
    $("btnTheme").addEventListener("click", () => {
      const next =
        document.documentElement.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
      applyTheme(next);
      localStorage.setItem("epr_theme", next);
      renderCharts(getFilteredPartners());
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    $("iconSun").style.display = theme === "dark" ? "none" : "block";
    $("iconMoon").style.display = theme === "dark" ? "block" : "none";
  }

  function themeColors() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      grid: dark ? "rgba(148, 163, 184, 0.12)" : "rgba(15, 23, 42, 0.06)",
      tick: dark ? "#94a3b8" : "#64748b",
      text: dark ? "#f8fafc" : "#0f172a",
    };
  }

  // Period-aware metrics for a partner
  function partnerMetrics(p) {
    const monthsSlice =
      state.period === "h1" ? [0, 6] : state.period === "h2" ? [6, 12] : [0, 12];
    const [s, e] = monthsSlice;

    const target =
      state.period === "h1"
        ? p.target_h1
        : state.period === "h2"
        ? p.target_h2
        : p.target_fy;

    const actual =
      state.period === "h1"
        ? p.actual_h1
        : state.period === "h2"
        ? p.actual_h2
        : p.actual_fy;

    const catTotals = {};
    CATS.forEach((c) => {
      const arr = p.monthly_by_cat?.[c] || [];
      catTotals[c] = arr.slice(s, e).reduce((a, b) => a + (b || 0), 0);
    });

    const ach = target > 0 ? actual / target : null;
    const midHiRatio = p.actual_fy > 0 ? (p.mid_hi || 0) / p.actual_fy : 0;
    const midHiEst = state.period === "fy" ? p.mid_hi || 0 : actual * midHiRatio;

    return {
      ...p,
      target,
      actual,
      ach,
      midhi_val: midHiEst,
      midhi_pct: actual > 0 ? midHiEst / actual : 0,
      Consumer: catTotals.Consumer,
      Scanner: catTotals.Scanner,
      Consumables: catTotals.Consumables,
      Dotmatrix: catTotals.Dotmatrix,
    };
  }

  function populateFilters(partners) {
    const tiers = [...new Set(partners.map((p) => p.tier).filter(Boolean))].sort();
    const cities = [...new Set(partners.map((p) => p.city).filter(Boolean))].sort();

    const tierSel = $("tierFilter");
    tierSel.innerHTML =
      '<option value="ALL">Semua Tier</option>' +
      tiers.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");

    const citySel = $("cityFilter");
    citySel.innerHTML =
      '<option value="ALL">Semua Kota</option>' +
      cities.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
  }

  function getFilteredPartners() {
    if (!rawData) return [];
    const q = state.search.trim().toLowerCase();
    return rawData.partners
      .map(partnerMetrics)
      .filter((p) => {
        if (state.tier !== "ALL" && p.tier !== state.tier) return false;
        if (state.city !== "ALL" && p.city !== state.city) return false;
        if (
          q &&
          !p.name.toLowerCase().includes(q) &&
          !p.code.toLowerCase().includes(q) &&
          !p.city.toLowerCase().includes(q)
        ) {
          return false;
        }
        if (state.status === "achieved" && !(p.ach != null && p.ach >= 1))
          return false;
        if (
          state.status === "ontrack" &&
          !(p.ach != null && p.ach >= 0.75 && p.ach < 1)
        )
          return false;
        if (state.status === "behind" && !(p.ach == null || p.ach < 0.75))
          return false;
        return true;
      })
      .sort((a, b) => {
        const k = state.sortKey;
        const dir = state.sortDir === "asc" ? 1 : -1;
        if (k === "name" || k === "tier") {
          return String(a[k]).localeCompare(String(b[k])) * dir;
        }
        const av = a[k] ?? -1;
        const bv = b[k] ?? -1;
        return (av - bv) * dir;
      });
  }

  function render() {
    if (!rawData) return;
    const list = getFilteredPartners();
    renderMeta();
    renderKpis(list);
    renderCharts(list);
    renderTable(list);
    renderEppSummary(list);
    renderAudit();
  }

  function renderMeta() {
    const m = rawData.meta || {};
    $("fyBadge").textContent = state.period.toUpperCase();
    const parts = [];
    if (m.fiscal_year) parts.push(m.fiscal_year);
    if (m.verified_rows) parts.push(`${m.verified_rows.toLocaleString("id-ID")} transaksi terverifikasi`);
    if (m.generated_at) parts.push(`Diperbarui ${m.generated_at}`);
    $("metaSubtitle").textContent = parts.join(" · ");
    $("footerSource").textContent = m.last_source_file
      ? `Sumber terakhir: ${m.last_source_file}`
      : "";
  }

  function renderKpis(list) {
    const totalRev = list.reduce((s, p) => s + p.actual, 0);
    const totalTarget = list.reduce((s, p) => s + p.target, 0);
    const ach = totalTarget > 0 ? totalRev / totalTarget : null;
    const activeCount = list.filter((p) => p.actual > 0).length;
    const achievedCount = list.filter((p) => p.ach != null && p.ach >= 1).length;
    const totalMidHi = list.reduce((s, p) => s + p.midhi_val, 0);
    const midHiPct = totalRev > 0 ? totalMidHi / totalRev : 0;

    $("kpiRevenue").textContent = fmtCompact(totalRev);
    $("kpiRevenueSub").textContent = `Target ${state.period.toUpperCase()}: ${fmtCompact(totalTarget)}`;

    $("kpiAch").textContent = fmtPct(ach);
    const badge = $("kpiAchBadge");
    badge.className = `kpi-pill ${achBadgeClass(ach)}`;
    badge.textContent = achLabel(ach);

    const bar = $("kpiAchBar");
    bar.style.width = `${Math.min(100, Math.max(0, (ach || 0) * 100)).toFixed(1)}%`;
    bar.className = "progress-fill " + (
      ach >= 1 ? "emerald" : ach >= 0.75 ? "" : ach >= 0.5 ? "amber" : "rose"
    );

    const gap = totalRev - totalTarget;
    $("kpiAchSub").textContent =
      gap >= 0
        ? `Surplus +${fmtCompact(gap)}`
        : `Sisa target ${fmtCompact(Math.abs(gap))}`;

    $("kpiPartners").textContent = `${activeCount} / ${list.length}`;
    $("kpiPartnersSub").textContent = `${achievedCount} partner sudah ≥ 100% target`;

    $("kpiMidHi").textContent = fmtPct(midHiPct);
    $("kpiMidHiBar").style.width = `${(midHiPct * 100).toFixed(1)}%`;
    $("kpiMidHiSub").textContent = `Mid High ${fmtCompact(totalMidHi)} · Low End ${fmtCompact(
      Math.max(0, totalRev - totalMidHi)
    )}`;
  }

  function renderCharts(list) {
    const tc = themeColors();
    const months = rawData.meta?.months || DEFAULT_MONTHS;

    // 1. Monthly stacked bar
    const monthlySeries = {};
    CATS.forEach((c) => {
      monthlySeries[c] = new Array(12).fill(0);
      list.forEach((p) => {
        const arr = p.monthly_by_cat?.[c] || [];
        for (let i = 0; i < 12; i++) monthlySeries[c][i] += arr[i] || 0;
      });
    });

    if (charts.monthly) charts.monthly.destroy();
    charts.monthly = new Chart($("monthlyChart"), {
      type: "bar",
      data: {
        labels: months,
        datasets: CATS.map((c) => ({
          label: c,
          data: monthlySeries[c],
          backgroundColor: CAT_COLORS[c],
          borderRadius: 4,
          borderSkipped: false,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { color: tc.tick, boxWidth: 10, usePointStyle: true },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${fmtRp(ctx.raw)}`,
            },
          },
        },
        scales: {
          x: { stacked: true, grid: { display: false }, ticks: { color: tc.tick } },
          y: {
            stacked: true,
            grid: { color: tc.grid },
            ticks: {
              color: tc.tick,
              callback: (v) => (v >= 1e9 ? `${(v / 1e9).toFixed(1)}M` : v >= 1e6 ? `${(v / 1e6).toFixed(0)}Jt` : v),
            },
          },
        },
      },
    });

    // 2. Category Doughnut
    const catSums = CATS.map((c) => list.reduce((s, p) => s + p[c], 0));
    const catGrand = catSums.reduce((a, b) => a + b, 0) || 1;

    if (charts.category) charts.category.destroy();
    charts.category = new Chart($("categoryChart"), {
      type: "doughnut",
      data: {
        labels: CATS,
        datasets: [
          {
            data: catSums,
            backgroundColor: CATS.map((c) => CAT_COLORS[c]),
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "68%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) =>
                `${ctx.label}: ${fmtCompact(ctx.raw)} (${((ctx.raw / catGrand) * 100).toFixed(1)}%)`,
            },
          },
        },
      },
    });

    $("catLegend").innerHTML = CATS.map((c, idx) => {
      const val = catSums[idx];
      const pct = ((val / catGrand) * 100).toFixed(1);
      return `<div class="cat-item">
        <span><i class="cat-dot" style="background:${CAT_COLORS[c]}"></i>${c}</span>
        <strong class="mono">${pct}%</strong>
      </div>`;
    }).join("");

    // 3. Top 12 Partners Actual vs Target
    const top = [...list]
      .sort((a, b) => b.actual - a.actual)
      .slice(0, 12);
    $("chartRankNote").textContent = `Menampilkan ${top.length} dari ${list.length} partner`;

    if (charts.partner) charts.partner.destroy();
    charts.partner = new Chart($("partnerChart"), {
      type: "bar",
      data: {
        labels: top.map((p) => p.name),
        datasets: [
          {
            label: "Aktual (Net)",
            data: top.map((p) => p.actual),
            backgroundColor: top.map((p) =>
              p.ach >= 1 ? "#10b981" : p.ach >= 0.75 ? "#4f46e5" : "#f59e0b"
            ),
            borderRadius: 5,
          },
          {
            label: "Target",
            data: top.map((p) => p.target),
            backgroundColor: "rgba(148, 163, 184, 0.35)",
            borderRadius: 5,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "top",
            align: "end",
            labels: { color: tc.tick, boxWidth: 10, usePointStyle: true },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${fmtRp(ctx.raw)}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: tc.grid },
            ticks: {
              color: tc.tick,
              callback: (v) => (v >= 1e9 ? `${(v / 1e9).toFixed(1)}M` : v >= 1e6 ? `${(v / 1e6).toFixed(0)}Jt` : v),
            },
          },
          y: {
            grid: { display: false },
            ticks: { color: tc.text, font: { size: 11.5 } },
          },
        },
      },
    });
  }

  function renderTable(list) {
    $("tableCount").textContent = `${list.length} partner`;
    const body = $("tableBody");

    if (!list.length) {
      body.innerHTML = `<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--text-3)">Tidak ada partner yang cocok dengan filter.</td></tr>`;
      return;
    }

    body.innerHTML = list
      .map((p, i) => {
        const pct = p.ach != null ? p.ach * 100 : null;
        const barW = pct != null ? Math.min(100, Math.max(0, pct)).toFixed(1) : 0;
        const color = achColor(p.ach);
        const epps = p.epp_sources || [];
        const eppLabel = epps.length
          ? `${esc(epps[0].name)}${epps.length > 1 ? ` <span class="badge badge-neutral">+${epps.length - 1}</span>` : ""}`
          : '<span style="color:var(--text-3)">-</span>';
        return `<tr data-code="${esc(p.code)}">
          <td class="col-rank mono">${i + 1}</td>
          <td>
            <div class="partner-cell">
              <span class="partner-name">${esc(p.name)}</span>
              <span class="partner-meta mono">${esc(p.code)} · ${esc(p.city || "-")}</span>
            </div>
          </td>
          <td><span class="tier-pill tier-${esc(p.tier)}">${esc(p.tier || "-")}</span></td>
          <td style="max-width:210px;overflow:hidden;text-overflow:ellipsis" title="${esc(epps.map((e) => e.name).join(", "))}">${eppLabel}</td>
          <td class="num mono">
            ${fmtCompact(p.target)}
            ${p.target_original && p.target_original !== p.target_fy ? `<div class="partner-meta">Orig: ${fmtCompact(p.target_original)}</div>` : ""}
          </td>
          <td class="num mono"><strong>${fmtCompact(p.actual)}</strong></td>
          <td class="num">
            <div class="ach-cell">
              <div class="mini-bar"><span style="width:${barW}%;background:${color}"></span></div>
              <span class="mono" style="color:${color};font-weight:600;min-width:52px;text-align:right">${fmtPct(p.ach)}</span>
            </div>
          </td>
          <td class="num mono">${fmtPct(p.midhi_pct)}</td>
          <td class="num mono">${fmtCompact(p.Consumer)}</td>
          <td class="num mono">${fmtCompact(p.Scanner)}</td>
          <td class="num mono">${fmtCompact(p.Consumables)}</td>
          <td class="num mono">${fmtCompact(p.Dotmatrix)}</td>
        </tr>`;
      })
      .join("");

    body.querySelectorAll("tr[data-code]").forEach((tr) => {
      tr.addEventListener("click", () => openDrawer(tr.dataset.code));
    });
  }

  function renderEppSummary(list) {
    const map = new Map();
    let grand = 0;
    list.forEach((p) => {
      (p.epp_sources || []).forEach((ep) => {
        grand += ep.total || 0;
        let cur = map.get(ep.code);
        if (!cur) {
          cur = {
            code: ep.code,
            name: ep.name,
            city: ep.city || "",
            total: 0,
            tx: 0,
            cats: { Consumer: 0, Scanner: 0, Consumables: 0, Dotmatrix: 0 },
          };
          map.set(ep.code, cur);
        }
        cur.total += ep.total || 0;
        cur.tx += ep.tx || 0;
        CATS.forEach((c) => {
          cur.cats[c] += ep.cats?.[c] || 0;
        });
      });
    });

    const rows = [...map.values()].sort((a, b) => b.total - a.total);
    $("eppSummaryCount").textContent = `${rows.length} EPP`;
    const body = $("eppSummaryBody");
    if (!rows.length || grand <= 0) {
      body.innerHTML =
        '<tr><td colspan="9" style="text-align:center;color:var(--text-3);padding:20px">Belum ada data kontribusi EPP.</td></tr>';
      return;
    }

    body.innerHTML = rows
      .map((ep, i) => {
        const totPct = (ep.total / grand) * 100;
        const pctOf = (c) => ((ep.cats[c] || 0) / grand) * 100;
        const barSegs = CATS.map((c) => {
          const w = pctOf(c);
          return w > 0 ? `<span style="width:${w.toFixed(2)}%;background:${CAT_COLORS[c]}" title="${c}: ${w.toFixed(1)}%"></span>` : "";
        }).join("");

        return `<tr>
          <td class="col-rank mono">${i + 1}</td>
          <td>
            <div class="partner-cell">
              <span class="partner-name">${esc(ep.name)}</span>
              <span class="partner-meta mono">${esc(ep.code)} · ${ep.tx} transaksi</span>
            </div>
          </td>
          <td>${esc(ep.city || "-")}</td>
          <td class="num">
            <div class="ach-cell">
              <div class="epp-contrib-bar">${barSegs}</div>
              <span class="mono" style="font-weight:700;min-width:50px;text-align:right">${totPct.toFixed(1)}%</span>
            </div>
          </td>
          <td class="num mono">${fmtCompact(ep.total)}</td>
          <td class="num mono">${pctOf("Consumer").toFixed(1)}%</td>
          <td class="num mono">${pctOf("Consumables").toFixed(1)}%</td>
          <td class="num mono">${pctOf("Scanner").toFixed(1)}%</td>
          <td class="num mono">${pctOf("Dotmatrix").toFixed(1)}%</td>
        </tr>`;
      })
      .join("");
  }

  function getFilteredRejected() {
    const a = rawData?.audit;
    if (!a) return [];
    const list = a.recent_rejected || a.recent_doubles || [];
    const kind = $("rejectTypeFilter")?.value || "ALL";
    const q = ($("rejectSearch")?.value || "").trim().toLowerCase();
    return list.filter((d) => {
      const jenis = d.jenis || (d.keterangan === "LUAR DATABASE EPR" ? "luar_db" : "double");
      if (kind !== "ALL" && jenis !== kind) return false;
      if (q) {
        const hay = `${d.invoice_no || ""} ${d.epr || ""} ${d.epr_name || ""} ${d.material || ""} ${d.keterangan || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }

  function renderRejectedRows() {
    const rows = getFilteredRejected();
    $("doubleRejectBody").innerHTML = rows.length
      ? rows
          .slice(0, 100)
          .map(
            (d) => `<tr>
            <td>
              <div class="partner-cell">
                <span class="mono" style="font-weight:600">${esc(d.invoice_no || "-")}</span>
                <span class="partner-meta mono">${esc(d.invoice_date || "-")} · ${esc(d.sumber_file || "-")} baris ${d.baris_sumber || "-"}</span>
              </div>
            </td>
            <td>
              <div class="partner-cell">
                <span>${esc(d.epr_name || d.epr || "-")}</span>
                <span class="partner-meta mono">${esc(d.material || "-")} (qty ${d.qty || 0})</span>
              </div>
            </td>
            <td class="num mono">${fmtCompact(d.total || 0)}</td>
            <td><span class="badge ${d.jenis === "luar_db" ? "badge-neutral" : "badge-amber"}" title="${esc(d.keterangan)}">${esc(d.keterangan)}</span></td>
          </tr>`
          )
          .join("")
      : '<tr><td colspan="4" style="text-align:center;color:var(--text-3);padding:18px">Tidak ada data ditolak yang cocok.</td></tr>';
  }

  function exportRejectedCsv() {
    const rows = getFilteredRejected();
    const header = ["Invoice Date", "Invoice No", "EPR Code", "EPR Name", "Material", "Qty", "Total", "Alasan Reject", "File Sumber", "Baris"];
    const body = rows.map((d) => [
      d.invoice_date, d.invoice_no, d.epr, d.epr_name, d.material,
      d.qty, d.total, d.keterangan, d.sumber_file, d.baris_sumber,
    ]);
    const csv = [header, ...body]
      .map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "EPR_Data_Ditolak.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function renderAudit() {
    const a = rawData?.audit;
    if (!a) {
      $("auditPills").innerHTML = "";
      $("processLogBody").innerHTML =
        '<tr><td colspan="6" style="text-align:center;color:var(--text-3);padding:18px">Data audit tidak tersedia pada mode preview Excel lokal.</td></tr>';
      $("doubleRejectBody").innerHTML =
        '<tr><td colspan="4" style="text-align:center;color:var(--text-3);padding:18px">-</td></tr>';
      return;
    }

    $("auditPills").innerHTML = [
      `<span class="badge badge-amber">Double Ditolak: ${(a.double_total || 0).toLocaleString("id-ID")}</span>`,
      `<span class="badge badge-neutral">Luar DB EPR: ${(a.luar_db || 0).toLocaleString("id-ID")}</span>`,
      `<span class="badge badge-rose">Total Ditolak: ${(a.rejected_total || 0).toLocaleString("id-ID")}</span>`,
    ].join("");

    const logs = a.process_logs || [];
    $("processLogBody").innerHTML = logs.length
      ? logs
          .slice(0, 8)
          .map(
            (l) => `<tr>
            <td class="mono" style="font-size:12px">${esc(l.waktu)}</td>
            <td style="max-width:170px;overflow:hidden;text-overflow:ellipsis" title="${esc(l.file)}">${esc(l.file)}</td>
            <td class="num mono">${(l.baris_input || 0).toLocaleString("id-ID")}</td>
            <td class="num mono" style="color:var(--emerald);font-weight:600">${(l.masuk || 0).toLocaleString("id-ID")}</td>
            <td class="num mono" style="color:var(--amber);font-weight:600">${(l.double || 0).toLocaleString("id-ID")}</td>
            <td class="num mono">${(l.luar_db || 0).toLocaleString("id-ID")}</td>
          </tr>`
          )
          .join("")
      : '<tr><td colspan="6" style="text-align:center;color:var(--text-3);padding:18px">Belum ada log proses.</td></tr>';

    renderRejectedRows();
  }

  // Partner Detail Drawer
  let activeDrawerCode = null;

  function openDrawer(code) {
    const p = rawData?.partners.find((x) => x.code === code);
    if (!p) return;
    activeDrawerCode = code;

    const achFy = p.target_fy > 0 ? p.actual_fy / p.target_fy : null;
    const achH1 = p.target_h1 > 0 ? p.actual_h1 / p.target_h1 : null;
    const achH2 = p.target_h2 > 0 ? p.actual_h2 / p.target_h2 : null;

    $("dCode").textContent = p.code;
    $("dTier").textContent = p.tier || "-";
    $("dName").textContent = p.name;
    $("dMeta").textContent =
      `${p.city || "-"} · AM: ${p.am || "-"} · ${p.tx_count || 0} transaksi` +
      (p.target_original && p.target_original !== p.target_fy
        ? ` · Target Orig: ${fmtCompact(p.target_original)}`
        : "");

    $("dAchFy").textContent = fmtPct(achFy);
    $("dAchFy").style.color = achColor(achFy);
    $("dRevFy").textContent = `${fmtCompact(p.actual_fy)} / ${fmtCompact(p.target_fy)}`;

    $("dAchH1").textContent = fmtPct(achH1);
    $("dAchH1").style.color = achColor(achH1);
    $("dRevH1").textContent = `${fmtCompact(p.actual_h1)} / ${fmtCompact(p.target_h1)}`;

    $("dAchH2").textContent = fmtPct(achH2);
    $("dAchH2").style.color = achColor(achH2);
    $("dRevH2").textContent = `${fmtCompact(p.actual_h2)} / ${fmtCompact(p.target_h2)}`;

    const tc = themeColors();
    const months = rawData.meta?.months || DEFAULT_MONTHS;
    if (charts.drawer) charts.drawer.destroy();
    charts.drawer = new Chart($("drawerChart"), {
      type: "bar",
      data: {
        labels: months,
        datasets: CATS.map((c) => ({
          label: c,
          data: p.monthly_by_cat?.[c] || new Array(12).fill(0),
          backgroundColor: CAT_COLORS[c],
          borderRadius: 3,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtRp(ctx.raw)}` },
          },
        },
        scales: {
          x: { stacked: true, grid: { display: false }, ticks: { color: tc.tick, font: { size: 10 } } },
          y: {
            stacked: true,
            grid: { color: tc.grid },
            ticks: {
              color: tc.tick,
              font: { size: 10 },
              callback: (v) => (v >= 1e6 ? `${(v / 1e6).toFixed(0)}Jt` : v),
            },
          },
        },
      },
    });

    const catRows = CATS.map((c) => {
      const val = p.cat_totals?.[c] || 0;
      const pct = p.actual_fy > 0 ? (val / p.actual_fy) * 100 : 0;
      return `<div class="drawer-row">
        <span><i class="cat-dot" style="background:${CAT_COLORS[c]}"></i>${c}</span>
        <span class="mono"><strong>${fmtRp(val)}</strong> (${pct.toFixed(1)}%)</span>
      </div>`;
    });

    catRows.push(
      `<div class="drawer-row"><span>Mid High</span><span class="mono"><strong>${fmtRp(p.mid_hi || 0)}</strong></span></div>`,
      `<div class="drawer-row"><span>Low End</span><span class="mono"><strong>${fmtRp(p.low_end || 0)}</strong></span></div>`
    );
    $("dCatList").innerHTML = catRows.join("");

    const epps = p.epp_sources || [];
    $("dEppList").innerHTML = epps.length
      ? epps
          .map((ep) => {
            const share = p.actual_fy > 0 ? ((ep.total / p.actual_fy) * 100).toFixed(1) : "0.0";
            const catSummary = CATS.filter((c) => (ep.cats?.[c] || 0) > 0)
              .map((c) => `${c}: ${fmtCompact(ep.cats[c])}`)
              .join(" · ");
            return `<div class="drawer-row" style="flex-direction:column;align-items:stretch;gap:4px">
              <div style="display:flex;justify-content:space-between;gap:8px">
                <strong>${esc(ep.name)}</strong>
                <span class="mono"><strong>${fmtCompact(ep.total)}</strong> (${share}%)</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--text-3)">
                <span>${esc(ep.code)} · ${ep.tx} transaksi</span>
                <span>${esc(catSummary || "-")}</span>
              </div>
            </div>`;
          })
          .join("")
      : '<div class="drawer-row" style="color:var(--text-3)">Belum ada transaksi terverifikasi.</div>';

    $("drawerBackdrop").hidden = false;
    $("partnerDrawer").classList.add("open");
    $("partnerDrawer").setAttribute("aria-hidden", "false");
  }

  function closeDrawer() {
    $("drawerBackdrop").hidden = true;
    $("partnerDrawer").classList.remove("open");
    $("partnerDrawer").setAttribute("aria-hidden", "true");
  }

  function sharePartnerPdf() {
    const p = rawData?.partners.find((x) => x.code === activeDrawerCode);
    if (!p) return;

    const achFy = p.target_fy > 0 ? p.actual_fy / p.target_fy : null;
    const achH1 = p.target_h1 > 0 ? p.actual_h1 / p.target_h1 : null;
    const achH2 = p.target_h2 > 0 ? p.actual_h2 / p.target_h2 : null;
    const chartImg = charts.drawer ? charts.drawer.toBase64Image() : "";
    const gapFy = (p.actual_fy || 0) - (p.target_fy || 0);
    const gapH1 = (p.actual_h1 || 0) - (p.target_h1 || 0);
    const gapH2 = (p.actual_h2 || 0) - (p.target_h2 || 0);

    const catRows = CATS.map((c) => {
      const val = p.cat_totals?.[c] || 0;
      const pct = p.actual_fy > 0 ? ((val / p.actual_fy) * 100).toFixed(1) : "0.0";
      return `<tr><td>${c}</td><td class="num mono">${fmtRp(val)}</td><td class="num mono">${pct}%</td></tr>`;
    }).join("");

    const eppRows = (p.epp_sources || []).length
      ? (p.epp_sources || [])
          .map((ep) => {
            const share = p.actual_fy > 0 ? ((ep.total / p.actual_fy) * 100).toFixed(1) : "0.0";
            return `<tr>
              <td><strong>${esc(ep.name)}</strong><br><small>${esc(ep.code)} · ${esc(ep.city || "-")}</small></td>
              <td class="num mono">${ep.tx}</td>
              <td class="num mono">${fmtRp(ep.total)}</td>
              <td class="num mono">${share}%</td>
            </tr>`;
          })
          .join("")
      : '<tr><td colspan="4" style="text-align:center;color:#64748b">Belum ada transaksi terverifikasi.</td></tr>';

    const origNote =
      p.target_original && p.target_original !== p.target_fy
        ? ` · Target Orig: ${fmtCompact(p.target_original)}`
        : "";

    $("pdfReport").innerHTML = `
      <div class="pdf-head">
        <div>
          <h1>${esc(p.name)}</h1>
          <div class="pdf-meta">${esc(p.code)} · ${esc(p.city || "-")} · Tier ${esc(p.tier || "-")} · AM: ${esc(p.am || "-")}${esc(origNote)}</div>
        </div>
        <div class="pdf-meta" style="text-align:right">
          <div><b>Result Achievement EPR FY26</b></div>
          <div>Dicetak: ${new Date().toLocaleString("id-ID")}</div>
        </div>
      </div>

      <div class="pdf-kpis">
        <div class="pdf-kpi">
          <span>FY26 Achievement</span>
          <strong class="mono">${fmtPct(achFy)}</strong>
          <small class="mono">${fmtCompact(p.actual_fy)} / ${fmtCompact(p.target_fy)}</small>
        </div>
        <div class="pdf-kpi">
          <span>H1 (52% Target)</span>
          <strong class="mono">${fmtPct(achH1)}</strong>
          <small class="mono">${fmtCompact(p.actual_h1)} / ${fmtCompact(p.target_h1)}</small>
        </div>
        <div class="pdf-kpi">
          <span>H2 (48% Target)</span>
          <strong class="mono">${fmtPct(achH2)}</strong>
          <small class="mono">${fmtCompact(p.actual_h2)} / ${fmtCompact(p.target_h2)}</small>
        </div>
      </div>

      ${chartImg ? `<div class="pdf-sec"><h3>Tren Revenue Bulanan (Apr 26 – Mar 27)</h3><img class="pdf-chart-img" src="${chartImg}" alt="Grafik Bulanan" /></div>` : ""}

      <div class="pdf-sec">
        <h3>Result Achievement EPR</h3>
        <table class="pdf-table">
          <thead><tr><th>Periode</th><th class="num">Target (Excl.)</th><th class="num">Aktual (Net)</th><th class="num">Selisih / Sisa</th><th class="num">Achievement</th><th>Status</th></tr></thead>
          <tbody>
            <tr>
              <td><b>FY26 (Full Year)</b></td>
              <td class="num mono">${fmtRp(p.target_fy)}</td>
              <td class="num mono">${fmtRp(p.actual_fy)}</td>
              <td class="num mono">${gapFy >= 0 ? "+" + fmtRp(gapFy) : "-" + fmtRp(Math.abs(gapFy))}</td>
              <td class="num mono"><b>${fmtPct(achFy)}</b></td>
              <td><b>${achLabel(achFy)}</b></td>
            </tr>
            <tr>
              <td>H1 (Apr – Sep)</td>
              <td class="num mono">${fmtRp(p.target_h1)}</td>
              <td class="num mono">${fmtRp(p.actual_h1)}</td>
              <td class="num mono">${gapH1 >= 0 ? "+" + fmtRp(gapH1) : "-" + fmtRp(Math.abs(gapH1))}</td>
              <td class="num mono">${fmtPct(achH1)}</td>
              <td>${achLabel(achH1)}</td>
            </tr>
            <tr>
              <td>H2 (Okt – Mar)</td>
              <td class="num mono">${fmtRp(p.target_h2)}</td>
              <td class="num mono">${fmtRp(p.actual_h2)}</td>
              <td class="num mono">${gapH2 >= 0 ? "+" + fmtRp(gapH2) : "-" + fmtRp(Math.abs(gapH2))}</td>
              <td class="num mono">${fmtPct(achH2)}</td>
              <td>${achLabel(achH2)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pdf-sec">
        <h3>Komposisi Kategori &amp; Split (Exclude PPN 11%)</h3>
        <table class="pdf-table">
          <thead><tr><th>Kategori</th><th class="num">Net Revenue</th><th class="num">Kontribusi</th></tr></thead>
          <tbody>
            ${catRows}
            <tr><td><b>Mid High</b></td><td class="num mono">${fmtRp(p.mid_hi || 0)}</td><td class="num mono">${p.actual_fy > 0 ? (((p.mid_hi || 0) / p.actual_fy) * 100).toFixed(1) : "0.0"}%</td></tr>
            <tr><td><b>Low End</b></td><td class="num mono">${fmtRp(p.low_end || 0)}</td><td class="num mono">${p.actual_fy > 0 ? (((p.low_end || 0) / p.actual_fy) * 100).toFixed(1) : "0.0"}%</td></tr>
          </tbody>
        </table>
      </div>

      <div class="pdf-sec">
        <h3>Sumber Pembelian EPP</h3>
        <table class="pdf-table">
          <thead><tr><th>Nama EPP</th><th class="num">Tx</th><th class="num">Net Revenue</th><th class="num">Share</th></tr></thead>
          <tbody>${eppRows}</tbody>
        </table>
      </div>

      <div class="pdf-foot">
        <span>Result Achievement EPR FY26 · Semua nilai exclude PPN 11%</span>
        <span>${p.tx_count || 0} transaksi terverifikasi</span>
      </div>
    `;

    const prevTitle = document.title;
    document.title = `EPR_${p.code}_${p.name.replace(/[^A-Za-z0-9_-]+/g, "_")}`;
    window.print();
    setTimeout(() => {
      document.title = prevTitle;
    }, 500);
  }

  function openSharePdfModal() {
    $("sharePdfBackdrop").hidden = false;
    $("sharePdfModal").hidden = false;
  }

  function closeSharePdfModal() {
    $("sharePdfBackdrop").hidden = true;
    $("sharePdfModal").hidden = true;
  }

  function shareAllEprPdf(period = state.period) {
    closeSharePdfModal();
    const prevPeriod = state.period;
    state.period = period;
    const list = getFilteredPartners();
    state.period = prevPeriod;

    if (!list.length) {
      alert("Tidak ada data EPR untuk dicetak.");
      return;
    }

    const totalRev = list.reduce((s, p) => s + p.actual, 0);
    const totalTarget = list.reduce((s, p) => s + p.target, 0);
    const totalAch = totalTarget > 0 ? totalRev / totalTarget : null;
    const totalGap = list.reduce((s, p) => s + Math.max(0, (p.target || 0) - (p.actual || 0)), 0);
    const achievedCount = list.filter((p) => p.ach != null && p.ach >= 1).length;
    const periodLabel =
      period === "h1" ? "H1 (Apr – Sep 2026)" : period === "h2" ? "H2 (Okt 2026 – Mar 2027)" : "FY26 (Full Year)";

    const rowsHtml = list
      .map((p, i) => {
        const shortfall = Math.max(0, (p.target || 0) - (p.actual || 0));
        const isOk = p.target > 0 && shortfall === 0;
        const gapCell =
          p.target <= 0
            ? '<td class="num mono">-</td>'
            : isOk
            ? `<td class="num mono pdf-gap-ok">Achieved (${fmtPct(p.ach)})</td>`
            : `<td class="num mono pdf-gap-warn">${fmtRp(shortfall)}</td>`;

        return `<tr>
          <td class="mono">${i + 1}</td>
          <td><b>${esc(p.name)}</b><br><small class="mono">${esc(p.code)} · ${esc(p.city || "-")} · ${esc(p.tier || "-")}</small></td>
          <td class="num mono">${fmtRp(p.target)}</td>
          ${gapCell}
        </tr>`;
      })
      .join("");

    $("pdfReport").innerHTML = `
      <div class="pdf-head">
        <div>
          <h1>Result Achievement EPR — ${esc(periodLabel)}</h1>
          <div class="pdf-meta">${list.length} Partner EPR · ${achievedCount} Achieved (&ge; 100%)</div>
        </div>
        <div class="pdf-meta" style="text-align:right">
          <div><b>Laporan Kekurangan Target ${esc(period.toUpperCase())}</b></div>
          <div>Dicetak: ${new Date().toLocaleString("id-ID")}</div>
        </div>
      </div>

      <div class="pdf-sec">
        <h3>Daftar Target &amp; Kekurangan per EPR (${esc(period.toUpperCase())})</h3>
        <table class="pdf-table">
          <thead>
            <tr>
              <th style="width:36px">#</th>
              <th>Nama EPR</th>
              <th class="num">Target</th>
              <th class="num">Kekurangan</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>

      <div class="pdf-foot">
        <span>Result Achievement EPR (${esc(period.toUpperCase())}) · Exclude PPN 11%</span>
        <span>${list.length} partner</span>
      </div>
    `;

    const prevTitle = document.title;
    document.title = `Result_Achievement_EPR_${period.toUpperCase()}`;
    window.print();
    setTimeout(() => {
      document.title = prevTitle;
    }, 500);
  }

  // Export filtered CSV
  function exportCsv() {
    const list = getFilteredPartners();
    const header = [
      "EPR Code", "EPR Name", "City", "Tier", "AM",
      "Target", "Actual Net", "Achievement %", "Mid Hi",
      "Consumer", "Scanner", "Consumables", "Dotmatrix",
    ];
    const rows = list.map((p) => [
      p.code, p.name, p.city, p.tier, p.am,
      Math.round(p.target), Math.round(p.actual),
      p.ach != null ? (p.ach * 100).toFixed(2) : "",
      Math.round(p.midhi_val),
      Math.round(p.Consumer), Math.round(p.Scanner),
      Math.round(p.Consumables), Math.round(p.Dotmatrix),
    ]);
    const csv = [header, ...rows]
      .map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `EPR_Achievement_${state.period.toUpperCase()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Parse uploaded Data terverifikasi (.xlsx) directly in browser
  function handleExcelUpload(file) {
    if (!file || typeof XLSX === "undefined") return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const wb = XLSX.read(new Uint8Array(ev.target.result), { type: "array" });
        const sheetName = wb.SheetNames.includes("RETAIL") ? "RETAIL" : wb.SheetNames[0];
        const ws = wb.Sheets[sheetName];
        const aoa = XLSX.utils.sheet_to_json(ws, { header: 1, raw: true });

        const partners = [];
        const starts = { Consumer: 13, Scanner: 26, Consumables: 39, Dotmatrix: 52 };
        for (let r = 16; r < aoa.length; r++) {
          const row = aoa[r];
          if (!row || !row[1]) continue;
          const code = String(row[1]).trim();
          const name = String(row[2] || "").trim();
          const city = String(row[4] || "").trim();
          const am = String(row[7] || "").trim();
          const tier = String(row[9] || "").trim();
          const target_fy = Number(row[10] || 0);
          const target_h1 = Math.round(target_fy * 0.52);
          const target_h2 = Math.round(target_fy * 0.48);

          const monthly_by_cat = {};
          const cat_totals = {};
          CATS.forEach((c) => {
            const f0 = starts[c];
            const arr = [];
            for (let m = 0; m < 12; m++) arr.push(Number(row[f0 + m] || 0));
            monthly_by_cat[c] = arr;
            cat_totals[c] = arr.reduce((a, b) => a + b, 0);
          });

          const monthly_total = Array.from({ length: 12 }, (_, m) =>
            CATS.reduce((s, c) => s + monthly_by_cat[c][m], 0)
          );
          const actual_h1 = monthly_total.slice(0, 6).reduce((a, b) => a + b, 0);
          const actual_h2 = monthly_total.slice(6, 12).reduce((a, b) => a + b, 0);
          const actual_fy = actual_h1 + actual_h2;
          const mid_hi = Number(row[71] || 0);
          const low_end = Math.max(0, actual_fy - mid_hi);

          partners.push({
            code, name, city, tier, am,
            target_fy, target_h1, target_h2,
            actual_fy, actual_h1, actual_h2,
            mid_hi, low_end,
            tx_count: 0,
            cat_totals,
            monthly_total,
            monthly_by_cat,
          });
        }

        if (!partners.length) {
          alert("Tidak ditemukan baris EPR pada sheet RETAIL.");
          return;
        }

        rawData = {
          meta: {
            title: "EPR FY26 Achievement Dashboard",
            fiscal_year: "FY26 (Apr 2026 - Mar 2027)",
            generated_at: new Date().toLocaleString("id-ID"),
            last_source_file: file.name,
            verified_rows: 0,
            months: DEFAULT_MONTHS,
          },
          partners,
        };
        populateFilters(partners);
        render();
      } catch (err) {
        console.error(err);
        alert("Gagal membaca file Excel: " + err.message);
      }
    };
    reader.readAsArrayBuffer(file);
  }

  function bindEvents() {
    document.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.period = btn.dataset.period;
        render();
      });
    });

    $("searchInput").addEventListener("input", (e) => {
      state.search = e.target.value;
      render();
    });
    $("tierFilter").addEventListener("change", (e) => {
      state.tier = e.target.value;
      render();
    });
    $("cityFilter").addEventListener("change", (e) => {
      state.city = e.target.value;
      render();
    });
    $("statusFilter").addEventListener("change", (e) => {
      state.status = e.target.value;
      render();
    });

    document.querySelectorAll("th.sortable").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (state.sortKey === key) {
          state.sortDir = state.sortDir === "desc" ? "asc" : "desc";
        } else {
          state.sortKey = key;
          state.sortDir = key === "name" || key === "tier" ? "asc" : "desc";
        }
        document.querySelectorAll("th.sortable").forEach((el) => {
          el.classList.remove("sort-asc", "sort-desc");
        });
        th.classList.add(state.sortDir === "asc" ? "sort-asc" : "sort-desc");
        renderTable(getFilteredPartners());
      });
    });

    $("btnSharePdf").addEventListener("click", sharePartnerPdf);
    $("btnCloseDrawer").addEventListener("click", closeDrawer);
    $("drawerBackdrop").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDrawer();
    });

    $("btnShareAllPdf").addEventListener("click", openSharePdfModal);
    $("btnCloseSharePdf").addEventListener("click", closeSharePdfModal);
    $("sharePdfBackdrop").addEventListener("click", closeSharePdfModal);
    document.querySelectorAll(".share-period-btn").forEach((btn) => {
      btn.addEventListener("click", () => shareAllEprPdf(btn.dataset.sharePeriod));
    });
    $("btnExportCsv").addEventListener("click", exportCsv);
    $("rejectTypeFilter").addEventListener("change", renderRejectedRows);
    $("rejectSearch").addEventListener("input", renderRejectedRows);
    $("btnExportRejected").addEventListener("click", exportRejectedCsv);
    $("excelUpload").addEventListener("change", (e) => {
      if (e.target.files?.[0]) {
        handleExcelUpload(e.target.files[0]);
        closeUploadModal();
      }
      e.target.value = "";
    });

    bindUploadModal();
  }

  // ---------------- Upload Modal & GitHub API ----------------
  let selectedGhFile = null;

  function openUploadModal() {
    $("ghRepo").value = localStorage.getItem("epr_gh_repo") || "ariswidodo/EPR";
    $("ghToken").value = localStorage.getItem("epr_gh_token") || "";
    updateGhBtn();
    $("uploadModalBackdrop").hidden = false;
    $("uploadModal").hidden = false;
  }

  function closeUploadModal() {
    $("uploadModalBackdrop").hidden = true;
    $("uploadModal").hidden = true;
  }

  function updateGhBtn() {
    $("btnGhUpload").disabled = !(
      selectedGhFile &&
      $("ghRepo").value.trim() &&
      $("ghToken").value.trim()
    );
  }

  function setGhStatus(html, cls = "") {
    const el = $("ghStatus");
    el.hidden = false;
    el.className = "upload-status" + (cls ? " " + cls : "");
    el.innerHTML = html;
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result).split(",")[1] || "");
      r.onerror = reject;
      r.readAsDataURL(file);
    });
  }

  async function uploadToGithub() {
    const repo = $("ghRepo").value.trim();
    const token = $("ghToken").value.trim();
    const file = selectedGhFile;
    if (!repo || !token || !file) return;

    localStorage.setItem("epr_gh_repo", repo);
    localStorage.setItem("epr_gh_token", token);

    const btn = $("btnGhUpload");
    btn.disabled = true;
    setGhStatus(`Mengunggah <b>${esc(file.name)}</b> ke <code>${esc(repo)}/inbox/</code>...`);

    const headers = {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    };

    try {
      const path = `inbox/${encodeURIComponent(file.name)}`;
      const apiUrl = `https://api.github.com/repos/${repo}/contents/${path}`;

      let sha = undefined;
      const checkRes = await fetch(apiUrl, { headers });
      if (checkRes.ok) {
        const existing = await checkRes.json();
        sha = existing.sha;
      }

      const content = await fileToBase64(file);
      const putRes = await fetch(apiUrl, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `upload: ${file.name} via dashboard`,
          content,
          ...(sha ? { sha } : {}),
        }),
      });

      if (!putRes.ok) {
        const err = await putRes.json().catch(() => ({}));
        throw new Error(err.message || `HTTP ${putRes.status}`);
      }

      const putData = await putRes.json();
      const commitSha = putData.commit?.sha;
      setGhStatus(
        `File berhasil diunggah ke <code>inbox/</code>. Menunggu GitHub Actions memverifikasi...`
      );

      await pollVerificationRun(repo, headers, commitSha);
    } catch (err) {
      setGhStatus(`Gagal upload: ${esc(err.message)}`, "err");
      btn.disabled = false;
    }
  }

  async function pollVerificationRun(repo, headers, commitSha) {
    const runsUrl = `https://api.github.com/repos/${repo}/actions/workflows/verify-epr.yml/runs?per_page=3`;
    for (let i = 0; i < 45; i++) {
      await new Promise((r) => setTimeout(r, 4000));
      const res = await fetch(runsUrl, { headers, cache: "no-store" });
      if (!res.ok) continue;
      const data = await res.json();
      const run =
        (data.workflow_runs || []).find((r) => !commitSha || r.head_sha === commitSha) ||
        (data.workflow_runs || [])[0];
      if (!run) continue;

      if (run.status !== "completed") {
        setGhStatus(
          `Proses verifikasi berjalan di GitHub Actions (<b>${esc(run.status)}</b>)... ` +
            `<a href="${esc(run.html_url)}" target="_blank" rel="noopener">Lihat log</a>`
        );
        continue;
      }

      if (run.conclusion === "success") {
        setGhStatus(
          `Verifikasi selesai! <a href="${esc(run.html_url)}" target="_blank" rel="noopener">Unduh workbook hasil di Actions</a>. ` +
            `Memuat ulang data dashboard...`,
          "ok"
        );
        await reloadDashboardData(repo, headers);
      } else {
        setGhStatus(
          `Workflow selesai dengan status <b>${esc(run.conclusion)}</b>. ` +
            `<a href="${esc(run.html_url)}" target="_blank" rel="noopener">Cek detail error</a>`,
          "err"
        );
      }
      updateGhBtn();
      return;
    }

    setGhStatus(
      `Upload sukses, namun verifikasi masih berjalan lebih lama. Cek tab <b>Actions</b> di GitHub lalu muat ulang halaman.`
    );
    updateGhBtn();
  }

  async function reloadDashboardData(repo, headers) {
    try {
      // Ambil langsung dari GitHub Contents API agar tidak menunggu cache GitHub Pages
      const res = await fetch(
        `https://api.github.com/repos/${repo}/contents/data/epr_data.json`,
        {
          headers: { ...headers, Accept: "application/vnd.github.raw+json" },
          cache: "no-store",
        }
      );
      if (res.ok) {
        rawData = await res.json();
        populateFilters(rawData.partners || []);
        render();
        return;
      }
    } catch (_) {}
    // Fallback ke file lokal/Pages
    const localRes = await fetch(`./data/epr_data.json?t=${Date.now()}`, { cache: "no-store" });
    if (localRes.ok) {
      rawData = await localRes.json();
      populateFilters(rawData.partners || []);
      render();
    }
  }

  let selectedSrvFile = null;

  async function uploadToLocalServer() {
    if (!selectedSrvFile) return;
    const btn = $("btnSrvUpload");
    const logBox = $("srvLogBox");
    const st = $("srvStatus");
    btn.disabled = true;
    logBox.hidden = false;
    logBox.textContent = "Mengunggah file ke server lokal...\n";
    st.hidden = true;

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        headers: {
          "X-Filename": encodeURIComponent(selectedSrvFile.name),
          "X-Build-Excel": $("chkBuildExcel").checked ? "1" : "0",
        },
        body: selectedSrvFile,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${res.status} (Pastikan dijalankan lewat server.py / start_dashboard.bat)`);
      }

      while (true) {
        await new Promise((r) => setTimeout(r, 500));
        const sRes = await fetch("/api/status", { cache: "no-store" });
        const snap = await sRes.json();
        logBox.textContent = (snap.logs || []).join("\n");
        logBox.scrollTop = logBox.scrollHeight;
        if (!snap.running && snap.done) {
          if (snap.error) {
            st.hidden = false;
            st.className = "upload-status err";
            st.textContent = "Gagal: " + snap.error;
          } else {
            const stInfo = snap.stats || {};
            const links = (snap.files || [])
              .map((f) => `<a href="/api/download/${encodeURIComponent(f.name)}" target="_blank">${esc(f.label)}</a>`)
              .join(" · ");
            st.hidden = false;
            st.className = "upload-status ok";
            st.innerHTML =
              `<b>Selesai!</b> Terverifikasi: <b>${stInfo.kept ?? 0}</b> · ` +
              `Double ditolak: <b>${stInfo.doubles ?? 0}</b> · ` +
              `Luar DB EPR: <b>${stInfo.outside ?? 0}</b>` +
              (links ? `<div style="margin-top:6px">Unduh: ${links}</div>` : "");
            const dRes = await fetch(`./data/epr_data.json?t=${Date.now()}`, { cache: "no-store" });
            if (dRes.ok) {
              rawData = await dRes.json();
              populateFilters(rawData.partners || []);
              render();
            }
          }
          break;
        }
      }
    } catch (err) {
      st.hidden = false;
      st.className = "upload-status err";
      const msg = String(err?.message || err);
      st.textContent = msg.includes("Failed to fetch") || location.protocol === "file:"
        ? "Server lokal belum berjalan atau halaman dibuka dari file://. Jalankan start_dashboard.bat lalu buka http://127.0.0.1:8765/"
        : msg;
    } finally {
      btn.disabled = !selectedSrvFile;
    }
  }

  function bindUploadModal() {
    $("btnOpenUpload").addEventListener("click", openUploadModal);
    $("btnCloseUpload").addEventListener("click", closeUploadModal);
    $("uploadModalBackdrop").addEventListener("click", closeUploadModal);

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab;
        $("tabLocalServer").hidden = tab !== "local-server";
        $("tabLocal").hidden = tab !== "local";
        $("tabGithub").hidden = tab !== "github";
      });
    });

    $("srvFileInput").addEventListener("change", (e) => {
      selectedSrvFile = e.target.files?.[0] || null;
      $("srvFileName").textContent = selectedSrvFile
        ? `${selectedSrvFile.name} (${(selectedSrvFile.size / 1024 / 1024).toFixed(2)} MB)`
        : "Klik untuk pilih file Sell Out (.xlsx / .xlsm)";
      $("btnSrvUpload").disabled = !selectedSrvFile;
    });
    $("btnSrvUpload").addEventListener("click", uploadToLocalServer);

    $("btnToggleToken").addEventListener("click", () => {
      const inp = $("ghToken");
      const show = inp.type === "password";
      inp.type = show ? "text" : "password";
      $("btnToggleToken").textContent = show ? "Sembunyi" : "Lihat";
    });

    $("ghRepo").addEventListener("input", updateGhBtn);
    $("ghToken").addEventListener("input", updateGhBtn);
    $("ghFileInput").addEventListener("change", (e) => {
      selectedGhFile = e.target.files?.[0] || null;
      $("ghFileName").textContent = selectedGhFile
        ? `${selectedGhFile.name} (${(selectedGhFile.size / 1024 / 1024).toFixed(2)} MB)`
        : "Klik untuk pilih file Sell Out (.xlsx / .xlsm)";
      updateGhBtn();
    });

    $("btnGhUpload").addEventListener("click", uploadToGithub);
  }

  async function init() {
    initTheme();
    bindEvents();
    try {
      const res = await fetch("./data/epr_data.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      rawData = await res.json();
      populateFilters(rawData.partners || []);
      render();
    } catch (err) {
      $("metaSubtitle").textContent =
        "Gagal memuat data — pastikan menjalankan start_dashboard.bat lalu buka http://127.0.0.1:8765/";
      console.error(err);
    }
  }

  init();
})();
