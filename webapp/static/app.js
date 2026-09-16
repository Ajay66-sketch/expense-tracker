// Shared helpers used by every page.

function getToken() {
  return localStorage.getItem('token');
}

function setToken(token) {
  localStorage.setItem('token', token);
}

function clearToken() {
  localStorage.removeItem('token');
}

function requireAuth() {
  if (!getToken()) {
    window.location.href = 'login.html';
  }
}

async function api(path, options = {}) {
  const headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${window.API_BASE}${path}`, Object.assign({}, options, { headers }));
  const contentType = res.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await res.json() : null;

  if (res.status === 401) {
    clearToken();
    window.location.href = 'login.html';
    throw new Error('Not authenticated');
  }
  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

function showFlash(message, type = 'danger') {
  const el = document.getElementById('flash');
  if (!el) return;
  el.textContent = message;
  el.className = `flash flash-${type}`;
  el.style.display = 'block';
}

function money(n) {
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}
