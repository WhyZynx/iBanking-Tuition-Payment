document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;
	const details = document.getElementById('profile-details');
	const errorBox = document.getElementById('profile-error');
	try {
		const user = await window.IBanking.apiRequest('/api/v1/users/me');
		details.replaceChildren();
		const heading = document.createElement('div');
		heading.className = 'profile-identity';
		const name = document.createElement('h2');
		name.textContent = user.fullName || 'User';
		const username = document.createElement('p');
		username.textContent = user.username || '-';
		heading.append(name, username);

		const information = document.createElement('div');
		information.className = 'profile-information';
		for (const [label, value] of [
			['Full Name', user.fullName], ['Username', user.username],
			['Phone', user.phone], ['Email', user.email]
		]) {
			const item = document.createElement('div');
			item.className = 'detail-item';
			const fieldLabel = document.createElement('span');
			fieldLabel.className = 'detail-label';
			fieldLabel.textContent = label;
			const fieldValue = document.createElement('span');
			fieldValue.className = 'detail-value';
			fieldValue.textContent = value || '-';
			item.append(fieldLabel, fieldValue);
			information.append(item);
		}
		details.append(heading, information);
	} catch (error) {
		details.innerHTML = '';
		errorBox.textContent = error.message;
	}
});
