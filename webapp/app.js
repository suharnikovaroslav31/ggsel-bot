const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#0c1118");
  tg.setBackgroundColor("#0c1118");
}

const I18N = {
  ru: {
    sub: "P2P-гарант сделок",
    home: "Главная",
    req: "Реквизиты",
    create: "Сделка",
    bal: "Баланс",
    deals: "Сделки",
    refs: "Рефералы",
    admin: "Админ",
    support: "Поддержка",
    welcome: "Надёжный P2P-гарант: NFT, подарки, полная защита сторон. 50% от комиссии рефералам.",
    reqHint: "Кошелёк, карта и юзернейм для вывода.",
    ton: "TON-кошелёк",
    card: "Карта",
    uname: "Юзернейм",
    save: "Сохранить",
    role: "Кто вы в сделке?",
    seller: "Я продавец",
    buyer: "Я покупатель",
    type: "Тип сделки",
    pay: "Метод оплаты",
    amount: "Сумма",
    desc: "Описание или ссылка NFT",
    make: "Создать",
    copy: "Скопировать ссылку",
    emptyDeals: "Активных сделок пока нет.",
    refsText: "Вы получаете 50% от комиссии бота.",
    invited: "Приглашено",
    withdraw: "Вывести",
    credit: "Начислить",
    transfer: "Передать на баланс",
    grant: "Добавить воркера",
    ban: "Забанить",
    unban: "Разбанить",
    cancel: "Отменить",
    paybal: "Оплатить с баланса",
    sent: "Товар гаранту",
    recv: "Подтвердить получение",
    join: "Войти в сделку",
  },
  en: {
    sub: "P2P deal guarantor",
    home: "Home",
    req: "Details",
    create: "Deal",
    bal: "Balance",
    deals: "Deals",
    refs: "Referrals",
    admin: "Admin",
    support: "Support",
    welcome: "Reliable P2P guarantor for NFTs and gifts. 50% of the fee to referrals.",
    reqHint: "Wallet, card and username for withdrawals.",
    ton: "TON wallet",
    card: "Card",
    uname: "Username",
    save: "Save",
    role: "Your role",
    seller: "I am seller",
    buyer: "I am buyer",
    type: "Deal type",
    pay: "Payment",
    amount: "Amount",
    desc: "Description or NFT link",
    make: "Create",
    copy: "Copy link",
    emptyDeals: "No deals yet.",
    refsText: "You get 50% of the bot fee.",
    invited: "Invited",
    withdraw: "Withdraw",
    credit: "Credit",
    transfer: "Transfer",
    grant: "Add worker",
    ban: "Ban",
    unban: "Unban",
    cancel: "Cancel",
    paybal: "Pay from balance",
    sent: "Sent to guarantor",
    recv: "Confirm received",
    join: "Join deal",
  },
};

const TYPES = [
  ["gift", "Подарок", "🎁"],
  ["channel", "Канал/чат", "📣"],
  ["stars", "Звезды", "⭐"],
  ["nft", "НФТ", "⛓️"],
];
const PAYS = [
  ["ton", "TON", "💎"],
  ["card", "Карта", "💳"],
  ["stars", "Stars", "⭐"],
  ["usdt", "USDT", "🪙"],
  ["usd", "USD", "💸"],
  ["eur", "EUR", "💰"],
  ["byn", "BYN", "🇧🇾"],
  ["kzt", "KZT", "🇰🇿"],
  ["uah", "UAH", "🇺🇦"],
];
const GROUPS = [
  ["Crypto", ["ton", "usdt", "stars"]],
  ["Fiat", ["rub", "byn", "kzt", "uah", "usd", "eur"]],
];
const WDRAW = [
  ["ton", "TON"],
  ["card", "RUB"],
  ["byn", "BYN"],
  ["kzt", "KZT"],
  ["uah", "UAH"],
  ["stars", "STARS"],
  ["usdt", "USDT"],
  ["usd", "USD"],
  ["eur", "EUR"],
];

const state = {
  user: null,
  screen: "home",
  draft: { role: "", deal_type: "", pay_method: "", amount: "", description: "" },
};

function t(key) {
  const lang = state.user?.language === "en" ? "en" : "ru";
  return I18N[lang][key] || key;
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 2400);
}

