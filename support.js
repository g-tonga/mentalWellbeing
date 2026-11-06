/* Milestone 2 frontend: support options plus the human-escalation card.
   Reads the page's theme variables, so it matches light and dark mode. */
(function () {
  "use strict";

  const sid =
    (crypto.randomUUID && crypto.randomUUID()) ||
    "s" + Date.now() + Math.random().toString(16).slice(2);
  const $ = (id) => document.getElementById(id);
  const el = (tag, props = {}, ...kids) => {
    const n = document.createElement(tag);
    Object.assign(n, props);
    kids.forEach((k) => n.append(k));
    return n;
  };

  const style = document.createElement("style");
  style.textContent = `
    .sp-card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:16px;display:grid;gap:10px}
    .sp-escalate{border-left:6px solid var(--alert)}
    .sp-card h3{margin:0}
    .sp-demo{background:var(--sage);border-radius:12px;padding:8px 12px;font-size:.9rem;margin:0}
    .sp-note{font-size:.85rem;color:var(--muted);margin:0}
    .sp-label{font-weight:600;margin:4px 0 0}
    .sp-check{display:flex;gap:10px;align-items:flex-start;font-size:.95rem}
    .sp-chips{display:flex;gap:8px;flex-wrap:wrap}
    .sp-input{font:inherit;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--screen);color:var(--ink);width:100%}
    .sp-status{margin:0;font-weight:600;min-height:1.2em}
    .sp-card a.btn{text-decoration:none}
    .sp-tier{border:1px solid var(--line);border-radius:16px;padding:10px 14px;background:var(--screen)}
    .sp-tier summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:8px;font-weight:600}
    .sp-dots{display:inline-flex;gap:3px}
    .sp-dots span{width:8px;height:8px;border-radius:50%;background:var(--line)}
    .sp-dots span.on{background:var(--trend)}
    .sp-tier p{margin:8px 0 0;font-size:.95rem}
    .sp-items{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:10px}
    .sp-items li{border-top:1px solid var(--line);padding-top:10px}
    .sp-badge{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:999px;background:var(--sage);font-size:.75rem;font-weight:600}
  `;
  document.head.append(style);

  const STATUS_TEXT = {
    new: "Request received. Waiting for a counsellor to pick it up.",
    acknowledged: "A counsellor has seen your request.",
    contacted: "A counsellor has marked you as contacted.",
  };

  let pollTimer = null;
  let caseId = null;

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPolling(statusEl) {
    stopPolling();
    pollTimer = setInterval(async () => {
      if (!caseId) return stopPolling();
      try {
        const res = await fetch("/api/escalate/" + caseId);
        if (res.status === 404) {
          statusEl.textContent = "This request is no longer active.";
          caseId = null;
          return stopPolling();
        }
        if (!res.ok) return;
        const j = await res.json();
        statusEl.textContent = STATUS_TEXT[j.status] || j.status;
        if (j.status === "contacted") stopPolling();
      } catch (e) {
        /* network blip: try again on the next tick */
      }
    }, 5000);
  }

  function buildEscalation(data) {
    const card = el("div", {
      id: "escalateCard",
      className: "sp-card sp-escalate",
    });
    card.append(el("h3", { textContent: "Talk to a person" }));
    card.append(
      el("p", {
        className: "sp-demo",
        textContent:
          "Demo mode: this prototype does not contact a real counsellor. In a real emergency, call the numbers above.",
      }),
    );

    const consent = el("input", { type: "checkbox", id: "escConsent" });
    card.append(
      el(
        "label",
        { className: "sp-check", htmlFor: "escConsent" },
        consent,
        el("span", {
          textContent:
            "I agree to share my result category (for example: PHQ-9, severe range) and the contact detail below with a counsellor. I can withdraw this at any time.",
        }),
      ),
    );

    let channel = "call";
    const chips = el("div", { className: "sp-chips" });
    [
      ["call", "Call me"],
      ["message", "Message me"],
    ].forEach(([value, label]) => {
      const b = el("button", {
        type: "button",
        className: "chip" + (value === channel ? " on" : ""),
        textContent: label,
      });
      b.addEventListener("click", () => {
        channel = value;
        chips
          .querySelectorAll(".chip")
          .forEach((c) => c.classList.toggle("on", c === b));
      });
      chips.append(b);
    });
    card.append(
      el("p", {
        className: "sp-label",
        textContent: "How would you like to be reached?",
      }),
      chips,
    );

    const hint = el("input", {
      type: "text",
      className: "sp-input",
      maxLength: 64,
      placeholder: "Phone number or handle (optional)",
    });
    hint.setAttribute("aria-label", "Contact detail, optional");
    card.append(hint);

    const send = el("button", {
      type: "button",
      className: "btn block",
      textContent: "Request a counsellor",
      disabled: true,
    });
    const withdraw = el("button", {
      type: "button",
      className: "btn ghost block",
      textContent: "Withdraw my request",
      hidden: true,
    });
    const status = el("p", { className: "sp-status" });
    status.setAttribute("aria-live", "polite");

    const setLocked = (locked) => {
      consent.disabled = locked;
      hint.disabled = locked;
      chips.querySelectorAll("button").forEach((b) => {
        b.disabled = locked;
      });
    };

    consent.addEventListener("change", () => {
      send.disabled = !consent.checked;
    });

    send.addEventListener("click", async () => {
      send.disabled = true;
      status.textContent = "Sending...";
      try {
        const res = await fetch("/api/escalate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sid,
            region: $("region").value,
            instrument: data.instrument,
            band: data.band,
            crisis_flag: !!data.crisis_flag,
            consent: true,
            channel,
            contact_hint: hint.value.trim() || null,
          }),
        });
        if (!res.ok) throw new Error("status " + res.status);
        const j = await res.json();
        caseId = j.case_id;
        status.textContent = STATUS_TEXT[j.status] || j.status;
        setLocked(true);
        withdraw.hidden = false;
        startPolling(status);
      } catch (e) {
        status.textContent =
          "Could not send the request. Please use the phone numbers above.";
        send.disabled = !consent.checked;
      }
    });

    withdraw.addEventListener("click", async () => {
      withdraw.disabled = true;
      try {
        if (caseId)
          await fetch("/api/escalate/" + caseId, { method: "DELETE" });
      } catch (e) {
        /* the case expires on its own after 24 hours */
      }
      stopPolling();
      caseId = null;
      status.textContent = "Request withdrawn. Nothing about it is kept.";
      withdraw.hidden = true;
      withdraw.disabled = false;
      setLocked(false);
      send.disabled = !consent.checked;
    });

    card.append(send, status, withdraw);

    const msg =
      "Hi, I'm having a hard time right now and could use someone to talk to. Could you call me or come over?";
    card.append(
      el("a", {
        className: "btn ghost block",
        href: "sms:?&body=" + encodeURIComponent(msg),
        textContent: "Message someone I trust",
      }),
      el("p", {
        className: "sp-note",
        textContent:
          "This opens your own messaging app. Nothing is sent through this site.",
      }),
    );
    return card;
  }

  function buildPlan(plan) {
    const card = el("div", { id: "supportPlan", className: "sp-card" });
    card.append(el("h3", { textContent: "Your support options" }));
    card.append(el("p", { textContent: plan.rationale }));
    card.append(
      el("p", { className: "sp-note", textContent: plan.directory_note }),
    );

    plan.tiers.forEach((t, idx) => {
      const details = el("details", { className: "sp-tier" });
      if (idx === 0) details.open = true;

      const dots = el("span", { className: "sp-dots" });
      dots.setAttribute("role", "img");
      dots.setAttribute("aria-label", "Intensity " + t.level + " of 5");
      for (let i = 1; i <= 5; i++)
        dots.append(el("span", { className: i <= t.level ? "on" : "" }));
      details.append(
        el("summary", {}, el("span", { textContent: t.label }), dots),
      );

      details.append(
        el(
          "p",
          {},
          el("strong", { textContent: "Who it is for: " }),
          t.eligibility,
        ),
      );
      details.append(
        el(
          "p",
          {},
          el("strong", { textContent: "What happens next: " }),
          t.what_happens,
        ),
      );

      const list = el("ul", { className: "sp-items" });
      t.items.forEach((item) => {
        const li = el("li");
        const title = el("strong", { textContent: item.name });
        if (item.kind === "service" && !item.verified) {
          title.append(
            el("span", {
              className: "sp-badge",
              textContent: "Placeholder, verify before use",
            }),
          );
        }
        li.append(title, el("p", { textContent: item.description }));
        li.append(
          el(
            "p",
            {},
            el("strong", { textContent: "How to reach it: " }),
            item.how_to_reach,
          ),
        );
        list.append(li);
      });
      details.append(list);
      card.append(details);
    });
    return card;
  }

  function render(data) {
    stopPolling();
    caseId = null;
    ["escalateCard", "supportPlan"].forEach((id) => {
      const n = $(id);
      if (n) n.remove();
    });

    const anchor = $("support");
    if (data.urgent && anchor)
      anchor.insertAdjacentElement("afterend", buildEscalation(data));

    const plan = data.support_plan;
    if (plan && plan.tiers && plan.tiers.length)
      $("v-result").append(buildPlan(plan));
  }

  window.Support = { render };
})();
