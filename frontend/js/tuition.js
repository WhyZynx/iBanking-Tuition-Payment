const USER_API = "http://localhost:8001/api/v1/users/me";
const ACCOUNT_API = "http://localhost:8001/api/v1/accounts/me";
const TUITION_API = "http://localhost:8002/api/v1/tuition";

const payerName = document.getElementById("payerName");
const payerPhone = document.getElementById("payerPhone");
const payerEmail = document.getElementById("payerEmail");
const headerUserName = document.getElementById("headerUserName");
const avatar = document.getElementById("avatar");

const studentIdInput = document.getElementById("studentId");
const searchButton = document.getElementById("searchButton");

const pageMessage = document.getElementById("pageMessage");
const tuitionMessage = document.getElementById("tuitionMessage");
const balanceMessage = document.getElementById("balanceMessage");

const tuitionResult = document.getElementById("tuitionResult");
const paymentSection = document.getElementById("paymentSection");

const resultStudentId = document.getElementById("resultStudentId");
const resultStudentName = document.getElementById("resultStudentName");
const resultTuitionFee = document.getElementById("resultTuitionFee");
const statusBadge = document.getElementById("statusBadge");

const availableBalance = document.getElementById("availableBalance");
const paymentAmount = document.getElementById("paymentAmount");

const termsCheckbox = document.getElementById("termsCheckbox");
const confirmButton = document.getElementById("confirmButton");

let selectedTuition = null;
let currentUser = null;
let currentAccount = null;
let currentBalance = null;

document.addEventListener("DOMContentLoaded", loadPayerInformation);

searchButton.addEventListener("click", searchTuition);

studentIdInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
        searchTuition();
    }
});

termsCheckbox.addEventListener("change", updateConfirmButton);
confirmButton.addEventListener("click", confirmTransaction);

async function loadPayerInformation() {
    const token =
        localStorage.getItem("access_token") ||
        localStorage.getItem("token");

    if (!token) {
        pageMessage.textContent =
            "Account information will be loaded automatically after login integration.";
        pageMessage.style.display = "block";
        return;
    }

    try {
        const headers = {
            Authorization: `Bearer ${token}`
        };

        const [userResponse, accountResponse] = await Promise.all([
            fetch(USER_API, { headers }),
            fetch(ACCOUNT_API, { headers })
        ]);

        if (!userResponse.ok || !accountResponse.ok) {
            pageMessage.textContent =
                "Unable to load the logged-in user's information.";
            pageMessage.style.display = "block";
            return;
        }

        const user = await userResponse.json();
        const accountData = await accountResponse.json();

        currentUser = user;
        currentAccount = getDefaultAccount(accountData);

        payerName.value = user.full_name || "";
        payerPhone.value = user.phone || "";
        payerEmail.value = user.email || "";

        headerUserName.textContent =
            user.full_name || "User";

        avatar.textContent =
            getInitial(user.full_name);

        if (currentAccount) {
            currentBalance = Number(currentAccount.balance);

            availableBalance.textContent =
                formatCurrency(currentBalance);
        }

        pageMessage.style.display = "none";
        validateBalance();
        updateConfirmButton();
    } catch (error) {
        pageMessage.textContent =
            "Unable to connect to the User and Account Service.";
        pageMessage.style.display = "block";
    }
}

async function searchTuition() {
    const studentId =
        studentIdInput.value.trim().toUpperCase();

    resetTuitionResult();

    if (!studentId) {
        showTuitionError("Please enter a student ID.");
        return;
    }

    setSearchLoading(true);

    try {
        const response = await fetch(
            `${TUITION_API}/${encodeURIComponent(studentId)}`
        );

        if (response.status === 404) {
            showTuitionError(
                "Student tuition information was not found."
            );
            return;
        }

        if (!response.ok) {
            showTuitionError(
                "Unable to retrieve tuition information."
            );
            return;
        }

        const tuition = await response.json();

        selectedTuition = tuition;

        displayTuition(tuition);
    } catch (error) {
        showTuitionError(
            "Cannot connect to the Tuition Service."
        );
    } finally {
        setSearchLoading(false);
    }
}

