// 目标词表选择：读取启用词表，一次保存全部选择。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const list = document.getElementById("wordbook-list");
  const status = document.getElementById("wordbook-status");
  const examNames = { cet6: "六级", postgraduate: "考研", ielts: "雅思" };

  async function request(method, url, body) {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error.message);
    return payload.data;
  }

  async function loadAll() {
    const items = [];
    for (let page = 1; ; page += 1) {
      const data = await request("GET", `/api/v1/wordbooks?page=${page}`);
      items.push(...data.items);
      if (page * data.page_size >= data.total) return items;
    }
  }

  function render(items) {
    list.replaceChildren();
    if (items.length === 0) {
      list.textContent = "暂无可选词表，请先由管理员导入内容。";
      return;
    }
    for (const book of items) {
      const label = document.createElement("label");
      label.className = "wordbook";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = book.id;
      box.checked = book.selected;
      const title = document.createElement("strong");
      title.textContent = `${examNames[book.exam_type] || book.exam_type} · ${book.name}`;
      const meta = document.createElement("span");
      meta.className = "field-hint";
      meta.textContent = `${book.word_count} 个词条 · 版本 ${book.version} · 来源：${book.source}`;
      label.append(box, title, meta);
      list.append(label);
    }
  }

  document.getElementById("wordbook-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const ids = [...list.querySelectorAll("input:checked")].map((box) => Number(box.value));
    status.textContent = "正在保存…";
    try {
      const data = await request("PUT", "/api/v1/me/wordbooks", { wordbook_ids: ids });
      status.textContent = data.wordbooks.length ? `已保存 ${data.wordbooks.length} 个目标。` : "已清空目标。";
    } catch (error) {
      status.textContent = `保存失败：${error.message}`;
    }
  });

  loadAll().then(render).catch((error) => {
    list.textContent = `加载失败：${error.message}`;
  });
})();
