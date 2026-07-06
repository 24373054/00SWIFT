/* SWIFT Developer Testing System v2 — frontend.
 * "SWIFT financial professional" — deep indigo + gold, institutional.
 * Single-file SPA, vanilla JS. Aligned with official-contract backend:
 * /swift-preval/v2, /swiftrefdata/v4, /swift-apitracker/v4, /alliancecloud/v2.
 * Renders SwAP error envelopes; fetches payment-state metadata from /api/states.
 */
'use strict';

/* ============================================================
 * State + config
 * ============================================================ */
var App = {
  page: 'dashboard',
  states: {},          // code -> {label,color,icon}
  theme: localStorage.getItem('swift-theme') || 'light',
  sidebarCollapsed: localStorage.getItem('swift-sidebar') === 'collapsed',
  toasts: [],
  currentCred: null,   // last-viewed credential (for signed calls)
};

var PAGES = ['dashboard','credentials','catalogue','preval','swiftref','payments','messaging','builder','iso20022','ecny_overview','ecny_wallets','ecny_issuance','ecny_crossborder','ecny_ledger'];
var PAGE_TITLES = {
  dashboard:'Dashboard', credentials:'App Credentials', catalogue:'API Catalogue',
  preval:'Pre-validation', swiftref:'SwiftRef', payments:'GPI Tracker',
  messaging:'Messaging', builder:'Request Builder', iso20022:'ISO 20022 Builder'
};

/* ============================================================
 * Bootstrap
 * ============================================================ */
function boot() {
  document.documentElement.setAttribute('data-theme', App.theme);
  updateThemeIcon();
  if (App.sidebarCollapsed) document.getElementById('sidebar').classList.add('collapsed');

  // Nav clicks
  document.querySelectorAll('.nav-item').forEach(function (el) {
    el.addEventListener('click', function () { navigate(el.dataset.page); closeMobileSidebar(); });
  });
  // Sidebar collapse
  document.getElementById('sidebarToggle').addEventListener('click', toggleSidebar);
  // Mobile menu
  document.getElementById('menuToggle').addEventListener('click', toggleMobileSidebar);
  document.getElementById('sidebarOverlay').addEventListener('click', closeMobileSidebar);
  // Theme
  document.getElementById('themeToggle').addEventListener('click', toggleTheme);

  // Clock
  setInterval(updateClock, 1000); updateClock();
  // Env label
  api('/health').then(function (h) {
    document.getElementById('envLabel').textContent = h.env;
    document.getElementById('connStatus').textContent = h.env === 'live' ? 'Live (real SWIFT)' : 'Connected';
    if (h.env === 'live') document.getElementById('liveBanner').classList.add('show');
  }).catch(function () { document.getElementById('connStatus').textContent = 'Offline'; });

  // Load state metadata (single source of truth for labels/colors)
  loadStates().then(function () { navigate('dashboard'); });
}

/* ============================================================
 * Navigation
 * ============================================================ */
function navigate(page) {
  if (!PAGES.includes(page)) page = 'dashboard';
  App.page = page;
  document.querySelectorAll('.nav-item').forEach(function (e) { e.classList.remove('active'); });
  var nav = document.querySelector('.nav-item[data-page="' + page + '"]');
  if (nav) nav.classList.add('active');
  document.getElementById('pageTitle').textContent = PAGE_TITLES[page] || page;
  document.title = (PAGE_TITLES[page] || page) + ' · SWIFT Dev';
  renderPage(page);
  // scroll content to top on page change
  var vc = document.getElementById('viewContainer'); vc.scrollTop = 0;
}

function renderPage(page) {
  var vc = document.getElementById('viewContainer');
  vc.innerHTML = skeletonFor(page);
  try {
    var result = Pages[page];
    if (!result) { vc.innerHTML = emptyState('Page not found', 'This page does not exist.'); return; }
    var r = result();
    if (r && r.then) {
      r.then(function (html) {
        vc.innerHTML = '<div class="page-enter">' + html + '</div>';
        bindPageEvents(page);
      }).catch(function (e) {
        vc.innerHTML = '<div class="page-enter">' + (e.envelope ? renderErrorEnvelope(e.envelope) : errorBox(e.message)) + '</div>';
      });
    } else {
      vc.innerHTML = '<div class="page-enter">' + r + '</div>';
      bindPageEvents(page);
    }
  } catch (e) {
    vc.innerHTML = '<div class="page-enter">' + errorBox(e.message) + '</div>';
  }
}

function skeletonFor(page) {
  // Generic loading skeleton while page content fetches.
  if (page === 'dashboard') {
    return '<div class="stats-grid">' + repeat(4, '<div class="skeleton skeleton-card"></div>') + '</div>' +
           '<div class="grid-2"><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div></div>';
  }
  return '<div style="padding:24px"><div class="skeleton skeleton-line" style="width:40%"></div>' +
         '<div class="skeleton skeleton-line" style="width:80%"></div>' +
         '<div class="skeleton skeleton-line" style="width:65%"></div>' +
         '<div class="skeleton skeleton-card mt-4"></div></div>';
}

/* ============================================================
 * API layer (wraps fetch, parses SwAP error envelopes)
 * ============================================================ */
function api(path, opts) {
  opts = opts || {};
  opts.headers = opts.headers || {};
  if (!opts.headers['Content-Type'] && opts.body) opts.headers['Content-Type'] = 'application/json';
  return fetch(path, opts).then(function (res) {
    return res.text().then(function (txt) {
      var data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = { raw: txt }; }
      if (!res.ok) {
        var errs = data.errors || [];
        var msg = errs.length ? (errs[0].code + ': ' + errs[0].text) : ('HTTP ' + res.status + ' ' + res.statusText);
        var err = new Error(msg); err.envelope = data; err.status = res.status; throw err;
      }
      return data;
    });
  });
}

/* Signed call: uses /api/dev/sign to obtain signature + token, then calls the endpoint.
 * bodyObj is JSON-stringified. Returns a Promise of the parsed response. */
function signedCall(method, path, bodyObj, scope) {
  var bodyStr = JSON.stringify(bodyObj);
  // need a credential + audience
  if (!App.currentCred) {
    return Promise.reject(new Error('No credential selected. Create one in App Credentials first.'));
  }
  var audience = location.host + path;
  return api('/api/dev/sign', {
    method: 'POST',
    body: JSON.stringify({ consumer_key: App.currentCred.consumer_key, body: bodyStr, audience: audience, scope: scope || '' })
  }).then(function (sr) {
    var headers = { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + sr.access_token, 'X-SWIFT-Signature': sr.signature };
    if (path.indexOf('/swift-preval/') === 0) headers['x-bic'] = 'swhqbebb';
    return fetch(path, { method: method, headers: headers, body: bodyStr }).then(function (res) {
      return res.text().then(function (txt) {
        var data; try { data = txt ? JSON.parse(txt) : {}; } catch (e) { data = { raw: txt }; }
        if (!res.ok) {
          var errs = data.errors || [];
          var msg = errs.length ? (errs[0].code + ': ' + errs[0].text) : ('HTTP ' + res.status);
          var err = new Error(msg); err.envelope = data; throw err;
        }
        return data;
      });
    });
  });
}

/* ============================================================
 * Theme + sidebar + clock
 * ============================================================ */
function toggleTheme() {
  App.theme = App.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('swift-theme', App.theme);
  document.documentElement.setAttribute('data-theme', App.theme);
  updateThemeIcon();
}
function updateThemeIcon() {
  var icon = document.getElementById('themeIcon');
  if (App.theme === 'dark') {
    icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
  } else {
    icon.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
  }
}
function toggleSidebar() {
  App.sidebarCollapsed = !App.sidebarCollapsed;
  localStorage.setItem('swift-sidebar', App.sidebarCollapsed ? 'collapsed' : 'expanded');
  document.getElementById('sidebar').classList.toggle('collapsed', App.sidebarCollapsed);
}
function toggleMobileSidebar() { document.getElementById('sidebar').classList.toggle('open'); document.getElementById('sidebarOverlay').classList.toggle('show'); }
function closeMobileSidebar() { document.getElementById('sidebar').classList.remove('open'); document.getElementById('sidebarOverlay').classList.remove('show'); }
function updateClock() { document.getElementById('clock').textContent = new Date().toLocaleTimeString([], {hour12:false}); }

/* ============================================================
 * Toast queue
 * ============================================================ */
