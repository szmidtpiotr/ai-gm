// Sekcja "Księga Zasad" — osadza interaktywną Księgę Zasad (/rules/).
// Zastąpiła stary podgląd game_mechanics.md (już niepotrzebny).
export async function init(panel) {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;height:100%;min-height:75vh;gap:10px';
    wrap.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
            <h2 style="margin:0;font-size:18px">📖 Księga Zasad</h2>
            <span style="color:#8a7233;font-size:13px">Interaktywny podręcznik gracza — z trybem edycji dla admina.</span>
            <a href="/rules/" target="_blank" rel="noopener"
               style="margin-left:auto;background:#1d1812;border:1px solid #8a7233;color:#c9a24b;
                      border-radius:7px;padding:8px 14px;text-decoration:none;font-size:13px;white-space:nowrap">
               Otwórz w nowej karcie &#8599;</a>
        </div>
        <iframe src="/rules/" title="Księga Zasad" loading="lazy"
                style="flex:1;width:100%;min-height:72vh;border:1px solid #3a2f20;border-radius:9px;background:#15110c"></iframe>
    `;
    panel.appendChild(wrap);
}
