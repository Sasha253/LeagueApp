// Canvas panels: open questions, proposed components, FR coverage.
export const panel = (title, html) => `<section class="cv-panel">${title ? `<h2>${title}</h2>` : ''}${html}</section>`;
export const list = (items, ordered = true) => `<${ordered ? 'ol' : 'ul'}>${items.map((i) => `<li>${i}</li>`).join('')}</${ordered ? 'ol' : 'ul'}>`;
