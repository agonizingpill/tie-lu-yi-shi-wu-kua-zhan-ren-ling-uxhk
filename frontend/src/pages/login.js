import {api} from '../api.js';
import {stationLine} from '../components/stations.js';
import {formAction} from '../forms.js';
import {userSession} from '../store.js';

const route = [{code: 'BAL', display_name: '北砾'}, {code: 'HQG', display_name: '河桥关'},
  {code: 'YSH', display_name: '远沙河'}];

export function loginPage(main, signedIn) {
  main.innerHTML = `<div class="login-grid"><section class="login-cover">
      <p class="eyebrow">BEILI / PROPERTY COUNTER</p>
      <h1>铁路失物，<br>沿线接力归还。</h1>
      <p>登记拾获封签、匹配旅客公开描述，并由两个站点完成封袋交接。</p>
      ${stationLine(route, 'BAL')}
    </section>
    <section class="login-sheet"><h2>柜台登录</h2>
      <p class="muted">使用站点柜员、区段调度或稽核账号。</p>
      <div id="login-message"></div>
      <form id="login-form">
        <label>账号<input type="email" name="email" autocomplete="username" required></label>
        <label>口令<input type="password" name="password" autocomplete="current-password" required></label>
        <button type="submit">进入业务台</button>
      </form>
      <div class="demo-list"><p>演示工作位可自动填入账号和口令。</p><div class="quick">
        <button type="button" class="secondary slim" data-email="beili">北砾柜员</button>
        <button type="button" class="secondary slim" data-email="heqiao">河桥关柜员</button>
        <button type="button" class="secondary slim" data-email="dispatch">区段调度</button>
        <button type="button" class="secondary slim" data-email="audit">票务稽核</button>
      </div></div>
    </section></div>`;
  const form = main.querySelector('#login-form');
  main.querySelectorAll('[data-email]').forEach(button => button.addEventListener('click', () => {
    form.elements.email.value = button.dataset.email + '@rail.test';
    form.elements.password.value = 'RailDemo26';
    form.querySelector('[type=submit]').focus();
  }));
  formAction(form, main.querySelector('#login-message'), async details => {
    const result = await api.login(details);
    userSession(result.token, result.profile);
    await signedIn();
  });
}
