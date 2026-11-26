import {api} from '../api.js';
import {pageTitle} from '../components/layout.js';
import {status} from '../components/status.js';
import {dateTime, escape, station} from '../format.js';
import {formAction, showMessage} from '../forms.js';
import {store} from '../store.js';

export async function claims(main) {
  main.innerHTML = pageTitle('HANDOVER / 领回', '认领和取件交付', '取件站在柜核对封签。完成交付后，认领单和封袋同时封结。')
    + `<div class="domain-grid"><section class="panel"><h2>已验私密特征的认领单</h2><div id="claim-list"></div></section>
      <aside class="stack"><section class="panel"><h2>凭封签交付</h2>
      <div id="release-message"></div><div id="claim-detail"><p class="empty">选择认领单查看取件条件。</p></div></section>
      <section class="panel"><h2>离柜核对</h2><ul class="notes"><li><b>取件站一致</b>柜员只能交付本站办理的认领。</li>
      <li><b>封袋到站且锁定</b>跨站封袋由接收柜员复扫后才回到可交付状态。</li>
      <li><b>一次性交付</b>已交付封袋的封签仍可在台账查阅。</li></ul></section></aside></div>`;
  const list = main.querySelector('#claim-list');
  const detail = main.querySelector('#claim-detail');
  const message = main.querySelector('#release-message');
  function select(claim) {
    store.selectedClaim = claim.id;
    const mayRelease = store.user.station_code === claim.pickup_station
      && claim.current_station === claim.pickup_station && claim.bag_state === 'reserved';
    detail.innerHTML = '<p><span class="stamp">认领 #' + claim.id + '</span></p><p class="mono">'
      + escape(claim.seal_id) + '</p><p>取件站 <b>' + escape(station(claim.pickup_station)) + '</b> · '
      + status(claim.bag_state) + '</p>' + (mayRelease
      ? '<form class="row-toolbar"><label>现场扫描封签<input name="seal" required></label><button type="submit">确认交付</button></form>'
      : '<p class="empty">' + (claim.released_at ? '交付时间 ' + escape(dateTime(claim.released_at))
        : '所选封袋尚未满足本站交付条件。') + '</p>');
    if (mayRelease) formAction(detail.querySelector('form'), message, async body => {
      await api.release(claim.id, body.seal);
      await refresh();
      showMessage(message, '封袋 ' + claim.seal_id + ' 已核销交付。');
    });
  }
  async function refresh() {
    const rows = await api.claims();
    list.innerHTML = rows.length ? '<div class="table-wrap"><table><thead><tr><th>认领单</th><th>实物封签</th>'
      + '<th>取件站</th><th>封袋状态</th><th>认领状态</th></tr></thead><tbody>' + rows.map(claim =>
        '<tr><td><button class="secondary slim mono" type="button" data-claim="' + claim.id + '">#' + claim.id
        + '</button></td><td class="mono">' + escape(claim.seal_id) + '</td><td>' + escape(station(claim.pickup_station))
        + '</td><td>' + status(claim.bag_state) + '</td><td>' + status(claim.status) + '</td></tr>').join('')
      + '</tbody></table></div>' : '<p class="empty">暂无线索通过核验。请到线索匹配核对私密特征。</p>';
    list.querySelectorAll('[data-claim]').forEach(button => button.addEventListener('click',
      () => select(rows.find(claim => claim.id === Number(button.dataset.claim)))));
    const active = rows.find(claim => claim.id === store.selectedClaim);
    if (active) select(active);
  }
  await refresh();
}
