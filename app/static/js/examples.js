// 实验四：提交英语查询，显示最相近的例句、目标词义与相似度。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const form = document.getElementById("search-form");
  const box = document.getElementById("search-result");

  function line(text, className) {
    const p = document.createElement("p");
    p.textContent = text;
    if (className) p.className = className;
    return p;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const body = { text: data.get("text"), top_k: Number(data.get("top_k")) };
    if (data.get("wordbook_id")) body.wordbook_id = Number(data.get("wordbook_id"));
    const response = await fetch("/api/v1/examples/search", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    box.replaceChildren();
    if (!response.ok) {
      const fields = payload.error.fields ? Object.values(payload.error.fields).join("；") : "";
      box.append(line(`无法检索：${payload.error.message}${fields ? "：" + fields : ""}`, "verdict wrong"));
    } else {
      const d = payload.data;
      for (const r of d.results) {
        box.append(
          line(`${r.cosine_similarity.toFixed(3)}  ${r.text_en}`, "verdict"),
          line(`${r.sense.lemma}（${r.sense.part_of_speech}）${r.sense.definition_zh} · ${r.translation_zh || ""}`),
        );
      }
      box.append(line(`模型计算 ${d.model_time_ms} ms · 处理 ${d.processing_time_ms} ms · request_id ${payload.request_id}`, "form-note"));
    }
    box.hidden = false;
  });
})();
