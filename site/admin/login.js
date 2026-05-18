        const form = document.getElementById('loginForm');
        const errorMsg = document.getElementById('errorMsg');
        const submitBtn = document.getElementById('submitBtn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.textContent = 'Вход...';
            errorMsg.style.display = 'none';

            try {
                const res = await fetch('/api/admin/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: document.getElementById('username').value,
                        password: document.getElementById('password').value
                    })
                });

                if (!res.ok) throw new Error('Auth failed');
                const data = await res.json();

                // Сохраняем токен в cookie
                // const expires = new Date(Date.now() + data.expires_in * 1000).toUTCString();
                // document.cookie = `token=${data.token};expires=${expires};path=/`;
                
                window.location.href = '/admin';
            } catch (err) {
                errorMsg.style.display = 'block';
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Войти';
            }
        });