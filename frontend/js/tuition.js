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
	const createPaymentButton = document.getElementById('confirm-payment');
	const actionMessage = document.getElementById('payment-action-message');
	const otpSection = document.getElementById('otp-section');
	const otpForm = document.getElementById('otp-form');
	const otpInput = document.getElementById('otp-code');
	const otpError = document.getElementById('otp-error');
	const otpDeliveryMessage = document.getElementById('otp-delivery-message');
	const resendOtpButton = document.getElementById('resend-otp');
	const confirmOtpButton = document.getElementById('confirm-otp');
	const paymentSuccess = document.getElementById('payment-success');
	const studentMappingNote = document.getElementById('student-mapping-note');

	let accounts = [];
	let selectedAccountNumber = '';
	let selectedTuition = null;
	let currentUser = null;
	let pendingPayment = readPendingPayment();

	searchForm.addEventListener('submit', searchTuition);
	document.querySelectorAll('input[name="payment-target"]').forEach(choice => {
		choice.addEventListener('change', () => {
			studentMappingNote.classList.toggle('hidden', choice.value !== 'self' || !choice.checked);
		});
	});
	confirmDetails.addEventListener('change', updatePaymentState);
	createPaymentButton.addEventListener('click', createPayment);
	resendOtpButton.addEventListener('click', requestOtp);
	otpForm.addEventListener('submit', confirmPayment);

	if (pendingPayment) showOtpStep('A payment is waiting for OTP verification.');
	await loadPayerAndAccounts();

	async function loadPayerAndAccounts() {
		try {
			currentUser = await window.IBanking.apiRequest('/api/v1/users/me');
			renderPayer(currentUser);
		} catch (error) {
			showServiceMessage(userMessage, error.message);
			payerInformation.textContent = 'Payer information is unavailable.';
		}

		try {
			accounts = await window.IBanking.apiRequest('/api/v1/accounts/me');
			renderAccounts(accounts);
		} catch (error) {
			showServiceMessage(userMessage, error.message);
			accountLoading.textContent = 'Payment accounts are unavailable.';
		}
		updatePaymentState();
	}

	function renderPayer(user) {
		payerInformation.replaceChildren();
		for (const [label, value] of [
			['Full Name', user.fullName],
			['Username', user.username],
			['Phone Number', user.phone],
			['Email Address', user.email]
		]) {
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
		if (!accountList.length) {
			accountMessage.textContent = 'No payment accounts are available.';
			return;
		}
		if (!accountList.some(account => account.status === 'ACTIVE')) {
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
		if (pendingPayment) lockPaymentForm();
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
			const tuition = await window.IBanking.tuitionRequest(`/api/v1/tuition/${encodeURIComponent(studentId)}`);
			if (!tuition || !tuition.student_id || !tuition.student_name || tuition.amount == null || !tuition.status) {
				throw new Error('Tuition Service returned an invalid response.');
			}
			selectedTuition = tuition;
			renderTuition(tuition);
		} catch (error) {
			lookupMessage.textContent = error.status === 404 ? 'Student tuition record not found.' : error.message;
		} finally {
			searchButton.disabled = false;
			searchButton.textContent = 'Search';
		}
	}

	function renderTuition(tuition) {
		document.getElementById('result-student-id').textContent = tuition.student_id;
		document.getElementById('result-student-name').textContent = tuition.student_name;
		document.getElementById('result-tuition-amount').textContent = formatCurrency(tuition.amount);
		const currentStatus = String(tuition.status).toUpperCase();
		const statusElement = document.getElementById('result-tuition-status');
		statusElement.textContent = currentStatus;
		statusElement.className = `tuition-status ${currentStatus === 'PAID' ? 'paid' : currentStatus === 'UNPAID' ? '' : 'unknown'}`;
		tuitionResult.classList.remove('hidden');
		if (currentStatus === 'PAID') {
			lookupMessage.textContent = 'This tuition has already been paid.';
			return;
		}
		if (currentStatus !== 'UNPAID') {
			lookupMessage.textContent = 'This tuition record has an unsupported payment status.';
			return;
		}
		document.getElementById('selected-tuition-amount').textContent = formatCurrency(tuition.amount);
		paymentSection.classList.remove('hidden');
		updatePaymentState();
	}

	function updatePaymentState() {
		const account = accounts.find(item => item.accountNumber === selectedAccountNumber);
		const selectedBalance = account && account.status === 'ACTIVE' ? account.balance : null;
		const tuitionAmount = selectedTuition && selectedTuition.status === 'UNPAID' ? selectedTuition.amount : null;
		document.getElementById('selected-account-balance').textContent = selectedBalance === null ? '-' : formatCurrency(selectedBalance);
		balanceMessage.textContent = '';
		if (tuitionAmount !== null) {
			if (!account || account.status !== 'ACTIVE') balanceMessage.textContent = 'Select an active payment account.';
			else if (!hasEnoughBalance(selectedBalance, tuitionAmount)) balanceMessage.textContent = 'Insufficient balance.';
		}
		createPaymentButton.disabled = !isPaymentReady();
	}

	function isPaymentReady() {
		const account = accounts.find(item => item.accountNumber === selectedAccountNumber);
		return Boolean(
			currentUser && selectedTuition && selectedTuition.status === 'UNPAID' &&
			account && account.status === 'ACTIVE' && hasEnoughBalance(account.balance, selectedTuition.amount) &&
			confirmDetails.checked && !pendingPayment
		);
	}

	async function createPayment() {
		if (!isPaymentReady()) return;
		const account = accounts.find(item => item.accountNumber === selectedAccountNumber);
		createPaymentButton.disabled = true;
		createPaymentButton.textContent = 'Creating payment...';
		actionMessage.textContent = '';
		try {
			const created = await window.IBanking.paymentRequest('/api/v1/payments', {
				method: 'POST',
				body: JSON.stringify({
					student_id: selectedTuition.student_id,
					account_number: account.accountNumber
				})
			});
			pendingPayment = {
				transactionId: created.transaction_id,
				studentId: selectedTuition.student_id,
				studentName: selectedTuition.student_name,
				amount: created.amount,
				accountNumber: account.accountNumber
			};
			storePendingPayment();
			lockPaymentForm();
			showOtpStep();
			await requestOtp();
		} catch (error) {
			actionMessage.textContent = error.message;
		} finally {
			createPaymentButton.textContent = 'Continue to OTP';
			updatePaymentState();
		}
	}

	async function requestOtp() {
		if (!pendingPayment) return;
		resendOtpButton.disabled = true;
		otpError.textContent = '';
		try {
			await window.IBanking.paymentRequest(`/api/v1/payments/${encodeURIComponent(pendingPayment.transactionId)}/otp`, { method: 'POST' });
			otpDeliveryMessage.textContent = 'OTP has been sent to your email.';
		} catch (error) {
			otpError.textContent = error.message;
		} finally {
			resendOtpButton.disabled = false;
		}
	}

	async function confirmPayment(event) {
		event.preventDefault();
		if (!pendingPayment || !/^\d{6}$/.test(otpInput.value)) {
			otpError.textContent = 'Enter the six-digit OTP from your email.';
			return;
		}
		confirmOtpButton.disabled = true;
		otpError.textContent = '';
		try {
			const result = await window.IBanking.paymentRequest('/api/v1/payments/confirm', {
				method: 'POST',
				body: JSON.stringify({ transactionId: pendingPayment.transactionId, otpCode: otpInput.value })
			});
			renderSuccess(result);
			sessionStorage.removeItem(window.IBanking.PENDING_TRANSACTION_KEY);
		sessionStorage.removeItem(window.IBanking.PENDING_CONTEXT_KEY);
			pendingPayment = null;
		} catch (error) {
			otpError.textContent = error.message;
			otpInput.select();
		} finally {
			confirmOtpButton.disabled = false;
		}
	}

	function renderSuccess(result) {
		const completed = result.completed_at ? new Date(result.completed_at) : null;
		document.getElementById('success-transaction-id').textContent = result.transaction_id || pendingPayment.transactionId;
		document.getElementById('success-student').textContent = `${result.student_name || pendingPayment.studentName} (${result.student_id || pendingPayment.studentId})`;
		document.getElementById('success-amount').textContent = formatCurrency(result.amount);
		document.getElementById('success-account').textContent = pendingPayment.accountNumber;
		document.getElementById('success-status').textContent = result.status;
		document.getElementById('success-completed-at').textContent = completed && !Number.isNaN(completed.getTime()) ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(completed) : '-';
		otpSection.classList.add('hidden');
		paymentSuccess.classList.remove('hidden');
		if (selectedTuition) {
			selectedTuition.status = 'PAID';
			const tuitionStatus = document.getElementById('result-tuition-status');
			tuitionStatus.textContent = 'PAID';
			tuitionStatus.className = 'tuition-status paid';
		}
	}

	function showOtpStep(message) {
		otpSection.classList.remove('hidden');
		if (message) otpDeliveryMessage.textContent = message;
		lockPaymentForm();
	}

	function lockPaymentForm() {
		studentIdInput.disabled = Boolean(pendingPayment);
		searchButton.disabled = Boolean(pendingPayment);
		confirmDetails.disabled = Boolean(pendingPayment);
		document.querySelectorAll('input[name="payment-account"]').forEach(input => input.disabled = true);
		createPaymentButton.disabled = true;
	}

	function storePendingPayment() {
		sessionStorage.setItem(window.IBanking.PENDING_TRANSACTION_KEY, pendingPayment.transactionId);
		sessionStorage.setItem(window.IBanking.PENDING_CONTEXT_KEY, JSON.stringify(pendingPayment));
	}

	function readPendingPayment() {
		try {
			const context = JSON.parse(sessionStorage.getItem(window.IBanking.PENDING_CONTEXT_KEY) || 'null');
			if (context && context.transactionId === sessionStorage.getItem(window.IBanking.PENDING_TRANSACTION_KEY)) return context;
		} catch (_error) {
			sessionStorage.removeItem(window.IBanking.PENDING_TRANSACTION_KEY);
			sessionStorage.removeItem(window.IBanking.PENDING_CONTEXT_KEY);
		}
		return null;
	}

	function showServiceMessage(element, message) {
		element.textContent = message;
		element.classList.remove('hidden');
	}

	function hasEnoughBalance(balance, amount) {
		const balanceMinor = toMinorUnits(balance);
		const amountMinor = toMinorUnits(amount);
		return balanceMinor !== null && amountMinor !== null && balanceMinor >= amountMinor;
	}

	function toMinorUnits(value) {
		const match = String(value).trim().match(/^(\d+)(?:\.(\d{1,2}))?$/);
		if (!match) return null;
		return BigInt(match[1]) * 100n + BigInt((match[2] || '').padEnd(2, '0'));
	}

	function formatCurrency(amount) {
		return new Intl.NumberFormat('vi-VN', {
			style: 'currency',
			currency: 'VND',
			maximumFractionDigits: 2
		}).format(Number(amount));
	}
});
