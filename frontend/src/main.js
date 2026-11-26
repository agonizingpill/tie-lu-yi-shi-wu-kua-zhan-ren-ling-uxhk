import {api} from './api.js';
import {masthead} from './components/layout.js';
import {showMessage} from './forms.js';
import {endSession, store} from './store.js';
import {claims} from './pages/claims.js';
import {loginPage} from './pages/login.js';
import {recall} from './pages/recall.js';
import {registry} from './pages/registry.js';
import {transfer} from './pages/transfer.js';

const shell = document.getElementById('shell');
const pages = {registry, recall, transfer, claims};

async function render() {
  const route = location.hash.slice(1);
  const page = Object.hasOwn(pages, route) ? route : 'registry';
  shell.innerHTML = masthead(store.user, page) + '<main></main>';
  const main = shell.querySelector('main');
  if (!store.user) {
    loginPage(main, async () => {
      store.stations = await api.stations();
      await render();
    });
    return;
  }
  main.className = 'workspace frame';
  shell.querySelector('#logout').addEventListener('click', () => {
    endSession();
    render();
  });
  try {
    await pages[page](main);
  } catch (error) {
    if (main.isConnected) {
      const message = document.createElement('div');
      main.prepend(message);
      showMessage(message, error.message, 'error');
    }
  }
}

if (store.token) {
  try {
    [store.user, store.stations] = await Promise.all([api.profile(), api.stations()]);
  } catch {
    endSession();
  }
}
window.addEventListener('hashchange', render);
await render();
