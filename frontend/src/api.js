import {store} from './store.js';

async function request(path, body, options = {}) {
  const {headers: extraHeaders, ...fetchOptions} = options;
  const response = await fetch('/api' + path, {
    method: body === undefined && options.method === undefined ? 'GET' : (options.method || 'POST'),
    headers: {
      ...(body === undefined ? {} : {'Content-Type': 'application/json'}),
      ...(store.token ? {'Authorization': 'Bearer ' + store.token} : {}),
      ...(extraHeaders || {}),
    },
    body: body === undefined ? null : JSON.stringify(body),
    ...fetchOptions,
  });
  const result = await response.json();
  if (!response.ok) {
    const issues = result.issues?.map(item => item.field + ' ' + item.message).join('；');
    const error = new Error(issues ? result.detail + '：' + issues : result.detail);
    error.status = response.status;
    error.data = result;
    throw error;
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
  callNumber: searchId => request('/calls', {search_id: searchId}),
  currentCalls: () => request('/calls/current', undefined, {method: 'GET'}),
  currentNumber: searchId => request('/calls/current?search_id=' + encodeURIComponent(searchId), undefined, {method: 'GET'}),
  verifyNumber: (id, answer, key) => request('/calls/' + encodeURIComponent(id) + '/verify', {answer},
    {headers: {'Idempotency-Key': key || ('verify-number-' + id)}}),
  claims: () => request('/claims'),
  claim: body => request('/claims', body),
  release: (id, seal) => request('/claims/' + id + '/release', {scanned_seal: seal}),
  transfers: () => request('/transfers'),
  dispatch: body => request('/transfers', body),
  receive: (code, seal) => request('/transfers/' + encodeURIComponent(code) + '/receive', {scanned_seal: seal}),
};
