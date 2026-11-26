import {api} from '../api.js';
import {pageTitle} from '../components/layout.js';
import {status} from '../components/status.js';
import {CATEGORIES} from '../enums.js';
import {escape, station} from '../format.js';
import {formAction, showMessage} from '../forms.js';
import {store} from '../store.js';

function entries(mayClaim) {
  if (!mayClaim) return '<p class="empty">调度和稽核可查阅已受理线索。</p>';
  return `<form id="recall-form">
    <div class="fields"><label>遗失物类别<select name="category">${CATEGORIES.map(item => '<option>' + item + '</option>').join('')}</select></label>
      <label>主色<input name="color" maxlength="32" required placeholder="深蓝"></label></div>
    <div class="fields"><label>乘车日期<input type="date" name="travel_on" required></label>
      <label>已知车次<input name="train_no" placeholder="G216"></label></div>
    <label>可观察描述<textarea name="description" required maxlength="160" placeholder="双肩包 黄色拉链 织布 背带"></textarea></label>
    <button type="submit">提交公开线索</button>
  </form>`;
}

function resultTicket(hit, mayClaim) {
  const canCheck = mayClaim && hit.auditable && hit.bag_state === 'sealed';
  return `<div class="recall-ticket">
    <div><strong class="mono">${escape(hit.seal_id)}</strong><small>${escape(station(hit.current_station))} · ${escape(hit.train_no)}</small></div>
    <div><progress aria-label="相似度" max="1" value="${hit.score}"></progress><small>相似度 ${Math.round(hit.score * 100)}%</small>
      <small>同特征 ${hit.exact_features} · 碰撞桶 ${hit.collision_slots}</small></div>
    ${canCheck ? '<form data-seal="' + escape(hit.seal_id) + '"><input name="answer" type="password"'
      + ' required placeholder="私密特征" minlength="3" aria-label="旅客提供的私密特征"><button type="submit" class="slim">核验</button></form>'
      : '<small>' + (!hit.auditable ? '公开证据不足' : status(hit.bag_state)) + '</small>'}
  </div>`;
}

export async function recall(main) {
  const mayClaim = store.user.role === 'clerk';
  main.innerHTML = pageTitle('OBSERVATION / 线索', '公开线索匹配', '按公开描述、类别、位置标签和车次生成相似封袋。核验前检查同特征与碰撞桶。')
    + `<div class="domain-grid search-grid"><div class="stack"><section class="panel"><h2>录入查找线索</h2>
      <p class="muted">建议把拉链、背带等可见特征分词填写。</p><div id="submit-result"></div>${entries(mayClaim)}
      </section><section class="panel recall-history"><h2>近期线索单</h2><div id="search-history"></div></section>
      </div><section class="panel"><h2>候选分析与核验</h2><p class="muted">检索覆盖乘车日前一天至后两天的在柜封袋。</p>
      <div id="claim-message"></div><div id="results"><p class="empty">提交线索或从历史区选择线索单取得结果。</p></div></section></div>`;
  const result = main.querySelector('#results');
  const message = main.querySelector('#claim-message');
  const history = main.querySelector('#search-history');
  let activeRequest = 0;
  async function select(id, wait) {
    store.selectedSearch = id;
    const requestId = ++activeRequest;
    result.innerHTML = '<p class="empty">正在读取线索单…</p>';
    try {
      let bundle = await api.search(id);
      for (let i = 0; wait && i < 35 && bundle.search.status === 'queued'; i++) {
        await new Promise(resolve => setTimeout(resolve, 400));
        if (requestId !== activeRequest || !result.isConnected) return;
        bundle = await api.search(id);
      }
      if (requestId !== activeRequest || !result.isConnected) return;
      const {search, candidates} = bundle;
      const summary = search.model_summary;
      result.innerHTML = `<div class="recall-head"><div><span class="stamp">线索 #${search.id}</span>
      <p>${escape(search.description)}</p></div>${status(search.status)}</div>
      ${summary ? '<p class="muted mono">FeatureHasher · ' + summary.dimensions + ' 维 · 对比 ' + summary.compared
        + ' 件 · 可核验 ' + summary.usable + ' 件</p>' : ''}
      ${candidates.length ? candidates.map(hit => resultTicket(hit, mayClaim)).join('')
        : '<p class="empty">' + (search.status === 'queued' ? '匹配处理中。可稍后从历史区重新打开。'
          : '当前没有可展示的封袋候选。请核对日期与公开描述。') + '</p>'}`;
      result.querySelectorAll('form[data-seal]').forEach(form => formAction(form, message, async body => {
        const claim = await api.claim({search_id: search.id, seal_id: form.dataset.seal, answer: body.answer});
        store.selectedClaim = claim.id;
        await select(search.id, false);
        message.innerHTML = '<p class="message" role="status">封袋已锁定。'
          + '<a href="#claims">前往认领交付，办理认领单 #' + claim.id + '</a></p>';
      }));
    } catch (error) {
      showMessage(result, error.message, 'error');
    }
  }
  async function refreshHistory() {
    const searches = await api.searches();
    history.innerHTML = searches.length ? '<ul class="notes">' + searches.slice(0, 12).map(search =>
      '<li><button type="button" class="secondary slim mono" data-search="' + search.id + '">#' + search.id
      + '</button> ' + status(search.status) + '<p>' + escape(search.description) + '</p></li>').join('')
      + '</ul>' : '<p class="empty">还没有已受理线索。</p>';
    history.querySelectorAll('[data-search]').forEach(button => button.addEventListener('click',
      () => select(Number(button.dataset.search), true)));
  }
  const form = main.querySelector('#recall-form');
  if (form) formAction(form, main.querySelector('#submit-result'), async body => {
    const ticket = await api.recall({...body, train_no: body.train_no || null});
    await select(ticket.id, true);
    await refreshHistory();
  });
  await refreshHistory();
  if (store.selectedSearch) await select(store.selectedSearch, true);
}
