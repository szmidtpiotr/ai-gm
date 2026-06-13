export async function init(panel) {
    const container = document.createElement('div');
    container.className = 'game-mechanics-viewer';
    container.innerHTML = `
        <div class=gm-layout>
            <div class=gm-sidebar>
                <h2>Nawigacja</h2>
                <input type=text class=gm-search id=gmSearch placeholder=Szukaj nagłówków...>
                <div class=gm-toc-container id=gmToc></div>
            </div>
            <div class=gm-main>
                <div class=gm-loading>Ładowanie game_mechanics.md...</div>
                <div class=gm-content id=gmContent></div>
            </div>
        </div>
    `;

    panel.appendChild(container);
    addStyles();
    loadMechanics(container);
}

async function loadMechanics(container) {
    try {
        const response = await fetch('/api/admin/game-mechanics/content');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const markdown = await response.text();
        const contentDiv = container.querySelector('#gmContent');
        const tocDiv = container.querySelector('#gmToc');
        const loadingDiv = container.querySelector('.gm-loading');

        parseAndRender(markdown, contentDiv, tocDiv);
        loadingDiv.style.display = 'none';

        setupInteractivity(container);
    } catch (error) {
        const contentDiv = container.querySelector('#gmContent');
        contentDiv.innerHTML = `<div class=gm-error>Błąd ładowania: ${error.message}</div>`;
    }
}

