document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-citation]');
  if (!button) return;

  const citation = document.querySelector('.rn-citation-text');
  if (!citation) return;

  try {
    await navigator.clipboard.writeText(citation.textContent.trim());
    button.textContent = 'Citation copied';
  } catch (_) {
    citation.hidden = false;
    citation.focus();
    button.textContent = 'Select citation below';
  }
});
