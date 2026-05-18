
async function updateSchedule() {
	await fetch('/api/schedule')
		.then(res => res.json())
		.then(data => {
			const container = document.getElementById('schedule-view');
			container.innerHTML = '';
			const addCard = (icon, title, rows) => {
				const card = document.createElement('div');
				card.style.cssText = 'background: #f7fafc; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0;';
				let html = `<div style="font-weight: 600; margin-bottom: 10px; font-size: 16px;">${icon} ${title}</div>`;
				rows.forEach(([label, val]) => {
					html += `<div style="display: flex; justify-content: space-between; font-size: 14px; color: #4a5568; margin-bottom: 6px;">
						<span>${label}</span> <span style="font-weight: 500; color: #2d3748;">${val || '—'}</span>
					</div>`;
				});
				card.innerHTML = html;
				container.appendChild(card);
			};

			const l = data.light || data.osveshchenie || data.light_schedule;
			const f = data.fan || data.ventilyator || data.fan_schedule;
			const w = data.water || data.poliv || data.water_schedule;

			if (l) addCard('💡', 'Освещение', [['Включение', l.start || l.on || '—'], ['Выключение', l.end || l.off || '—']]);
			if (f) addCard('🌀', 'Обдув', [['Интервал', f.interval_hours ? `${f.interval_hours} ч` : '—'], ['Длительность', f.duration_minutes ? `${f.duration_minutes} мин` : '—']]);
			if (w) addCard('🚿', 'Полив', [['Интервал', w.interval_hours ? `${w.interval_hours} ч` : '—'], ['Длительность', w.duration_minutes ? `${w.duration_minutes} мин` : '—']]);

			if (!l && !f && !w) {
				const fallback = document.createElement('pre');
				fallback.style.cssText = 'background: #f7fafc; padding: 15px; border-radius: 12px; white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #2d3748; grid-column: 1 / -1;';
				fallback.textContent = JSON.stringify(data, null, 2);
				container.appendChild(fallback);
			}
		})
		.catch(() => {
			document.getElementById('schedule-view').textContent = 'Ошибка загрузки расписания';
		});
}

async function updateState() {
	const rw = document.getElementById('relay-water');
	const rl = document.getElementById('relay-light');
	const rf = document.getElementById('relay-fan');
	const elements = [rw, rl, rf];
	await fetch('/api/last_state')
		.then(res => res.json())
		.then(data => {
			rw.textContent = (data.water ? 'ON' : 'OFF');
			rw.className = 'relay-status ' + (data.water ? 'on' : 'off');

			rl.textContent = (data.light ? 'ON' : 'OFF');
			rl.className = 'relay-status ' + (data.light ? 'on' : 'off');

			rf.textContent = (data.fan ? 'ON' : 'OFF');
			rf.className = 'relay-status ' + (data.fan ? 'on' : 'off');
		})
		.catch(() => {
			elements.forEach(element => {
				element.textContent = '???';
				element.className = 'relay-status wtf';
			});
		});
}


const baseChartConfig = {
	type: 'line',
	data: {
		labels: [],
		datasets: [{
			label: 'Состояние',
			data: [],
			borderColor: '#2563eb',
			backgroundColor: 'rgba(37, 99, 235, 0.15)',
			stepped: 'before',
			tension: 0.0,
			pointRadius: 3,
			pointHoverRadius: 6,
			fill: true
		}]
	},
	options: {
		responsive: true,
		maintainAspectRatio: false,
		animation: false,
		interaction: { mode: 'nearest', intersect: false },
		scales: {
			y: {
				min: -0.1,
				max: 1.1,
				ticks: {
					stepSize: 1,
					// callback: value => value > 0 ? 'Вкл' : 'Выкл'
				},
				grid: { color: 'rgba(0,0,0,0.08)' }
			},
			x: {
				grid: { display: false },
				ticks: { maxRotation: 45 }
			}
		},
		plugins: {
			legend: { display: false },
			tooltip: {
				callbacks: {
					// title: items => `Время: ${items[0].label}`,
					// label: ctx => `Состояние: ${ctx.raw === 1 ? 'Вкл' : 'Выкл'}`
				}
			}
		}
	}
}

function getChartConfig(table) {
	const config = structuredClone(baseChartConfig);
	config.options.plugins.tooltip.callbacks.title = items => `Время: ${items[0].label}`;
	switch (table) {
		case 'ph':
			config.data.datasets[0].stepped = false;
			config.data.datasets[0].tension = 0.4;
			config.options.scales.y.min = 0;
			config.options.scales.y.max = 14;
			config.options.scales.y.ticks.stepSize = 0.5;
			config.options.scales.y.ticks.callback = value => value
			config.options.plugins.tooltip.callbacks.label = ctx => `Среда: ${ctx.raw} ${ctx.raw < 6 ? '(кислотная)' : (ctx.raw > 8 ? '(щелочная)' : '(нейтральная)')}`
			break;

		case 'temperature':
			config.data.datasets[0].stepped = false;
			config.data.datasets[0].tension = 0.4;
			config.options.scales.y.min = -10;
			config.options.scales.y.max = 40;
			config.options.scales.y.ticks.stepSize = 5;
			config.options.scales.y.ticks.callback = value => value
			config.options.plugins.tooltip.callbacks.label = ctx => `Температура: ${ctx.raw}°C`
			break;

		case 'humidity':
			config.data.datasets[0].stepped = false;
			config.data.datasets[0].tension = 0.4;
			config.options.scales.y.min = 0;
			config.options.scales.y.max = 100;
			config.options.scales.y.ticks.stepSize = 10;
			config.options.scales.y.ticks.callback = value => value
			config.options.plugins.tooltip.callbacks.label = ctx => `Влажность: ${ctx.raw}%`
			break;
	
		default:
			config.data.datasets[0].stepped = 'before';
			config.data.datasets[0].tension = 0.0;
			config.options.scales.y.min = -0.1;
			config.options.scales.y.max = 1.1;
			config.options.scales.y.ticks.stepSize = 1;
			config.options.scales.y.ticks.callback = value => value > 0 ? 'Вкл' : 'Выкл'
			config.options.plugins.tooltip.callbacks.label = ctx => `Состояние: ${ctx.raw === 1 ? 'Вкл' : 'Выкл'}`
			break;
	}
	return config;
}

