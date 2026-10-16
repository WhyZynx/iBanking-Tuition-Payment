document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;
	const errorBox = document.getElementById('dashboard-error');
	try {
		const [user, accounts] = await Promise.all([
			window.IBanking.apiRequest('/api/v1/users/me'),
			window.IBanking.apiRequest('/api/v1/accounts/me')
		]);
		document.getElementById('welcome-title').textContent = `Welcome back, ${user.fullName}`;
		const account = accounts.find(item => item.isDefault) || accounts[0];
		const summary = document.getElementById('dashboard-account-summary');
		if (!account) {
			summary.textContent = 'No payment accounts are available.';
			return;
		}
		document.getElementById('dashboard-account-number').textContent = account.accountNumber;
		document.getElementById('dashboard-account-balance').textContent = new Intl.NumberFormat('en-US', {
			style: 'currency', currency: 'VND', maximumFractionDigits: 0
		}).format(Number(account.balance));
		document.getElementById('dashboard-account-status').textContent = account.status;
		document.getElementById('dashboard-account-default').textContent = account.isDefault ? 'Default account' : 'Account summary';
		summary.classList.remove('muted');
	} catch (error) {
		errorBox.textContent = error.message;
	}
});
