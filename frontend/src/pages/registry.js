import {api} from '../api.js';
import {pageTitle} from '../components/layout.js';
import {status} from '../components/status.js';
import {CATEGORIES, EVENT_NAMES} from '../enums.js';
import {dateTime, escape, station} from '../format.js';
import {formAction, showMessage} from '../forms.js';
import {store} from '../store.js';

const intakeForm = `<form id="intake-form">
  <div class="fields"><label>封签号<input name="seal_id" required placeholder="BL-261123-031"></label>
    <label>拾获车次<input name="train_no" required placeholder="G216"></label></div>
  <div class="fields"><label>类别<select name="category">${CATEGORIES.map(item => '<option>' + item + '</option>').join('')}</select></label>
    <label>主色<input name="color" required maxlength="32" placeholder="深蓝"></label></div>
  <label>拾获日期<input type="date" name="found_on" required></label>
  <label>公开描述<textarea name="description" maxlength="160" required placeholder="织布 双肩包 金属扣"></textarea></label>
  <label>仅用于核验的私密特征<input name="private_mark" type="password" minlength="3" maxlength="80" required autocomplete="off"></label>
  <button type="submit">登记并封袋</button>
</form>`;

function unpackLedger(result) {
  return `<p><span class="stamp">${escape(result.bag.seal_id)}</span> ${status(result.bag.state)}</p><ol class="ledger">${result.events.map(event =>
    '<li><strong>' + escape(EVENT_NAMES[event.action] || event.action) + '</strong>'
    + '<br><time>' + escape(dateTime(event.at)) + ' · ' + escape(event.actor) + '</time>'
    + '<p>' + escape(event.detail) + '</p></li>').join('')}</ol>`;
}

export async function registry(main) {
  main.innerHTML = pageTitle('CUSTODY / 封存', '拾获封袋台账', '封签号随物件流转，公开描述提供线索，封内特征仅用于核验。')
    + `<div class="domain-grid registry"><section class="panel"><h2>沿线在柜与交接</h2><div id="bag-result"></div>
      <div id="bag-table"></div></section><aside class="stack"><section class="panel"><h2>新封袋登记</h2>
      <div id="intake-message"></div>${store.user.role === 'clerk' ? intakeForm : '<p class="empty">请选择左侧封袋查阅交班记录。</p>'}
      </section><section class="panel"><h2>封袋履历</h2><div id="ledger"><p class="empty">点选任一封签查看办理履历。</p></div></section></aside></div>`;
  const panel = main.querySelector('#bag-table');
  const ledger = main.querySelector('#ledger');
  async function displayLedger(seal) {
    try {
      store.selectedSeal = seal;
      ledger.innerHTML = unpackLedger(await api.ledger(seal));
    } catch (error) {
      showMessage(ledger, error.message, 'error');
    }
  }
  async function refresh() {
    const bags = await api.bags();
    panel.innerHTML = bags.length ? '<div class="table-wrap"><table><thead><tr><th>封签</th><th>公开描述</th>'
      + '<th>车次</th><th>当前位置</th><th>状态</th></tr></thead><tbody>' + bags.map(bag =>
        '<tr><td><button class="secondary slim mono" type="button" data-seal="' + escape(bag.seal_id) + '">'
        + escape(bag.seal_id) + '</button></td><td><b>' + escape(bag.category + ' · ' + bag.color)
        + '</b><br><small>' + escape(bag.description) + '</small></td><td class="mono">' + escape(bag.train_no)
        + '</td><td>' + escape(station(bag.current_station)) + '</td><td>' + status(bag.state) + '</td></tr>').join('')
      + '</tbody></table></div>' : '<p class="empty">尚无封袋。站点柜员可登记拾获件。</p>';
    panel.querySelectorAll('[data-seal]').forEach(button => button.addEventListener('click',
      () => displayLedger(button.dataset.seal)));
  }
  const form = main.querySelector('#intake-form');
  if (form) {
    const output = main.querySelector('#intake-message');
    formAction(form, output, async body => {
      const bag = await api.intake(body);
      form.reset();
      await refresh();
      await displayLedger(bag.seal_id);
      showMessage(output, '新封袋 ' + bag.seal_id + ' 已入柜');
    });
  }
  await refresh();
  if (store.selectedSeal) await displayLedger(store.selectedSeal);
}
