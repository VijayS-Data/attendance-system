document.addEventListener("DOMContentLoaded", () => {

    document.querySelectorAll("form").forEach(form => {

        const fields = Array.from(
            form.querySelectorAll("input, select, textarea")
        ).filter(el =>
            el.type !== "submit" &&
            el.type !== "button" &&
            !el.disabled
        );

        fields.forEach((field, index) => {
            field.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();

                    // Move to next field if exists
                    if (fields[index + 1]) {
                        fields[index + 1].focus();
                    }
                }
            });
        });
    });

});
