document.addEventListener("DOMContentLoaded", () => {
    const languageForm = document.querySelector(".language-form");
    const languageSelect = document.querySelector(".language-select");
    if (languageForm && languageSelect) {
        languageSelect.addEventListener("change", () => languageForm.submit());
    }
});

