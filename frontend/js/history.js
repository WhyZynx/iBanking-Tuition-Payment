document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;

	const message = document.getElementById('history-message');
	const tableWrap = document.getElementById('history-table-wrap');
	const rows = document.getElementById('history-items');

	try {
		const result = await window.IBanking.paymentRequest('/api/v1/transactions/me');
		const items = Array.isArray(result) ? result : result.items;
		if (!Array.isArray(items)) throw new Error('Payment Service returned an invalid history response.');
		if (!items.length) {
			message.textContent = 'No transactions found.';
			return;
		}

		for (const item of items) {
			const row = document.createElement('tr');
			for (const value of [
				item.transactionId,
				item.studentId,
				item.studentName,
				item.sourceAccountNumber,
				formatAmount(item.amount),
				item.status,
				formatDate(item.createdAt),
				formatDate(item.completedAt)
			]) {
				const cell = document.createElement('td');
				cell.textContent = value || '-';
				row.append(cell);
			}
			rows.append(row);
		}
		message.classList.add('hidden');
		tableWrap.classList.remove('hidden');
	} catch (error) {
		message.textContent = error.message || 'Something went wrong. Please try again.';
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
