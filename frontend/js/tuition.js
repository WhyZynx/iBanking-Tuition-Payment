document.addEventListener('DOMContentLoaded', async () => {
	if (!window.IBanking.requireAuthentication()) return;

	const userMessage = document.getElementById('user-service-message');
	const tuitionServiceMessage = document.getElementById('tuition-service-message');
	const payerInformation = document.getElementById('payer-information');
	const searchForm = document.getElementById('tuition-search-form');
	const searchButton = document.getElementById('search-button');
	const studentIdInput = document.getElementById('student-id');
	const lookupMessage = document.getElementById('tuition-lookup-message');
	const tuitionResult = document.getElementById('tuition-result');
	const paymentSection = document.getElementById('payment-section');
	const accountOptions = document.getElementById('account-options');
	const accountLoading = document.getElementById('account-loading');
	const accountMessage = document.getElementById('account-selection-message');
	const balanceMessage = document.getElementById('balance-message');
	const confirmDetails = document.getElementById('confirm-details');
	const confirmButton = document.getElementById('confirm-payment');
	const readyMessage = document.getElementById('payment-ready-message');
	const studentMappingNote = document.getElementById('student-mapping-note');

	let accounts = [];
	let selectedAccountNumber = '';
	let selectedTuition = null;
	let currentUser = null;

	searchForm.addEventListener('submit', searchTuition);
	document.querySelectorAll('input[name="payment-target"]').forEach(choice => {
		choice.addEventListener('change', () => {
			studentMappingNote.classList.toggle('hidden', choice.value !== 'self' || !choice.checked);
		});
	});
	confirmDetails.addEventListener('change', updatePaymentState);
	confirmButton.addEventListener('click', () => {
		if (!isPaymentReady()) return;
		readyMessage.classList.remove('hidden');
	});

	await loadPayerAndAccounts();

	async function loadPayerAndAccounts() {
		try {
			currentUser = await window.IBanking.apiRequest('/api/v1/users/me');
			renderPayer(currentUser);
		} catch (error) {
			console.error('Unable to load payer profile:', error);
			showServiceMessage(userMessage, 'Unable to load account information. Please make sure User Service is running.');
			payerInformation.innerHTML = '<p class="muted">Payer information is unavailable.</p>';
		}

		try {
			accounts = await window.IBanking.apiRequest('/api/v1/accounts/me');
			renderAccounts(accounts);
		} catch (error) {
			console.error('Unable to load payer accounts:', error);
			showServiceMessage(userMessage, 'Unable to load account information. Please make sure User Service is running.');
			accountLoading.textContent = 'Payment accounts are unavailable.';
		}
		updatePaymentState();
	}

	function renderPayer(user) {
		const fields = [
			['Full Name', user.fullName],
			['Username', user.username],
			['Phone Number', user.phone],
			['Email Address', user.email]
		];
		payerInformation.replaceChildren();
		for (const [label, value] of fields) {
			const item = document.createElement('div');
			item.className = 'tuition-detail';
			const fieldLabel = document.createElement('span');
			fieldLabel.textContent = label;
			const fieldValue = document.createElement('strong');
			fieldValue.textContent = value || '-';
			item.append(fieldLabel, fieldValue);
			payerInformation.append(item);
		}
	}

	function renderAccounts(accountList) {
		accountLoading.classList.add('hidden');
		accountOptions.replaceChildren();
		const activeAccounts = accountList.filter(account => account.status === 'ACTIVE');
		if (!accountList.length) {
			accountMessage.textContent = 'No payment accounts are available.';
			return;
		}
		if (!activeAccounts.length) {
			accountMessage.textContent = 'No active payment accounts are available.';
		}

		for (const account of accountList) {
			const option = document.createElement('label');
			option.className = 'account-option';
			const radio = document.createElement('input');
			radio.type = 'radio';
			radio.name = 'payment-account';
			radio.value = account.accountNumber;
			radio.disabled = account.status !== 'ACTIVE';
			radio.checked = account.status === 'ACTIVE' && account.isDefault;
			if (radio.checked) selectedAccountNumber = account.accountNumber;
			radio.addEventListener('change', () => {
				selectedAccountNumber = radio.value;
				readyMessage.classList.add('hidden');
				updatePaymentState();
			});

			option.append(radio);
			option.append(createAccountField('Account Number', account.accountNumber));
			option.append(createAccountField('Balance', formatCurrency(account.balance)));
			const statusField = createAccountField('Status', account.status);
			statusField.classList.add('option-status');
			option.append(statusField);
			const defaultLabel = document.createElement('span');
			defaultLabel.className = 'default-label';
			defaultLabel.textContent = account.isDefault ? 'Default account' : '';
			option.append(defaultLabel);
			accountOptions.append(option);
		}
	}

	function createAccountField(label, value) {
		const field = document.createElement('span');
		const fieldLabel = document.createElement('span');
		fieldLabel.className = 'option-label';
		fieldLabel.textContent = label;
		const fieldValue = document.createElement('strong');
		fieldValue.textContent = value == null ? '-' : String(value);
		field.append(fieldLabel, fieldValue);
		return field;
	}

	async function searchTuition(event) {
		event.preventDefault();
		const studentId = studentIdInput.value.trim().toUpperCase();
		lookupMessage.textContent = '';
		tuitionServiceMessage.classList.add('hidden');
		tuitionResult.classList.add('hidden');
		paymentSection.classList.add('hidden');
		readyMessage.classList.add('hidden');
		selectedTuition = null;
		confirmDetails.checked = false;
		updatePaymentState();

		if (!studentId) {
			lookupMessage.textContent = 'Please enter a student ID.';
			return;
		}

		searchButton.disabled = true;
		searchButton.textContent = 'Searching...';
		try {
			const url = `${window.IBanking.TUITION_API_URL}/${encodeURIComponent(studentId)}`;
			const response = await fetch(url);
			if (response.status === 404) {
				lookupMessage.textContent = 'Student tuition record not found.';
				return;
			}
			if (!response.ok) {
				throw new Error(`Tuition Service returned HTTP ${response.status}`);
			}
			const tuition = await response.json();
			if (!tuition || !tuition.student_id || !tuition.student_name || tuition.amount == null || !tuition.status) {
				throw new Error('Tuition Service response is missing required fields.');
			}
			selectedTuition = tuition;
			renderTuition(tuition);
		} catch (error) {
			console.error('Unable to look up tuition:', error);
			showServiceMessage(tuitionServiceMessage, 'Tuition Service is unavailable. Please start Tuition Service on port 8002.');
		} finally {
			searchButton.disabled = false;
			searchButton.textContent = 'Search';
		}
	}

	function renderTuition(tuition) {
		document.getElementById('result-student-id').textContent = tuition.student_id;
		document.getElementById('result-student-name').textContent = tuition.student_name;
		document.getElementById('result-tuition-amount').textContent = formatCurrency(tuition.amount);

		const status = String(tuition.status).toUpperCase();
		const statusElement = document.getElementById('result-tuition-status');
		statusElement.textContent = status;
		statusElement.className = `tuition-status ${status === 'PAID' ? 'paid' : status === 'UNPAID' ? '' : 'unknown'}`;
		tuitionResult.classList.remove('hidden');

		if (status === 'PAID') {
			lookupMessage.textContent = 'This tuition has already been paid.';
			return;
		}
		if (status !== 'UNPAID') {
			lookupMessage.textContent = 'This tuition record has an unsupported payment status.';
			return;
		}

		document.getElementById('selected-tuition-amount').textContent = formatCurrency(tuition.amount);
		paymentSection.classList.remove('hidden');
		updatePaymentState();
	}

	function updatePaymentState() {
		const account = accounts.find(item => item.accountNumber === selectedAccountNumber);
		const selectedBalance = account && account.status === 'ACTIVE' ? Number(account.balance) : null;
		const tuitionAmount = selectedTuition ? Number(selectedTuition.amount) : null;
		document.getElementById('selected-account-balance').textContent = selectedBalance === null ? '-' : formatCurrency(selectedBalance);
		balanceMessage.textContent = '';
		if (selectedTuition && selectedTuition.status === 'UNPAID') {
			if (!account || account.status !== 'ACTIVE') {
				balanceMessage.textContent = 'Select an active payment account.';
			} else if (selectedBalance < tuitionAmount) {
				balanceMessage.textContent = 'Insufficient balance.';
			}
		}
		confirmButton.disabled = !isPaymentReady();
	}

	function isPaymentReady() {
		const account = accounts.find(item => item.accountNumber === selectedAccountNumber);
		return Boolean(
			window.IBanking &&
			sessionStorage.getItem(window.IBanking.TOKEN_KEY) &&
			currentUser &&
			selectedTuition &&
			selectedTuition.status === 'UNPAID' &&
			account &&
			account.status === 'ACTIVE' &&
			Number(account.balance) >= Number(selectedTuition.amount) &&
			confirmDetails.checked
		);
	}

	function showServiceMessage(element, message) {
		element.textContent = message;
		element.classList.remove('hidden');
	}

	function formatCurrency(amount) {
		return new Intl.NumberFormat('vi-VN', {
			style: 'currency',
			currency: 'VND',
			maximumFractionDigits: 0
		}).format(Number(amount));
	}
});
