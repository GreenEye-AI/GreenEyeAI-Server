

// --- Auth & Cookies ---
function getToken() {
	const match = document.cookie.match(/token=([^;]+)/);
	return match ? match[1] : null;
}

async function send_ph() {
	// 1. Получаем значения из полей
	const dateStr = document.getElementById('phDateInput').value;
	const timeStr = document.getElementById('phTimeInput').value;
	const phStr   = document.getElementById('phFloatInput').value;

	if (!phStr) {
		alert('⚠️ Введите значение pH.');
		return;
	}

	const level = parseFloat(phStr);
	if (isNaN(level) || level < 0 || level > 14) {
		alert('❌ Ошибка: pH должен быть числом от 0 до 14.');
		return;
	}

	const body = { level, }
	if (dateStr && timeStr) {
		const [year, month, day] = dateStr.split('-').map(Number);
		const [hours, minutes]   = timeStr.split(':').map(Number);
		const dateObj = new Date(year, month - 1, day, hours, minutes);
		const time = dateObj.getTime() / 1000;
		body.time = time;
	}

	const res = await fetch('/api/ph', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ token: getToken(), ...body })
	});
	if (!res.ok) alert(`Ошибка отправки pH: ${res.status} ${res.statusText}`);
}

function logout() {
	document.cookie = 'token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
	window.location.href = '/admin/login';
}

// --- API Calls ---
async function apiPost(url, body = {}) {
	const res = await fetch(url, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ token: getToken(), ...body })
	});
	return res.ok;
}

async function apiGet(url) {
	const res = await fetch(url);
	return res.ok ? res.json() : null;
}

// --- State ---
let currentMode = 'auto';

// --- UI Updates ---
function updateUI(mode, relays) {
	currentMode = mode;
	const isAuto = mode === 'auto';
	
	// Toggle visual
	const toggle = document.getElementById('mode-toggle');
	toggle.classList.toggle('active', isAuto);
	
	// Labels
	const modeText = isAuto ? 'Автоматический' : 'Ручной';
	document.getElementById('water-mode-label').textContent = modeText;
	document.getElementById('light-mode-label').textContent = modeText;
	document.getElementById('fan-mode-label').textContent = modeText;

	// Relays Status
	const setStatus = (id, val) => {
		const el = document.getElementById(id);
		el.textContent = val === 1 ? 'ВКЛ' : 'ВЫКЛ';
		el.style.color = val === 1 ? 'var(--primary)' : 'var(--danger)';
	};

	if (relays) {
		setStatus('water-status', relays.water);
		setStatus('light-status', relays.light);
		setStatus('fan-status', relays.fan);
		
		document.getElementById('water-state-text').textContent = `Состояние: ${relays.light ? 'ВКЛ' : 'ВЫКЛ'}`;
		document.getElementById('light-state-text').textContent = `Состояние: ${relays.light ? 'ВКЛ' : 'ВЫКЛ'}`;
		document.getElementById('fan-state-text').textContent = `Состояние: ${relays.fan ? 'ВКЛ' : 'ВЫКЛ'}`;
	}
}

// --- Actions ---
async function controlDevice(device, state) {
	// В ручном режиме мы можем управлять напрямую
	if (currentMode === 'auto') {
		alert('Переключите режим в Ручной для прямого управления');
		return;
	}
	
	const success = await apiPost(`/api/command/${device}`, { state });
	if (success) {
		// Optimistic update
		const val = state === 'on' ? 1 : 0;
		const el = document.getElementById(`${device}-status`);
		el.textContent = state === 'on' ? 'ВКЛ' : 'ВЫКЛ';
		el.style.color = state === 'on' ? 'var(--primary)' : 'var(--danger)';
	} else {
		alert('Ошибка управления');
	}
}

async function toggleSystemMode() {
	const newMode = currentMode === 'auto' ? 'manual' : 'auto';
	const success = await apiPost('/api/command/mode', { mode: newMode });
	if (success) {
		loadData(); // Refresh UI
	}
}

async function saveSchedule() {
	const data = {
		light: {
			start: document.getElementById('sched-light-start').value,
			end: document.getElementById('sched-light-end').value
		},
		fan: {
			interval_hours: parseInt(document.getElementById('sched-fan-int').value),
			duration_minutes: parseInt(document.getElementById('sched-fan-dur').value)
		},
		water: {
			interval_hours: parseInt(document.getElementById('sched-water-int').value),
			duration_minutes: parseInt(document.getElementById('sched-water-dur').value)
		}
	};
	
	const success = await apiPost('/api/schedule', data);
	alert(success ? 'Расписание сохранено' : 'Ошибка сохранения');
}

function showDiseases() {
	document.getElementById('diseases-panel').classList.remove('hidden');
	loadDiseases();
	document.querySelector('.nav-item.active').classList.remove('active');
	event.target.classList.add('active');
}

async function loadDiseases() {
	const data = await apiGet('/api/plants/status');
	const container = document.getElementById('plants-container');
	if (!data || !data.plants.length) {
		container.innerHTML = '<p>Нет данных о растениях</p>';
		return;
	}
	
	container.innerHTML = data.plants.map(p => `
		<div class="plant-card ${p.diagnosis}">
			<div style="font-size:24px">${p.diagnosis === 'healthy' ? '' : '⚠️'}</div>
			<strong>Позиция ${p.position}</strong><br>
			<span class="status-badge ${p.diagnosis === 'healthy' ? 'status-on' : 'status-off'}">${p.diagnosis}</span><br>
			<small>${new Date(p.last_diagnosis_at).toLocaleTimeString()}</small>
		</div>
	`).join('');
}

// --- Load Data ---
async function loadData() {
	// Parallel requests
	const [modeData, relays] = await Promise.all([
		apiGet('/api/command/mode'),
		apiGet('/api/last_state'),
	]);

	if (modeData) updateUI(modeData.mode, relays);

}

async function loadSchedule() {
	const res = await fetch('/api/schedule');
	if (res.ok) {
		const schedule = await res.json();
		// console.log(schedule);
		document.getElementById('sched-light-start').value = schedule.light?.start || '';
		document.getElementById('sched-light-end').value = schedule.light?.end || '';
		document.getElementById('sched-fan-int').value = schedule.fan?.interval_hours || '';
		document.getElementById('sched-fan-dur').value = schedule.fan?.duration_minutes || '';
		document.getElementById('sched-water-int').value = schedule.water?.interval_hours || '';
		document.getElementById('sched-water-dur').value = schedule.water?.duration_minutes || '';
	}
}

// Init
loadSchedule();
loadData();
setInterval(loadData, 10000); // Refresh every 10s