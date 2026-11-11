/* The console's cloud mode, "On a rented cloud machine" / "Kiralık bulut makinesinde" (D-S49 item 3).
   Presentation only: every figure comes from the server (scripts/console_cloud.py), which reads it
   from the seal, the ledger and the controller's receipts. The page never asks for, holds or shows
   the provider key; a launch needs the cap typed back to the cent and a one-time code. */
var ShimmerCloud = (function () {
  "use strict";
  var TR = {
    "On a rented cloud machine": "Kiralık bulut makinesinde",
    "Provider key file found": "Sağlayıcı anahtar dosyası bulundu",
    "No provider key file found. Set SHIMMER_CONFIG_PATH to your own key file outside the repository, then reload.":
      "Sağlayıcı anahtar dosyası bulunamadı. SHIMMER_CONFIG_PATH değişkenini depo dışındaki kendi anahtar dosyanıza ayarlayın, sonra sayfayı yenileyin.",
    "The key is read only by the program that starts the machine; this page never asks for it and never shows it.":
      "Anahtarı yalnızca makineyi başlatan program okur; bu sayfa anahtarı hiçbir zaman istemez ve göstermez.",
    "Settings ready": "Ayarlar hazır",
    "Budget open": "Bütçe açık",
    "No budget is open. The operator opens one in the ledger; this page never does.":
      "Açık bütçe yok. Bütçeyi operatör kayıt defterinde açar; bu sayfa açmaz.",
    "left": "kalan",
    "Machines running": "Çalışan makineler",
    "no maximum; the total budget is the limit": "üst sınır yok; sınır toplam bütçedir",
    "Documents to review": "İncelenecek belgeler",
    "Reference documents (optional)": "Başvuru belgeleri (isteğe bağlı)",
    "Review conventions": "İnceleme kuralları",
    "Prepare (spends nothing)": "Hazırla (ücret doğmaz)",
    "Preparing": "Hazırlanıyor",
    "Ready to start": "Başlatmaya hazır",
    "Starting": "Başlatılıyor",
    "Running": "Çalışıyor",
    "Finished": "Bitti",
    "Stopped": "Durdu",
    "steps done": "adım tamamlandı",
    "seconds in this step": "saniyedir bu adımda",
    "Each step reports only on completion; the count of steps done is the measured progress.":
      "Her adım yalnızca bitince bildirir; ölçülen ilerleme, tamamlanan adım sayısıdır.",
    "Forecast time": "Öngörülen süre",
    "Forecast cost": "Öngörülen maliyet",
    "Most it can cost (the cap)": "En fazla maliyet (üst sınır)",
    "Machine": "Makine",
    "per hour": "saatlik",
    "Upload of the models included": "Modellerin yüklenmesi dahil",
    "Measured": "Ölçüldü",
    "Estimate": "Tahmin",
    "minutes": "dakika",
    "Get a confirmation code": "Onay kodu al",
    "This starts a rented machine that costs up to": "Bu, en fazla şu tutarda ücreti olan kiralık bir makine başlatır:",
    "It is shut down after the review.": "İnceleme bitince kapatılır.",
    "Type the amount to confirm": "Onaylamak için tutarı yazın",
    "The code expires at": "Kodun geçerliliği şu saatte biter:",
    "Start the rented machine": "Kiralık makineyi başlat",
    "Progress": "İlerleme",
    "Phase": "Aşama",
    "Actual time": "Gerçek süre",
    "Actual cost": "Gerçek maliyet",
    "upper bound": "üst sınır",
    "The machine was shut down.": "Makine kapatıldı.",
    "The machine was NOT confirmed shut down. Check the provider's console now.":
      "Makinenin kapatıldığı DOĞRULANMADI. Sağlayıcının konsoluna hemen bakın.",
    "Minutes per part": "Bölüm başına dakika",
    "start_machine": "Makineyi başlatma",
    "copy_files": "Dosyaları kopyalama",
    "prepare_machine": "Makineyi hazırlama",
    "review": "İnceleme",
    "collect_results": "Sonuçları toplama",
    "shut_down": "Kapatma",
    "other": "Diğer",
    "Results": "Sonuçlar",
    "Plans on this computer": "Bu bilgisayardaki planlar",
    "Your results": "Sonuçlarınız",
    "Download all files of this document": "Bu belgenin tüm dosyalarını indir",
    "Download": "İndir",
    "This run's own files": "Bu çalışmanın kendi dosyaları",
    "The results were not collected into this run folder": "Sonuçlar bu çalışma klasörüne toplanmadı",
    "The request did not reach the server.": "İstek sunucuya ulaşmadı."
  };
  var DOCS = {
    en: "Your documents are copied to the rented machine for this review and deleted with it when it is shut down.",
    tr: "Belgeleriniz bu inceleme için kiralık makineye kopyalanır ve makine kapatılınca onunla birlikte silinir."
  };
  function lang() { return ShimmerLocale.language() === "tr" ? "tr" : "en"; }
  function t(s) { return lang() === "tr" && Object.prototype.hasOwnProperty.call(TR, s) ? TR[s] : s; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function head() {
    return "<h2>" + esc(t("On a rented cloud machine")) + "</h2><p class=\"notice\">" + esc(DOCS[lang()]) + "</p>";
  }
  function money(x) { return x == null ? "-" : esc(Number(x).toFixed(2)) + " USD"; }
  function basisLine(basis) {
    if (!basis) return "";
    if (basis.kind === "measured") {
      var on = basis.measured_on || {};
      return "<p><strong>" + esc(t("Measured")) + "</strong>: " + esc(on.date) + ", " + esc(on.machine) + "</p>";
    }
    return "<p><strong>" + esc(t("Estimate")) + "</strong>: " + esc(basis.rests_on) + "</p>";
  }
  function stateWord(s) {
    return t({ preparing: "Preparing", ready: "Ready to start", launching: "Starting", launched: "Running",
               finished: "Finished", failed: "Stopped" }[s] || s);
  }

  var timer = null;
  function stop() { if (timer) { clearTimeout(timer); timer = null; } }

  function renderSetup(app, deps) {
    stop();
    app.innerHTML = head();
    deps.apiJson("/cloud").then(function (res) {
      if (!res.ok) { app.innerHTML = head() + "<div class=\"notice error\">" + esc(deps.detailText(res.body)) + "</div>"; return; }
      var s = res.body, b = s.budget || {}, html = head() + "<ul>";
      html += "<li>" + (s.credential_found ? esc(t("Provider key file found"))
        : "<strong>" + esc(t("No provider key file found. Set SHIMMER_CONFIG_PATH to your own key file outside the repository, then reload.")) + "</strong>")
        + " " + esc(t("The key is read only by the program that starts the machine; this page never asks for it and never shows it.")) + "</li>";
      html += "<li>" + (s.settings_ready ? esc(t("Settings ready")) : "<strong>" + esc(ShimmerLocale.message(s.settings_problem)) + "</strong>") + "</li>";
      html += "<li>" + (b.budget_open ? esc(t("Budget open")) + ": " + money(b.left_usd) + " " + esc(t("left"))
        : "<strong>" + esc(t("No budget is open. The operator opens one in the ledger; this page never does.")) + "</strong>") + "</li>";
      html += "<li>" + esc(t("Machines running")) + ": " + esc(b.running_instances == null ? 0 : b.running_instances)
        + ", " + esc(t("no maximum; the total budget is the limit")) + "</li></ul>";
      var ready = s.credential_found && s.settings_ready && b.budget_open;
      html += "<form id=\"cloud-form\"><p><label>" + esc(t("Documents to review")) + " <input type=\"file\" id=\"cloud-target\" multiple></label></p>"
        + "<p><label>" + esc(t("Reference documents (optional)")) + " <input type=\"file\" id=\"cloud-grounding\" multiple></label></p>"
        + "<p><label>" + esc(t("Review conventions")) + " <input type=\"file\" id=\"cloud-conventions\" multiple></label></p>"
        + "<p><button type=\"submit\"" + (ready ? "" : " disabled") + ">" + esc(t("Prepare (spends nothing)")) + "</button></p>"
        + "<div id=\"cloud-result\"></div></form>";
      if ((s.plans || []).length) {
        html += "<h3>" + esc(t("Plans on this computer")) + "</h3><ul>";
        s.plans.forEach(function (p) {
          html += "<li><a href=\"#/cloud/" + encodeURIComponent(p.plan_id) + "\">" + esc(p.plan_id) + "</a> "
            + esc(stateWord(p.state)) + " " + esc((p.targets || []).join(", ")) + "</li>";
        });
        html += "</ul>";
      }
      app.innerHTML = html;
      document.getElementById("cloud-form").addEventListener("submit", function (e) {
        e.preventDefault();
        var form = new FormData(), roles = {};
        [["cloud-target", "target"], ["cloud-grounding", "grounding"], ["cloud-conventions", "conventions"]].forEach(function (pair) {
          Array.prototype.forEach.call(document.getElementById(pair[0]).files, function (f) {
            form.append("files", f, f.name); roles[f.name] = pair[1];
          });
        });
        form.append("roles", JSON.stringify(roles));
        deps.apiJson("/cloud/plans", { method: "POST", body: form }).then(function (r) {
          if (r.ok) location.hash = "#/cloud/" + encodeURIComponent(r.body.plan_id);
          else document.getElementById("cloud-result").innerHTML = "<div class=\"notice error\">" + esc(deps.detailText(r.body)) + "</div>";
        });
      });
    }).catch(function () { app.innerHTML = head() + "<div class=\"notice error\">" + esc(t("The request did not reach the server.")) + "</div>"; });
  }

  function partsTable(parts) {
    if (!parts) return "";
    var rows = Object.keys(parts).filter(function (k) { return parts[k] !== null && (parts[k] > 0 || k === "review"); });
    return "<h3>" + esc(t("Minutes per part")) + "</h3><table><tbody>" + rows.map(function (k) {
      return "<tr><td>" + esc(t(k)) + "</td><td>" + esc(parts[k]) + "</td></tr>";
    }).join("") + "</tbody></table>";
  }

  function deliverablesHtml(planId, d) {
    if (!d) return "";
    if (!d.available) return "<p><strong>" + esc(t(d.why)) + "</strong></p>";
    var base = "/cloud/plans/" + encodeURIComponent(planId);
    function fileButton(doc, f) {
      return "<button type=\"button\" class=\"button secondary\" data-cloud-download=\"" + esc(base + "/files/" + encodeURIComponent(doc) + "/"
        + f.name.split("/").map(encodeURIComponent).join("/")) + "\" data-name=\"" + esc(f.name.split("/").pop()) + "\">"
        + esc(t("Download")) + "</button> " + esc(f.name) + " (" + esc(f.bytes) + " B)";
    }
    var html = "<h3>" + esc(t("Your results")) + "</h3>";
    (d.documents || []).forEach(function (doc) {
      html += "<h4>" + esc(doc.doc_id) + "</h4><p><button type=\"button\" class=\"button\" data-cloud-download=\""
        + esc(base + "/deliverables/" + encodeURIComponent(doc.doc_id)) + "\" data-name=\"" + esc(doc.doc_id) + ".zip\">"
        + esc(t("Download all files of this document")) + "</button></p><ul>"
        + doc.files.map(function (f) { return "<li>" + fileButton(doc.doc_id, f) + "</li>"; }).join("") + "</ul>";
    });
    if ((d.run_files || []).length) {
      html += "<h4>" + esc(t("This run's own files")) + "</h4><ul>"
        + d.run_files.map(function (f) { return "<li>" + fileButton("_run", f) + "</li>"; }).join("") + "</ul>";
    }
    return html;
  }

  function renderPlan(app, deps, planId) {
    stop();
    deps.apiJson("/cloud/plans/" + encodeURIComponent(planId)).then(function (res) {
      if (deps.currentPlan() !== planId) return;
      if (!res.ok) { app.innerHTML = head() + "<div class=\"notice error\">" + esc(deps.detailText(res.body)) + "</div>"; return; }
      var p = res.body, q = p.quote || {}, html = head() + "<p><strong>" + esc(stateWord(p.state)) + "</strong> "
        + esc((p.targets || []).join(", ")) + "</p>";
      if (p.error) html += "<div class=\"notice error\">" + esc(ShimmerLocale.message(p.error)) + "</div>";
      if (p.preparation) {
        html += "<p>" + esc(p.preparation.done) + " / " + esc(p.preparation.total) + " " + esc(t("steps done"))
          + (p.preparation.step ? ", " + esc(p.preparation.step) + ": " + esc(p.preparation.step_seconds) + " " + esc(t("seconds in this step")) : "")
          + "</p><p class=\"muted\">" + esc(t("Each step reports only on completion; the count of steps done is the measured progress.")) + "</p>";
      }
      if (p.quote) {
        html += "<table><tbody><tr><td>" + esc(t("Forecast time")) + "</td><td>" + esc(q.forecast_minutes) + " " + esc(t("minutes")) + "</td></tr>"
          + "<tr><td>" + esc(t("Forecast cost")) + "</td><td>" + money(q.forecast_usd) + "</td></tr>"
          + "<tr><td>" + esc(t("Most it can cost (the cap)")) + "</td><td>" + esc(q.cap_text) + " USD</td></tr>"
          + "<tr><td>" + esc(t("Machine")) + "</td><td>" + esc(q.instance_type) + ", " + money(q.hourly_rate_usd) + " " + esc(t("per hour")) + "</td></tr>"
          + (q.upload_in_forecast ? "<tr><td colspan=\"2\">" + esc(t("Upload of the models included")) + "</td></tr>" : "")
          + "</tbody></table>" + basisLine(p.basis);
      }
      if (p.state === "ready") html += "<p><button type=\"button\" id=\"cloud-code\">" + esc(t("Get a confirmation code")) + "</button></p><div id=\"cloud-confirm\"></div>";
      if (p.progress) html += "<p><strong>" + esc(t("Progress")) + "</strong>: " + esc(p.progress) + "</p>";
      if (p.phase) html += "<p>" + esc(t("Phase")) + ": " + esc(p.phase) + "</p>";
      if (p.run_error) html += "<div class=\"notice error\">" + esc(ShimmerLocale.message(p.run_error)) + "</div>";
      var o = p.outcome;
      if (o) {
        html += "<p><strong>" + esc(o.shut_down ? t("The machine was shut down.") : t("The machine was NOT confirmed shut down. Check the provider's console now.")) + "</strong></p>"
          + "<table><tbody><tr><td>" + esc(t("Actual time")) + "</td><td>" + esc(o.actual_minutes) + " " + esc(t("minutes")) + "</td></tr>"
          + "<tr><td>" + esc(t("Actual cost")) + "</td><td>" + money(o.actual_cost_usd) + " (" + esc(t("upper bound")) + " " + money(o.cost_upper_bound_usd) + ")</td></tr>"
          + "<tr><td>" + esc(t("Results")) + "</td><td>" + esc(o.results_folder) + "</td></tr></tbody></table>"
          + "<p class=\"muted\">" + esc(o.cost_note) + "</p>" + partsTable(o.parts_minutes) + "<p class=\"muted\">" + esc(o.parts_note) + "</p>";
        if (o.gone) html += "<p><strong>" + esc(o.gone[lang()]) + "</strong></p>";
        html += deliverablesHtml(planId, o.deliverables);
      }
      app.innerHTML = html;
      if (app.querySelectorAll && deps.download) app.querySelectorAll("[data-cloud-download]").forEach(function (b) {
        b.addEventListener("click", function () { deps.download(b.getAttribute("data-cloud-download"), b.getAttribute("data-name"), b); });
      });
      var button = document.getElementById("cloud-code");
      if (button) button.addEventListener("click", function () { confirmStep(planId, deps); });
      if (["preparing", "launching", "launched"].indexOf(p.state) >= 0)
        timer = setTimeout(function () { renderPlan(app, deps, planId); }, p.state === "preparing" ? 5000 : 15000);
    }).catch(function () { app.innerHTML = head() + "<div class=\"notice error\">" + esc(t("The request did not reach the server.")) + "</div>"; });
  }

  function confirmStep(planId, deps) {
    stop();
    deps.apiJson("/cloud/plans/" + encodeURIComponent(planId) + "/confirmation", { method: "POST" }).then(function (r) {
      var box = document.getElementById("cloud-confirm");
      if (!box) return;
      if (!r.ok) { box.innerHTML = "<div class=\"notice error\">" + esc(deps.detailText(r.body)) + "</div>"; return; }
      var c = r.body;
      box.innerHTML = "<p>" + esc(t("This starts a rented machine that costs up to")) + " <strong>" + esc(c.quote.cap_text) + " USD</strong>. "
        + esc(t("It is shut down after the review.")) + "</p>" + basisLine(c.basis)
        + "<p><label>" + esc(t("Type the amount to confirm")) + " <input id=\"cloud-amount\" inputmode=\"decimal\" autocomplete=\"off\"></label></p>"
        + "<p class=\"muted\">" + esc(t("The code expires at")) + " " + esc(c.expires_utc) + "</p>"
        + "<p><button type=\"button\" id=\"cloud-start\">" + esc(t("Start the rented machine")) + "</button></p><div id=\"cloud-start-result\"></div>";
      document.getElementById("cloud-start").addEventListener("click", function () {
        var form = new FormData();
        form.append("code", c.code);
        form.append("confirm_cap_usd", document.getElementById("cloud-amount").value.trim());
        this.disabled = true;
        deps.apiJson("/cloud/plans/" + encodeURIComponent(planId) + "/launch", { method: "POST", body: form }).then(function (l) {
          if (l.ok) deps.rerender();
          else document.getElementById("cloud-start-result").innerHTML = "<div class=\"notice error\">" + esc(deps.detailText(l.body)) + "</div>";
        });
      });
    });
  }

  return { renderSetup: renderSetup, renderPlan: renderPlan, stop: stop, text: t, documents: DOCS };
})();