function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toastContainer');
  var t = document.createElement('div'); t.className = 'toast ' + type;
  var icons = { success: '✓', error: '✕', info: 'ℹ' };
  t.innerHTML = '<span style="font-weight:700">' + (icons[type]||'') + '</span><span>' + escapeHtml(msg) + '</span>';
  c.appendChild(t);
  setTimeout(function () { t.classList.add('leaving'); setTimeout(function () { t.remove(); }, 200); }, 3200);
}

/* ============================================================
 * Utilities
 * ============================================================ */
function escapeHtml(s) { return (s == null ? '' : String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function formatTime(iso) { if (!iso) return '—'; try { var d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}); } catch(e){ return iso; } }
function relativeTime(iso) { if (!iso) return '—'; var d = new Date(iso); var s = (Date.now()-d.getTime())/1000; if (s<60) return Math.floor(s)+'s ago'; if (s<3600) return Math.floor(s/60)+'m ago'; if (s<86400) return Math.floor(s/3600)+'h ago'; return Math.floor(s/86400)+'d ago'; }
function copyText(t, btn) {
  navigator.clipboard.writeText(t).then(function () {
    toast('Copied to clipboard', 'success');
    if (btn) { var orig = btn.innerHTML; btn.classList.add('copied'); btn.innerHTML = '✓ Copied'; setTimeout(function () { btn.classList.remove('copied'); btn.innerHTML = orig; }, 1500); }
  });
}
function repeat(n, s) { var o=''; for (var i=0;i<n;i++) o+=s; return o; }
function ellipsis(s, n) { s = String(s||''); return s.length>n ? s.slice(0,n)+'…' : s; }

/* XML/JSON syntax highlighting for code blocks */
function highlightXml(xml) {
  return escapeHtml(xml)
    .replace(/(&lt;\?[^?]*\?&gt;)/g, '<span class="xml-decl">$1</span>')
    .replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span class="xml-comment">$1</span>')
    .replace(/(&lt;\/?)([\w.-]+)/g, '$1<span class="xml-tag">$2</span>')
    .replace(/([\w.-]+)(=)(&quot;[^&]*&quot;)/g, '<span class="xml-attr">$1</span>$2<span class="xml-val">$3</span>');
}
function highlightJson(json) {
  return escapeHtml(json)
    .replace(/(&quot;[^&]*&quot;)(\s*:)/g, '<span style="color:#c4b5fd">$1</span>$2')
    .replace(/:\s*(&quot;[^&]*&quot;)/g, ': <span style="color:#86efac">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span style="color:#fbbf24">$1</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span style="color:#7dd3fc">$1</span>');
}
function prettyJson(obj) { try { return JSON.stringify(obj, null, 2); } catch(e){ return String(obj); } }

/* ============================================================
 * Component helpers (return HTML strings)
 * ============================================================ */
function card(title, bodyHtml, opts) {
  opts = opts || {};
  var header = title ? '<div class="card-header"><span>' + escapeHtml(title) + '</span>' + (opts.headerRight||'') + '</div>' : '';
  return '<div class="card' + (opts.hover?' card-hover':'') + '">' + header + bodyHtml + '</div>';
}
function btn(label, opts) {
  opts = opts || {};
  var cls = 'btn ' + (opts.cls || 'btn-secondary');
  if (opts.size === 'sm') cls += ' btn-sm'; if (opts.size === 'xs') cls += ' btn-xs';
  return '<button class="' + cls + '" id="' + (opts.id||'') + '" ' + (opts.disabled?'disabled':'') + '>' + (opts.icon||'') + escapeHtml(label) + '</button>';
}
function badge(text, cls) { return '<span class="badge ' + (cls||'badge-gray') + '">' + escapeHtml(text) + '</span>'; }
function stateBadge(code) {
  var m = App.states[code] || { label: code, color: '#6b7280' };
  return '<span class="badge" style="background:' + m.color + '22;color:' + m.color + ';border:1px solid ' + m.color + '44">' + escapeHtml(m.label) + '</span>';
}
function methodBadge(m) { return '<span class="method-badge method-' + m + '">' + m + '</span>'; }

