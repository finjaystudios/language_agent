(function () {
  const loginForm = document.getElementById("lla-login-form");
  const loginMessage = document.getElementById("lla-login-message");
  const loginSubmit = document.getElementById("lla-login-submit");
  const signupForm = document.getElementById("lla-signup-form");
  const signupMessage = document.getElementById("lla-signup-message");
  const signupSubmit = document.getElementById("lla-signup-submit");
  const minPasswordLength = Number(
    document.body?.dataset.minPasswordLength || "12"
  );

  function showMessage(node, message, state) {
    if (!node) return;
    node.textContent = message;
    node.hidden = !message;
    node.dataset.state = state || "error";
  }

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(loginMessage, "", "error");
    loginSubmit.disabled = true;
    loginSubmit.textContent = "Signing in...";
    const formData = new FormData(loginForm);

    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          username: String(formData.get("username") || "").trim(),
          password: String(formData.get("password") || ""),
        }),
      });
      if (!response.ok) {
        showMessage(
          loginMessage,
          "Sign-in failed. Check your username and password, then try again.",
          "error"
        );
        return;
      }
      window.location.href = "/";
    } catch (_error) {
      showMessage(
        loginMessage,
        "Sign-in is unavailable right now. Please try again shortly.",
        "error"
      );
    } finally {
      loginSubmit.disabled = false;
      loginSubmit.textContent = "Sign In";
    }
  });

  signupForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(signupMessage, "", "error");
    const formData = new FormData(signupForm);
    const username = String(formData.get("username") || "").trim();
    const displayName = String(formData.get("display_name") || "").trim();
    const password = String(formData.get("password") || "");
    const confirmPassword = String(formData.get("confirm_password") || "");

    if (!username) {
      showMessage(signupMessage, "Enter a username to create your account.", "error");
      return;
    }
    if (!password) {
      showMessage(signupMessage, "Enter a password to create your account.", "error");
      return;
    }
    if (password.length < minPasswordLength) {
      showMessage(
        signupMessage,
        `Use a password with at least ${minPasswordLength} characters.`,
        "error"
      );
      return;
    }
    if (password !== confirmPassword) {
      showMessage(
        signupMessage,
        "Passwords do not match yet. Re-enter them and try again.",
        "error"
      );
      return;
    }

    signupSubmit.disabled = true;
    signupSubmit.textContent = "Creating account...";
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
      const data = await response.json().catch(() => ({ success: false }));
      if (!response.ok || !data.success) {
        showMessage(
          signupMessage,
          String(
            data.message ||
              "Account sign-up is unavailable right now. Please try again shortly."
          ),
          "error"
        );
        return;
      }
      showMessage(
        signupMessage,
        String(data.message || "Account created. Please sign in."),
        "success"
      );
      signupForm.reset();
      if (loginForm?.elements?.username) {
        loginForm.elements.username.value = String(data.username || username);
      }
      if (loginForm?.elements?.password) {
        loginForm.elements.password.value = "";
        loginForm.elements.password.focus();
      }
    } catch (_error) {
      showMessage(
        signupMessage,
        "Account sign-up is unavailable right now. Please try again shortly.",
        "error"
      );
    } finally {
      signupSubmit.disabled = false;
      signupSubmit.textContent = "Create account";
    }
  });
})();
