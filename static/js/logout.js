document.addEventListener('DOMContentLoaded', () => {
    /**
     * Handles the secure logout process via a JavaScript fetch request.
     */
    const handleLogout = () => {
        // 1. Get the CSRF token from the hidden div.
        const csrfContainer = document.getElementById('csrf-token-container-logout');
        if (!csrfContainer) {
            console.error('CSRF token container not found. Logout will fail.');
            return;
        }
        const csrfToken = csrfContainer.dataset.csrf;

        // Immediately remove the temporary div from the DOM.
        csrfContainer.remove();

        // 2. Perform the fetch request to the logout URL.
        fetch('/logout/', { // Your actual logout URL
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
            },
            redirect: 'manual'
        })
        .then(response => {
            window.location.href = '/';
        })
        .catch(error => {
            console.error('Error during logout:', error);
            alert('Logout failed. Please try again.');
        });
    };

    // --- Attach the event listener to BOTH logout buttons ---
    const logoutButtonDesktop = document.getElementById('logout-button-desktop');
    if (logoutButtonDesktop) {
        logoutButtonDesktop.addEventListener('click', handleLogout);
    }

    const logoutButtonMobile = document.getElementById('logout-button-mobile');
    if (logoutButtonMobile) {
        logoutButtonMobile.addEventListener('click', handleLogout);
    }

});