/* System section — thin pass-through to system_llm.js
   (which now hosts LLM/DB/Config/Slash/Admin/Wskrzeszenie + Wygląd/Głos/Email as tabs) */

export async function init(panel) {
    const { init: subInit } = await import('/admin_panel_v2/sections/system_llm.js?v=stage11c-alias-1');
    return subInit(panel);
}
