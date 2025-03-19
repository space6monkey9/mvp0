function showTrackBribeForm() {
    document.getElementById('trackBribeBanner').style.display = 'block';
}

function hideTrackBribeForm() {
    document.getElementById('trackBribeBanner').style.display = 'none';
}

function handleTrackBribeSubmit(event) {
    event.preventDefault(); // Prevent default form submission

    const form = event.target;
    const formData = new FormData(form);
    
    const trackMessageDiv = document.getElementById('trackMessage');
    trackMessageDiv.innerHTML = ''; // Clear previous messages
    trackMessageDiv.style.color = ''; // Reset text color

    const trackBribeForm = document.getElementById('trackBribeForm');

    // Check if all form fields are empty
    let isEmpty = true;
    for (let pair of formData.entries()) {
        if (pair[1].trim() !== '') {
            isEmpty = false;
            break;
        }
    }

    if (isEmpty) {
        trackMessageDiv.innerHTML = '<p style="color: red; text-align:center">Please fill in the form before submitting.</p>';
        trackMessageDiv.style.color = 'red';
        return; // Stop form submission
    }

    fetch('/track_bribe', {
        method: 'POST',
        body: formData,
    })
        .then(response => {
            if (response.redirected) {
                window.location.href = response.url; // Redirect to track_report page
            } else {
                // Handle error responses (non-redirect and not ok)
                return response.json().catch(() => response.text()); // Try to parse JSON, if not, get text
            }
        })
        .then(data => {
            // 'data' will be HTML text on success, or JSON/text error message
            if (typeof data === 'string') {
                // It's HTML or a text error message
                trackMessageDiv.innerHTML = data; // Display HTML or text error
                trackMessageDiv.style.color = data.includes('error') ? 'red' : ''; // Color red if it seems like an error message
            } else if (typeof data === 'object' && data.error) { // Changed 'else' to 'else if' to correctly handle the condition
                // It's a JSON error response
                trackMessageDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`; // Display JSON error message in red
            }
            trackBribeForm.reset();
        })
        .catch(error => {
            console.error('Network error:', error);
            trackMessageDiv.innerHTML = '<p style="color: red;">Network error. Please try again.</p>';
            trackMessageDiv.style.color = 'red'; // Indicate network error
            trackBribeForm.reset();
        });
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('trackBribeBanner').style.display = 'none'; // Initially hide the banner
});