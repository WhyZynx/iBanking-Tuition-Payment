(function () {
	const API_BASE_URL = 'http://localhost:8001';
	const TUITION_API_URL = 'http://localhost:8002/api/v1/tuition';
	const TOKEN_KEY = 'ibanking_access_token';

	async function apiRequest(path, options = {}) {
		const token = sessionStorage.getItem(TOKEN_KEY);
		const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
		if (token) headers.Authorization = `Bearer ${token}`;

		const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
		const data = await response.json().catch(() => ({}));
		if (!response.ok) {
			if (response.status === 401 && token) {
				sessionStorage.removeItem(TOKEN_KEY);
				if (isProtectedPage()) window.location.href = 'login.html';
			}
			throw new Error(data.detail || 'The request could not be completed.');
		}
		return data;
	}

	function isProtectedPage() {
		return ['dashboard.html', 'profile.html', 'accounts.html', 'tuition.html', 'history.html'].includes(window.location.pathname.split('/').pop());
	}

	function requireAuthentication() {
		if (!sessionStorage.getItem(TOKEN_KEY)) {
			window.location.replace('login.html');
			return false;
		}
		document.body.classList.remove('auth-pending');
		return true;
	}

	async function login(username, password) {
		const result = await apiRequest('/api/v1/auth/login', {
			method: 'POST',
			body: JSON.stringify({ username, password })
		});
		sessionStorage.setItem(TOKEN_KEY, result.access_token);
		return result;
	}

	function logout() {
		sessionStorage.removeItem(TOKEN_KEY);
		window.location.href = 'login.html';
	}

	function updateNavigation() {
		const isLoggedIn = Boolean(sessionStorage.getItem(TOKEN_KEY));
		document.querySelectorAll('.logged-in-only').forEach(item => item.classList.toggle('hidden', !isLoggedIn));
		document.querySelectorAll('.logged-out-only').forEach(item => item.classList.toggle('hidden', isLoggedIn));
		document.querySelectorAll('.public-home-link').forEach(item => item.classList.toggle('hidden', isLoggedIn));
		document.querySelectorAll('[data-logout]').forEach(item => item.addEventListener('click', event => {
			event.preventDefault();
			logout();
		}));
	}

	document.addEventListener('DOMContentLoaded', updateNavigation);
	window.IBanking = { API_BASE_URL, TUITION_API_URL, TOKEN_KEY, apiRequest, login, logout, requireAuthentication };
})();
