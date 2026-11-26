import {escape} from '../format.js';
import {ROLES} from '../enums.js';

export const navigation = [
  ['registry', '封袋台账'], ['recall', '线索匹配'], ['transfer', '跨站转运'], ['claims', '认领交付'],
];

export function masthead(user, active) {
  return '<header class="topbar"><div class="frame masthead"><a class="brand" href="#registry">'
    + '<span class="rail-mark mono" aria-hidden="true">北</span><span>北砾铁路拾遗交接</span></a>'
    + (user ? '<div class="profile"><span>' + escape(user.display_name) + ' / ' + escape(ROLES[user.role])
      + '</span><button class="subtle" id="logout" type="button">退出</button></div>' : '') + '</div>'
    + (user ? '<nav class="frame" aria-label="业务导航">' + navigation.map(([key, label]) =>
      '<a href="#' + key + '"' + (active === key ? ' aria-current="page"' : '') + '>' + label + '</a>').join('')
      + '</nav>' : '') + '</header>';
}

export function pageTitle(eyebrow, title, help) {
  return '<header class="page-title"><p class="eyebrow">' + eyebrow + '</p><h1>' + title + '</h1><p>' + help
    + '</p></header>';
}
