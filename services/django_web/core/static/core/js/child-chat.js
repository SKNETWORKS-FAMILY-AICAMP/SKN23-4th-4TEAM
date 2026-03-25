(function initChildChatPage() {
  function createChip(label) {
    const chip = document.createElement("span");
    chip.className = "chip chip-ai";
    chip.textContent = label;
    return chip;
  }

  function createMessageNode(role, text) {
    const row = document.createElement("li");
    row.className = "chat-row chat-" + role;

    const meta = document.createElement("p");
    meta.className = "chat-meta";

    const chip = document.createElement("span");
    chip.className = "chip chip-" + role;
    chip.textContent = role;

    const time = document.createElement("time");
    time.dateTime = new Date().toISOString();
    time.textContent = new Date().toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });

    meta.append(chip, time);

    const content = document.createElement("p");
    content.className = "chat-content";
    content.textContent = text;

    row.append(meta, content);
    return row;
  }

  function showError(errorNode, retryNode, message) {
    errorNode.textContent = message;
    errorNode.classList.remove("is-hidden");
    retryNode.classList.remove("is-hidden");
  }

  function hideError(errorNode, retryNode) {
    errorNode.textContent = "";
    errorNode.classList.add("is-hidden");
    retryNode.classList.add("is-hidden");
  }

  function setSubmitting(sendButton, input, submitting) {
    sendButton.disabled = submitting;
    input.disabled = submitting;
    if (submitting) {
      sendButton.textContent = "전송 중...";
      return;
    }
    sendButton.textContent = sendButton.getAttribute("data-submit-label") || "전송";
  }

  document.addEventListener("DOMContentLoaded", function onReady() {
    const root = document.querySelector("[data-child-chat]");
    if (!root) {
      return;
    }

    const sessionId = root.getAttribute("data-session-id") || "";
    const childId = Number(root.getAttribute("data-child-id") || "0");
    const chatLog = root.querySelector("[data-chat-log]");
    const emptyRow = root.querySelector("[data-chat-empty]");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const sendButton = document.getElementById("chat-send-btn");
    const retryButton = document.getElementById("chat-retry-btn");
    const errorNode = document.getElementById("chat-error");
    const rateLimitNode = document.getElementById("chat-rate-limit-msg");
    const suggestedTodosNode = document.getElementById("suggested-todos");
    const todoModal = document.getElementById("child-todo-modal");
    const todoOpenButton = document.getElementById("child-todo-open-btn");

    let inFlight = false;
    let lastPayload = null;
    let lastSentAt = 0;
    let retryWaitMs = 0;

    function openTodoModal() {
      if (!todoModal) {
        return;
      }
      todoModal.classList.remove("is-hidden");
    }

    function closeTodoModal() {
      if (!todoModal) {
        return;
      }
      todoModal.classList.add("is-hidden");
    }

    function appendMessage(role, text) {
      if (emptyRow) {
        emptyRow.classList.add("is-hidden");
      }
      const row = createMessageNode(role, text);
      chatLog.appendChild(row);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function renderSuggestedTodos(items) {
      suggestedTodosNode.replaceChildren();
      if (!Array.isArray(items) || items.length === 0) {
        return;
      }
      items.forEach(function appendItem(item) {
        if (!item) {
          return;
        }
        suggestedTodosNode.appendChild(createChip(String(item)));
      });
    }

    async function sendPayload(payload) {
      if (inFlight) {
        return;
      }
      inFlight = true;
      setSubmitting(sendButton, input, true);
      hideError(errorNode, retryButton);

      try {
        const data = await window.apiClient.request("/api/chat/send", {
          method: "POST",
          body: payload,
          timeoutMs: 12000,
        });

        appendMessage("ai", data.reply_text || "응답이 없습니다.");
        renderSuggestedTodos(data.suggested_todos || []);
        lastPayload = null;
        retryWaitMs = 0;
      } catch (error) {
        const message = error && error.message ? error.message : "요청 처리 중 오류가 발생했습니다.";
        showError(errorNode, retryButton, message);
        lastPayload = payload;
        retryWaitMs = retryWaitMs > 0 ? Math.min(8000, retryWaitMs * 2) : 1000;
        retryButton.disabled = true;
        setTimeout(function enableRetry() {
          retryButton.disabled = false;
        }, retryWaitMs);
      } finally {
        inFlight = false;
        setSubmitting(sendButton, input, false);
      }
    }

    form.addEventListener("submit", function onSubmit(event) {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) {
        return;
      }

      const now = Date.now();
      if (now - lastSentAt < 900) {
        rateLimitNode.textContent = "잠시 후 다시 전송해 주세요.";
        return;
      }

      rateLimitNode.textContent = "";
      lastSentAt = now;
      input.value = "";
      appendMessage("child", text);

      sendPayload({
        session_id: sessionId,
        child_id: childId,
        user_text: text,
      });
    });

    retryButton.addEventListener("click", function onRetry() {
      if (!lastPayload || inFlight || retryButton.disabled) {
        return;
      }
      sendPayload(lastPayload);
    });

    if (todoOpenButton) {
      todoOpenButton.addEventListener("click", function onOpenTodoModal() {
        openTodoModal();
      });
    }

    if (todoModal) {
      todoModal.addEventListener("click", function onTodoModalClick(event) {
        const closeTarget = event.target.closest("[data-modal-close='child-todo']");
        if (closeTarget) {
          closeTodoModal();
        }
      });

      const autoOpenKey =
        "yoto:child-todo-modal:" +
        String(childId) +
        ":" +
        new Date().toISOString().slice(0, 10);
      if (!window.sessionStorage.getItem(autoOpenKey)) {
        window.sessionStorage.setItem(autoOpenKey, "1");
        openTodoModal();
      }
    }
  });
})();
