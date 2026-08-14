// ── Init Lucide icons ─────────────────────────────────────────────────────────
lucide.createIcons();

// ── DOM refs ──────────────────────────────────────────────────────────────────
const emailListEl    = document.getElementById('email-list');
const inboxCountEl   = document.getElementById('inbox-count');
const btnRefresh     = document.getElementById('btn-refresh');
const listTitle      = document.getElementById('list-title');
const resultsBar     = document.getElementById('results-bar');
const cacheAgeLabel  = document.getElementById('cache-age-label');

const readingEmpty   = document.getElementById('reading-empty');
const readingContent = document.getElementById('reading-content');
const readSubject    = document.getElementById('read-subject');
const readFrom       = document.getElementById('read-from');
const readDate       = document.getElementById('read-date');
const readAvatar     = document.getElementById('read-avatar');
const readBody       = document.getElementById('read-body');

const composeModal   = document.getElementById('compose-modal');
const btnCompose     = document.getElementById('btn-compose');
const btnCloseCompose= document.getElementById('btn-close-compose');
const btnCancelCompose=document.getElementById('btn-cancel-compose');
const btnSend        = document.getElementById('btn-send');
const btnReply       = document.getElementById('btn-reply');
const composeTo      = document.getElementById('compose-to');
const composeSubject = document.getElementById('compose-subject');
const composeBody    = document.getElementById('compose-body');
const toast          = document.getElementById('toast');

// ── State ─────────────────────────────────────────────────────────────────────
let allEmails      = [];
let activeEmailId  = null;
let activeFilter   = 'all';
let activeEmail    = null;
let cacheAgeTimer  = null;
let lastFetchedAt  = null; // unix seconds from server

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatEmailDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date)) return dateStr;
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1)   return 'Just now';
    if (diffMins < 60)  return `${diffMins}m ago`;
    if (date.toDateString() === now.toDateString())
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function showToast(msg, type = 'success') {
    toast.textContent = msg;
    toast.className = `toast ${type}`;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

function startCacheTimer(serverAge) {
    if (cacheAgeTimer) clearInterval(cacheAgeTimer);
    let age = serverAge;
    const update = () => {
        if (age < 60) {
            cacheAgeLabel.textContent = `Updated ${age}s ago`;
        } else {
            cacheAgeLabel.textContent = `Updated ${Math.floor(age/60)}m ago`;
        }
        age++;
    };
    update();
    cacheAgeTimer = setInterval(update, 1000);
}

// ── Filter Pills ──────────────────────────────────────────────────────────────
document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter;
        // Filter from cache — instant, no IMAP call
        fetchEmails(false);
    });
});

