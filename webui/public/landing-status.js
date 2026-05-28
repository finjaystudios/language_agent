(function () {
  const STATUS_ID = "lla-backend-status";
  const COMPOSER_PLACEHOLDER = "Ask your local language assistant...";
  const AUTH_ERROR_MESSAGES = new Map([
    [
      "credentialssignin",
      "Sign-in failed. Check your username and password, then try again.",
    ],
    [
      "signin",
      "Sign-in failed. Check your username and password, then try again.",
    ],
    [
      "sessionrequired",
      "Please sign in to continue.",
    ],
  ]);
  const DEFAULT_AUTH_UI_CONFIG = {
    signupEnabled: false,
    minPasswordLength: 12,
    requireAdminApproval: false,
  };
  const CONVERSATION_START_LABELS = new Set([
    "translate",
    "define",
    "learn",
    "translate to isixhosa",
    "define recursion",
    "practice greetings",
    "retry",
  ]);
  let latestStatusData = null;
  let conversationStarted = false;
  let composerEnhancementEnabled = false;
  let authBannerMessage = "";
  let authUiConfig = { ...DEFAULT_AUTH_UI_CONFIG };
  let authConfigPromise = null;

  function hasConversationMessages() {
    return conversationStarted;
  }

  function findComposerHost() {
    const textarea = document.querySelector("textarea");
    if (!textarea) return null;

    let current = textarea.closest("form") || textarea.parentElement;
    let best = current;

    for (let depth = 0; current && depth < 6; depth += 1) {
      const rect = current.getBoundingClientRect();
      if (rect.width >= 360 && rect.height <= 180) best = current;
      current = current.parentElement;
    }

    return best;
  }

  function createStatusCard() {
    let card = document.getElementById(STATUS_ID);
    if (card) return card;

    const composerHost = findComposerHost();
    if (!composerHost || !composerHost.parentElement) return null;

    card = document.createElement("section");
    card.id = STATUS_ID;
    card.className = "lla-status-card lla-status-pending";
    card.innerHTML = `
      <div class="lla-status-main">
        <div class="lla-status-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" role="img">
            <path d="M9 21h6" />
            <path d="M10 17h4" />
            <path d="M8.5 14.5c-1.6-1.1-2.5-2.9-2.5-4.9A6 6 0 0 1 18 9.6c0 2-1 3.8-2.5 4.9-.7.5-1.1 1.2-1.2 2H9.7c-.1-.8-.5-1.5-1.2-2Z" />
          </svg>
        </div>
        <div>
          <div class="lla-status-title">Checking language service</div>
          <div class="lla-status-target">Backend target: checking...</div>
        </div>
      </div>
      <button class="lla-status-refresh" type="button" aria-label="Refresh language service status" title="Refresh status">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M21 12a9 9 0 0 1-15.3 6.4" />
          <path d="M3 12A9 9 0 0 1 18.3 5.6" />
          <path d="M18 2v4h-4" />
          <path d="M6 22v-4h4" />
        </svg>
      </button>
    `;

    const refreshButton = card.querySelector(".lla-status-refresh");
    if (refreshButton) {
      refreshButton.addEventListener("click", refreshStatus);
    }

    composerHost.parentElement.insertBefore(card, composerHost);
    if (latestStatusData) applyStatusToCard(card, latestStatusData);
    return card;
  }

  function placeStatusCard(card) {
    const composerHost = findComposerHost();
    if (!composerHost || !composerHost.parentElement) return;

    if (card.parentElement !== composerHost.parentElement) {
      composerHost.parentElement.insertBefore(card, composerHost);
    } else if (card.nextElementSibling !== composerHost) {
      composerHost.parentElement.insertBefore(card, composerHost);
    }
  }

  function syncVisibility() {
    const card = createStatusCard();
    if (!card) return;
    placeStatusCard(card);
    card.hidden = hasConversationMessages();
  }

  function markConversationStarted() {
    conversationStarted = true;
    syncVisibility();
  }

  function enhanceAccessibility() {
    const textarea = document.querySelector("textarea");
    if (textarea && composerEnhancementEnabled) {
      if (textarea.getAttribute("placeholder") !== COMPOSER_PLACEHOLDER) {
        textarea.setAttribute("placeholder", COMPOSER_PLACEHOLDER);
      }
      if (textarea.getAttribute("aria-label") !== COMPOSER_PLACEHOLDER) {
        textarea.setAttribute("aria-label", COMPOSER_PLACEHOLDER);
      }
    }

    document.querySelectorAll('[data-testid="assistant-message"], [data-testid="message"], .message-content')
      .forEach((node) => {
        node.setAttribute("aria-live", "polite");
        node.setAttribute("aria-atomic", "false");
      });

    document.querySelectorAll("button").forEach((button) => {
      const text = (button.textContent || "").trim();
      if (!button.getAttribute("aria-label") && text) {
        button.setAttribute("aria-label", text);
      }
    });
  }

  function isLoginPage() {
    return Boolean(
      document.querySelector('input[type="password"]') &&
      document.querySelector('input[type="text"], input[type="email"]')
    );
  }

  function findLoginForm() {
    const passwordInput = document.querySelector('input[type="password"]');
    if (!passwordInput) return null;
    return passwordInput.closest("form");
  }

  function findLoginUsernameInput() {
    return document.querySelector('input[type="text"], input[type="email"]');
  }

  function findLoginPasswordInput() {
    return document.querySelector('input[type="password"]');
  }

  async function loadAuthUiConfig() {
    if (authConfigPromise) return authConfigPromise;

    authConfigPromise = fetch("/webui/auth/config", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : DEFAULT_AUTH_UI_CONFIG))
      .then((data) => {
        authUiConfig = {
          signupEnabled: Boolean(data && data.signupEnabled),
          minPasswordLength: Number(data && data.minPasswordLength) || DEFAULT_AUTH_UI_CONFIG.minPasswordLength,
          requireAdminApproval: Boolean(data && data.requireAdminApproval),
        };
        return authUiConfig;
      })
      .catch(() => {
        authUiConfig = { ...DEFAULT_AUTH_UI_CONFIG };
        return authUiConfig;
      });

    return authConfigPromise;
  }

  function createAuthBanner() {
    const form = findLoginForm();
    if (!form) return null;

    let banner = document.getElementById("lla-auth-error");
    if (banner) return banner;

    banner = document.createElement("div");
    banner.id = "lla-auth-error";
    banner.className = "lla-auth-error";
    banner.hidden = true;
    banner.setAttribute("role", "alert");
    banner.setAttribute("aria-live", "polite");
    form.appendChild(banner);
    return banner;
  }

  function showFriendlyAuthError(message) {
    authBannerMessage = message;
    const banner = createAuthBanner();
    if (banner) {
      banner.textContent = message;
      banner.hidden = false;
    }
  }

  function hideFriendlyAuthError() {
    authBannerMessage = "";
    const banner = document.getElementById("lla-auth-error");
    if (banner) banner.hidden = true;
  }

  function showSignupStatus(message, type) {
    const messageNode = document.getElementById("lla-signup-message");
    if (!messageNode) return;
    messageNode.textContent = message;
    messageNode.hidden = !message;
    messageNode.dataset.state = type || "info";
  }

  function setSignupMode(isOpen) {
    const panel = document.getElementById("lla-signup-panel");
    const form = document.getElementById("lla-signup-form");
    const toggle = document.getElementById("lla-signup-toggle");
    if (!panel || !form || !toggle) return;

    form.hidden = !isOpen;
    panel.dataset.expanded = isOpen ? "true" : "false";
    toggle.textContent = isOpen ? "Hide sign-up form" : "Create an account";
    if (!isOpen) {
      showSignupStatus("", "info");
    }
  }

  async function submitSignupForm(event) {
    event.preventDefault();
    const form = document.getElementById("lla-signup-form");
    if (!form) return;

    const formData = new FormData(form);
    const username = String(formData.get("username") || "").trim();
    const displayName = String(formData.get("display_name") || "").trim();
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");
    const submitButton = document.getElementById("lla-signup-submit");
    const minLength = authUiConfig.minPasswordLength || DEFAULT_AUTH_UI_CONFIG.minPasswordLength;

    if (!username) {
      showSignupStatus("Enter a username to create your account.", "error");
      return;
    }
    if (!password) {
      showSignupStatus("Enter a password to create your account.", "error");
      return;
    }
    if (password.length < minLength) {
      showSignupStatus(`Use a password with at least ${minLength} characters.`, "error");
      return;
    }
    if (password !== confirmPassword) {
      showSignupStatus("Passwords do not match yet. Re-enter them and try again.", "error");
      return;
    }

    showSignupStatus("Creating your account...", "info");
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.dataset.originalLabel = submitButton.textContent || "Create account";
      submitButton.textContent = "Creating account...";
    }

    try {
      const response = await fetch("/webui/auth/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          display_name: displayName || null,
          password,
          confirm_password: confirmPassword,
        }),
      });
      const data = await response.json().catch(() => ({
        success: false,
        message: "Account sign-up is unavailable right now. Please try again shortly.",
      }));

      if (!response.ok || !data.success) {
        showSignupStatus(
          String(data.message || "Account sign-up is unavailable right now. Please try again shortly."),
          "error"
        );
        return;
      }

      const loginUsername = findLoginUsernameInput();
      const loginPassword = findLoginPasswordInput();
      if (loginUsername) loginUsername.value = String(data.username || username);
      if (loginPassword) loginPassword.value = "";
      form.reset();
      setSignupMode(false);
      showSignupStatus(
        String(
          data.message ||
            (authUiConfig.requireAdminApproval
              ? "Account created. Please wait for approval before signing in."
              : "Account created. Please sign in.")
        ),
        "success"
      );
      if (loginPassword) loginPassword.focus();
    } catch (_) {
      showSignupStatus(
        "Account sign-up is unavailable right now. Please try again shortly.",
        "error"
      );
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = submitButton.dataset.originalLabel || "Create account";
      }
    }
  }

  function bindSignupUi(panel) {
    const toggle = panel.querySelector("#lla-signup-toggle");
    const cancelButton = panel.querySelector("#lla-signup-cancel");
    const form = panel.querySelector("#lla-signup-form");

    if (toggle) {
      toggle.addEventListener("click", () => {
        setSignupMode(form ? form.hidden : true);
      });
    }
    if (cancelButton) {
      cancelButton.addEventListener("click", () => setSignupMode(false));
    }
    if (form) {
      form.addEventListener("submit", submitSignupForm);
      form.querySelectorAll("input").forEach((input) => {
        input.addEventListener("input", () => {
          const messageNode = document.getElementById("lla-signup-message");
          if (messageNode && messageNode.dataset.state === "error") {
            showSignupStatus("", "info");
          }
        });
      });
    }
  }

  function createSignupPanel() {
    if (!isLoginPage() || !authUiConfig.signupEnabled) return null;

    const loginForm = findLoginForm();
    if (!loginForm || !loginForm.parentElement) return null;

    let panel = document.getElementById("lla-signup-panel");
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = "lla-signup-panel";
    panel.className = "lla-signup-panel";
    panel.dataset.expanded = "false";
    panel.innerHTML = `
      <div class="lla-signup-header">
        <div>
          <h2>Create an account</h2>
          <p>New here? Create a LanguageAgent account, then sign in to start chatting.</p>
        </div>
        <button id="lla-signup-toggle" class="lla-signup-toggle" type="button">Create an account</button>
      </div>
      <div id="lla-signup-message" class="lla-signup-message" role="status" aria-live="polite" hidden></div>
      <form id="lla-signup-form" class="lla-signup-form" hidden>
        <label class="lla-signup-field">
          <span>Username</span>
          <input name="username" type="text" autocomplete="username" maxlength="64" required />
        </label>
        <label class="lla-signup-field">
          <span>Display name <em>Optional</em></span>
          <input name="display_name" type="text" autocomplete="name" maxlength="80" />
        </label>
        <label class="lla-signup-field">
          <span>Password</span>
          <input name="password" type="password" autocomplete="new-password" required />
        </label>
        <label class="lla-signup-field">
          <span>Confirm password</span>
          <input name="confirm_password" type="password" autocomplete="new-password" required />
        </label>
        <p class="lla-signup-hint">Use a unique password with at least ${authUiConfig.minPasswordLength} characters.</p>
        <div class="lla-signup-actions">
          <button id="lla-signup-submit" class="lla-signup-submit" type="submit">Create account</button>
          <button id="lla-signup-cancel" class="lla-signup-cancel" type="button">Back to sign in</button>
        </div>
      </form>
    `;
    loginForm.parentElement.appendChild(panel);
    bindSignupUi(panel);
    return panel;
  }

  function normalizeAuthErrorText(text) {
    const normalized = String(text || "").trim();
    if (!normalized) return "";
    return AUTH_ERROR_MESSAGES.get(normalized.toLowerCase()) || "";
  }

  function shouldTreatAsAuthError(nodeText) {
    return Boolean(normalizeAuthErrorText(nodeText));
  }

  function enhanceAuthErrors() {
    if (!isLoginPage()) return;

    createSignupPanel();

    document
      .querySelectorAll('[role="alert"], [data-sonner-toast], [data-toast], .toast')
      .forEach((node) => {
        const friendlyMessage = normalizeAuthErrorText(node.textContent);
        if (!friendlyMessage) return;

        node.textContent = friendlyMessage;
        node.setAttribute("data-lla-auth-error", "true");
        showFriendlyAuthError(friendlyMessage);
      });

    const form = findLoginForm();
    if (!form) return;

    form.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]').forEach((input) => {
      if (input.dataset.llaAuthErrorBound === "true") return;
      input.dataset.llaAuthErrorBound = "true";
      input.addEventListener("input", () => {
        if (authBannerMessage) hideFriendlyAuthError();
      });
    });
  }

  function updateStatusCard(data) {
    latestStatusData = data;
    const card = createStatusCard();
    if (!card) return;
    applyStatusToCard(card, data);
    setRefreshLoading(card, false);
    syncVisibility();
  }

  function applyStatusToCard(card, data) {
    const online = data && data.status === "online";
    card.classList.toggle("lla-status-online", online);
    card.classList.toggle("lla-status-offline", !online);
    card.classList.remove("lla-status-pending");

    const title = card.querySelector(".lla-status-title");
    const target = card.querySelector(".lla-status-target");
    if (title) title.textContent = online ? "Language service online" : "Language service offline";
    if (target) target.textContent = `Backend target: ${data && data.target ? data.target : "not configured"}`;
  }

  function setPending() {
    const card = createStatusCard();
    if (!card) return;
    card.classList.add("lla-status-pending");
    card.classList.remove("lla-status-online", "lla-status-offline");
    const title = card.querySelector(".lla-status-title");
    if (title) title.textContent = "Checking language service";
    setRefreshLoading(card, true);
  }

  function setRefreshLoading(card, isLoading) {
    const refreshButton = card.querySelector(".lla-status-refresh");
    if (!refreshButton) return;
    refreshButton.disabled = isLoading;
    refreshButton.classList.toggle("lla-status-refresh-loading", isLoading);
  }

  async function refreshStatus() {
    setPending();
    try {
      const response = await fetch("/webui/backend-status", { cache: "no-store" });
      if (!response.ok) throw new Error("status unavailable");
      updateStatusCard(await response.json());
    } catch (_) {
      updateStatusCard({ status: "offline", target: "not reachable" });
    }
  }

  function boot() {
    createStatusCard();
    refreshStatus();
    syncVisibility();
    enhanceAccessibility();
    loadAuthUiConfig().then(() => enhanceAuthErrors());
    window.setTimeout(() => {
      composerEnhancementEnabled = true;
      enhanceAccessibility();
      enhanceAuthErrors();
    }, 3000);
    document.addEventListener("submit", markConversationStarted, true);
    document.addEventListener("click", (event) => {
      const button = event.target.closest && event.target.closest("button");
      if (!button) return;
      if (button.id === "chat-submit") {
        const textarea = document.querySelector("textarea");
        if (textarea && textarea.value.trim()) markConversationStarted();
        return;
      }
      const label = (button.textContent || button.getAttribute("aria-label") || "")
        .trim()
        .toLowerCase();
      if (CONVERSATION_START_LABELS.has(label)) markConversationStarted();
    }, true);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        const textarea = document.querySelector("textarea");
        if (textarea && textarea.value.trim()) {
          window.setTimeout(markConversationStarted, 100);
        }
      }
    }, true);
    new MutationObserver(() => {
      syncVisibility();
      enhanceAccessibility();
      enhanceAuthErrors();
    }).observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
