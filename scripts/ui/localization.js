/* Presentation only. Never translate source quotations, input values or API objects. */
var ShimmerLocale = (function () {
  "use strict";
  var language = "en", formBindings = [], catalog = SHIMMER_TR;
  try { language = sessionStorage.getItem("shimmer_output_language") === "tr" ? "tr" : "en"; } catch (_) {}
  function text(original, lang) {
    if ((lang || language) !== "tr" || typeof original !== "string") return original;
    if (Object.prototype.hasOwnProperty.call(catalog, original)) return catalog[original];
    var trimmed=original.trim();
    return Object.prototype.hasOwnProperty.call(catalog, trimmed)
      ? original.slice(0,original.length-original.trimStart().length)+catalog[trimmed]+original.slice(original.trimEnd().length)
      : original;
  }
  function value(original, fallback, lang) {
    var values = catalog._values || {};
    return (lang || language) === "tr" && Object.prototype.hasOwnProperty.call(values, original)
      ? values[original] : (fallback === undefined ? original : fallback);
  }
  function message(original, lang) {
    if ((lang || language) !== "tr" || typeof original !== "string") return original;
    if (Object.prototype.hasOwnProperty.call(catalog, original)) return catalog[original];
    for (var row of (catalog._messages || [])) {
      var match = original.match(new RegExp(row.pattern, "s"));
      if (match) return row.translation.replace(/\{(\d+)\}/g, function (_, n) { return match[Number(n) + 1]; });
    }
    // Unrecognized diagnostics remain exact, never replaced by an invented explanation.
    return original;
  }
  function english(original) {
    if (language === "en") return original;
    for (var key of Object.keys(catalog)) if (typeof catalog[key] === "string" && catalog[key] === original) return key;
    return original;
  }
  function refresh() {
    if (typeof document === "undefined") return;
    document.documentElement.lang = language;
    document.title = text("Project Shimmer: Review desk");
    var labels = {"nav-runs":"Runs", "nav-submit":"Submit", "nav-agents":"Agents",
      "view-switch-human":"Reviewer", "view-switch-developer":"Developer", "ui-language-label":"Output language"};
    Object.keys(labels).forEach(function (id) { var el=document.getElementById(id); if(el) el.textContent=text(labels[id]); });
    var masthead=document.querySelector(".masthead-name"); if(masthead) masthead.textContent=text("SHIMMER: Review desk");
    var views=document.getElementById("view-switch"); if(views) views.setAttribute("aria-label",text("Language"));
    var control=document.getElementById("ui-language"); if(control) control.value=language;
    if(control && control.options && control.options[0]) control.options[0].textContent=text("English");
    formBindings=formBindings.filter(function (b) { return b.node.isConnected; });
    formBindings.forEach(function (b) {
      if(b.attribute) b.node.setAttribute(b.attribute,text(b.original)); else b.node.nodeValue=text(b.original);
    });
    var selector=document.getElementById("s-language"); if(selector) selector.value=language;
  }
  function select(lang) {
    language=lang === "tr" ? "tr" : "en";
    try { sessionStorage.setItem("shimmer_output_language",language); } catch (_) {}
    refresh();
  }
  function bindForm(form) {
    // Capture only the static form shell before filenames, source text or server responses arrive.
    var walk=document.createTreeWalker(form,4), node;
    while((node=walk.nextNode())) {
      if(node.parentElement && /^(TEXTAREA|SCRIPT|STYLE)$/.test(node.parentElement.tagName)) continue;
      var original=english(node.nodeValue.trim());
      if(Object.prototype.hasOwnProperty.call(catalog,original)) {
        var whitespace=node.nodeValue.match(/^(\s*)[\s\S]*?(\s*)$/);
        formBindings.push({node:node,original:whitespace[1]+original+whitespace[2]});
      }
    }
    form.querySelectorAll("[placeholder], [aria-label], [title]").forEach(function (el) {
      ["placeholder","aria-label","title"].forEach(function (attr) {
        if(el.hasAttribute(attr)) formBindings.push({node:el,attribute:attr,original:english(el.getAttribute(attr))});
      });
    });
    var selector=document.getElementById("s-language");
    selector.value=language;
    selector.addEventListener("change",function () { select(selector.value); });
  }
  return {text:text,value:value,message:message,select:select,refresh:refresh,bindForm:bindForm,
    language:function () {return language;}};
})();