function displayTuition(tuition) {
    resultStudentId.textContent =
        tuition.student_id;

    resultStudentName.textContent =
        tuition.student_name;

    resultTuitionFee.textContent =
        formatCurrency(tuition.amount);

    statusBadge.textContent =
        tuition.status;

    tuitionResult.classList.remove("hidden");

    if (tuition.status === "PAID") {
        statusBadge.className =
            "status status-paid";

        paymentSection.classList.add("hidden");

        showTuitionError(
            "This tuition fee has already been paid."
        );

        return;
    }

    statusBadge.className =
        "status status-unpaid";

    paymentAmount.textContent =
        formatCurrency(tuition.amount);

    paymentSection.classList.remove("hidden");

    validateBalance();
    updateConfirmButton();
}

function validateBalance() {
    hideBalanceError();

    if (!selectedTuition) {
        return false;
    }

    if (currentBalance === null) {
        availableBalance.textContent = "—";

        showBalanceError(
            "Available balance will be loaded from the logged-in account."
        );

        return false;
    }

    if (currentBalance < Number(selectedTuition.amount)) {
        showBalanceError(
            "Insufficient available balance for this tuition payment."
        );

        return false;
    }

    return true;
}

function updateConfirmButton() {
    const tuitionValid =
        selectedTuition !== null &&
        selectedTuition.status === "UNPAID";

    const balanceValid =
        selectedTuition !== null &&
        currentBalance !== null &&
        currentBalance >= Number(selectedTuition.amount);

    confirmButton.disabled =
        !tuitionValid ||
        !balanceValid ||
        !termsCheckbox.checked;
}

function confirmTransaction() {
    if (confirmButton.disabled) {
        return;
    }

    const paymentData = {
        payer: {
            full_name: currentUser.full_name,
            phone: currentUser.phone,
            email: currentUser.email
        },
        account: {
            account_number: currentAccount.account_number,
            balance: currentBalance
        },
        tuition: {
            student_id: selectedTuition.student_id,
            student_name: selectedTuition.student_name,
            amount: Number(selectedTuition.amount)
        }
    };

    sessionStorage.setItem(
        "tuitionPayment",
        JSON.stringify(paymentData)
    );
}

function resetTuitionResult() {
    selectedTuition = null;

    tuitionResult.classList.add("hidden");
    paymentSection.classList.add("hidden");

    tuitionMessage.style.display = "none";
    balanceMessage.style.display = "none";

    termsCheckbox.checked = false;
    confirmButton.disabled = true;

    resultStudentId.textContent = "";
    resultStudentName.textContent = "";
    resultTuitionFee.textContent = "";
    statusBadge.textContent = "";
    paymentAmount.textContent = "—";
}

function showTuitionError(message) {
    tuitionMessage.textContent = message;
    tuitionMessage.style.display = "block";
}

function showBalanceError(message) {
    balanceMessage.textContent = message;
    balanceMessage.style.display = "block";
}

function hideBalanceError() {
    balanceMessage.textContent = "";
    balanceMessage.style.display = "none";
}

function setSearchLoading(loading) {
    searchButton.disabled = loading;

    searchButton.textContent =
        loading ? "Searching..." : "Search";
}

function getDefaultAccount(accountData) {
    if (Array.isArray(accountData)) {
        return (
            accountData.find(
                account => account.is_default === true
            ) ||
            accountData[0] ||
            null
        );
    }

    if (
        accountData &&
        Array.isArray(accountData.accounts)
    ) {
        return (
            accountData.accounts.find(
                account => account.is_default === true
            ) ||
            accountData.accounts[0] ||
            null
        );
    }

    if (
        accountData &&
        accountData.balance !== undefined
    ) {
        return accountData;
    }

    return null;
}

function getInitial(fullName) {
    if (!fullName) {
        return "U";
    }

    const parts =
        fullName.trim().split(/\s+/);

    return parts[parts.length - 1]
        .charAt(0)
        .toUpperCase();
}

function formatCurrency(amount) {
    return new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND"
    }).format(Number(amount));
}