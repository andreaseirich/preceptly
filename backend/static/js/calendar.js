document.addEventListener("DOMContentLoaded", () => {
    const dialog = document.getElementById("create-dialog");
    const overlay = document.getElementById("dialog-overlay");
    const timeInfo = document.getElementById("dialog-time-info");
    const eventTypeInput = document.querySelector('input[name="event-type"]:checked');
    const confirmBtn = document.querySelector(".js-confirm-create");
    const cancelBtn = document.querySelector(".js-cancel-create");

    const formatTime = (date) =>
        date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

    const formatDate = (date) => date.toLocaleDateString("en-US");

    const openCreateFromSlot = (cell) => {
        const date = cell.dataset.date;
        const hour = parseInt(cell.dataset.hour, 10);
        const startDateTime = new Date(`${date}T${String(hour).padStart(2, "0")}:00:00`);
        const endDateTime = new Date(`${date}T${String(hour + 1).padStart(2, "0")}:00:00`);
        showCreateDialog(startDateTime, endDateTime, date);
    };

    const showCreateDialog = (startDateTime, endDateTime, date) => {
        if (!dialog || !overlay || !timeInfo) return;

        const startStr = startDateTime.toISOString().slice(0, 16);
        const endStr = endDateTime.toISOString().slice(0, 16);

        timeInfo.textContent = `From: ${formatTime(startDateTime)} to ${formatTime(
            endDateTime
        )} on ${formatDate(new Date(date))}`;

        dialog.dataset.start = startStr;
        dialog.dataset.end = endStr;
        dialog.dataset.date = date;

        dialog.style.display = "block";
        overlay.style.display = "block";
    };

    const cancelCreate = () => {
        if (!dialog || !overlay) return;
        dialog.style.display = "none";
        overlay.style.display = "none";
    };

    const confirmCreate = () => {
        if (!dialog) return;
        const selectedType =
            (document.querySelector('input[name="event-type"]:checked') || eventTypeInput)?.value ||
            "lesson";
        const start = dialog.dataset.start;
        const end = dialog.dataset.end;

        let url;
        if (selectedType === "lesson") {
            url = dialog.dataset.lessonCreateUrl;
        } else {
            url = dialog.dataset.blockedCreateUrl;
        }
        const target = `${url}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
        window.location.href = target;
    };

    // Event delegation for time slots
    document.querySelectorAll(".time-slot").forEach((slot) => {
        slot.addEventListener("click", () => openCreateFromSlot(slot));
    });

    if (confirmBtn) confirmBtn.addEventListener("click", confirmCreate);
    if (cancelBtn) cancelBtn.addEventListener("click", cancelCreate);
    if (overlay) overlay.addEventListener("click", cancelCreate);

    // Prevent bubble on marked elements
    document.body.addEventListener("click", (event) => {
        if (event.target.closest(".js-stop-propagation")) {
            event.stopPropagation();
        }
    });

    // Lesson block interactions
    const lessonBlocks = document.querySelectorAll(".lesson-block");
    let previewTooltip = null;

    const buildLessonPreview = (element) => {
        const student = element.dataset.student || "";
        const timeInfo = element.dataset.time || "";
        const hasConflict = element.dataset.hasConflict === "true";
        return `
            <strong>${student}</strong><br>
            <small>${timeInfo}</small>
            ${hasConflict ? "<br><small style='color: #ffeb3b;'>⚠️ Conflict</small>" : ""}
        `;
    };

    const buildBlockedPreview = (element) => {
        const title = element.dataset.title || "";
        const timeInfo = element.dataset.time || "";
        return `
            <strong>${title}</strong><br>
            <small>${timeInfo}</small>
        `;
    };

    const showPreview = (element, content) => {
        if (previewTooltip) return;
        previewTooltip = document.createElement("div");
        previewTooltip.className = "lesson-preview";
        previewTooltip.innerHTML = content;
        document.body.appendChild(previewTooltip);
        const rect = element.getBoundingClientRect();
        previewTooltip.style.left = `${rect.left + rect.width / 2 - previewTooltip.offsetWidth / 2}px`;
        previewTooltip.style.top = `${rect.top - previewTooltip.offsetHeight - 8}px`;
    };

    const hidePreview = () => {
        if (previewTooltip) {
            previewTooltip.remove();
            previewTooltip = null;
        }
    };

    lessonBlocks.forEach((block) => {
        block.addEventListener("mouseenter", () => {
            block.style.transform = "scale(1.02)";
            block.style.zIndex = "20";
            const content = buildLessonPreview(block);
            showPreview(block, content);
        });
        block.addEventListener("mouseleave", () => {
            block.style.transform = "scale(1)";
            block.style.zIndex = "10";
            hidePreview();
        });
        block.addEventListener("click", (event) => {
            const planUrl = block.dataset.planUrl;
            if (planUrl) {
                window.location.href = planUrl;
                event.stopPropagation();
            }
        });
    });

    // Position lesson blocks (top/height based on data)
    lessonBlocks.forEach((block) => {
        const startMinute = parseInt(block.dataset.startMinute || "0", 10);
        const duration = parseInt(block.dataset.duration || "60", 10);
        block.style.top = `${startMinute}px`;
        block.style.height = `${duration}px`;
    });

    // Blocked time interactions
    document.querySelectorAll(".blocked-time-block").forEach((block) => {
        const startMinute = parseInt(block.dataset.startMinute || "0", 10);
        const endMinute = parseInt(block.dataset.endMinute || "60", 10);
        const height = Math.max(10, (endMinute > startMinute ? endMinute - startMinute : 60));
        block.style.top = `${startMinute}px`;
        block.style.height = `${height}px`;
        block.addEventListener("mouseenter", () => {
            block.style.transform = "scale(1.02)";
            block.style.zIndex = "20";
            const content = buildBlockedPreview(block);
            showPreview(block, content);
        });
        block.addEventListener("mouseleave", () => {
            block.style.transform = "scale(1)";
            block.style.zIndex = "10";
            hidePreview();
        });
        block.addEventListener("click", (event) => {
            const editUrl = block.dataset.editUrl;
            if (editUrl) {
                window.location.href = editUrl;
                event.stopPropagation();
            }
        });
    });
});