function emptyState(title, desc, icon) {
  icon = icon || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
  return '<div class="empty-state">' + icon + '<div class="empty-state-title">' + escapeHtml(title) + '</div><div class="empty-state-desc">' + escapeHtml(desc) + '</div></div>';
}
function errorBox(msg) {
  return '<div class="error-envelope"><div class="error-envelope-title">✕ Error</div><div style="font-size:13px;color:var(--text-2)">' + escapeHtml(msg) + '</div></div>';
}
function renderErrorEnvelope(envelope) {
  if (!envelope || !envelope.errors || !envelope.errors.length) return errorBox('Unknown error');
  var h = '<div class="error-envelope"><div class="error-envelope-title">✕ SWIFT API Error</div><table><thead><tr><th>Code</th><th>Severity</th><th>Text</th></tr></thead><tbody>';
  envelope.errors.forEach(function (e) {
    var sev = e.severity==='Fatal'?'badge-red':e.severity==='Transient'?'badge-yellow':'badge-gray';
    h += '<tr><td><code class="mono">' + escapeHtml(e.code) + '</code></td><td><span class="badge ' + sev + '">' + escapeHtml(e.severity) + '</span></td><td>' + escapeHtml(e.text) + '</td></tr>';
  });
  h += '</tbody></table></div>';
  return h;
}
function codeBlock(content, lang) {
  var html = lang === 'xml' ? highlightXml(content) : (lang === 'json' ? highlightJson(content) : escapeHtml(content));
  return '<div class="code-block">' + html + '</div>';
}
function field(label, inputHtml, hint) {
  return '<div class="form-group"><label>' + escapeHtml(label) + '</label>' + inputHtml + (hint?'<div class="form-hint">' + escapeHtml(hint) + '</div>':'') + '</div>';
}
function input(id, val, placeholder, opts) {
  opts = opts || {};
  var extra = opts.maxlength ? ' maxlength="' + opts.maxlength + '"' : '';
  return '<input id="' + id + '" value="' + escapeHtml(val||'') + '" placeholder="' + escapeHtml(placeholder||'') + '"' + extra + '>';
}
function select(id, options, selected) {
  var h = '<select id="' + id + '">';
  options.forEach(function (o) {
    var v = typeof o === 'string' ? o : o.value, l = typeof o === 'string' ? o : o.label;
    h += '<option value="' + escapeHtml(v) + '"' + (v===selected?' selected':'') + '>' + escapeHtml(l) + '</option>';
  });
  return h + '</select>';
}
function kvDisplay(label, value, copyable) {
  var copy = copyable ? ' <button class="copy-btn" onclick="copyText(\'' + escapeHtml(String(value).replace(/'/g,"\\'")) + '\', this)">Copy</button>' : '';
  return '<div><label>' + escapeHtml(label) + '</label><div class="flex-row gap-2"><div class="kv-display flex-1">' + escapeHtml(value) + '</div>' + copy + '</div></div>';
}

/* Simple sortable/paginated table renderer */
function dataTable(columns, rows, opts) {
  opts = opts || {};
  if (!rows.length) return emptyState(opts.emptyTitle||'No data', opts.emptyDesc||'There is nothing to show here yet.');
  var h = '<div class="table-wrap"><table><thead><tr>';
  columns.forEach(function (c) {
    h += '<th' + (c.sortable!==false?' class="sortable" onclick="sortTable(this, ' + c.key + ')"':'')+'>' + escapeHtml(c.label) + '</th>';
  });
  h += '</tr></thead><tbody>';
  rows.forEach(function (r) {
    h += '<tr>';
    columns.forEach(function (c) { h += '<td>' + (c.render ? c.render(r) : escapeHtml(r[c.key])) + '</td>'; });
    h += '</tr>';
  });
  h += '</tbody></table></div>';
  return h;
}

/* ============================================================
 * State metadata
 * ============================================================ */
function loadStates() {
  return api('/api/states').then(function (r) {
    (r.states || []).forEach(function (s) { App.states[s.code] = s; });
  }).catch(function () {});
}

/* ============================================================
 * Pages registry (defined in pages section below)
 * ============================================================ */
var Pages = {};

/* ============================================================
 * e-CNY: shared helpers
 * ============================================================ */
function ecnyApi(path, opts) {
  opts = opts || {};
  opts.headers = opts.headers || {};
  opts.headers['X-Admin-Token'] = 'dev';
  if (opts.body && !opts.headers['Content-Type']) opts.headers['Content-Type'] = 'application/json';
  return api(path, opts);
}
function fenToYuan(fen) { return (fen / 100).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
function tierBadge(tier) {
  var map = {1: ['badge-gold','一类·强实名'], 2: ['badge-blue','二类·中实名'], 3: ['badge-gray','三类·匿名']};
  var m = map[tier] || ['badge-gray','未知'];
  return '<span class="badge ' + m[0] + '">' + m[1] + '</span>';
}

/* ============================================================
 * Page: e-CNY 概览
 * ============================================================ */
Pages.ecny_overview = function () {
  return ecnyApi('/api/ecny/stats').then(function (s) {
    var h = '<div class="stats-grid">';
    h += statCard('净发行额', '¥ ' + Number(s.net_issuance_cny).toLocaleString('zh-CN'), 'CNY', 'gold');
    h += statCard('钱包总数', s.wallets_total, '个', 'blue');
    h += statCard('账本交易', s.ledger_transactions, '笔', 'green');
    h += statCard('合规报告', s.compliance_reports, '条', 'yellow');
    h += '</div>';
    h += card('系统说明', '<div class="form-hint">' +
      '<p>本系统是<b>数字人民币（e-CNY）跨境支付系统</b>技术原型，底层采用中心化/联盟账本（类 mBridge 联邦节点模型）。</p>' +
      '<p>跨境模式：<b>双边/多边互操作</b>，支持 mBridge 多 CBDC 原子结算（PvP）与 CIPS 人民币跨境双边通道。</p>' +
      '<p>保留 SWIFT 接口为<b>传统桥接</b>通道，ISO 20022 pacs.008 报文兼容。</p>' +
      '<p>定位：面向真实对接的技术原型，含 KYC/AML/可控匿名/监管报送预留。当前为沙盒，不接真实资金网。</p></div>');
    h += card('快速操作', '<div class="form-row">' +
      '<button class="primary-btn" onclick="navigate(\'ecny_issuance\')">央行发行</button>' +
      '<button class="secondary-btn" onclick="navigate(\'ecny_wallets\')">开立钱包</button>' +
      '<button class="secondary-btn" onclick="navigate(\'ecny_crossborder\')">发起跨境</button>' +
      '<button class="secondary-btn" onclick="navigate(\'ecny_ledger\')">账本浏览器</button>' +
      '</div>');
    return h;
  });
};

/* ============================================================
 * Page: 数字钱包
 * ============================================================ */
Pages.ecny_wallets = function () {
  return ecnyApi('/api/ecny/wallets').then(function (wallets) {
    var h = card('开立数字钱包', '' +
      '<div class="form-row">' +
        '<label>分级 <select id="ecnyTier" class="form-input">' +
          '<option value="3">三类（小额匿名）</option>' +
          '<option value="2">二类（中实名）</option>' +
          '<option value="1">一类（强实名·大额）</option>' +
        '</select></label>' +
        '<label>运营机构账户 <input id="ecnyOpAcct" class="form-input" value="acct-op-icbc" placeholder="acct-op-xxx"></label>' +
        '<label>持有人姓名（一类/二类必填） <input id="ecnyHolderName" class="form-input" placeholder="张三"></label>' +
      '</div>' +
      '<div class="form-hint mt-2">三类钱包匿名，不关联身份；一类/二类需 KYC 实名。限额：三类单笔≤200元，二类≤1000元，一类≤50000元。</div>' +
      '<button class="primary-btn mt-3" id="btnEcnyOpenWallet">开立钱包</button>');
    h += card('钱包列表', wallets.length === 0 ? emptyState('暂无钱包', '点击上方开立第一个数字钱包') :
      '<table class="data-table"><thead><tr><th>钱包 ID</th><th>分级</th><th>余额</th><th>状态</th><th>运营机构</th></tr></thead><tbody>' +
      wallets.map(function (w) {
        return '<tr><td><code>' + escapeHtml(w.wallet_id.slice(0,16)) + '…</code></td><td>' + tierBadge(w.tier) + '</td><td>¥ ' + fenToYuan(w.balance) + '</td><td><span class="badge badge-green">' + escapeHtml(w.status) + '</span></td><td>' + (w.operator_id||'-') + '</td></tr>';
      }).join('') + '</tbody></table>');
    return h;
  });
};

/* ============================================================
 * Page: 央行发行台
 * ============================================================ */
Pages.ecny_issuance = function () {
  return ecnyApi('/api/ecny/ledger-accounts').then(function (accts) {
    var opList = accts.filter(function(a){return a.owner_type==='operator';}).map(function(a){return '<option value="'+escapeHtml(a.account_id)+'">'+escapeHtml(a.owner_ref)+' ('+escapeHtml(a.currency)+')</option>';}).join('');
    var h = card('央行发行 / 回笼', '' +
      '<div class="form-hint">央行向运营机构发行（mint）e-CNY，或运营机构回笼（burn）给央行。单位：分（1 元 = 100 分）。</div>' +
      '<div class="form-row mt-3">' +
        '<label>操作 <select id="ecnyIssueAction" class="form-input">' +
          '<option value="mint">发行 mint（央行→运营机构）</option>' +
          '<option value="burn">回笼 burn（运营机构→央行）</option>' +
          '<option value="issue_to_wallet">兑换到钱包（运营机构→钱包）</option>' +
          '<option value="redeem_from_wallet">钱包兑回（钱包→运营机构）</option>' +
        '</select></label>' +
        '<label>运营机构账户 <select id="ecnyIssueAcct" class="form-input">' + opList + '</select></label>' +
        '<label>金额（分） <input id="ecnyIssueAmt" class="form-input" type="number" value="100000" min="1"></label>' +
        '<label>钱包ID（兑换/兑回时必填） <input id="ecnyIssueWallet" class="form-input" placeholder="wlt-xxx"></label>' +
      '</div>' +
      '<button class="primary-btn mt-3" id="btnEcnyIssue">执行</button>' +
      '<div id="ecnyIssueResult" class="mt-3"></div>');
    h += card('运营机构账户', accts.length === 0 ? emptyState('暂无账户','先在 API Catalogue 或通过 /api/ecny/provision-operator 创建') :
      '<table class="data-table"><thead><tr><th>账户 ID</th><th>类型</th><th>归属</th><th>币种</th><th>余额（分）</th></tr></thead><tbody>' +
      accts.map(function(a){return '<tr><td><code>'+escapeHtml(a.account_id)+'</code></td><td>'+escapeHtml(a.owner_type)+'</td><td>'+escapeHtml(a.owner_ref||'-')+'</td><td>'+escapeHtml(a.currency)+'</td><td>'+a.balance+'</td></tr>';}).join('') +
      '</tbody></table>');
    return h;
  });
};

/* ============================================================
 * Page: 跨境支付
 * ============================================================ */
Pages.ecny_crossborder = function () {
  return ecnyApi('/api/ecny/wallets').then(function (wallets) {
    var wOpts = wallets.map(function(w){return '<option value="'+escapeHtml(w.wallet_id)+'">'+escapeHtml(w.wallet_id.slice(0,12))+'… (¥'+fenToYuan(w.balance)+')</option>';}).join('');
    var h = card('发起跨境支付', '' +
      '<div class="form-hint">选择桥接通道：mBridge（多 CBDC 原子 PvP 结算，外币）或 CIPS（人民币双边通道）。留空自动路由。</div>' +
      '<div class="form-row mt-3">' +
        '<label>付款钱包 <select id="ecnyCbFrom" class="form-input">' + wOpts + '</select></label>' +
        '<label>收款账户 <input id="ecnyCbTo" class="form-input" value="acct-op-hkd" placeholder="acct-op-xxx"></label>' +
        '<label>金额（分） <input id="ecnyCbAmt" class="form-input" type="number" value="5000" min="1"></label>' +
        '<label>目标币种 <select id="ecnyCbCcy" class="form-input"><option>HKD</option><option>THB</option><option>AED</option><option>USD</option><option>EUR</option><option>CNY</option></select></label>' +
        '<label>通道（可选） <select id="ecnyCbChannel" class="form-input"><option value="">自动</option><option value="mbridge">mBridge</option><option value="cips">CIPS</option></select></label>' +
        '<label>对手方 <input id="ecnyCbCp" class="form-input" placeholder="HKMA-Bank"></label>' +
      '</div>' +
      '<button class="primary-btn mt-3" id="btnEcnyCb">发起跨境</button>' +
      '<div id="ecnyCbResult" class="mt-3"></div>');
    h += card('桥接通道状态', '<div id="ecnyChannels">加载中…</div>');
    h += card('UETR 追踪', '<div class="form-row"><input id="ecnyTrackUetr" class="form-input" placeholder="粘贴 UETR"><button class="secondary-btn" id="btnEcnyTrack">追踪</button></div><div id="ecnyTrackResult" class="mt-3"></div>');
    return h;
  }).then(function(html){
    return ecnyApi('/ecny/v1/bridge/channels').then(function(ch){
      var wrap = '<table class="data-table"><thead><tr><th>通道</th><th>类型</th><th>对手方</th><th>币种对</th><th>汇率</th><th>状态</th></tr></thead><tbody>';
      wrap += ch.channels.map(function(c){return '<tr><td><code>'+escapeHtml(c.channel_id)+'</code></td><td>'+escapeHtml(c.channel_type)+'</td><td>'+escapeHtml(c.counterparty||'-')+'</td><td>'+escapeHtml(c.currency_pair)+'</td><td>'+(c.fx_rate.rate||'-')+'</td><td><span class="badge badge-green">'+escapeHtml(c.status)+'</span></td></tr>';}).join('');
      wrap += '</tbody></table>';
      return html.replace('<div id="ecnyChannels">加载中…</div>', wrap);
    });
  });
};

/* ============================================================
 * Page: 账本浏览器
 * ============================================================ */
Pages.ecny_ledger = function () {
  return ecnyApi('/ecny/v1/ledger/transactions').then(function (txs) {
    var h = card('账本交易流水', txs.length === 0 ? emptyState('暂无交易','先在央行发行台执行一笔发行') :
      '<table class="data-table"><thead><tr><th>交易 ID</th><th>类型</th><th>状态</th><th>金额</th><th>币种</th><th>借方</th><th>贷方</th><th>UETR</th><th>时间</th></tr></thead><tbody>' +
      txs.map(function(t){
        return '<tr><td><code>'+escapeHtml(t.tx_id.slice(0,12))+'…</code></td><td>'+escapeHtml(t.tx_type)+'</td><td><span class="badge '+(t.status==='settled'?'badge-green':'badge-yellow')+'">'+escapeHtml(t.status)+'</span></td><td>'+fenToYuan(t.amount)+'</td><td>'+escapeHtml(t.currency)+'</td><td><code>'+(t.from_account?escapeHtml(t.from_account.slice(0,12))+'…':'-')+'</code></td><td><code>'+(t.to_account?escapeHtml(t.to_account.slice(0,12))+'…':'-')+'</code></td><td>'+(t.uetr?'<code>'+escapeHtml(t.uetr.slice(0,8))+'…</code>':'-')+'</td><td>'+escapeHtml(t.created_at)+'</td></tr>';
      }).join('') + '</tbody></table>');
    h += card('合规报告', '<div id="ecnyReports">加载中…</div>');
    return h;
  }).then(function(html){
    return ecnyApi('/ecny/v1/compliance/reports').then(function(reps){
      var body = reps.length===0 ? emptyState('暂无合规报告','大额/跨境交易将自动生成报告') :
        '<table class="data-table"><thead><tr><th>报告 ID</th><th>类型</th><th>金额</th><th>阈值</th><th>详情</th><th>时间</th></tr></thead><tbody>' +
        reps.map(function(r){return '<tr><td><code>'+escapeHtml(r.report_id.slice(0,12))+'…</code></td><td><span class="badge badge-yellow">'+escapeHtml(r.report_type)+'</span></td><td>¥ '+fenToYuan(r.amount)+'</td><td>'+(r.threshold?'¥ '+fenToYuan(r.threshold):'-')+'</td><td><code>'+escapeHtml(JSON.stringify(r.details).slice(0,40))+'</code></td><td>'+escapeHtml(r.created_at)+'</td></tr>';}).join('') +
        '</tbody></table>';
      return html.replace('<div id="ecnyReports">加载中…</div>', body);
    });
  });
};



/* ============================================================
 * Page: Dashboard
 * ============================================================ */
Pages.dashboard = function () {
  return api('/api/dashboard/stats').then(function (s) {
    var h = '<div class="stats-grid">';
    h += statCard(s.app_credentials, 'App Credentials', 'key');
    h += statCard(s.active_tokens, 'Active Tokens', 'shield');
    h += statCard(s.total_api_requests, 'API Requests', 'activity');
    h += statCard(s.total_payments, 'Tracked Payments', 'clock');
    h += '</div>';
    h += '<div class="grid-2">';
    h += card('Payment State Distribution', (function(){
      if (!s.total_payments) return emptyState('No payments yet', 'Inject a payment from the GPI Tracker page.');
      var entries = Object.entries(s.payments_by_state || {});
      var total = entries.reduce(function(a,e){return a+e[1];},0) || 1;
      var bar = '<div class="dist-bar">';
      entries.forEach(function(e){ var m=App.states[e[0]]||{color:'#6b7280'}; bar += '<div class="dist-bar-segment" style="width:'+(e[1]/total*100)+'%;background:'+m.color+'" title="'+escapeHtml(e[0])+': '+e[1]+'"></div>'; });
      bar += '</div>';
      var legend = '';
      entries.forEach(function(e){ legend += '<div class="flex-between mt-2"><div class="flex-row gap-2">'+stateBadge(e[0])+'</div><span style="font-weight:600;color:var(--text)">'+e[1]+'</span></div>'; });
      return bar + legend;
    })(), {headerRight: badge(s.total_payments, 'badge-gray')});
    h += card('Recent API Requests', (function(){
      if (!s.recent_requests || !s.recent_requests.length) return emptyState('No requests yet', 'API calls will appear here.');
      var t = '<div class="table-wrap"><table><thead><tr><th>API</th><th>Method</th><th>Endpoint</th><th>Status</th><th>Latency</th><th>When</th></tr></thead><tbody>';
      s.recent_requests.forEach(function(r){
        var sb = r.status<300?'badge-green':r.status<500?'badge-yellow':'badge-red';
        var latColor = r.latency_ms<100?'var(--success)':r.latency_ms<500?'var(--warning)':'var(--danger)';
        var latPct = Math.min(r.latency_ms/500*100,100);
        t += '<tr><td>'+escapeHtml(r.api_name)+'</td><td>'+methodBadge(r.method)+'</td><td class="mono muted">'+escapeHtml(r.endpoint)+'</td><td><span class="badge '+sb+'">'+r.status+'</span></td><td><span class="lat-bar"><span class="lat-bar-track"><span class="lat-bar-fill" style="width:'+latPct+'%;background:'+latColor+'"></span></span><span class="mono muted">'+r.latency_ms+'ms</span></span></td><td class="muted nowrap">'+relativeTime(r.created_at)+'</td></tr>';
      });
      return t + '</tbody></table></div>';
    })(), {headerRight: badge(s.total_api_requests, 'badge-gray')});
    h += '</div>';
    return h;
  });
};
function statCard(val, label, iconType) {
  var icons = {
    key:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.778-7.778zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>',
    shield:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    activity:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    clock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
  };
  return '<div class="stat-card"><div style="display:flex;justify-content:space-between;align-items:start"><div><div class="stat-value">'+escapeHtml(val)+'</div><div class="stat-label">'+escapeHtml(label)+'</div></div><div style="color:var(--primary);opacity:.5">'+(icons[iconType]||'')+'</div></div></div>';
}

/* ============================================================
 * Page: Credentials
 * ============================================================ */
Pages.credentials = function () {
  return api('/api/credentials').then(function (creds) {
    var h = card('Create App Credential',
      '<div class="form-row">' +
        field('App Name', input('credAppName', '', 'e.g. My Payment App')) +
        field('Environment', select('credEnv', [{value:'sandbox',label:'Sandbox'},{value:'pilot',label:'Pilot'},{value:'live',label:'Live'}], 'sandbox')) +
      '</div><div class="form-hint mb-3">Sandbox auto-provisions a mock PKI certificate (CA-signed) so the full JWT-Bearer OAuth flow works without a real SWIFT cert.</div>' +
      btn('Generate Credentials', {cls:'btn-primary', id:'btnCreateCred', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>'})
    );
    h += card('Your App Credentials', creds.length ? '<div class="flex-col">'+creds.map(credCard).join('')+'</div>' : emptyState('No credentials yet', 'Create one above to get started.'), {headerRight: badge(creds.length+' total', 'badge-gray')});
    return h;
  });
};
function credCard(c) {
  var isActive = App.currentCred && App.currentCred.consumer_key === c.consumer_key;
  return '<div style="border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--sp-4);background:var(--surface-2)">' +
    '<div class="flex-between mb-3"><div class="flex-row gap-2"><span style="font-weight:600;color:var(--text)">'+escapeHtml(c.app_name)+'</span>'+badge(c.environment, 'badge-blue')+(isActive?badge('selected','badge-gold'):'')+'</div><div class="flex-row gap-2">' +
      btn('Use', {cls: isActive?'btn-secondary':'btn-ghost', size:'sm', id:'useCred_'+c.id}) +
      btn('Delete', {cls:'btn-danger', size:'sm', id:'delCred_'+c.id}) +
    '</div></div>' +
    '<div class="form-row mb-2">' + kvDisplay('Consumer Key', c.consumer_key, true) + kvDisplay('Consumer Secret', c.consumer_secret, true) + '</div>' +
    (c.cert_subject ? '<div class="mt-2">' + kvDisplay('Cert Subject (JWT sub)', c.cert_subject, true) + '</div>' : '') +
    '<div class="form-hint mt-2">Created '+relativeTime(c.created_at)+(c.last_used?' · last used '+relativeTime(c.last_used):' · never used')+'</div>' +
  '</div>';
}

/* ============================================================
 * Page: Catalogue
 * ============================================================ */
Pages.catalogue = function () {
  return api('/api/catalogue').then(function (cat) {
    var h = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:var(--sp-4)">';
    cat.apis.forEach(function (a) {
      h += '<div class="card card-hover"><div class="flex-between mb-3"><div><div style="font-weight:600;font-size:var(--fs-md);color:var(--text)">'+escapeHtml(a.product)+'</div><div class="form-hint mono">Base: '+escapeHtml(a.base_path)+'</div></div>'+badge('v'+a.version, 'badge-gray')+'</div>';
      h += '<div class="flex-col" style="gap:6px;margin-bottom:var(--sp-3)">';
      a.endpoints.forEach(function (e) {
        h += '<div class="flex-row" style="gap:var(--sp-2);align-items:flex-start"><div style="min-width:48px">'+methodBadge(e.method)+'</div><div style="flex:1;min-width:0"><div class="mono" style="font-size:var(--fs-xs);color:var(--text);word-break:break-all">'+escapeHtml(a.base_path+e.path)+'</div><div class="form-hint">'+escapeHtml(e.desc)+'</div></div></div>';
      });
      h += '</div><div class="flex-wrap flex-row" style="gap:4px">';
      (a.scopes || []).forEach(function (s) { h += badge(s, 'badge-purple'); });
      h += '</div></div>';
    });
    return h + '</div>';
  });
};

/* ============================================================
 * Page: SwiftRef
 * ============================================================ */
Pages.swiftref = function () {
  var types = [
    {value:'bic_validity', label:'BIC Validity'}, {value:'bic_details', label:'BIC Details'},
    {value:'iban_validity', label:'IBAN Validity'}, {value:'iban_bic', label:'IBAN to BIC'},
    {value:'ccy_validity', label:'Currency Validity'}, {value:'ccy_details', label:'Currency Details'}
  ];
  var h = card('SwiftRef Reference Lookup',
    '<div class="mb-3">' + (App.currentCred ? '<span class="badge badge-gold">Using: '+escapeHtml(App.currentCred.app_name)+'</span>' : '<span class="badge badge-yellow">Select a credential in App Credentials</span>') + ' <span class="form-hint">Read lookups require a bearer token (swift.swiftref scope)</span></div>' +
    '<div class="form-row">' +
      field('Lookup Type', select('srType', types, 'bic_validity')) +
      field('Value', input('srVal', 'DEUTDEFFXXX', 'e.g. DEUTDEFFXXX')) +
    '</div>' +
    btn('Lookup', {cls:'btn-primary', id:'btnSr', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'}) +
    '<div class="form-hint mt-2">No auth required for read lookups in sandbox. Results render as structured fields.</div>'
  );
  h += card('Result', '<div id="srResult">'+emptyState('Run a lookup', 'Enter a BIC/IBAN/currency above and click Lookup.')+'</div>');
  return Promise.resolve(h);
};

/* ============================================================
 * Page: Payments (GPI Tracker)
 * ============================================================ */
Pages.payments = function () {
  return api('/api/payments').then(function (ps) {
    var h = card('Inject Test Payment',
      '<div class="form-row">' + field('Amount', input('pmAmt', '10000.00')) + field('Currency', input('pmCcy', 'EUR')) + '</div>' +
      '<div class="form-row">' + field('Debtor Agent BIC', input('pmD', 'BANKDEFFXXX')) + field('Creditor Agent BIC', input('pmC', 'BANKFRPPXXX')) + '</div>' +
      btn('Inject Payment', {cls:'btn-primary', id:'btnInject', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>'}) +
      '<div class="form-hint mt-2">Creates a PDNG payment so tracker endpoints can query/mutate it. Real SWIFT payments originate via Messaging; this is a mock convenience.</div>'
    );
    var cols = [
      {label:'UETR', key:'uetr', render:function(p){return '<span class="mono">'+escapeHtml(ellipsis(p.uetr,18))+'</span>';}},
      {label:'Status', key:'transaction_status', render:function(p){return stateBadge(p.transaction_status);}},
      {label:'Amount', key:'amount', render:function(p){return escapeHtml(p.amount+' '+p.currency);}},
      {label:'Route', key:'debtor_agent', render:function(p){return '<span class="mono muted" style="font-size:11px">'+escapeHtml(p.debtor_agent+' to '+p.creditor_agent)+'</span>';}},
      {label:'Updated', key:'updated_at', render:function(p){return '<span class="muted nowrap">'+relativeTime(p.updated_at)+'</span>';}}
    ];
    h += card('Tracked Payments', dataTable(cols, ps, {emptyTitle:'No payments', emptyDesc:'Inject a payment above to start tracking.'}), {headerRight: badge(ps.length+' total', 'badge-gray')});
    return h;
  });
};

/* ============================================================
 * Page: Pre-validation (REAL signed call via /api/dev/sign)
 * ============================================================ */
Pages.preval = function () {
  var credNote = App.currentCred
    ? '<div class="badge badge-gold">Using: ' + escapeHtml(App.currentCred.app_name) + '</div>'
    : '<div class="badge badge-yellow">No credential selected — create one in App Credentials first</div>';
  var h = card('Payment Instruction Validation',
    '<div class="mb-3">' + credNote + ' <span class="form-hint">POST /swift-preval/v2/payment/payment-instruction · requires x-bic + X-SWIFT-Signature</span></div>' +
    '<div class="form-row">' + field('Amount', input('pvAmt', '10000.00')) + field('Currency', input('pvCcy', 'EUR', '', {maxlength:3})) + '</div>' +
    '<div class="form-row">' + field('Debtor Agent Country', input('pvDc', 'DE', '', {maxlength:2})) + field('Creditor Agent Country', input('pvCc', 'FR', '', {maxlength:2})) + '</div>' +
    '<div class="form-row">' + field('Creditor Agent BIC', input('pvBic', 'BNPAFRPP')) + field('Creditor Account (IBAN)', input('pvAcc', 'FR7630006000011234567890189')) + '</div>' +
    field('UETR (optional)', input('pvUetr', '', 'auto-generated if blank')) +
    btn('Validate Payment Instruction', {cls:'btn-primary', id:'btnPreval', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>'})
  );
  h += card('Validation Result', '<div id="prevalResult">'+emptyState('Run a validation', 'The structured PaymentInstructionValidation response will appear here.')+'</div>');
  return Promise.resolve(h);
};

/* ============================================================
 * Page: Messaging
 * ============================================================ */
Pages.messaging = function () {
  // Distributions require a bearer token; in sandbox the dev-sign helper can mint one.
  var credNote = App.currentCred
    ? '<div class="badge badge-gold">Using: ' + escapeHtml(App.currentCred.app_name) + '</div>'
    : '<div class="badge badge-yellow">Select a credential in App Credentials to send FIN messages</div>';
  var h = card('Send FIN Message',
    '<div class="mb-3">' + credNote + ' <span class="form-hint">POST /alliancecloud/v2/fin/messages · signed</span></div>' +
    '<div class="form-row">' + field('Sender Reference (UUMID)', input('msgRef', 'UUMID-001', '', {maxlength:70})) + field('Message Type', select('msgType', ['fin.103','fin.202.COV','fin.999','fin.101'], 'fin.103')) + '</div>' +
    '<div class="form-row">' + field('Sender (BIC12)', input('msgSender', 'BANKDEFFXXXX', '', {maxlength:12})) + field('Receiver (BIC12)', input('msgReceiver', 'BANKFRPPXXXX', '', {maxlength:12})) + '</div>' +
    field('Network Priority', select('msgPrio', ['Normal','Urgent','System'], 'Normal')) +
    btn('Send FIN Message', {cls:'btn-primary', id:'btnSendMsg', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>'})
  );
  h += '<div id="msgDistWrap">' + card('Distributions (Inbox)', '<div id="msgDists">'+emptyState('No distributions', 'Send a FIN message above, or distributions require a bearer token.')+'</div>') + '</div>';
  // Try to load distributions (will fail without token; that's fine)
  loadDistributions();
  return Promise.resolve(h);
};
function loadDistributions() {
  if (!App.currentCred) return;
  // Use dev-sign to get a token (no body to sign for GET, but helper mints token)
  api('/api/dev/sign', {method:'POST', body: JSON.stringify({consumer_key: App.currentCred.consumer_key, body:'', audience: location.host+'/alliancecloud/v2/distributions', scope:'swift.messaging'})}).then(function(sr){
    return fetch('/alliancecloud/v2/distributions', {headers:{'Authorization':'Bearer '+sr.access_token}});
  }).then(function(res){ return res.json(); }).then(function(r){
    var dists = r.distributions || [];
    var el = document.getElementById('msgDists');
    if (!el) return;
    if (!dists.length) { el.innerHTML = emptyState('No distributions', 'Send a FIN message to see it here.'); return; }
    var cols = [
      {label:'Distribution ID', key:'distribution_id', render:function(d){return '<span class="mono">'+escapeHtml(ellipsis(d.distribution_id,16))+'</span>';}},
      {label:'Service', key:'service'},
      {label:'Sender to Receiver', key:'sender', render:function(d){return '<span class="mono muted" style="font-size:11px">'+escapeHtml((d.sender||'')+' to '+(d.receiver||''))+'</span>';}},
      {label:'Status', key:'status', render:function(d){return badge(d.status, d.status==='acked'?'badge-green':d.status==='naked'?'badge-red':'badge-gray');}},
      {label:'Created', key:'created_at', render:function(d){return '<span class="muted nowrap">'+relativeTime(d.created_at)+'</span>';}}
    ];
    el.innerHTML = dataTable(cols, dists, {emptyTitle:'No distributions', emptyDesc:'Send a FIN message to see it here.'});
  }).catch(function(){ /* silent */ });
}

/* ============================================================
 * Page: Request Builder
 * ============================================================ */
Pages.builder = function () {
  var h = card('API Request Builder',
    '<div class="flex-row mb-3" style="gap:var(--sp-2)">' +
      select('reqMethod', ['GET','POST','PATCH','DELETE'], 'GET') +
      input('reqUrl', '/api/dashboard/stats', '/api/dashboard/stats', {}) +
      btn('Send', {cls:'btn-primary', id:'btnSend', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'}) +
    '</div>' +
    '<div class="tabs"><div class="tab active" data-rtab="headers">Headers</div><div class="tab" data-rtab="body">Body</div><div class="tab" data-rtab="history">History</div></div>' +
    '<div id="reqHeadersPanel"><textarea id="reqHeaders" style="min-height:100px">{\n  "Accept": "application/json"\n}</textarea></div>' +
    '<div id="reqBodyPanel" style="display:none"><textarea id="reqBody" style="min-height:140px">{}</textarea></div>' +
    '<div id="reqHistoryPanel" style="display:none"><div id="reqHistory">'+emptyState('No history','Sent requests will be listed here.')+'</div></div>' +
    '<div class="mt-3 flex-row">' + btn('Copy as cURL', {cls:'btn-secondary', size:'sm', id:'btnCurl'}) + '</div>'
  );
  h += card('Response', '<div id="respContainer">'+emptyState('Send a request','The response will appear here with syntax highlighting.')+'</div>', {headerRight:'<span id="respMeta" class="form-hint"></span>'});
  return Promise.resolve(h);
};

/* ============================================================
 * Page: ISO 20022 Builder
 * ============================================================ */
Pages.iso20022 = function () {
  var h = card('ISO 20022 — pacs.008 Builder',
    '<div class="form-row">' + field('Amount', input('isoAmt', '10000.00')) + field('Currency', input('isoCcy', 'EUR')) + '</div>' +
    '<div class="form-row">' + field('Debtor BIC', input('isoD', 'BANKDEFFXXX')) + field('Creditor BIC', input('isoC', 'BANKFRPPXXX')) + '</div>' +
    '<div class="form-row">' + field('Debtor Name', input('isoDname', 'Acme Corp GmbH')) + field('Creditor Name', input('isoCname', 'Widget Industries SA')) + '</div>' +
    btn('Generate pacs.008', {cls:'btn-primary', id:'btnIso', icon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>'}) +
    '<div class="form-hint mt-2">Generates a pacs.008.001.10 message via the backend escape-safe builder + XSD validation.</div>'
  );
  h += card('Generated pacs.008', '<div id="isoOutput">'+emptyState('No message yet','Generate a pacs.008 to see the ISO 20022 XML with syntax highlighting.')+'</div>');
  return Promise.resolve(h);
};

/* ============================================================
 * Event binding per page
 * ============================================================ */
function bindPageEvents(page) {
  if (page === 'credentials') {
    var b = document.getElementById('btnCreateCred');
    if (b) b.onclick = function () {
      var n = document.getElementById('credAppName').value.trim();
      var e = document.getElementById('credEnv').value;
      if (!n) { toast('App name required', 'error'); return; }
      b.disabled = true; b.textContent = 'Generating...';
      api('/api/credentials', {method:'POST', body: JSON.stringify({app_name:n, environment:e})}).then(function(r){
        App.currentCred = r;
        toast('Credentials created (mock PKI cert auto-provisioned)', 'success');
        navigate('credentials');
      }).catch(function(e){ toast(e.message, 'error'); b.disabled=false; b.textContent='Generate Credentials'; });
    };
    // Use / Delete buttons
    document.querySelectorAll('[id^="useCred_"]').forEach(function(btn){
      btn.onclick = function(){
        var id = btn.id.split('_')[1];
        api('/api/credentials').then(function(creds){
          var c = creds.find(function(x){return String(x.id)===id;});
          if (c) { App.currentCred = c; toast('Selected credential: '+c.app_name, 'success'); navigate('credentials'); }
        });
      };
    });
    document.querySelectorAll('[id^="delCred_"]').forEach(function(btn){
      btn.onclick = function(){
        var id = btn.id.split('_')[1];
        api('/api/credentials/'+id, {method:'DELETE'}).then(function(){ toast('Credential deleted', 'success'); navigate('credentials'); }).catch(function(e){ toast(e.message, 'error'); });
      };
    });
  }

  if (page === 'preval') {
    var b = document.getElementById('btnPreval');
    if (b) b.onclick = function(){ doPreval(); };
  }

  if (page === 'swiftref') {
    var b = document.getElementById('btnSr');
    if (b) b.onclick = function(){ doSwiftref(); };
    document.getElementById('srType').onchange = function(){
      var t = document.getElementById('srType').value;
      var defaults = {bic_validity:'DEUTDEFFXXX', bic_details:'BNPAFRPP', iban_validity:'DE89370400440532013000', iban_bic:'FR7630006000011234567890189', ccy_validity:'EUR', ccy_details:'JPY'};
      document.getElementById('srVal').value = defaults[t] || '';
    };
  }

  if (page === 'payments') {
    var b = document.getElementById('btnInject');
    if (b) b.onclick = function(){
      var body = {amount: document.getElementById('pmAmt').value, currency: document.getElementById('pmCcy').value, debtor_agent: document.getElementById('pmD').value, creditor_agent: document.getElementById('pmC').value};
      b.disabled = true; b.textContent = 'Injecting...';
      api('/api/payments', {method:'POST', body: JSON.stringify(body)}).then(function(r){
        toast('Payment injected: '+r.uetr.slice(0,8)+'...', 'success');
        navigate('payments');
      }).catch(function(e){ toast(e.message, 'error'); b.disabled=false; b.textContent='Inject Payment'; });
    };
  }

  if (page === 'messaging') {
    var b = document.getElementById('btnSendMsg');
    if (b) b.onclick = function(){ doSendFin(); };
  }

  if (page === 'builder') {
    var b = document.getElementById('btnSend');
    if (b) b.onclick = sendRequest;
    document.getElementById('btnCurl').onclick = copyCurl;
    document.querySelectorAll('.tab[data-rtab]').forEach(function(t){
      t.onclick = function(){ switchReqTab(t.dataset.rtab); };
    });
  }

  if (page === 'iso20022') {
    var b = document.getElementById('btnIso');
    if (b) b.onclick = function(){
      var body = {amount: document.getElementById('isoAmt').value, currency: document.getElementById('isoCcy').value, debtor_agent: document.getElementById('isoD').value, creditor_agent: document.getElementById('isoC').value, debtor_name: document.getElementById('isoDname').value, creditor_name: document.getElementById('isoCname').value};
      b.disabled = true; b.textContent = 'Generating...';
      api('/api/payments', {method:'POST', body: JSON.stringify(body)}).then(function(r){
        document.getElementById('isoOutput').innerHTML = '<div class="flex-between mb-2"><span class="badge badge-green">UETR '+escapeHtml(ellipsis(r.uetr,20))+'</span>'+btn('Copy XML',{cls:'btn-secondary',size:'xs',id:'btnCopyXml'})+'</div>' + codeBlock(r.iso20022_payload, 'xml');
        document.getElementById('btnCopyXml').onclick = function(){ copyText(r.iso20022_payload, this); };
        b.disabled = false; b.textContent = 'Generate pacs.008';
      }).catch(function(e){ toast(e.message, 'error'); b.disabled=false; b.textContent='Generate pacs.008'; });
    };
  }

  if (page === 'ecny_wallets') {
    var b = document.getElementById('btnEcnyOpenWallet');
    if (b) b.onclick = function(){
      var body = {tier: parseInt(document.getElementById('ecnyTier').value), operator_account_id: document.getElementById('ecnyOpAcct').value.trim()};
      var nm = document.getElementById('ecnyHolderName').value.trim();
      if (nm) { body.holder_name = nm; body.holder_id_type = 'id_card'; body.holder_id_hash = 'h_'+nm; }
      b.disabled = true; b.textContent = '开立中...';
      ecnyApi('/ecny/v1/wallets', {method:'POST', body: JSON.stringify(body)}).then(function(r){
        toast('钱包已开立：'+r.wallet_id.slice(0,12)+'...', 'success'); navigate('ecny_wallets');
      }).catch(function(e){ toast(e.message, 'error'); b.disabled=false; b.textContent='开立钱包'; });
    };
  }

  if (page === 'ecny_issuance') {
    var b = document.getElementById('btnEcnyIssue');
    if (b) b.onclick = function(){
      var body = {operator_account_id: document.getElementById('ecnyIssueAcct').value, amount_fen: parseInt(document.getElementById('ecnyIssueAmt').value), action: document.getElementById('ecnyIssueAction').value};
      var wid = document.getElementById('ecnyIssueWallet').value.trim();
      if (wid) body.wallet_id = wid;
      b.disabled = true; b.textContent = '执行中...';
      ecnyApi('/ecny/v1/issuance', {method:'POST', body: JSON.stringify(body)}).then(function(r){
        document.getElementById('ecnyIssueResult').innerHTML = '<div class="badge badge-green">成功 · tx_id '+escapeHtml(r.tx_id.slice(0,16))+'…</div>';
        toast('发行操作完成', 'success'); navigate('ecny_issuance');
      }).catch(function(e){ toast(e.message, 'error'); document.getElementById('ecnyIssueResult').innerHTML = errorBox(e.message); b.disabled=false; b.textContent='执行'; });
    };
  }

  if (page === 'ecny_crossborder') {
    var b = document.getElementById('btnEcnyCb');
    if (b) b.onclick = function(){
      var body = {from_wallet_id: document.getElementById('ecnyCbFrom').value, to_account_id: document.getElementById('ecnyCbTo').value.trim(), amount_fen: parseInt(document.getElementById('ecnyCbAmt').value), target_currency: document.getElementById('ecnyCbCcy').value};
      var ch = document.getElementById('ecnyCbChannel').value; if (ch) body.channel = ch;
      var cp = document.getElementById('ecnyCbCp').value.trim(); if (cp) body.counterparty = cp;
      b.disabled = true; b.textContent = '处理中...';
      ecnyApi('/ecny/v1/cross-border', {method:'POST', body: JSON.stringify(body)}).then(function(r){
        document.getElementById('ecnyCbResult').innerHTML = '<div class="badge badge-green">已结算 · UETR '+escapeHtml(r.uetr.slice(0,16))+'… · '+escapeHtml(r.from_currency)+' '+fenToYuan(r.from_amount)+' → '+escapeHtml(r.to_currency)+' '+fenToYuan(r.to_amount)+' @ '+escapeHtml(r.fx_rate||'1')+'</div>';
        toast('跨境支付已原子结算', 'success');
        b.disabled = false; b.textContent = '发起跨境';
      }).catch(function(e){ toast(e.message, 'error'); document.getElementById('ecnyCbResult').innerHTML = errorBox(e.message); b.disabled=false; b.textContent='发起跨境'; });
    };
    var tb = document.getElementById('btnEcnyTrack');
    if (tb) tb.onclick = function(){
      var uetr = document.getElementById('ecnyTrackUetr').value.trim();
      if (!uetr) { toast('请输入 UETR','error'); return; }
      ecnyApi('/ecny/v1/cross-border/'+uetr).then(function(r){
        document.getElementById('ecnyTrackResult').innerHTML = '<div class="badge '+(r.status==='settled'?'badge-green':'badge-yellow')+'">'+escapeHtml(r.status)+'</div> '+escapeHtml(r.from_currency)+' '+fenToYuan(r.from_amount)+' → '+escapeHtml(r.to_currency)+' '+fenToYuan(r.to_amount)+' · 通道 '+escapeHtml(r.channel_id);
      }).catch(function(e){ document.getElementById('ecnyTrackResult').innerHTML = errorBox(e.message); });
    };
  }
}

/* ============================================================
 * Page actions
 * ============================================================ */
function doPreval() {
  if (!App.currentCred) { toast('Select a credential in App Credentials first', 'error'); return; }
  var b = document.getElementById('btnPreval'); b.disabled = true; b.textContent = 'Validating...';
  var body = {
    instructed_amount: {currency_code: document.getElementById('pvCcy').value, amount: document.getElementById('pvAmt').value},
    debtor_agent_country: document.getElementById('pvDc').value,
    creditor_agent: {bicfi: document.getElementById('pvBic').value},
    creditor_agent_country: document.getElementById('pvCc').value,
    creditor_account: document.getElementById('pvAcc').value
  };
  var u = document.getElementById('pvUetr').value.trim(); if (u) body.uetr = u;
  signedCall('POST', '/swift-preval/v2/payment/payment-instruction', body, 'swift.preval').then(function(v){
    var resBadge = v.payment_instruction_validation_result === 'ALL_VALID' ? 'badge-green' :
                   v.payment_instruction_result === 'ERROR' ? 'badge-red' : 'badge-yellow';
    var sum = v.validation_summary || {};
    var h = '<div class="flex-row gap-3 mb-4"><span class="badge '+resBadge+'" style="font-size:13px;padding:6px 12px">'+escapeHtml(v.payment_instruction_validation_result)+'</span>' +
            '<span class="form-hint">UETR '+escapeHtml(v.uetr||'(none)')+'</span></div>';
    h += '<div class="grid-2 mb-4">';
    h += '<div class="card" style="margin:0"><div class="card-header">Validation Summary</div>';
    h += '<div class="flex-col" style="gap:6px">';
    h += summaryRow('Errors', sum.ERROR_count||0, 'badge-red');
    h += summaryRow('Warnings', sum.WARNING_count||0, 'badge-yellow');
    h += summaryRow('Valid', sum.VALID_count||0, 'badge-green');
    h += summaryRow('N/A', sum.N_A_count||0, 'badge-gray');
    h += '</div></div>';
    h += '<div class="card" style="margin:0"><div class="card-header">Checks</div>';
    var checks = v.validations || [];
    if (!checks.length) h += '<div class="form-hint">No checks returned</div>';
    else checks.forEach(function(c){
      var st = c.status==='FVAL_valid'?'badge-green':c.status==='IVAL_invalid'?'badge-red':c.status==='CVAL_valid_with_comments'?'badge-yellow':'badge-gray';
      h += '<div class="flex-between" style="padding:4px 0;border-bottom:1px solid var(--border)"><div class="flex-col" style="gap:2px"><span style="font-size:12px;font-weight:500">'+escapeHtml(humanize(c.check_type))+'</span><span class="form-hint mono">'+escapeHtml((c.reason||[]).map(function(r){return r.code;}).join(', ')||'—')+'</span></div><span class="badge '+st+'">'+escapeHtml(c.status)+'</span></div>';
    });
    h += '</div></div>';
    document.getElementById('prevalResult').innerHTML = h;
    b.disabled = false; b.textContent = 'Validate Payment Instruction';
  }).catch(function(e){
    document.getElementById('prevalResult').innerHTML = e.envelope ? renderErrorEnvelope(e.envelope) : errorBox(e.message);
    b.disabled = false; b.textContent = 'Validate Payment Instruction';
  });
}
function summaryRow(label, val, cls) {
  return '<div class="flex-between"><span class="form-hint">'+escapeHtml(label)+'</span><span class="badge '+cls+'">'+val+'</span></div>';
}
function humanize(s) { return (s||'').replace(/_/g,' ').replace(/\b\w/g, function(c){return c.toUpperCase();}); }

function doSwiftref() {
  var t = document.getElementById('srType').value;
  var v = document.getElementById('srVal').value.trim();
  if (!v) { toast('Enter a value', 'error'); return; }
  var paths = {
    bic_validity:'/swiftrefdata/v4/bics/'+v+'/validity', bic_details:'/swiftrefdata/v4/bics/'+v,
    iban_validity:'/swiftrefdata/v4/ibans/'+v+'/validity', iban_bic:'/swiftrefdata/v4/ibans/'+v+'/bic',
    ccy_validity:'/swiftrefdata/v4/currency_codes/'+v+'/validity', ccy_details:'/swiftrefdata/v4/currency_codes/'+v
  };
  var path = paths[t];
  var el = document.getElementById('srResult');
  el.innerHTML = '<div class="skeleton skeleton-card"></div>';
  // SwiftRef reads require a bearer token (swift.swiftref scope). Mint one via dev/sign.
  function doFetch(token) {
    var headers = {}; if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(path, {headers: headers}).then(function(res){ return res.text().then(function(txt){ var d; try{d=JSON.parse(txt)}catch(e){d={raw:txt}} if(!res.ok){var err=new Error('HTTP '+res.status);err.envelope=d;throw err} return d; }); });
  }
  var promise;
  if (App.currentCred) {
    promise = api('/api/dev/sign', {method:'POST', body: JSON.stringify({consumer_key: App.currentCred.consumer_key, body:'', audience: location.host+path, scope:'swift.swiftref'})}).then(function(sr){ return doFetch(sr.access_token); });
  } else {
    promise = doFetch(null); // will likely 401 in sandbox-with-token, but try
  }
  promise.then(function(r){ el.innerHTML = renderSwiftrefResult(t, r); })
    .catch(function(e){ el.innerHTML = e.envelope ? renderErrorEnvelope(e.envelope) : errorBox(e.message); });
}
function renderSwiftrefResult(type, r) {
  var h = '<div class="flex-row gap-2 mb-3">';
  if (r.validity) {
    var ok = r.validity === 'VBIC' || r.validity === 'VIBN' || r.validity === 'VCUC';
    h += '<span class="badge '+(ok?'badge-green':'badge-red')+'">'+escapeHtml(r.validity)+'</span>';
  }
  if (r.bic) h += '<span class="badge badge-blue">BIC '+escapeHtml(r.bic)+'</span>';
  if (r.iban) h += '<span class="badge badge-purple">IBAN '+escapeHtml(r.iban)+'</span>';
  h += '</div>';
  h += '<div class="table-wrap"><table><tbody>';
  Object.keys(r).forEach(function(k){
    if (k === 'validity') return;
    var val = typeof r[k] === 'object' ? prettyJson(r[k]) : String(r[k]);
    h += '<tr><td class="muted nowrap" style="width:160px">'+escapeHtml(k)+'</td><td class="mono">'+escapeHtml(val)+'</td></tr>';
  });
  h += '</tbody></table></div>';
  h += '<details class="mt-3"><summary class="form-hint" style="cursor:pointer">Raw JSON</summary><div class="mt-2">'+codeBlock(prettyJson(r), 'json')+'</div></details>';
  return h;
}

function doSendFin() {
  if (!App.currentCred) { toast('Select a credential in App Credentials first', 'error'); return; }
  var b = document.getElementById('btnSendMsg'); b.disabled = true; b.textContent = 'Sending...';
  var payload = btoa(':20:12345\n:79:Test FIN message'); // demo payload
  var body = {
    sender_reference: document.getElementById('msgRef').value,
    message_type: document.getElementById('msgType').value,
    sender: document.getElementById('msgSender').value,
    receiver: document.getElementById('msgReceiver').value,
    payload: payload,
    network_info: {network_priority: document.getElementById('msgPrio').value, possible_duplicate: false}
  };
  signedCall('POST', '/alliancecloud/v2/fin/messages', body, 'swift.messaging').then(function(r){
    toast('FIN message sent · distribution '+r.distribution_id.slice(0,8)+'...', 'success');
    loadDistributions();
    b.disabled = false; b.textContent = 'Send FIN Message';
  }).catch(function(e){
    toast(e.message, 'error'); b.disabled = false; b.textContent = 'Send FIN Message';
  });
}

/* Request builder */
var reqHistory = [];
function switchReqTab(t) {
  document.querySelectorAll('.tab[data-rtab]').forEach(function(e){ e.classList.remove('active'); });
  document.querySelector('.tab[data-rtab="'+t+'"]').classList.add('active');
  ['headers','body','history'].forEach(function(p){
    document.getElementById('req'+p.charAt(0).toUpperCase()+p.slice(1)+'Panel').style.display = (p===t?'block':'none');
  });
}
function sendRequest() {
  var url = document.getElementById('reqUrl').value.trim();
  var method = document.getElementById('reqMethod').value;
  if (!url) { toast('Enter a URL', 'error'); return; }
  var headers = {};
  try { var ht = document.getElementById('reqHeaders').value.trim(); if (ht) Object.assign(headers, JSON.parse(ht)); } catch (e) { toast('Invalid headers JSON', 'error'); return; }
  var body = undefined; if (method === 'POST' || method === 'PATCH') { body = document.getElementById('reqBody').value.trim() || undefined; }
  var opts = {method: method, headers: headers}; if (body) opts.body = body;
  var t0 = Date.now();
  var meta = document.getElementById('respMeta'); meta.textContent = 'Sending...';
  document.getElementById('respContainer').innerHTML = '<div class="skeleton skeleton-card"></div>';
  fetch(url, opts).then(function(res){
    var lat = Date.now() - t0;
    return res.text().then(function(txt){
      var f = txt; try { f = JSON.stringify(JSON.parse(txt), null, 2); } catch (e) {}
      var sb = res.status<300?'badge-green':res.status<500?'badge-yellow':'badge-red';
      meta.innerHTML = '<span class="badge '+sb+'">'+res.status+' '+res.statusText+'</span> · '+lat+'ms';
      var lang = f.trim().charAt(0) === '<' ? 'xml' : 'json';
      document.getElementById('respContainer').innerHTML = codeBlock(f, lang);
      reqHistory.unshift({method:method, url:url, status:res.status, lat:lat, when:new Date().toISOString()});
      reqHistory = reqHistory.slice(0, 20);
      renderReqHistory();
    });
  }).catch(function(e){
    meta.textContent = 'Error';
    document.getElementById('respContainer').innerHTML = codeBlock('Error: '+e.message, '');
  });
}
function renderReqHistory() {
  var el = document.getElementById('reqHistory');
  if (!el) return;
  if (!reqHistory.length) { el.innerHTML = emptyState('No history','Sent requests will be listed here.'); return; }
  var h = '<div class="table-wrap"><table><thead><tr><th>Method</th><th>URL</th><th>Status</th><th>Latency</th><th>When</th></tr></thead><tbody>';
  reqHistory.forEach(function(r, i){
    var sb = r.status<300?'badge-green':r.status<500?'badge-yellow':'badge-red';
    h += '<tr style="cursor:pointer" onclick="replayReq('+i+')"><td>'+methodBadge(r.method)+'</td><td class="mono muted">'+escapeHtml(r.url)+'</td><td><span class="badge '+sb+'">'+r.status+'</span></td><td class="mono">'+r.lat+'ms</td><td class="muted nowrap">'+relativeTime(r.when)+'</td></tr>';
  });
  h += '</tbody></table></div>';
  el.innerHTML = h;
}
function replayReq(i) {
  var r = reqHistory[i];
  document.getElementById('reqMethod').value = r.method;
  document.getElementById('reqUrl').value = r.url;
  switchReqTab('headers');
}
function copyCurl() {
  var method = document.getElementById('reqMethod').value;
  var url = document.getElementById('reqUrl').value.trim();
  var headers = {}; try { Object.assign(headers, JSON.parse(document.getElementById('reqHeaders').value.trim()||'{}')); } catch(e){}
  var body = (method==='POST'||method==='PATCH') ? document.getElementById('reqBody').value.trim() : '';
  var curl = 'curl -X '+method+' \''+url+'\'';
  Object.keys(headers).forEach(function(k){ curl += ' -H \''+k+': '+headers[k]+'\''; });
  if (body) curl += ' -d \''+body.replace(/'/g,"'\\''")+'\'';
  copyText(curl);
}

/* ============================================================
 * Boot
 * ============================================================ */
boot();
