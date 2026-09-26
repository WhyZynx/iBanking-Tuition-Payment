const TUITION_API_URL = "http://localhost:8002/api/v1/tuition";

const searchForm = document.getElementById("tuition-search-form");
const studentIdInput = document.getElementById("student-id");
const searchButton = document.getElementById("search-button");

const serviceMessage = document.getElementById("tuition-service-message");
const lookupMessage = document.getElementById("tuition-lookup-message");

const tuitionResult = document.getElementById("tuition-result");
const resultStudentId = document.getElementById("result-student-id");
const resultStudentName = document.getElementById("result-student-name");
const resultTuitionAmount = document.getElementById("result-tuition-amount");
const resultTuitionStatus = document.getElementById("result-tuition-status");

const paymentSection = document.getElementById("payment-section");
const selectedTuitionAmount = document.getElementById("selected-tuition-amount");
const paymentStatusMessage = document.getElementById("payment-status-message");

function formatMoney(value) {
    return new Intl.NumberFormat("vi-VN", {
        style: "currency",
        currency: "VND"
    }).format(Number(value));
}

function resetResult() {
    tuitionResult.classList.add("hidden");
    paymentSection.classList.add("hidden");

    resultStudentId.textContent = "-";
    resultStudentName.textContent = "-";
    resultTuitionAmount.textContent = "-";
    resultTuitionStatus.textContent = "-";

    resultTuitionStatus.className = "tuition-status unknown";

    selectedTuitionAmount.textContent = "-";
    lookupMessage.textContent = "";
    paymentStatusMessage.textContent = "";
}

function showServiceError(message) {
    serviceMessage.textContent = message;
    serviceMessage.classList.remove("hidden");
}

function hideServiceError() {
    serviceMessage.textContent = "";
    serviceMessage.classList.add("hidden");
}

function displayTuition(tuition) {
    resultStudentId.textContent = tuition.student_id;
    resultStudentName.textContent = tuition.student_name;
    resultTuitionAmount.textContent = formatMoney(tuition.amount);
    resultTuitionStatus.textContent = tuition.status;

    resultTuitionStatus.className = "tuition-status";

    if (tuition.status === "PAID") {
        resultTuitionStatus.classList.add("paid");
    }

    tuitionResult.classList.remove("hidden");
    paymentSection.classList.remove("hidden");

    selectedTuitionAmount.textContent = formatMoney(tuition.amount);

    if (tuition.status === "PAID") {
        paymentStatusMessage.textContent =
            "This tuition bill has already been paid.";
    } else {
        paymentStatusMessage.textContent =
            "Payment Service is not connected in this standalone Tuition Service test.";
    }
}

async function searchTuition(studentId) {
    hideServiceError();
    resetResult();

    searchButton.disabled = true;
    searchButton.textContent = "Searching...";

    try {
        const response = await fetch(
            `${TUITION_API_URL}/${encodeURIComponent(studentId)}`
        );

        if (!response.ok) {
            let message = "Unable to retrieve tuition information.";

            try {
                const error = await response.json();

                if (error.detail) {
                    message = error.detail;
                }
            } catch {
            }

            if (response.status === 404) {
                lookupMessage.textContent = message;
                return;
            }

            throw new Error(message);
        }

        const tuition = await response.json();

        displayTuition(tuition);
    } catch (error) {
        showServiceError(
            error.message ||
            "Unable to connect to Tuition Service."
        );
    } finally {
        searchButton.disabled = false;
        searchButton.textContent = "Search";
    }
}

searchForm.addEventListener("submit", function (event) {
    event.preventDefault();

    const studentId = studentIdInput.value.trim().toUpperCase();

    if (!studentId) {
        resetResult();
        lookupMessage.textContent = "Student ID is required.";
        return;
    }

    studentIdInput.value = studentId;

    searchTuition(studentId);
});