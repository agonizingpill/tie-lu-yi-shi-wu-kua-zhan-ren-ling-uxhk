import {STATUS} from '../enums.js';
import {escape} from '../format.js';

export function status(value) {
  return '<span class="state" data-state="' + escape(value) + '">' + escape(STATUS[value] || value) + '</span>';
}
