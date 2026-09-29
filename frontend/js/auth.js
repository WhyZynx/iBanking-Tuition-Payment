(function () {
	const API_BASE_URL = 'http://localhost:8001';
	const TUITION_API_URL = 'http://localhost:8002/api/v1/tuition';
	const PAYMENT_API_URL = 'http://localhost:8003';
	const TOKEN_KEY = 'ibanking_access_token';
	const PENDING_TRANSACTION_KEY = 'ibanking_pending_transaction_id';
	const PENDING_CONTEXT_KEY = 'ibanking_pending_payment_context';
	const AUTH_MESSAGE_KEY = 'ibanking_auth_message';

	class ApiError extends Error {
		constructor(status, message) {
			super(message);
			this.status = status;
		}
	}

	function errorMessage(status, detail) {
		if (status === 401) return 'Session expired. Please sign in again.';
		if (status === 403) return 'You are not allowed to perform this action.';
		if (status === 404) return 'Data not found.';
		if (status === 409) return detail || 'This payment conflicts with the current account or tuition status.';
		if (status === 422) return 'Invalid input. Check the information and try again.';
		if (status >= 500) return 'Something went wrong. Please try again.';
		if (status === 400) return detail || 'The request could not be completed.';
		return detail || 'The request could not be completed.';
	}

	async function request(baseUrl, path, options = {}) {
		const token = sessionStorage.getItem(TOKEN_KEY);

		const headers = {
			...(options.body ? { 'Content-Type': 'application/json' } : {}),
			...(options.headers || {})
		};

		if (token) {
			headers.Authorization = `Bearer ${token}`;
		}

		let response;

		try {
			response = await fetch(`${baseUrl}${path}`, {
				...options,
				headers
			});
		} catch (_error) {
			throw new ApiError(
				0,
				'A service could not be reached. Check that the backend is running and try again.'
			);
		}

		const data = await response.json().catch(() => ({}));

		if (!response.ok) {
			if (response.status === 401 && token) {
				sessionStorage.setItem(
					AUTH_MESSAGE_KEY,
					errorMessage(401)
				);

				await failPendingTransactions();

				sessionStorage.removeItem(TOKEN_KEY);

				if (isProtectedPage()) {
					window.location.replace('login.html');
				}
			}

			const detail =
				typeof data.detail === 'string'
					? data.detail
					: '';

			throw new ApiError(
				response.status,
				errorMessage(response.status, detail)
			);
		}

		return data;
	}

	function isProtectedPage() {
		return [
			'dashboard.html',
			'profile.html',
			'accounts.html',
			'tuition.html',
			'history.html'
		].includes(
			window.location.pathname.split('/').pop()
		);
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
		try {
			const result = await request(
				API_BASE_URL,
				'/api/v1/auth/login',
				{
					method: 'POST',
					body: JSON.stringify({
						username,
						password
					})
				}
			);

			sessionStorage.setItem(
				TOKEN_KEY,
				result.access_token
			);

			return result;
		} catch (error) {
			if (error.status === 401) {
				throw new ApiError(
					401,
					'Invalid username or password.'
				);
			}

			throw error;
		}
	}

	async function failPendingTransactions() {
		const token = sessionStorage.getItem(TOKEN_KEY);

		if (!token) {
			return;
		}

		try {
			await fetch(
				`${PAYMENT_API_URL}/api/v1/payments/cancel-pending`,
				{
					method: 'POST',
					headers: {
						'Authorization': `Bearer ${token}`
					}
				}
			);
		} catch (error) {
			console.error(
				'Could not fail pending transactions:',
				error
			);
		}
	}

	function failPendingTransactionsOnExit() {
		const token = sessionStorage.getItem(TOKEN_KEY);

		if (!token) {
			return;
		}

		fetch(
			`${PAYMENT_API_URL}/api/v1/payments/cancel-pending`,
			{
				method: 'POST',
				headers: {
					'Authorization': `Bearer ${token}`
				},
				keepalive: true
			}
		).catch(() => { });
	}

	async function logout() {
		await failPendingTransactions();

		sessionStorage.removeItem(TOKEN_KEY);
		sessionStorage.removeItem(PENDING_TRANSACTION_KEY);
		sessionStorage.removeItem(PENDING_CONTEXT_KEY);
		sessionStorage.removeItem(AUTH_MESSAGE_KEY);

		window.location.href = 'login.html';
	}

	function updateNavigation() {
		const isLoggedIn = Boolean(
			sessionStorage.getItem(TOKEN_KEY)
		);

		document
			.querySelectorAll('.logged-in-only')
			.forEach(item =>
				item.classList.toggle(
					'hidden',
					!isLoggedIn
				)
			);

		document
			.querySelectorAll('.logged-out-only')
			.forEach(item =>
				item.classList.toggle(
					'hidden',
					isLoggedIn
				)
			);

		document
			.querySelectorAll('.public-home-link')
			.forEach(item =>
				item.classList.toggle(
					'hidden',
					isLoggedIn
				)
			);

		document
			.querySelectorAll('[data-logout]')
			.forEach(item =>
				item.addEventListener(
					'click',
					event => {
						event.preventDefault();
						logout();
					}
				)
			);
	}

	window.addEventListener(
		'pagehide',
		failPendingTransactionsOnExit
	);

	document.addEventListener(
		'DOMContentLoaded',
		updateNavigation
	);

	window.IBanking = {
		API_BASE_URL,
		TUITION_API_URL,
		PAYMENT_API_URL,
		TOKEN_KEY,
		PENDING_TRANSACTION_KEY,
		PENDING_CONTEXT_KEY,
		AUTH_MESSAGE_KEY,
		ApiError,
		apiRequest: (path, options) =>
			request(API_BASE_URL, path, options),
		paymentRequest: (path, options) =>
			request(PAYMENT_API_URL, path, options),
		tuitionRequest: (path, options) =>
			request('http://localhost:8002', path, options),
		login,
		logout,
		requireAuthentication
	};
})();