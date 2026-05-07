// Auto Safety Check — Frontend
// Loads pre-aggregated NHTSA complaint data and provides
// make/model/year search with component breakdown and timeline.

(function () {
    'use strict';

    // State
    let makes = null;     // makes.json: { MAKE: [{ m: MODEL, y: [min,max], n: count }] }
    let vehicles = null;  // vehicles.json: { "MAKE|MODEL|YEAR": { n, cr, fi, in, de, co, tl, mfr } }
    let stats = null;     // stats.json: national summary
    let meta = null;      // meta.json: data vintage

    // DOM refs
    const makeSelect = document.getElementById('make-select');
    const modelSelect = document.getElementById('model-select');
    const yearSelect = document.getElementById('year-select');
    const hint = document.getElementById('search-hint');
    const statsBanner = document.getElementById('stats-banner');
    const topSection = document.getElementById('top-section');
    const topList = document.getElementById('top-list');
    const detailSection = document.getElementById('detail-section');
    const modelSection = document.getElementById('model-section');

    // Formatting
    function fmt(n) {
        if (n == null) return '—';
        return n.toLocaleString();
    }

    function fmtShort(n) {
        if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
        if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return String(n);
    }

    // Title case
    function titleCase(s) {
        return s.toLowerCase().replace(/(?:^|\s|-)\S/g, c => c.toUpperCase());
    }

    // Load data
    async function init() {
        hint.textContent = 'Loading vehicle data...';

        try {
            const [makesRes, vehiclesRes, statsRes, metaRes] = await Promise.all([
                fetch('data/makes.json'),
                fetch('data/vehicles.json'),
                fetch('data/stats.json'),
                fetch('data/meta.json'),
            ]);

            makes = await makesRes.json();
            vehicles = await vehiclesRes.json();
            stats = await statsRes.json();
            meta = await metaRes.json();
        } catch (e) {
            hint.textContent = 'Error loading data. Please refresh.';
            console.error(e);
            return;
        }

        // Populate make dropdown
        const makeNames = Object.keys(makes).sort();
        for (const m of makeNames) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = titleCase(m);
            makeSelect.appendChild(opt);
        }

        // Show stats
        document.getElementById('stat-complaints').textContent = fmt(stats.total_complaints);
        document.getElementById('stat-crashes').textContent = fmt(stats.total_crashes);
        document.getElementById('stat-deaths').textContent = fmt(stats.total_deaths);
        document.getElementById('stat-vehicles').textContent = fmt(stats.unique_vehicles);

        // Show top vehicles
        renderTopVehicles();

        // Footer vintage
        if (meta.data_freshness) {
            document.getElementById('footer-vintage').textContent =
                `Data vintage: ${meta.data_freshness.vintage}`;
        }

        hint.textContent = `${fmt(stats.total_complaints)} complaints across ${fmt(Object.keys(makes).length)} makes. Select a make to start.`;

        // Event listeners
        makeSelect.addEventListener('change', onMakeChange);
        modelSelect.addEventListener('change', onModelChange);
        yearSelect.addEventListener('change', onYearChange);
    }

    function renderTopVehicles() {
        if (!stats.top_vehicles) return;

        topList.innerHTML = '';
        const top = stats.top_vehicles.slice(0, 20);

        for (const v of top) {
            const el = document.createElement('div');
            el.className = 'top-item';
            el.innerHTML = `
                <div class="vehicle-name">
                    ${titleCase(v.m)} ${titleCase(v.mo)} <span>${v.y}</span>
                </div>
                <div class="count">
                    <div>${fmt(v.n)}</div>
                    <div class="count-label">Complaints</div>
                </div>
                <div class="count${v.cr ? ' severity' : ''}">
                    <div>${v.cr || 0}</div>
                    <div class="count-label">Crashes</div>
                </div>
                <div class="count${v.de ? ' severity' : ''}">
                    <div>${v.de || 0}</div>
                    <div class="count-label">Deaths</div>
                </div>
            `;
            el.addEventListener('click', () => {
                makeSelect.value = v.m;
                onMakeChange();
                modelSelect.value = v.mo;
                onModelChange();
                yearSelect.value = String(v.y);
                onYearChange();
            });
            topList.appendChild(el);
        }
    }

    function onMakeChange() {
        const make = makeSelect.value;
        modelSelect.innerHTML = '<option value="">Select model...</option>';
        yearSelect.innerHTML = '<option value="">All years</option>';
        modelSelect.disabled = true;
        yearSelect.disabled = true;

        hideAll();

        if (!make) {
            topSection.classList.remove('hidden');
            statsBanner.classList.remove('hidden');
            return;
        }

        const models = makes[make];
        if (!models) return;

        // Sort by complaint count descending
        const sorted = [...models].sort((a, b) => b.n - a.n);

        for (const m of sorted) {
            const opt = document.createElement('option');
            opt.value = m.m;
            opt.textContent = `${titleCase(m.m)} (${fmt(m.n)} complaints)`;
            modelSelect.appendChild(opt);
        }

        modelSelect.disabled = false;
        hint.textContent = `${sorted.length} models for ${titleCase(make)}. Select a model.`;
    }

    function onModelChange() {
        const make = makeSelect.value;
        const model = modelSelect.value;
        yearSelect.innerHTML = '<option value="">All years</option>';
        yearSelect.disabled = true;

        hideAll();

        if (!model) return;

        // Find year range and populate
        const modelInfo = makes[make].find(m => m.m === model);
        if (!modelInfo) return;

        // Collect all years with data
        const years = [];
        for (let y = modelInfo.y[1]; y >= modelInfo.y[0]; y--) {
            const key = `${make}|${model}|${y}`;
            if (vehicles[key]) {
                years.push(y);
            }
        }

        for (const y of years) {
            const key = `${make}|${model}|${y}`;
            const v = vehicles[key];
            const opt = document.createElement('option');
            opt.value = String(y);
            opt.textContent = `${y} (${fmt(v.n)} complaints)`;
            yearSelect.appendChild(opt);
        }

        yearSelect.disabled = false;

        // Show all-years model view
        renderModelView(make, model, years);
    }

    function onYearChange() {
        const make = makeSelect.value;
        const model = modelSelect.value;
        const year = yearSelect.value;

        hideAll();

        if (!year) {
            // Show model overview
            const modelInfo = makes[make].find(m => m.m === model);
            if (!modelInfo) return;
            const years = [];
            for (let y = modelInfo.y[1]; y >= modelInfo.y[0]; y--) {
                if (vehicles[`${make}|${model}|${y}`]) years.push(y);
            }
            renderModelView(make, model, years);
            return;
        }

        const key = `${make}|${model}|${year}`;
        const v = vehicles[key];
        if (!v) {
            hint.textContent = 'No complaint data for this vehicle/year.';
            return;
        }

        renderDetail(make, model, parseInt(year), v);
    }

    function hideAll() {
        topSection.classList.add('hidden');
        statsBanner.classList.add('hidden');
        detailSection.classList.add('hidden');
        modelSection.classList.add('hidden');
    }

    // Model view (all years for a given make/model)
    function renderModelView(make, model, years) {
        modelSection.classList.remove('hidden');

        // Find total complaints across all years
        let totalComplaints = 0;
        let maxComplaints = 0;
        let totalCrashes = 0;
        let totalDeaths = 0;
        let mfrName = '';

        const yearData = [];
        for (const y of years) {
            const key = `${make}|${model}|${y}`;
            const v = vehicles[key];
            if (!v) continue;
            totalComplaints += v.n;
            totalCrashes += v.cr || 0;
            totalDeaths += v.de || 0;
            if (v.n > maxComplaints) maxComplaints = v.n;
            if (v.mfr) mfrName = v.mfr;
            yearData.push({ y, v });
        }

        const mh = document.getElementById('model-header');
        mh.innerHTML = `
            <span class="back-link" id="model-back">&larr; Back</span>
            <h2>${titleCase(make)} ${titleCase(model)}</h2>
            <div class="mfr-name">${mfrName} &middot; ${fmt(totalComplaints)} total complaints across ${years.length} model years</div>
        `;
        document.getElementById('model-back').addEventListener('click', () => {
            makeSelect.value = '';
            onMakeChange();
            topSection.classList.remove('hidden');
            statsBanner.classList.remove('hidden');
            modelSection.classList.add('hidden');
        });

        const my = document.getElementById('model-years');
        my.innerHTML = '';

        for (const { y, v } of yearData) {
            const pct = maxComplaints > 0 ? (v.n / maxComplaints * 100) : 0;
            const el = document.createElement('div');
            el.className = 'year-card';
            el.innerHTML = `
                <div class="year">${y}</div>
                <div class="complaints-bar">
                    <div class="complaints-bar-fill" style="width:${pct}%"></div>
                </div>
                <div class="count">
                    <div>${fmt(v.n)}</div>
                    <div class="count-label">Complaints</div>
                </div>
                <div class="count${v.cr ? ' severity' : ''}">
                    <div>${v.cr || 0}</div>
                    <div class="count-label">Crashes</div>
                </div>
                <div class="count${v.fi ? ' severity' : ''}">
                    <div>${v.fi || 0}</div>
                    <div class="count-label">Fires</div>
                </div>
                <div class="count${v.de ? ' severity' : ''}">
                    <div>${v.de || 0}</div>
                    <div class="count-label">Deaths</div>
                </div>
            `;
            el.addEventListener('click', () => {
                yearSelect.value = String(y);
                onYearChange();
            });
            my.appendChild(el);
        }

        hint.textContent = `${titleCase(make)} ${titleCase(model)} — ${years.length} model years, ${fmt(totalComplaints)} complaints, ${fmt(totalCrashes)} crashes, ${fmt(totalDeaths)} deaths.`;
    }

    // Detail view for a specific make/model/year
    function renderDetail(make, model, year, v) {
        detailSection.classList.remove('hidden');

        // Header
        const vh = document.getElementById('vehicle-header');
        vh.innerHTML = `
            <span class="back-link" id="detail-back">&larr; All ${titleCase(model)} years</span>
            <h2>${year} ${titleCase(make)} ${titleCase(model)}</h2>
            <div class="mfr-name">${v.mfr || ''} &middot; ${fmt(v.n)} consumer complaints</div>
        `;
        document.getElementById('detail-back').addEventListener('click', () => {
            yearSelect.value = '';
            onYearChange();
        });

        // Severity grid
        const sg = document.getElementById('severity-grid');
        const items = [
            { label: 'Complaints', val: v.n, cls: '' },
            { label: 'Crashes', val: v.cr || 0, cls: v.cr ? 'has-value' : '' },
            { label: 'Fires', val: v.fi || 0, cls: v.fi ? 'has-value' : '' },
            { label: 'Injuries', val: v.in || 0, cls: v.in ? 'has-value' : '' },
        ];

        // Add deaths if any
        if (v.de) {
            items.push({ label: 'Deaths', val: v.de, cls: 'has-value' });
        }

        sg.innerHTML = items.map(i => `
            <div class="severity-card ${i.cls}">
                <div class="sev-value${i.cls ? ' red' : ''}">${fmt(i.val)}</div>
                <div class="sev-label">${i.label}</div>
            </div>
        `).join('');

        // Component breakdown
        renderComponents(v.co || {});

        // Timeline
        renderTimeline(v.tl || {});

        // Compare table
        renderCompare(make, model, year);

        hint.textContent = `${year} ${titleCase(make)} ${titleCase(model)} — ${fmt(v.n)} complaints.`;
    }

    function renderComponents(comps) {
        const chart = document.getElementById('components-chart');
        const entries = Object.entries(comps).sort((a, b) => b[1] - a[1]);

        if (entries.length === 0) {
            chart.innerHTML = '<p style="color:var(--text-dim)">No component data available.</p>';
            return;
        }

        const maxCount = entries[0][1];

        chart.innerHTML = entries.map(([name, count]) => {
            const pct = (count / maxCount * 100).toFixed(1);
            const displayName = titleCase(name.replace(/, /g, '/'));
            return `
                <div class="comp-bar">
                    <div class="comp-name" title="${name}">${displayName}</div>
                    <div class="comp-fill">
                        <div class="comp-fill-inner" style="width:${pct}%"></div>
                    </div>
                    <div class="comp-count">${fmt(count)}</div>
                </div>
            `;
        }).join('');
    }

    function renderTimeline(tl) {
        const chart = document.getElementById('timeline-chart');
        const entries = Object.entries(tl).sort((a, b) => a[0] - b[0]);

        if (entries.length === 0) {
            chart.innerHTML = '<p style="color:var(--text-dim)">No timeline data available.</p>';
            return;
        }

        const maxCount = Math.max(...entries.map(e => e[1]));

        chart.innerHTML = entries.map(([year, count]) => {
            const pct = (count / maxCount * 100).toFixed(1);
            return `
                <div class="tl-bar-wrapper">
                    <div class="tl-bar" style="height:${pct}%">
                        <span class="tooltip">${year}: ${fmt(count)}</span>
                    </div>
                    <div class="tl-label">${year.slice(2)}</div>
                </div>
            `;
        }).join('');
    }

    function renderCompare(make, model, currentYear) {
        const container = document.getElementById('compare-table');

        // Find all years for this model
        const modelInfo = makes[make].find(m => m.m === model);
        if (!modelInfo) {
            container.innerHTML = '';
            return;
        }

        const rows = [];
        for (let y = modelInfo.y[1]; y >= modelInfo.y[0]; y--) {
            const key = `${make}|${model}|${y}`;
            const v = vehicles[key];
            if (!v) continue;
            rows.push({ y, v });
        }

        if (rows.length < 2) {
            container.innerHTML = '';
            document.getElementById('compare-section').classList.add('hidden');
            return;
        }

        document.getElementById('compare-section').classList.remove('hidden');

        let html = `
            <table class="compare-table">
                <thead>
                    <tr>
                        <th>Year</th>
                        <th>Complaints</th>
                        <th>Crashes</th>
                        <th>Fires</th>
                        <th>Injuries</th>
                        <th>Deaths</th>
                    </tr>
                </thead>
                <tbody>
        `;

        for (const { y, v } of rows) {
            const active = y === currentYear ? ' class="active"' : '';
            html += `
                <tr${active} data-year="${y}">
                    <td><strong>${y}</strong></td>
                    <td>${fmt(v.n)}</td>
                    <td${v.cr ? ' class="severity"' : ''}>${v.cr || 0}</td>
                    <td${v.fi ? ' class="severity"' : ''}>${v.fi || 0}</td>
                    <td${v.in ? ' class="severity"' : ''}>${v.in || 0}</td>
                    <td${v.de ? ' class="severity"' : ''}>${v.de || 0}</td>
                </tr>
            `;
        }

        html += '</tbody></table>';
        container.innerHTML = html;

        // Click handler for compare rows
        container.querySelectorAll('tr[data-year]').forEach(tr => {
            tr.addEventListener('click', () => {
                const y = tr.dataset.year;
                yearSelect.value = y;
                onYearChange();
            });
        });
    }

    // Init
    init();
})();
