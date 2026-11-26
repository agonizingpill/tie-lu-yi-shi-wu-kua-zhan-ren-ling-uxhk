import {store} from './store.js';

async function request(path, body) {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      ...(body === undefined ? {} : {'Content-Type': 'application/json'}),
      ...(store.token ? {'Authorization': 'Bearer ' + store.token} : {}),
    },
    body: body === undefined ? null : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) {
    const issues = result.issues?.map(item => item.field + ' ' + item.message).join('；');
    throw new Error(issues ? result.detail + '：' + issues : result.detail);
  }
  return result;
}

export const api = {
  login: body => request('/auth/login', body),
  profile: () => request('/auth/profile'),
  stations: () => request('/stations'),
  bags: () => request('/bags'),
  intake: body => request('/bags', body),
  ledger: seal => request('/bags/' + encodeURIComponent(seal) + '/ledger'),
  searches: () => request('/searches'),
  search: id => request('/searches/' + id),
  recall: body => request('/searches', body),
  claims: () => request('/claims'),
  claim: body => request('/claims', body),
  release: (id, seal) => request('/claims/' + id + '/release', {scanned_seal: seal}),
  transfers: () => request('/transfers'),
  dispatch: body => request('/transfers', body),
  receive: (code, seal) => request('/transfers/' + encodeURIComponent(code) + '/receive', {scanned_seal: seal}),
};
