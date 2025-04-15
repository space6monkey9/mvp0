function showUsernameForm() {
    document.getElementById('usernameBanner').style.display = 'block';
    const form = document.getElementById('usernameForm');
    form.reset();

    const availabilityStatusEl = document.getElementById('usernameAvailabilityStatus');
    const addTextEl = document.getElementById('addText');
    const suggestionsEl = document.getElementById('usernameSuggestions');
    const messageEl = document.querySelector('#usernameBanner .modal-content #message'); 

    if (availabilityStatusEl) availabilityStatusEl.textContent = '';
    if (addTextEl) addTextEl.textContent = '';
    if (suggestionsEl) suggestionsEl.innerHTML = ''; 
    if (messageEl) messageEl.innerHTML = ''; 

    const refreshButton = document.getElementById('refreshSuggestions');
    if (refreshButton) refreshButton.style.display = 'none'; 
}

function hideUsernameForm() {
    document.getElementById('usernameBanner').style.display = 'none';
    document.querySelector('#usernameBanner .modal-content #message').innerHTML = '';
}

function showSigninForm(title = "Sign-in to Report", reportingId = null) {
    const banner = document.getElementById('signinBanner');
    if (banner) {
        const heading = banner.querySelector('h2');
        if (heading) {
            heading.textContent = title;
        }
        banner.style.display = 'block';
    }
    const form = document.getElementById('signinForm');
    form.reset();

    // Set reportingId if provided
    const reportingIdInput = document.getElementById('signinReportingId');
    if (reportingIdInput) {
        reportingIdInput.value = reportingId || '';
    }
}

function hideSigninForm() {
    document.getElementById('signinBanner').style.display = 'none';
    document.querySelector('#signinBanner .modal-content #message').innerHTML = '';
}

let debounceTimer;
const DEBOUNCE_DELAY = 500; // milliseconds

