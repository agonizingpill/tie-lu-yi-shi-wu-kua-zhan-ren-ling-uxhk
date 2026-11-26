export const store = {
  token: sessionStorage.getItem('rail-session'),
  user: null,
  stations: [],
  selectedSeal: null,
  selectedSearch: null,
  selectedClaim: null,
};

export function userSession(token, profile) {
  store.token = token;
  store.user = profile;
  sessionStorage.setItem('rail-session', token);
}

export function endSession() {
  Object.assign(store, {token: null, user: null, stations: [], selectedSeal: null,
    selectedSearch: null, selectedClaim: null});
  sessionStorage.removeItem('rail-session');
}
