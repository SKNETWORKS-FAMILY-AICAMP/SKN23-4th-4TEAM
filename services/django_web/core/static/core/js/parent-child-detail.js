(function initParentChildDetailPage() {
  function setHidden(node, hidden) {
    if (!node) {
      return;
    }
    node.classList.toggle("is-hidden", hidden);
  }

  function toDateKey(value) {
    if (!value) {
      return "";
    }
    return String(value).slice(0, 10);
  }

  function buildTag(term, polarity, score) {
    const chip = document.createElement("span");
    const numericScore = Number(score || 0);
    let weightClass = "w1";
    if (numericScore >= 0.8) {
      weightClass = "w5";
    } else if (numericScore >= 0.6) {
      weightClass = "w4";
    } else if (numericScore >= 0.4) {
      weightClass = "w3";
    } else if (numericScore >= 0.2) {
      weightClass = "w2";
    }

    chip.className = "tag-chip " + weightClass + " polarity-" + (polarity || "neutral");
    chip.textContent = term;
    return chip;
  }

  function buildTodoNode(todo) {
    const item = document.createElement("li");
    item.className = "todo-item";
    item.setAttribute("data-todo-id", String(todo.id));
    item.setAttribute("data-status", todo.status);
    item.setAttribute("data-done-date", toDateKey(todo.done_at));

    const main = document.createElement("div");
    main.className = "todo-main";

    const title = document.createElement("p");
    title.className = "todo-title";
    title.textContent = todo.title;

    const meta = document.createElement("p");
    meta.className = "muted";
    const dueText = todo.due_date ? " · 기한 " + todo.due_date : "";
    meta.textContent = "우선순위 P" + todo.priority + dueText;

    main.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "todo-actions";
    actions.setAttribute("role", "group");
    actions.setAttribute("aria-label", "상태 변경");

    const statusOptions = [
      ["todo", "대기"],
      ["doing", "진행"],
      ["done", "완료"],
    ];

    statusOptions.forEach(function appendButton(pair) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-chip" + (todo.status === pair[0] ? " active" : "");
      button.setAttribute("data-status-btn", "");
      button.setAttribute("data-next-status", pair[0]);
      button.textContent = pair[1];
      actions.appendChild(button);
    });

    item.append(main, actions);
    return item;
  }

  function updateTodoButtonStates(todoItem, activeStatus) {
    todoItem.setAttribute("data-status", activeStatus);
    const buttons = todoItem.querySelectorAll("[data-status-btn]");
    buttons.forEach(function toggle(button) {
      const nextStatus = button.getAttribute("data-next-status");
      button.classList.toggle("active", nextStatus === activeStatus);
    });
  }

  function collectDoneDateSet(todoList) {
    const values = new Set();
    todoList.querySelectorAll("[data-todo-id]").forEach(function eachTodo(todoItem) {
      const doneDate = String(todoItem.getAttribute("data-done-date") || "").trim();
      if (doneDate) {
        values.add(doneDate);
      }
    });
    return values;
  }

  function renderDoneDateList(listNode, doneDateSet) {
    if (!listNode) {
      return;
    }
    listNode.replaceChildren();
    const dates = Array.from(doneDateSet).sort();
    if (dates.length === 0) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "완료 처리된 날짜가 아직 없습니다.";
      listNode.appendChild(empty);
      return;
    }

    dates.forEach(function appendDate(dateText) {
      const item = document.createElement("li");
      const time = document.createElement("time");
      time.dateTime = dateText;
      time.textContent = dateText;
      item.appendChild(time);
      listNode.appendChild(item);
    });
  }

  function renderCalendar(calendarNode, doneDateSet) {
    if (!calendarNode) {
      return;
    }

    calendarNode.replaceChildren();
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth();
    const firstDay = new Date(year, month, 1);
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    const header = document.createElement("p");
    header.className = "calendar-title";
    header.textContent = year + "년 " + (month + 1) + "월";
    calendarNode.appendChild(header);

    const weekdays = document.createElement("div");
    weekdays.className = "todo-calendar-weekdays";
    ["일", "월", "화", "수", "목", "금", "토"].forEach(function appendWeekday(label) {
      const cell = document.createElement("span");
      cell.className = "todo-calendar-weekday";
      cell.textContent = label;
      weekdays.appendChild(cell);
    });
    calendarNode.appendChild(weekdays);

    const grid = document.createElement("div");
    grid.className = "todo-calendar-grid";

    for (let i = 0; i < firstDay.getDay(); i += 1) {
      const emptyCell = document.createElement("span");
      emptyCell.className = "todo-calendar-day empty";
      grid.appendChild(emptyCell);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const key = year + "-" + String(month + 1).padStart(2, "0") + "-" + String(day).padStart(2, "0");
      const cell = document.createElement("span");
      cell.className = "todo-calendar-day";
      cell.textContent = String(day);
      if (doneDateSet.has(key)) {
        cell.classList.add("checked");
        cell.setAttribute("title", "완료된 할 일이 있는 날짜");
      }
      grid.appendChild(cell);
    }

    calendarNode.appendChild(grid);
  }

  document.addEventListener("DOMContentLoaded", function onReady() {
    const root = document.querySelector("[data-parent-child-detail]");
    if (!root) {
      return;
    }

    const childId = Number(root.getAttribute("data-child-id") || "0");
    const todoList = document.getElementById("todo-list");
    const openButton = document.getElementById("todo-open-btn");
    const modal = document.getElementById("todo-modal");
    const createForm = document.getElementById("todo-create-form");
    const modalError = document.getElementById("todo-modal-error");
    const keywordDays = document.getElementById("keyword-days");
    const keywordRefreshButton = document.getElementById("keyword-refresh-btn");
    const keywordCloud = document.getElementById("keyword-cloud");
    const calendarNode = document.getElementById("todo-done-calendar");
    const doneDateList = document.getElementById("todo-done-date-list");

    function refreshDoneCalendar() {
      const doneDateSet = collectDoneDateSet(todoList);
      renderCalendar(calendarNode, doneDateSet);
      renderDoneDateList(doneDateList, doneDateSet);
    }

    function closeModal() {
      setHidden(modal, true);
      createForm.reset();
      modalError.textContent = "";
      setHidden(modalError, true);
    }

    function openModal() {
      setHidden(modal, false);
      const titleInput = document.getElementById("todo-title");
      if (titleInput) {
        titleInput.focus();
      }
    }

    function removeInitialEmptyRow() {
      const emptyNode = document.getElementById("todo-empty");
      if (emptyNode) {
        emptyNode.remove();
      }
    }

    async function refreshKeywordCloud() {
      keywordRefreshButton.disabled = true;
      keywordRefreshButton.textContent = "갱신 중...";
      try {
        const days = Number(keywordDays.value || "7");
        const response = await window.apiClient.request(
          "/api/children/" + childId + "/keyword-cloud?days=" + days,
          { method: "GET", timeoutMs: 10000 }
        );

        keywordCloud.replaceChildren();
        const items = response.keyword_cloud || [];
        if (items.length === 0) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent = "아직 분석 데이터가 없습니다.";
          keywordCloud.appendChild(empty);
          return;
        }

        items.forEach(function appendKeyword(item) {
          keywordCloud.appendChild(buildTag(item.term, item.polarity, item.weight));
        });
      } catch (error) {
        keywordCloud.replaceChildren();
        const fail = document.createElement("p");
        fail.className = "error-banner";
        fail.textContent = error && error.message ? error.message : "키워드 데이터를 불러오지 못했습니다.";
        keywordCloud.appendChild(fail);
      } finally {
        keywordRefreshButton.disabled = false;
        keywordRefreshButton.textContent = "갱신";
      }
    }

    if (openButton) {
      openButton.addEventListener("click", openModal);
    }

    if (modal) {
      modal.addEventListener("click", function onModalClick(event) {
        const closeTarget = event.target.closest("[data-modal-close='todo-modal']");
        if (closeTarget) {
          closeModal();
        }
      });
    }

    if (createForm) {
      createForm.addEventListener("submit", async function onCreate(event) {
        event.preventDefault();
        const formData = new FormData(createForm);
        const title = String(formData.get("title") || "").trim();
        const priority = Number(formData.get("priority") || "3");
        const dueDate = String(formData.get("due_date") || "").trim();

        if (!title) {
          modalError.textContent = "할 일 제목은 필수입니다.";
          setHidden(modalError, false);
          return;
        }

        const submitButton = createForm.querySelector("button[type='submit']");
        submitButton.disabled = true;
        submitButton.textContent = "저장 중...";

        try {
          const created = await window.apiClient.request(
            "/api/children/" + childId + "/todos",
            {
              method: "POST",
              body: {
                title: title,
                priority: priority,
                due_date: dueDate || null,
              },
            }
          );

          removeInitialEmptyRow();
          todoList.prepend(buildTodoNode(created));
          refreshDoneCalendar();
          closeModal();
        } catch (error) {
          modalError.textContent = error && error.message ? error.message : "할 일 저장에 실패했습니다.";
          setHidden(modalError, false);
        } finally {
          submitButton.disabled = false;
          submitButton.textContent = submitButton.getAttribute("data-submit-label") || "저장";
        }
      });
    }

    todoList.addEventListener("click", async function onTodoStatusClick(event) {
      const button = event.target.closest("[data-status-btn]");
      if (!button) {
        return;
      }

      const todoItem = button.closest("[data-todo-id]");
      if (!todoItem) {
        return;
      }

      const todoId = todoItem.getAttribute("data-todo-id");
      const nextStatus = button.getAttribute("data-next-status");
      const currentStatus = todoItem.getAttribute("data-status");
      if (!todoId || !nextStatus || nextStatus === currentStatus) {
        return;
      }

      button.disabled = true;
      try {
        const patched = await window.apiClient.request("/api/todos/" + todoId, {
          method: "PATCH",
          body: { status: nextStatus },
        });
        updateTodoButtonStates(todoItem, patched.status);
        todoItem.setAttribute("data-done-date", toDateKey(patched.done_at));
        refreshDoneCalendar();
      } catch (error) {
        window.alert(error && error.message ? error.message : "상태를 변경하지 못했습니다.");
      } finally {
        button.disabled = false;
      }
    });

    keywordRefreshButton.addEventListener("click", function onRefreshClick() {
      refreshKeywordCloud();
    });

    refreshDoneCalendar();
  });
})();