async function api(path, opts = {}) {
  const initData = tg?.initData || "";
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `tma ${initData}`,
      ...(opts.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({ ok: false, error: "bad_json" }));
  if (!data.ok) {
    const map = {
      auth: "Открой Mini App из Telegram",
      banned: "Вы заблокированы",
      need_deals: "Нужно минимум 3 завершённые сделки",
      need_ton: "Сначала добавь TON в реквизитах",
      need_card: "Сначала добавь карту",
      need_username: "Сначала добавь юзернейм",
      empty: "Недостаточно средств",
      nft_link: "Нужна ссылка https://t.me/nft/...",
      forbidden: "Нет доступа",
    };
    throw new Error(map[data.error] || data.error || "Ошибка");
  }
  return data;
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderTabs() {
  const items = [
    ["home", t("home")],
    ["create", t("create")],
    ["bal", t("bal")],
    ["deals", t("deals")],
    ["req", t("req")],
  ];
  document.getElementById("tabs").innerHTML = items
    .map(
      ([id, label]) =>
        `<button class="${state.screen === id ? "on" : ""}" data-go="${id}">${label}</button>`
    )
    .join("");
}

function go(name) {
  state.screen = name;
  draw();
}

async function loadMe() {
  const data = await api("/api/me");
  state.user = data.user;
  document.getElementById("welcome-sub").textContent = t("sub");
  document.getElementById("btn-lang").textContent = state.user.language === "en" ? "EN" : "RU";
  const sp = data.user.start_param || tg?.initDataUnsafe?.start_param || "";
  if (sp.startsWith("deal_")) {
    try {
      await api(`/api/deals/${sp.slice(5)}/join`, { method: "POST" });
      toast("Вы вошли в сделку");
      state.screen = "deals";
    } catch (e) {
      toast(e.message);
    }
  }
}

function screenHome() {
  const u = state.user;
  const admin = u.is_admin
    ? `<div class="tile" data-go="admin"><span class="ico">🛠</span><b>${t("admin")}</b></div>`
    : "";
  return `
    <div class="card hero">
      <b>Добро пожаловать в GGSel</b>
      <p>${t("welcome")}<br>Гарант @${esc(u.manager)}</p>
    </div>
    <div class="grid">
      <div class="tile" data-go="req"><span class="ico">💼</span><b>${t("req")}</b></div>
      <div class="tile" data-go="create"><span class="ico">➕</span><b>${t("create")}</b></div>
      <div class="tile" data-go="bal"><span class="ico">🧳</span><b>${t("bal")}</b></div>
      <div class="tile" data-go="deals"><span class="ico">📑</span><b>${t("deals")}</b></div>
      <div class="tile" data-go="refs"><span class="ico">🌐</span><b>${t("refs")}</b></div>
      <a class="tile" href="${esc(u.support_url)}" target="_blank" rel="noopener">
        <span class="ico">🎧</span><b>${t("support")}</b>
      </a>
      ${admin}
    </div>`;
}

function screenReq() {
  const u = state.user;
  return `
    <div class="card">
      <b>${t("req")}</b>
      <p class="hint">${t("reqHint")}</p>
      <label class="muted">${t("ton")}</label>
      <input id="f-ton" value="${esc(u.ton_wallet)}" placeholder="UQ..." />
      <button class="btn primary" data-save="ton">${t("save")}</button>
      <label class="muted">${t("card")}</label>
      <input id="f-card" value="${esc(u.card_number)}" inputmode="numeric" />
      <button class="btn primary" data-save="card">${t("save")}</button>
      <label class="muted">${t("uname")}</label>
      <input id="f-username" value="${esc(u.payout_username)}" placeholder="@username" />
      <button class="btn primary" data-save="username">${t("save")}</button>
    </div>`;
}

function screenCreate() {
  const d = state.draft;
  const chips = (arr, key) =>
    arr
      .map(
        ([id, label, ico]) =>
          `<button class="btn ${d[key] === id ? "primary" : ""}" data-draft="${key}:${id}">${ico} ${label}</button>`
      )
      .join("");
  return `
    <div class="card">
      <b>${t("create")}</b>
      <div class="group">${t("role")}</div>
      <div class="row">
        <button class="btn ${d.role === "seller" ? "primary" : ""}" data-draft="role:seller">${t("seller")}</button>
        <button class="btn ${d.role === "buyer" ? "primary" : ""}" data-draft="role:buyer">${t("buyer")}</button>
      </div>
      <div class="group">${t("type")}</div>
      <div class="grid">${chips(TYPES, "deal_type")}</div>
      <div class="group">${t("pay")}</div>
      <div class="grid">${chips(PAYS, "pay_method")}</div>
      <label class="muted">${t("amount")}</label>
      <input id="f-amount" value="${esc(d.amount)}" inputmode="decimal" placeholder="100" />
      <label class="muted">${t("desc")}</label>
      <textarea id="f-desc" rows="3" placeholder="https://t.me/nft/Name-1">${esc(d.description)}</textarea>
      <button class="btn primary" id="make-deal">${t("make")}</button>
      <div id="deal-link"></div>
    </div>`;
}

function screenBal() {
  const b = state.user.balances || {};
  const groups = GROUPS.map(([name, keys]) => {
    const rows = keys
      .map(
        (k) =>
          `<div class="item"><span>${k.toUpperCase()}</span><span class="bal-val">${b[k] ?? 0}</span></div>`
      )
      .join("");
    return `<div class="group">${name}</div><div class="card list">${rows}</div>`;
  }).join("");
  const methods = WDRAW.map(
    ([id, label]) => `<option value="${id}">${label}</option>`
  ).join("");
  return `
    ${groups}
    <div class="card">
      <b>${t("withdraw")}</b>
      <p class="hint">Нужно ${state.user.min_withdraw_deals} завершённых сделки. Сейчас: ${state.user.completed_deals}</p>
      <select id="w-method">${methods}</select>
      <input id="w-amount" inputmode="decimal" placeholder="${t("amount")}" />
      <button class="btn primary" id="do-withdraw">${t("withdraw")}</button>
    </div>`;
}

async function screenDeals() {
  const { deals } = await api("/api/deals");
  if (!deals.length) return `<div class="card">${t("emptyDeals")}</div>`;
  return deals
    .map((d) => {
      let actions = "";
      if (d.status === "open" && d.role) {
        actions += `<button class="btn danger" data-act="cancel:${d.code}">${t("cancel")}</button>`;
      }
      if (d.status === "active" && d.role === "buyer") {
        actions += `<button class="btn primary" data-act="paybal:${d.code}">${t("paybal")}</button>`;
      }
      if (d.status === "paid" && d.role === "seller") {
        actions += `<button class="btn primary" data-act="sent:${d.code}">${t("sent")}</button>`;
      }
      if (d.status === "goods_sent" && d.role === "buyer") {
        actions += `<button class="btn primary" data-act="recv:${d.code}">${t("recv")}</button>`;
      }
      return `<div class="card">
        <div class="item"><b>#${esc(d.code)}</b><span class="muted">${esc(d.status)}</span></div>
        <div class="muted">${esc(d.deal_type)} · ${esc(d.pay_method)} · ${d.amount} · ${esc(d.role)}</div>
        <div class="muted">${esc(d.description)}</div>
        ${actions}
      </div>`;
    })
    .join("");
}

function screenRefs() {
  const u = state.user;
  const link = u.bot_username
    ? `https://t.me/${u.bot_username}?start=${u.id}`
    : "";
  return `<div class="card">
    <b>${t("refs")}</b>
    <p>${t("refsText")}</p>
    <p>${t("invited")}: <b>${u.referral_count}</b></p>
    <input readonly value="${esc(link)}" />
    <button class="btn primary" data-copy="${esc(link)}">${t("copy")}</button>
  </div>`;
}

function screenAdmin() {
  const u = state.user;
  if (!u.is_admin) return `<div class="card">Нет доступа</div>`;
  const cur = Object.keys(u.balances)
    .map((k) => `<option value="${k}">${k.toUpperCase()}</option>`)
    .join("");
  const superBits = u.is_super_admin
    ? `
      <div class="group">${t("grant")}</div>
      <input id="a-grant" inputmode="numeric" placeholder="Telegram ID" />
      <button class="btn primary" id="do-grant">${t("grant")}</button>
      <div class="group">${t("ban")}</div>
      <input id="a-ban" inputmode="numeric" placeholder="Telegram ID" />
      <div class="row">
        <button class="btn danger" id="do-ban">${t("ban")}</button>
        <button class="btn" id="do-unban">${t("unban")}</button>
      </div>`
    : "";
  return `<div class="card">
    <b>${u.is_super_admin ? "Главный админ" : "Админ-панель"}</b>
    <div class="group">${t("credit")} / ${t("transfer")}</div>
    <select id="a-cur">${cur}</select>
    <input id="a-uid" inputmode="numeric" placeholder="Telegram ID" />
    <input id="a-amt" inputmode="decimal" placeholder="${t("amount")}" />
    <button class="btn primary" id="do-credit">${t("credit")}</button>
    <button class="btn primary" id="do-transfer">${t("transfer")}</button>
    ${superBits}
  </div>`;
}

async function draw() {
  renderTabs();
  const root = document.getElementById("screen");
  root.innerHTML = "…";
  try {
    if (state.screen === "home") root.innerHTML = screenHome();
    else if (state.screen === "req") root.innerHTML = screenReq();
    else if (state.screen === "create") root.innerHTML = screenCreate();
    else if (state.screen === "bal") root.innerHTML = screenBal();
    else if (state.screen === "deals") root.innerHTML = await screenDeals();
    else if (state.screen === "refs") root.innerHTML = screenRefs();
    else if (state.screen === "admin") root.innerHTML = screenAdmin();
  } catch (e) {
    root.innerHTML = `<div class="card err">${esc(e.message)}</div>`;
  }
}

document.body.addEventListener("click", async (ev) => {
  const goBtn = ev.target.closest("[data-go]");
  if (goBtn) {
    ev.preventDefault();
    go(goBtn.dataset.go);
    return;
  }
  const save = ev.target.closest("[data-save]");
  if (save) {
    const field = save.dataset.save;
    const value = document.getElementById(`f-${field}`).value;
    try {
      const data = await api("/api/requisites", {
        method: "POST",
        body: JSON.stringify({ field, value }),
      });
      state.user = { ...state.user, ...data.user };
      toast("Сохранено");
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  const draft = ev.target.closest("[data-draft]");
  if (draft) {
    const [k, v] = draft.dataset.draft.split(":");
    state.draft[k] = v;
    state.draft.amount = document.getElementById("f-amount")?.value || state.draft.amount;
    state.draft.description = document.getElementById("f-desc")?.value || state.draft.description;
    draw();
    return;
  }
  if (ev.target.id === "make-deal") {
    state.draft.amount = document.getElementById("f-amount").value;
    state.draft.description = document.getElementById("f-desc").value;
    try {
      const data = await api("/api/deals", {
        method: "POST",
        body: JSON.stringify(state.draft),
      });
      document.getElementById("deal-link").innerHTML =
        `<p class="ok">Сделка #${esc(data.deal.code)}</p>
         <input readonly value="${esc(data.link)}" />
         <button class="btn primary" data-copy="${esc(data.link)}">${t("copy")}</button>`;
      toast("Сделка создана");
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  if (ev.target.id === "do-withdraw") {
    try {
      await api("/api/withdraw", {
        method: "POST",
        body: JSON.stringify({
          method: document.getElementById("w-method").value,
          amount: document.getElementById("w-amount").value,
        }),
      });
      toast("Заявка принята");
      await loadMe();
      draw();
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  const act = ev.target.closest("[data-act]");
  if (act) {
    const [kind, code] = act.dataset.act.split(":");
    try {
      await api(`/api/deals/${code}/${kind}`, { method: "POST" });
      toast("Готово");
      await loadMe();
      draw();
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  const copy = ev.target.closest("[data-copy]");
  if (copy) {
    navigator.clipboard.writeText(copy.dataset.copy);
    toast("Скопировано");
    return;
  }
  if (ev.target.id === "do-credit" || ev.target.id === "do-transfer") {
    const path = ev.target.id === "do-credit" ? "/api/admin/credit" : "/api/admin/transfer";
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify({
          currency: document.getElementById("a-cur").value,
          user_id: document.getElementById("a-uid").value,
          amount: document.getElementById("a-amt").value,
        }),
      });
      toast("Готово");
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  if (ev.target.id === "do-grant") {
    try {
      await api("/api/admin/grant", {
        method: "POST",
        body: JSON.stringify({ user_id: document.getElementById("a-grant").value }),
      });
      toast("Воркер добавлен");
    } catch (e) {
      toast(e.message);
    }
    return;
  }
  if (ev.target.id === "do-ban" || ev.target.id === "do-unban") {
    try {
      await api("/api/admin/ban", {
        method: "POST",
        body: JSON.stringify({
          user_id: document.getElementById("a-ban").value,
          action: ev.target.id === "do-unban" ? "unban" : "ban",
        }),
      });
      toast("Готово");
    } catch (e) {
      toast(e.message);
    }
  }
});

document.getElementById("btn-lang").addEventListener("click", async () => {
  const next = state.user?.language === "en" ? "ru" : "en";
  try {
    await api("/api/language", { method: "POST", body: JSON.stringify({ language: next }) });
    await loadMe();
    draw();
  } catch (e) {
    toast(e.message);
  }
});

(async function init() {
  try {
    await loadMe();
    draw();
  } catch (e) {
    document.getElementById("screen").innerHTML =
      `<div class="card">${esc(e.message)}<p class="hint">Открой приложение кнопкой в боте Telegram, не в браузере.</p></div>`;
  }
})();
