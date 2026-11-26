export const ROLES = {clerk: '柜员', dispatcher: '调度', observer: '稽核'};
export const CATEGORIES = ['包袋', '衣物', '数码', '票证', '配件'];
export const STATUS = {
  sealed: '在柜封存', reserved: '认领锁定', in_transit: '转运途中', released: '已交付',
  verified: '已验私密特征', dispatched: '已发运', received: '已收运',
  queued: '待匹配', ranked: '匹配完成', failed: '匹配失败',
};
export const EVENT_NAMES = {seal_created: '建立封袋', proof_rejected: '私密核验拒绝',
  claim_verified: '认领核验', dispatched: '发运', received: '复扫入柜', released: '交付取件人'};