// Хранилище инстансов графиков
const charts = {};

// Обновление данных в существующем графике
function updateChartWithData(table, data) {
	const isph = table === 'ph';
	const containerId = 'history-' + table;

	if (!charts[containerId]) {
		const container = document.getElementById(containerId);
		if (!container) return;

		container.innerHTML = '';
		const canvas = document.createElement('canvas');
		container.appendChild(canvas);
		
		charts[containerId] = new Chart(canvas, getChartConfig(table));
	};

	const chart = charts[containerId];
	if (!chart) return;

	// Если данных нет или ошибка, очищаем график и выводим в консоль
	if (!Array.isArray(data) || data.length === 0) {
		console.warn(`Нет данных для графика: ${table}`);
		chart.data.labels = [];
		chart.data.datasets[0].data = [];
		chart.update();
		return;
	}

	// Оставляем только последние 20 записей
	data = data.slice(-20);

	// Преобразуем timestamp → ЧЧ:ММ
	chart.data.labels = data.map(([ts]) => {
		const d = new Date(ts * 1000);
		const hh = String(d.getHours()).padStart(2, '0');
		const mm = String(d.getMinutes()).padStart(2, '0');
		if (isph) {
			const dd = String(d.getDate()).padStart(2, '0');
			const mo = String(d.getMonth() + 1).padStart(2, '0');
			return `${hh}:${mm}  ${dd}.${mo}`;
		}
		return `${hh}:${mm}`;
	});
	chart.data.datasets[0].data = data.map(([, state]) => state);

	// Быстрое обновление без полной перерисовки
	chart.update();
}

async function reqToTable(table, seconds) {
	await fetch('/api/graph/table', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ table, seconds })
		})
		.then(res => {
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			return res.json();
		})
		.then(data => {
			if (table === 'sensors') {
				const temperature = data.map(subarray => [subarray[0], subarray[1]]);
				const humidity = data.map(subarray => [subarray[0], subarray[2]]);
				updateChartWithData('temperature', temperature);
				updateChartWithData('humidity', humidity);
			} else {
				updateChartWithData(table, data);
			}
		})
		.catch(err => console.error(`Ошибка загрузки графика ${table}:`, err))
}

// Параллельная загрузка и обновление графиков
async function updateGraphs() {
	const day = 24 * 60 * 60;
	await Promise.allSettled([
		reqToTable('water',   day  ),
		reqToTable('light',   day  ),
		reqToTable('fan',     day  ),
		reqToTable('ph',      day*7),
		reqToTable('sensors', day  ),
	]);
}

// === Логика сетки растений ===
const PLANT_STATUSES = {
	healthy:  { class: 'healthy',  label: '🌿 Здоровое' },
	wilted:   { class: 'wilted',   label: '🥀 Вялое' },
	diseased: { class: 'diseased', label: '🤒 Заболело' },
	dried:    { class: 'dried',    label: '💀 Засохло' },
	empty:    { class: 'empty',    label: '⬛ Нет растения' }
};

async function updatePlantGrid() {
	const grid = document.getElementById('plant-grid');
	if (!grid) return;

	let mockData = {};
	await fetch('/api/plants')
		.then(res => {
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			return res.json();
		})
		.then(data => {
			mockData = data;
		})
		.catch(err => {
			console.error('Ошибка загрузки растений:', err);
			return;
		})

	// === Отрисовка сетки ===
	grid.innerHTML = '';

	// Используем Object.entries() для перебора {id: status}
	Object.entries(mockData).forEach(([id, statusKey]) => {
		const status = PLANT_STATUSES[statusKey];
		if (!status) return; // защита от неизвестных статусов

		const square = document.createElement('div');
		square.className = `plant-square ${status.class}`;
		square.setAttribute('tabindex', '0');

		const tooltip = document.createElement('span');
		tooltip.className = 'plant-tooltip';
		tooltip.textContent = `${status.label} | Позиция: ${id}`;

		square.appendChild(tooltip);
		grid.appendChild(square);
	});
}

async function updateAll() {
	await updateState();
	await updateSchedule();
	await updateGraphs();
	await updatePlantGrid();
}

updateAll();
setInterval(updateAll, 5000);