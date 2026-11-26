import {escape} from './format.js';

export function showMessage(target, content, type = 'success') {
  target.innerHTML = content ? '<p class="message ' + type + '" role="status">' + escape(content) + '</p>' : '';
}

export function formAction(form, output, submit) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    showMessage(output, '');
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    try {
      await submit(Object.fromEntries(new FormData(form)));
    } catch (error) {
      showMessage(output, error.message, 'error');
    } finally {
      button.disabled = false;
    }
  });
}
