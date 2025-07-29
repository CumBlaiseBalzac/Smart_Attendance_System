// Remember Me functionality
document.addEventListener("DOMContentLoaded", () => {
  const savedEmail = localStorage.getItem("rememberedEmail");
  if (savedEmail) {
    document.getElementById("email").value = savedEmail;
    document.getElementById("rememberMe").checked = true;
  }
});

// Show/Hide Password
document.getElementById("togglePassword").addEventListener("click", () => {
  const password = document.getElementById("password");
  const toggle = document.getElementById("togglePassword");
  if (password.type === "password") {
    password.type = "text";
    toggle.textContent = "Hide";
  } else {
    password.type = "password";
    toggle.textContent = "Show";
  }
});

// Handle Login
document.getElementById("loginForm").addEventListener("submit", (e) => {
  e.preventDefault();

  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();
  const remember = document.getElementById("rememberMe").checked;
  const errorMessage = document.getElementById("errorMessage");

  // Mock validation
  if (email === "admin@example.com" && password === "password123") {
    errorMessage.textContent = "";
    if (remember) {
      localStorage.setItem("rememberedEmail", email);
    } else {
      localStorage.removeItem("rememberedEmail");
    }
    alert("Login successful!");
    // Redirect to dashboard here if you want
  } else {
    errorMessage.textContent = "Invalid email or password!";
  }
});

// Forgot Password → Show Reset Form
document.getElementById("forgotPasswordLink").addEventListener("click", () => {
  document.getElementById("loginForm").classList.add("hidden");
  document.getElementById("resetForm").classList.remove("hidden");
  document.getElementById("errorMessage").textContent = "";
});

// Back to Login
document.getElementById("backToLoginLink").addEventListener("click", () => {
  document.getElementById("resetForm").classList.add("hidden");
  document.getElementById("loginForm").classList.remove("hidden");
  document.getElementById("resetMessage").textContent = "";
});

// Handle Reset Password
document.getElementById("resetForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const email = document.getElementById("resetEmail").value.trim();
  const resetMessage = document.getElementById("resetMessage");

  // Mock send
  if (email) {
    resetMessage.textContent = "A reset link has been sent to " + email;
  }
});
