function showTrackBribeForm() {
    document.getElementById('trackBribeBanner').style.display = 'flex';
    const form = document.getElementById('trackBribeForm');
    form.reset();
    const trackMessageDiv = document.getElementById('trackMessage');
    trackMessageDiv.innerHTML = '';
}

function hideTrackBribeForm() {
    document.getElementById('trackBribeBanner').style.display = 'none';
}

function handleTrackBribeSubmit(event) {
    event.preventDefault(); 

    const form = event.target;
    const formData = new FormData(form);
    
    const trackMessageDiv = document.getElementById('trackMessage');
    trackMessageDiv.innerHTML = ''; 
    trackMessageDiv.style.color = ''; 

    const trackBribeForm = document.getElementById('trackBribeForm');

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
        setTimeout(() => {
            trackMessageDiv.innerHTML = '';
            trackMessageDiv.style.color = '';
        }, 1500);
        return; 
    }

    fetch('/track_bribe', {
        method: 'POST',
        body: formData,
    })
    .then(response => {
        
        if (response.ok) {
            return response.text(); 
        } else{
            return response.text().then(text => {
                //throw an error from JSON
                const errorData = JSON.parse(text);
                throw new Error(errorData.error || `Server error: ${response.status}`);
            })
        }
    })
    .then(html => {
        document.body.innerHTML = html;
    })
    
    .catch(error => {
        trackMessageDiv.innerHTML = `<p style="color: red; text-align:center;">Error: ${error.message}</p>`;
        trackMessageDiv.style.color = 'red';
        if (trackBribeForm) { 
            trackBribeForm.reset();
        }
        setTimeout(() => {
            trackMessageDiv.innerHTML = '';
            trackMessageDiv.style.color = '';
        }, 2000);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('trackBribeBanner').style.display = 'none'; 
});
