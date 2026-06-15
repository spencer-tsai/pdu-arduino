// Admin user-management page: list, create, and delete users via the REST API.
(function () {
  "use strict";

  const tbody = document.getElementById("users-body");
  const form = document.getElementById("create-form");
  const msg = document.getElementById("create-msg");
  const refreshBtn = document.getElementById("refresh-users");
  const currentUserId = window.CURRENT_USER_ID;

  function showMsg(text, ok) {
    msg.textContent = text;
    msg.classList.remove("ok", "err");
    msg.classList.add(ok ? "ok" : "err");
    msg.hidden = false;
  }

  function clearMsg() {
    msg.hidden = true;
    msg.textContent = "";
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function rowFor(user) {
    const isSelf = user.id === currentUserId;
    const tr = document.createElement("tr");
    tr.innerHTML =
      "<td>" + escapeHtml(user.id) + "</td>" +
      "<td>" + escapeHtml(user.username) +
      (isSelf ? '<span class="you-tag">(you)</span>' : "") + "</td>" +
      '<td><span class="role-badge role-' + escapeHtml(user.role) + '">' +
      escapeHtml(user.role) + "</span></td>" +
      '<td class="col-actions"></td>';

    const actions = tr.querySelector(".col-actions");
    if (!isSelf) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-danger btn-sm";
      btn.textContent = "Delete";
      btn.addEventListener("click", () => deleteUser(user));
      actions.appendChild(btn);
    } else {
      actions.innerHTML = '<span class="muted small">&mdash;</span>';
    }
    return tr;
  }

  async function loadUsers() {
    tbody.innerHTML = '<tr><td colspan="4" class="muted">Loading&hellip;</td></tr>';
    try {
      const res = await fetch("/api/users", { headers: { Accept: "application/json" } });
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const users = await res.json();
      tbody.innerHTML = "";
      if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="muted">No users.</td></tr>';
        return;
      }
      users.forEach((u) => tbody.appendChild(rowFor(u)));
    } catch (err) {
      tbody.innerHTML =
        '<tr><td colspan="4" class="muted">Failed to load users.</td></tr>';
    }
  }

  async function deleteUser(user) {
    if (!window.confirm('Delete user "' + user.username + '"?')) return;
    try {
      const res = await fetch("/api/users/" + user.id, {
        method: "DELETE",
        headers: { Accept: "application/json" },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMsg(data.error || "Could not delete user.", false);
        return;
      }
      clearMsg();
      loadUsers();
    } catch (err) {
      showMsg("Could not reach the server.", false);
    }
  }

  async function createUser(event) {
    event.preventDefault();
    clearMsg();
    const payload = {
      username: document.getElementById("new-username").value.trim(),
      password: document.getElementById("new-password").value,
      role: document.getElementById("new-role").value,
    };
    try {
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showMsg(data.error || "Could not create user.", false);
        return;
      }
      showMsg('Created user "' + data.username + '".', true);
      form.reset();
      loadUsers();
    } catch (err) {
      showMsg("Could not reach the server.", false);
    }
  }

  form.addEventListener("submit", createUser);
  refreshBtn.addEventListener("click", loadUsers);

  loadUsers();
})();
