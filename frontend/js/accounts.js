document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;
	const list = document.getElementById('account-list');
	const errorBox = document.getElementById('accounts-error');
	try {
		const accounts = await window.IBanking.apiRequest('/api/v1/accounts/me');
		if (!accounts.length) {
			list.innerHTML = '<div class="card empty-state">No payment accounts are available for this user.</div>';
			return;
		}
		list.innerHTML = accounts.map(account => `
			<article class="card account-card">
				<div class="account-card-top">
					<span class="account-number"></span>
					<span class="account-badge ${account.status === 'ACTIVE' ? '' : 'inactive'}"></span>
				</div>
				<p class="detail-label">Simulated balance</p>
				<p class="account-balance">${Number(account.balance).toLocaleString('en-US')} VND</p>
				<div class="account-meta"><span>Default account</span><strong>${account.isDefault ? 'Yes' : 'No'}</strong></div>
			</article>`).join('');
		list.querySelectorAll('.account-number').forEach((element, index) => {
			element.textContent = accounts[index].accountNumber;
		});
		list.querySelectorAll('.account-badge').forEach((element, index) => {
			element.textContent = accounts[index].status;
		});
	} catch (error) {
		list.innerHTML = '';
		errorBox.textContent = error.message;
	}
});
