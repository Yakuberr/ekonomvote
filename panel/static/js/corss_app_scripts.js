// Inicjalizacja elementów po załadowaniu DOM
document.addEventListener('DOMContentLoaded', function () {
    // Kod związany z tooltipami i popoverami bootstrap
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    popoverTriggerList.forEach(el => new bootstrap.Popover(el));

    // Kod związany z modalem ostrzegawczym
    const modalEl = document.getElementById('warningModal')
    if (modalEl) {
        const warningModal = new bootstrap.Modal(document.getElementById('warningModal'))
        if (modalEl.getAttribute('htmx') !== null) {
            const modalForm = modalEl.querySelector('form')
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('button[btn-type="delete"]')
                if (btn) {
                    const modalIdFieldName = document.getElementById('modalIdFieldName')
                    if (modalEl && modalIdFieldName) {
                        warningModal.show()
                        modalIdFieldName.value = Number(btn.getAttribute('btn-data'))
                        modalForm.setAttribute('hx-target', `#tableRow${btn.getAttribute('btn-row')}`)
                    }
                }
            })
        } else {
            const modalIdFieldName = document.getElementById('modalIdFieldName')
            document.querySelectorAll('button[btn-type="delete"]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    warningModal.show()
                    modalIdFieldName.value = Number(e.currentTarget.getAttribute('btn-data'))
                })
            })
        }
        document.body.addEventListener('htmx:afterRequest', function (event) {
            if (warningModal) {
                warningModal.hide();
            }
        });
    }

});
