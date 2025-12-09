document.addEventListener("DOMContentLoaded", () => {
    const recurrenceFields = document.getElementById("recurrence-fields");
    const weekdaysContainer = document.getElementById("weekdays-container");
    const isRecurring = document.getElementById("id_is_recurring");

    const toggleRecurrenceFields = () => {
        if (!recurrenceFields || !isRecurring) return;
        if (isRecurring.checked) {
            recurrenceFields.classList.add("active");
            if (weekdaysContainer) {
                weekdaysContainer.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
                    checkbox.disabled = false;
                });
            }
        } else {
            recurrenceFields.classList.remove("active");
        }
    };

    if (isRecurring) {
        isRecurring.addEventListener("change", toggleRecurrenceFields);
    }

    toggleRecurrenceFields();
});
