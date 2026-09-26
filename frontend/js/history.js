document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;

	// Set this after Student 3 confirms the Payment Service host and port.
	const PAYMENT_SERVICE_URL = '';
	const HISTORY_PATH = '/api/v1/transactions/me';
	const message = document.getElementById('history-message');
	const tableWrap = document.getElementById('history-table-wrap');
	const rows = document.getElementById('history-items');
	const token = sessionStorage.getItem(window.IBanking.TOKEN_KEY);
	if (!PAYMENT_SERVICE_URL) {
		message.textContent = 'Payment Service endpoint is not configured yet. Transaction history will appear after the service endpoint is confirmed.';
		return;
	}

	try {
		const response = await fetch(`${PAYMENT_SERVICE_URL}${HISTORY_PATH}`, {
			headers: { Authorization: `Bearer ${token}` }
		});
		if (!response.ok) throw new Error(`Payment Service returned HTTP ${response.status}`);
		const result = await response.json();
		const items = Array.isArray(result) ? result : result.items;
		if (!Array.isArray(items)) throw new Error('Payment Service response must contain an items array.');
		if (!items.length) {
			message.textContent = 'No transaction history.';
			return;
		}

		for (const item of items) {
			const row = document.createElement('tr');
			for (const value of [formatDate(item.createdAt), item.transactionId, item.studentName || item.studentId, formatAmount(item.amount), item.status]) {
				const cell = document.createElement('td');
				cell.textContent = value || '-';
				row.append(cell);
			}
			rows.append(row);
		}
		message.classList.add('hidden');
		tableWrap.classList.remove('hidden');
	} catch (error) {
		console.error('Unable to load transaction history:', error);
		message.textContent = 'Payment Service is unavailable. Transaction history will appear when its API is ready.';
	}

	function formatDate(value) {
		if (!value) return '-';
		const date = new Date(value);
		return Number.isNaN(date.getTime()) ? '-' : new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
	}

	function formatAmount(value) {
		const amount = Number(value);
		return Number.isFinite(amount) ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount) : '-';
	}
});
