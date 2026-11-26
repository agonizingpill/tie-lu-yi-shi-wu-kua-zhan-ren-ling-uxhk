import {escape} from '../format.js';

export function stationLine(stations, home = '') {
  return '<div class="station-line" aria-label="北砾区段站序">' + stations.map(({code, display_name}) =>
    '<div class="stop ' + (code === home ? 'active' : '') + '"><strong>' + escape(display_name)
    + '</strong><small class="mono">' + escape(code) + '</small></div>').join('') + '</div>';
}
