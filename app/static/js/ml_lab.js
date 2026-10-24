// 实验三：提交手工样例，显示模型输出、版本与耗时。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const form = document.getElementById("recall-form");
  const box = document.getElementById("recall-result");

  function line(text, className) {
    const p = document.createElement("p");
    p.textContent = text;
    if (className) p.className = className;
    return p;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const body = Object.fromEntries(["delta_seconds", "history_seen", "history_correct"].map((k) => [k, Number(data.get(k))]));
    const response = await fetch("/api/v1/ml/recall", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    box.replaceChildren();
    if (!response.ok) {
      box.append(line(`无法估计：${payload.error.message}`));
    } else if (payload.data.status === "cold_start") {
      box.append(line("没有历史作答，暂不估计。"));
    } else {
      const d = payload.data;
      box.append(
        line(`预期正确比例 ${(d.expected_recall * 100).toFixed(1)}%`, "verdict correct"),
        line(`${d.model.model_code} ${d.model.version} · 模型计算 ${d.model_time_ms} ms`, "form-note"),
      );
    }
    box.hidden = false;
  });
})();
