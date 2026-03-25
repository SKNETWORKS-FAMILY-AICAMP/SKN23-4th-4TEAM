(function setupAdminPortal() {
  function initOpenAiModels() {
    const providerInput = document.getElementById("llm-provider");
    const baseUrlInput = document.getElementById("llm-base-url");
    const select = document.getElementById("openai-model-select");
    const status = document.getElementById("openai-model-status");
    if (!select) {
      return;
    }

    const query = new URLSearchParams();
    if (providerInput && providerInput.value) {
      query.set("provider", providerInput.value);
    }
    if (baseUrlInput && baseUrlInput.value) {
      query.set("base_url", baseUrlInput.value);
    }

    const endpoint = "/admin/config/models" + (query.toString() ? "?" + query.toString() : "");
    fetch(endpoint, { credentials: "same-origin" })
      .then(function onResponse(response) {
        if (!response.ok) {
          throw new Error(String(response.status));
        }
        return response.json();
      })
      .then(function onPayload(payload) {
        const current = payload.current_model || select.getAttribute("data-current-model") || "";
        const models = Array.isArray(payload.models) ? payload.models : [];
        const unique = Array.from(new Set([current].concat(models).filter(Boolean)));

        if (unique.length === 0) {
          if (status) {
            status.textContent = "모델 목록이 비어 있습니다. 현재 값을 유지합니다.";
          }
          return;
        }

        select.innerHTML = "";
        unique.forEach(function appendOption(name) {
          const option = document.createElement("option");
          option.value = name;
          option.textContent = name;
          if (name === current) {
            option.selected = true;
          }
          select.appendChild(option);
        });

        if (status) {
          status.textContent = "모델 " + unique.length + "개를 불러왔습니다.";
        }
      })
      .catch(function onError() {
        if (status) {
          status.textContent = "모델 목록 조회 실패. 현재 모델로 저장 가능합니다.";
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function onDomReady() {
    initOpenAiModels();

    const providerInput = document.getElementById("llm-provider");
    const baseUrlInput = document.getElementById("llm-base-url");
    if (providerInput) {
      providerInput.addEventListener("change", initOpenAiModels);
    }
    if (baseUrlInput) {
      baseUrlInput.addEventListener("blur", initOpenAiModels);
    }
  });
})();