// Function to check username availability via backend
async function checkUsernameAvailability(username) {
    const availabilityStatusEl = document.getElementById('usernameAvailabilityStatus');
    if (!username || username.length < 3 || !/^(?!\d+$)(?!\d)[a-zA-Z0-9]+$/.test(username)) {
        availabilityStatusEl.textContent = ''; 
        return false; 
    }

    try {
        const response = await fetch('/check_username', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const result = await response.json();
        if (response.ok) {
            availabilityStatusEl.textContent = result.available ? '✅ Available' : '❌ Taken';
            availabilityStatusEl.style.color = result.available ? 'green' : 'red';
            return result.available;
        } else {
            availabilityStatusEl.textContent = '⚠️ Error checking';
            availabilityStatusEl.style.color = 'orange';
            return false;
        }
    } catch (error) {
        availabilityStatusEl.textContent = '⚠️ Network Error';
        availabilityStatusEl.style.color = 'orange';
        return false;
    }
}


function generateSuggestions(username) {
    const suggestionsEl = document.getElementById('usernameSuggestions');
    suggestionsEl.innerHTML = ''; 

    if (!username || !/^(?!\d+$)(?!\d)[a-zA-Z0-9]+$/.test(username)) {
        return; 
    }

    const suggestions = [];
    
    suggestions.push(`${username}${Math.floor(Math.random() * 100)}`);
    if (username.length > 5) {
        suggestions.push(`${username.substring(0, username.length - 2)}${Math.floor(Math.random() * 90 + 10)}`);
    } else {
         suggestions.push(`${username}User${Math.floor(Math.random() * 10)}`);
    }

    suggestions.slice(0, 2).forEach(suggestion => {

        if (suggestion.length >= 3) {
            const suggestionSpan = document.createElement('span');
            suggestionSpan.textContent = suggestion;
            suggestionSpan.className = 'suggestion-item';
            suggestionSpan.onclick = () => {
                const usernameInput = document.getElementById('newUsername');
                usernameInput.value = suggestion;
               
                usernameInput.dispatchEvent(new Event('input'));
            };
            suggestionsEl.appendChild(suggestionSpan);
        }
    });
}

async function handleUsernameSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const username = form.newUsername.value;
    const password = form.password.value;
    const confirmPassword = form.querySelector('#signupPassword').value;
    const messageDiv = document.querySelector('#usernameBanner .modal-content #message');

    messageDiv.innerHTML = '';
    messageDiv.style.color = '';

    if (/^\d+/.test(username) || username.length < 3 || !/^(?!\d+$)(?!\d)[a-zA-Z0-9]+$/.test(username)) {
        messageDiv.innerHTML = 'Invalid username!';
        messageDiv.style.color = 'red';
        return;
    }

    if (password !== confirmPassword) {
        messageDiv.innerHTML = 'Passwords do not match!';
        messageDiv.style.color = 'red';
        return;
    }

    try {  
        const response = await fetch('/signup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        const result = await response.json();
        if (response.ok) { 
            messageDiv.innerHTML = 'Username created successfully!';
            messageDiv.style.color = 'green';
            setTimeout(hideUsernameForm, 1500);
        } else {
            messageDiv.innerHTML = result.error || 'Error creating username';
            messageDiv.style.color = 'red';
            setTimeout(() => {
                messageDiv.innerHTML = '';
                messageDiv.style.color = '';
            }, 1500);
        }
    } catch (error) {
        messageDiv.innerHTML = 'Network error - please try again';
        messageDiv.style.color = 'red';
    }
}

async function handleSigninSubmitForm(event) {
    event.preventDefault();
    const form = event.target;
    const username = form.username.value;
    const password = form.querySelector('#signinPassword').value;
    const reportingId = form.querySelector('#signinReportingId').value;
    const messageDiv = document.querySelector('#signinBanner .modal-content #message');

    messageDiv.innerHTML = '';
    messageDiv.style.color = '';

    try {  
        const response = await fetch('/signin', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        let result;
        try {
            result = await response.json();
        } catch (jsonError) {
            messageDiv.innerHTML = 'An unexpected error occurred. Please try again.';
            messageDiv.style.color = 'red';
            return; 
        }

        if (response.ok) { 
            messageDiv.innerHTML = result.message ||'Signed-in Succeessfully!';
            messageDiv.style.color = 'green';
            if (reportingId) {
                
                setTimeout(() => {
                    // Create a form and submit it as POST
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = '/track_bribe';

                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'reportingId';
                    input.value = reportingId;
                    form.appendChild(input);

                    document.body.appendChild(form);
                    form.submit();
                }, 1000);
            } else if (result.redirect_url) {
                setTimeout(() => {
                    window.location.href = result.redirect_url;
                }, 1000); 
            } else {
                setTimeout(hideSigninForm, 1000);
            }
        } else {
            messageDiv.innerHTML = result.error || 'Error signing in - please try again';
            messageDiv.style.color = 'red';
            setTimeout(() => {
                messageDiv.innerHTML = '';
                messageDiv.style.color = '';
            }, 1500);
        }
    } catch (error) {
        messageDiv.innerHTML = 'Network error or server issue - please try again';
        messageDiv.style.color = 'red';
        setTimeout(() => {
            messageDiv.innerHTML = '';
            messageDiv.style.color = '';
        }, 1500);
    }
}

function togglePasswordVisibility() {
    const passwordInputs = document.querySelectorAll('#signinPassword, #signupPassword, #confirmPassword');
    
    passwordInputs.forEach(input => {
        if (input.type === 'password') {
            input.type = 'text';
        } else {
            input.type = 'password';
        }
    });
}

document.addEventListener('DOMContentLoaded', (event) => {

    const usernameInput = document.getElementById('newUsername');
    if (usernameInput) {
        
        usernameInput.addEventListener('input', (event) => {
            const username = event.target.value;
            const refreshButton = document.getElementById('refreshSuggestions');
            const suggestionsEl = document.getElementById('usernameSuggestions');
            const availabilityStatusEl = document.getElementById('usernameAvailabilityStatus');
            const addTextEl = document.getElementById('addText');

            clearTimeout(debounceTimer);

            if (username.length > 0 && /^\d+/.test(username)) {
                availabilityStatusEl.textContent = 'cannot start with digits';
                availabilityStatusEl.style.color = 'orange';
                suggestionsEl.innerHTML = '';
                refreshButton.style.display = 'none';
                addTextEl.textContent= "";
                return;
            }
            if (username.length > 0 && (username.length < 3)) {
                 availabilityStatusEl.textContent = 'Must be atleast 3 chars';
                 availabilityStatusEl.style.color = 'orange';
                 suggestionsEl.innerHTML = '';
                 refreshButton.style.display = 'none';
                 addTextEl.textContent= "";
                 return; 
            }
            if (username.length > 0 && !/^(?!\d+$)(?!\d)[a-zA-Z0-9]+$/.test(username)) {
                availabilityStatusEl.textContent = 'Alphanumeric only';
                availabilityStatusEl.style.color = 'orange';
                suggestionsEl.innerHTML = '';
                refreshButton.style.display = 'none';
                addTextEl.textContent= "";
                return;
            }
        
            if (username.length === 0) {
                availabilityStatusEl.textContent = '';
                suggestionsEl.innerHTML = '';
                refreshButton.style.display = 'none';
                addTextEl.textContent= "";
                return;
            }
            
            debounceTimer = setTimeout(async () => {
                
               const isAvailable = await checkUsernameAvailability(username);
               refreshButton.style.display = 'block';
    
               if (isAvailable) { 
                   suggestionsEl.innerHTML = '';
                   addTextEl.textContent= "";
                   refreshButton.style.display = 'none';
               } else {
                   addTextEl.textContent= "Try: ";
                   generateSuggestions(username);
               }
            }, DEBOUNCE_DELAY);
        });
    } else {
         console.error("#newUsername input element not found when trying to attach listener.");
    }

    const refreshButton = document.getElementById('refreshSuggestions');
    if (refreshButton) {
        
        refreshButton.addEventListener('click', () => {
            const username = document.getElementById('newUsername').value;
            if (username && username.length >= 3 && /^(?!\d+$)(?!\d)[a-zA-Z0-9]+$/.test(username)) {
                generateSuggestions(username);
            } else {
                document.getElementById('usernameSuggestions').innerHTML = ''; 
            }
        });
    } else {
        console.error("#refreshSuggestions button element not found.");
    }

    const styleSheet = document.styleSheets[0];
    if (styleSheet) {
        try {
            // Using more specific selectors and consolidating rules
             styleSheet.insertRule(`
                 #usernameBanner .username-feedback { margin-top: 5px; font-size: 0.9em; min-height: 25px; display: flex; align-items: center; flex-wrap: wrap; }
             `, styleSheet.cssRules.length);
             styleSheet.insertRule(`
                 #usernameBanner #usernameAvailabilityStatus { margin-right: 10px; font-weight: bold; flex-shrink: 0; }
             `, styleSheet.cssRules.length);
             styleSheet.insertRule(`
                 #usernameBanner #usernameSuggestions { display: inline-flex; gap: 5px; flex-grow: 1; }
             `, styleSheet.cssRules.length);
             styleSheet.insertRule(`
                 #usernameBanner .suggestion-item { display: inline-block; padding: 3px 6px; background-color: #e0e0e0; border-radius: 4px; cursor: pointer; font-size: 0.9em; }
             `, styleSheet.cssRules.length);
             styleSheet.insertRule(`
                 #usernameBanner .suggestion-item:hover { background-color: #c0c0c0; }
             `, styleSheet.cssRules.length);


        } catch (e) {
            console.error("Could not insert CSS rules:", e);
            // Fallback
            const style = document.createElement('style');
            style.textContent = `
                 #usernameBanner .username-feedback { margin-top: 5px; font-size: 0.9em; min-height: 25px; display: flex; align-items: center; flex-wrap: wrap; }
                 #usernameBanner #usernameAvailabilityStatus { margin-right: 10px; font-weight: bold; flex-shrink: 0; }
                 #usernameBanner #usernameSuggestions { display: inline-flex; gap: 5px; flex-grow: 1; }
                 #usernameBanner #refreshSuggestions { margin-left: 5px; cursor: pointer; font-size: 1.2em; padding: 0 5px; vertical-align: middle; border: none; background: none; flex-shrink: 0; }
                 #usernameBanner .suggestion-item { display: inline-block; padding: 3px 6px; background-color: #e0e0e0; border-radius: 4px; cursor: pointer; font-size: 0.9em; }
                 #usernameBanner .suggestion-item:hover { background-color: #c0c0c0; }
            `;
            document.head.appendChild(style);
        }
    } 
});