function parseAndRender(markdown, contentDiv, tocDiv) {
    const lines = markdown.split('\n');
    let html = '';
    let toc = [];
    let currentH1 = null;

    lines.forEach((line) => {
        const h1Match = line.match(/^# (.+)$/);
        const h2Match = line.match(/^## (.+)$/);
        const h3Match = line.match(/^### (.+)$/);

        if (h1Match) {
            const text = h1Match[1];
            const id = slugify(text);
            currentH1 = { id, text, children: [] };
            html += `<h1 id=${id}>${escapeHtml(text)}</h1>`;
            toc.push(currentH1);
        } else if (h2Match) {
            const text = h2Match[1];
            const id = slugify(text);
            const entry = { id, text, level: 2, children: [] };
            if (currentH1) currentH1.children.push(entry);
            html += `<h2 id=${id}>${escapeHtml(text)}</h2>`;
        } else if (h3Match) {
            const text = h3Match[1];
            const id = slugify(text);
            const entry = { id, text, level: 3, children: [] };
            if (currentH1 && currentH1.children.length > 0) {
                currentH1.children[currentH1.children.length - 1].children.push(entry);
            }
            html += `<h3 id=${id}>${escapeHtml(text)}</h3>`;
        } else if (line.match(/^>/)) {
            html += `<blockquote>${escapeHtml(line.replace(/^>\s*/, ''))}</blockquote>`;
        } else if (line.match(/^---/)) {
            html += '<hr>';
        } else if (line.trim()) {
            html += `<p>${escapeHtml(line)}</p>`;
        }
    });

    contentDiv.innerHTML = html;
    renderToc(toc, tocDiv);
}

function renderToc(toc, container) {
    container.innerHTML = '';
    toc.forEach((section) => {
        const div = document.createElement('div');
        div.className = 'gm-toc-section';

        const h1 = document.createElement('div');
        h1.className = 'gm-toc-h1';
        h1.textContent = section.text;
        h1.addEventListener('click', () => scrollToId(section.id));
        div.appendChild(h1);

        if (section.children.length > 0) {
            const ul = document.createElement('ul');
            ul.className = 'gm-toc-h2-list';
            section.children.forEach((h2) => {
                const li = document.createElement('li');
                li.className = 'gm-toc-h2-item';
                const span = document.createElement('span');
                span.className = 'gm-toc-h2-link';
                span.textContent = h2.text;
                span.addEventListener('click', () => scrollToId(h2.id));
                li.appendChild(span);

                if (h2.children.length > 0) {
                    const ul2 = document.createElement('ul');
                    ul2.className = 'gm-toc-h3-list';
                    h2.children.forEach((h3) => {
                        const li3 = document.createElement('li');
                        li3.className = 'gm-toc-h3-item';
                        const span3 = document.createElement('span');
                        span3.textContent = h3.text;
                        span3.addEventListener('click', () => scrollToId(h3.id));
                        li3.appendChild(span3);
                        ul2.appendChild(li3);
                    });
                    li.appendChild(ul2);
                }
                ul.appendChild(li);
            });
            div.appendChild(ul);
        }
        container.appendChild(div);
    });
}

function setupInteractivity(container) {
    const search = container.querySelector('#gmSearch');
    const toc = container.querySelector('#gmToc');
    const main = container.querySelector('.gm-main');

    search.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        toc.querySelectorAll('.gm-toc-section').forEach((sec) => {
            const h1 = sec.querySelector('.gm-toc-h1');
            const h2s = sec.querySelectorAll('.gm-toc-h2-item');
            const matchH1 = h1.textContent.toLowerCase().includes(query);
            let hasMatch = false;
            h2s.forEach((item) => {
                const match = item.textContent.toLowerCase().includes(query);
                item.style.display = match ? '' : 'none';
                if (match) hasMatch = true;
            });
            sec.style.display = matchH1 || hasMatch ? '' : 'none';
        });
    });
}

function scrollToId(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function slugify(text) {
    return text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').substring(0, 50);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .game-mechanics-viewer { height: 100%; display: flex; }
        .gm-layout { display: flex; width: 100%; height: 100%; }
        .gm-sidebar { width: 280px; background: #fff; border-right: 1px solid #ddd; padding: 20px; overflow-y: auto; flex-shrink: 0; }
        .gm-sidebar h2 { font-size: 13px; text-transform: uppercase; color: #666; margin-bottom: 15px; font-weight: 600; }
        .gm-search { width: 100%; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 13px; margin-bottom: 15px; background: #f9f9f9; }
        .gm-toc-section { margin: 12px 0; }
        .gm-toc-h1 { font-weight: 700; color: #222; padding: 6px 8px; border-left: 3px solid #2196F3; padding-left: 10px; margin-bottom: 8px; cursor: pointer; border-radius: 0 3px 3px 0; }
        .gm-toc-h1:hover { background: #f0f8ff; }
        .gm-toc-h2-list { list-style: none; margin: 0; padding: 0; }
        .gm-toc-h2-item { list-style: none; margin: 0; padding: 0; }
        .gm-toc-h2-link { display: block; padding: 4px 8px 4px 16px; color: #444; font-weight: 500; border-radius: 3px; cursor: pointer; }
        .gm-toc-h2-link:hover { background: #f0f0f0; }
        .gm-toc-h3-list { list-style: none; margin: 0; padding: 0; }
        .gm-toc-h3-item { list-style: none; margin: 0; padding: 0; }
        .gm-toc-h3-item span { display: block; padding: 2px 8px 2px 32px; color: #666; font-size: 12px; border-radius: 3px; cursor: pointer; }
        .gm-toc-h3-item span:hover { background: #f8f8f8; }
        .gm-main { flex: 1; overflow-y: auto; padding: 40px; background: #fff; }
        .gm-content { max-width: 900px; }
        .gm-content h1 { font-size: 28px; margin: 40px 0 20px; color: #222; border-bottom: 3px solid #2196F3; padding-bottom: 10px; }
        .gm-content h2 { font-size: 22px; margin: 35px 0 15px; color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }
        .gm-content h3 { font-size: 18px; margin: 25px 0 12px; color: #444; }
        .gm-content p { margin: 12px 0; line-height: 1.7; color: #444; }
        .gm-content blockquote { border-left: 4px solid #2196F3; background: #f0f8ff; padding: 12px 16px; margin: 16px 0; border-radius: 2px; color: #333; }
        .gm-content hr { border: none; border-top: 2px solid #e0e0e0; margin: 40px 0; }
        .gm-loading { text-align: center; padding: 40px; color: #999; }
        .gm-error { background: #ffebee; border: 1px solid #ef5350; color: #c62828; padding: 16px; border-radius: 4px; margin: 20px; }
    `;
    document.head.appendChild(style);
}