// ── Fetch Emails ──────────────────────────────────────────────────────────────
async function fetchEmails(forceRefresh = false) {
    if (forceRefresh) {
        // Show spinning animation on refresh button
        btnRefresh.classList.add('spinning');
        emailListEl.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <p>Fetching from Gmail...</p>
            </div>`;
    } else {
        // Soft loading — keep existing list, just show subtle indicator
        resultsBar.textContent = 'Filtering...';
    }

    try {
        const params = new URLSearchParams({
            filter: activeFilter,
            refresh: forceRefresh ? '1' : '0'
        });
        const response = await fetch(`/api/emails?${params}`);
        const data = await response.json();

        btnRefresh.classList.remove('spinning');

        if (data.success) {
            allEmails = data.emails;
            inboxCountEl.textContent = data.shown;

            // Update filter label
            const filterLabels = { all: 'Inbox', today: 'Today', '3h': 'Last 3 Hours', '1h': 'Last Hour' };
            listTitle.textContent = filterLabels[activeFilter] || 'Inbox';

            // Results summary
            if (activeFilter !== 'all') {
                resultsBar.textContent = `${data.shown} of ${data.total} emails match`;
                resultsBar.style.display = 'block';
            } else {
                resultsBar.style.display = 'none';
            }

            // Cache age counter
            startCacheTimer(data.cached_age || 0);

            renderEmailList();
        } else {
            btnRefresh.classList.remove('spinning');
            emailListEl.innerHTML = `<div class="error-state"><i data-lucide="alert-circle"></i><p>${data.error}</p></div>`;
            lucide.createIcons();
        }
    } catch (err) {
        btnRefresh.classList.remove('spinning');
        emailListEl.innerHTML = `<div class="error-state"><i data-lucide="wifi-off"></i><p>Connection error</p></div>`;
        lucide.createIcons();
    }
}

// ── Render Email List ─────────────────────────────────────────────────────────
function renderEmailList() {
    if (allEmails.length === 0) {
        const filterLabels = { all: 'No emails', today: 'No emails today', '3h': 'No emails in last 3 hours', '1h': 'No emails in last hour' };
        emailListEl.innerHTML = `
            <div class="empty-state" style="position:static;padding-top:60px">
                <i data-lucide="inbox"></i>
                <p>${filterLabels[activeFilter] || 'No emails'}</p>
            </div>`;
        lucide.createIcons();
        return;
    }

    emailListEl.innerHTML = allEmails.map(email => {
        const senderRaw = email.from || '';
        const senderName = senderRaw.includes('<')
            ? senderRaw.split('<')[0].trim().replace(/"/g, '')
            : senderRaw.split('@')[0];
        const avatar = senderName.charAt(0).toUpperCase() || '?';
        const isActive = String(email.uid) === String(activeEmailId);
        const preview = (email.body_text || '').trim().substring(0, 80).replace(/\s+/g, ' ');

        return `
        <div class="email-item ${isActive ? 'active' : ''}" data-uid="${email.uid}">
            <div class="email-item-left">
                <div class="email-avatar-sm">${avatar}</div>
            </div>
            <div class="email-item-right">
                <div class="email-item-header">
                    <span class="email-item-sender">${senderName}</span>
                    <span class="email-item-date">${formatEmailDate(email.date || email.date_raw)}</span>
                </div>
                <div class="email-item-subject">${email.subject || '(no subject)'}</div>
                <div class="email-item-preview">${preview || '(no preview)'}…</div>
            </div>
        </div>`;
    }).join('');

    // Click listeners
    document.querySelectorAll('.email-item').forEach(el => {
        el.addEventListener('click', () => selectEmail(el.dataset.uid));
    });

    lucide.createIcons();
}

// ── Select & Display Email ─────────────────────────────────────────────────────
function selectEmail(uid) {
    activeEmailId = uid;

    // Update active class without full re-render
    document.querySelectorAll('.email-item').forEach(el => {
        el.classList.toggle('active', el.dataset.uid === String(uid));
    });

    activeEmail = allEmails.find(e => String(e.uid) === String(uid));
    if (!activeEmail) return;

    readingEmpty.classList.add('hidden');
    readingContent.classList.remove('hidden');

    readSubject.textContent = activeEmail.subject || '(no subject)';

    const senderRaw = activeEmail.from || '';
    const senderName = senderRaw.includes('<')
        ? senderRaw.split('<')[0].trim().replace(/"/g, '')
        : senderRaw;
    readFrom.textContent = activeEmail.from;
    readAvatar.textContent = senderName.charAt(0).toUpperCase() || '?';

    const d = activeEmail.date ? new Date(activeEmail.date) : null;
    readDate.textContent = d && !isNaN(d)
        ? d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
        : (activeEmail.date_raw || '');

    if (activeEmail.body_html) {
        readBody.innerHTML = activeEmail.body_html;
    } else {
        readBody.innerHTML = `<pre style="white-space:pre-wrap;font-family:inherit">${activeEmail.body_text || ''}</pre>`;
    }
}

// ── Compose / Reply ───────────────────────────────────────────────────────────
function openCompose(replyTo = null) {
    composeModal.classList.remove('hidden');
    if (replyTo) {
        composeTo.value = replyTo.from || '';
        const subj = replyTo.subject || '';
        composeSubject.value = subj.toLowerCase().startsWith('re:') ? subj : `Re: ${subj}`;
        composeBody.value = '';
    }
    composeTo.focus();
}

function closeCompose() {
    composeModal.classList.add('hidden');
    composeTo.value = '';
    composeSubject.value = '';
    composeBody.value = '';
}

async function sendEmail() {
    const to      = composeTo.value.trim();
    const subject = composeSubject.value.trim();
    const body    = composeBody.value.trim();

    if (!to || !subject || !body) {
        showToast('Please fill all fields', 'error');
        return;
    }

    const origHTML = btnSend.innerHTML;
    btnSend.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div> Sending...';
    btnSend.disabled = true;

    try {
        const res = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ to, subject, body })
        });
        const data = await res.json();

        if (data.success) {
            closeCompose();
            showToast('Email sent successfully!');
            // Force refresh after send
            setTimeout(() => fetchEmails(true), 800);
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch {
        showToast('Failed to send email', 'error');
    }

    btnSend.innerHTML = origHTML;
    btnSend.disabled = false;
    lucide.createIcons();
}

// ── Event Listeners ───────────────────────────────────────────────────────────
btnRefresh.addEventListener('click', () => fetchEmails(true));
btnCompose.addEventListener('click', () => openCompose());
btnCloseCompose.addEventListener('click', closeCompose);
btnCancelCompose.addEventListener('click', closeCompose);
btnSend.addEventListener('click', sendEmail);
btnReply.addEventListener('click', () => {
    if (activeEmail) openCompose(activeEmail);
});

// Close modal on backdrop click
composeModal.addEventListener('click', e => {
    if (e.target === composeModal) closeCompose();
});

// ── Init ──────────────────────────────────────────────────────────────────────
fetchEmails(true);
