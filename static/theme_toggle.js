function initThemeToggle() {
    const themeToggleButton = document.getElementById('theme-toggle-button');
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
            let theme = 'light';
            if (document.body.classList.contains('dark-mode')) {
                theme = 'dark';
                themeToggleButton.textContent = 'Light Mode';
            } else {
                theme = 'light';
                themeToggleButton.textContent = 'Dark Mode';
            }
            localStorage.setItem('theme', theme);
        });
        // Set initial state
        const currentTheme = localStorage.getItem('theme');
        if (currentTheme === 'dark') {
            document.body.classList.add('dark-mode');
            themeToggleButton.textContent = 'Light Mode';
        } else {
            themeToggleButton.textContent = 'Dark Mode';
        }
    }
}

// On initial load
document.addEventListener('DOMContentLoaded', initThemeToggle);