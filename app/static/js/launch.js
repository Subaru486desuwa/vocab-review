// 开始练习按钮（今日任务、复习计划、学习诊断共用）：直接创建练习，再进入练习页作答。
// data-skill 必填；可选 data-count、data-focus、data-senses（逗号分隔的词义 id，定向练习）。
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const error = document.getElementById("launch-error");

  for (const button of document.querySelectorAll("button[data-skill]")) {
    button.addEventListener("click", async () => {
      if (button.disabled) return;
      button.disabled = true;
      error.textContent = "";
      const body = { skill_type: button.dataset.skill, count: Number(button.dataset.count || 10) };
      if (button.dataset.focus) body.focus = button.dataset.focus;
      if (button.dataset.senses) body.sense_ids = button.dataset.senses.split(",").map(Number);
      try {
        const response = await fetch("/api/v1/practice/sessions", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(body),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error.message);
        location.href = `/practice?session=${payload.data.id}`;
      } catch (err) {
        error.textContent = err.message;
        button.disabled = false;
      }
    });
  }
})();
