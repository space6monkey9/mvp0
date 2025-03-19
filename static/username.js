function showUsernameForm() {
    document.getElementById('usernameBanner').style.display = 'block';
}

function hideUsernameForm() {
    document.getElementById('usernameBanner').style.display = 'none';
    document.getElementById('message').innerHTML = '';
}

async function handleUsernameSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const username = form.newUsername.value;
    const confirmUsername = form.confirmUsername.value;
    const messageDiv = document.getElementById('message');

    if (username !== confirmUsername) {
        messageDiv.innerHTML = 'Usernames do not match!';
        messageDiv.style.color = 'red';
        return;
    }

    try {  
        const response = await fetch('/create_username', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username })
        });

        const result = await response.json();
        if (response.ok) { 
            messageDiv.innerHTML = 'Username created successfully!';
            messageDiv.style.color = 'green';
            setTimeout(hideUsernameForm, 1500);
        } else {
            messageDiv.innerHTML = result.error || 'Error creating username';
            messageDiv.style.color = 'red';
        }
    } catch (error) {
        messageDiv.innerHTML = 'Network error - please try again';
        messageDiv.style.color = 'red';
    }
}