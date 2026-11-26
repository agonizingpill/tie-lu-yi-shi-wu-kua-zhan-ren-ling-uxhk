import {store} from './store.js';

export function escape(value) {
  const map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
  return String(value ?? '').replace(/[&<>"']/g, character => map[character]);
}

export function dateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    hour12: false,
  }) : '—';
}

export function station(code) {
  const item = store.stations.find(stop => stop.code === code);
  return item?.display_name || code;
}
