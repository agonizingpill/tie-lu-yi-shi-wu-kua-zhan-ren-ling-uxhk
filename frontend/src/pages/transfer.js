import {api} from '../api.js';
import {pageTitle} from '../components/layout.js';
import {stationLine} from '../components/stations.js';
import {status} from '../components/status.js';
import {dateTime, escape, station} from '../format.js';
import {formAction, showMessage} from '../forms.js';
import {store} from '../store.js';

function movement(item) {
  const arrival = store.user.station_code === item.to_station && item.state === 'dispatched';
  return `<article class="movement"><div class="route">
      <span>${escape(station(item.from_station))}</span><i aria-hidden="true"></i><b class="mono">${escape(item.carrier_train)}</b>
      <i aria-hidden="true"></i><span>${escape(station(item.to_station))}</span></div>
    <p><span class="mono">${escape(item.code)} / ${escape(item.seal_id)}</span> · ${status(item.state)}</p>
    <small class="muted">发运 ${escape(dateTime(item.dispatched_at))} · 收运 ${escape(dateTime(item.received_at))}</small>
    ${arrival ? '<form data-arrival="' + escape(item.code) + '"><label>实扫封签<input name="scanned_seal" required></label>'
      + '<button type="submit" class="slim">核对并接收入柜</button></form>' : ''}
  </article>`;
}

export async function transfer(main) {
  main.innerHTML = pageTitle('INTERSTATION / 接力', '跨站转运单', '区段调度绑定承运车次，目的站柜员实扫原封签并确认入柜。')
    + `<div class="three-prongs"><section class="panel"><h2>区段接力轨迹</h2>
      <div style="color:var(--navy)">${stationLine(store.stations, store.user.station_code)}</div>
      <div id="transfer-messages"></div><div id="movement-list"></div></section>
      <section class="panel"><h2>待分配承运车次</h2><p class="muted">已核验且取件站与持有站不同的封袋才可发运。</p>
        <div id="dispatch-form"></div></section></div>`;
  const movementList = main.querySelector('#movement-list');
  const dispatchBox = main.querySelector('#dispatch-form');
  const message = main.querySelector('#transfer-messages');
  async function load() {
    const [transfers, claims] = await Promise.all([api.transfers(), api.claims()]);
    movementList.innerHTML = transfers.length ? transfers.map(movement).join('')
      : '<p class="empty">暂无在途封袋。待发运的已核验认领单在右侧列出。</p>';
    movementList.querySelectorAll('[data-arrival]').forEach(form => formAction(form, message, async body => {
      await api.receive(form.dataset.arrival, body.scanned_seal);
      await load();
      showMessage(message, '封袋已接收，取件站现可交付。');
    }));
    const waiting = claims.filter(claim => claim.bag_state === 'reserved'
      && claim.pickup_station !== claim.current_station && !claim.transfer_code);
    if (!waiting.length) {
      dispatchBox.innerHTML = '<p class="empty">没有等待发运的封袋。</p>';
      return;
    }
    if (store.user.role !== 'dispatcher') {
      dispatchBox.innerHTML = '<ul class="notes">' + waiting.map(claim => '<li><b>' + escape(claim.seal_id)
        + '</b>' + escape(station(claim.current_station) + ' → ' + station(claim.pickup_station))
        + '</li>').join('') + '</ul>';
      return;
    }
    dispatchBox.innerHTML = '<form id="dispatch"><label>跨站认领单<select name="claim_id">'
      + waiting.map(claim => '<option value="' + claim.id + '">#' + claim.id + ' ' + escape(claim.seal_id)
        + ' · ' + escape(station(claim.current_station) + ' → ' + station(claim.pickup_station)) + '</option>').join('')
      + '</select></label><label>承运车次<input name="carrier_train" required placeholder="D919"></label>'
      + '<button type="submit">绑定车次并发运</button></form>';
    formAction(dispatchBox.querySelector('form'), message, async body => {
      const result = await api.dispatch({...body, claim_id: Number(body.claim_id)});
      await load();
      showMessage(message, '转运单 ' + result.code + ' 已发运。');
    });
  }
  await load();
}
