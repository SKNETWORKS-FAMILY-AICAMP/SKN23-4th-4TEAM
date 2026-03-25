(function setupBaseUi() {
  function initLoginSubmitState() {
    const loginForm = document.querySelector("[data-login-form]");
    if (!loginForm) {
      return;
    }

    loginForm.addEventListener("submit", function onSubmit() {
      const submitButton = loginForm.querySelector("button[type='submit']");
      if (!submitButton) {
        return;
      }
      submitButton.disabled = true;
      const nextLabel = submitButton.getAttribute("data-submit-label") || "처리 중";
      submitButton.textContent = nextLabel + " 중...";
    });
  }

  function setHiddenState(element, hidden) {
    if (!element) {
      return;
    }
    if (hidden) {
      element.classList.add("is-hidden");
    } else {
      element.classList.remove("is-hidden");
    }
  }

  function initViewToggle() {
    const toggleButtons = document.querySelectorAll("[data-view-toggle]");
    if (toggleButtons.length === 0) {
      return;
    }

    toggleButtons.forEach(function bindToggle(button) {
      button.addEventListener("click", function onClick() {
        const toggleGroup = button.getAttribute("data-view-toggle");
        const targetPanelId = button.getAttribute("data-target");
        const panels = document.querySelectorAll("[data-view-panel='" + toggleGroup + "']");
        const peers = document.querySelectorAll("[data-view-toggle='" + toggleGroup + "']");

        peers.forEach(function updatePeer(peer) {
          peer.classList.toggle("active", peer === button);
        });

        panels.forEach(function updatePanel(panel) {
          const shouldShow = panel.id === targetPanelId;
          setHiddenState(panel, !shouldShow);
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function onDomReady() {
    initLoginSubmitState();
    initViewToggle();
  });
})();
