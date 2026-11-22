  /* ---------- Round tables: the views ----------
     Inserted into build/template-playbook.html at its views placeholder by build/build.py. A workshop's views.js defines
     VIEWS (id -> [render function, label]), ALIASES (id -> [view, section to scroll to]) and DETAIL(id) (a detail
     page's {html, label, nav, item}, or null), using the shared helpers above it in the template. */

  var byId = {}; D.challenges.forEach(function(c){ byId[c.id] = c; });
  var themeById = {}; D.themes.forEach(function(t){ themeById[t.id] = t; });

  function actionCount(){ return D.challenges.reduce(function(n, c){ return n + c.actions.length; }, 0); }

  // Where each piece of content comes from on the day. Mirrors the paper kit in forum-to-playbook.html.
  var FROM = {
    title: "From Sheet 1, “The one we’re tackling”. It’s also on the table’s tent card.",
    summary: "One or two sentences on why it’s hard, from Sheet 1 and the table lead’s voice note.",
    quote: "From the side sheet, Quotes column. Exact words, labelled by sector only.",
    helped: "From Sheet 2, Helped column. One line each, with who it worked for.",
    hindered: "From Sheet 2, Got in the way column. One line each, with who it was for.",
    lesson: "From Sheet 2, “If we did it again, we’d…”",
    question: "From the side sheet, Questions column.",
    resource: "From the side sheet, Resources column. Every link gets checked before publishing.",
    theme: "Every challenge from every table’s Sheet 1, grouped into themes. The ring lights up the tables that raised each one.",
    commitment: "From the commitment card stubs in the box by the door, with a name and organisation only if the person added them."
  };

  function viewOverview(){
    var themes = D.themes.slice().sort(function(a, b){ return b.tables.length - a.tables.length; });
    var challengesFor = {};
    D.challenges.forEach(function(c){ (challengesFor[c.theme] = challengesFor[c.theme] || []).push(c); });

    var themeHtml = themes.map(function(t){
      var linked = (challengesFor[t.id] || []).map(function(c){
        return '<p class="go"><a href="#' + esc(c.id) + '">Read: ' + esc(titleOf(c)) + '</a></p>';
      }).join("");
      var heard = t.heard && t.heard.length ? '<p class="heard"><span class="muted">Heard: </span>' +
        t.heard.map(function(h){ return "<q>" + esc(h) + "</q>"; }).join(" ") + "</p>" : "";
      return '<li class="theme">' + ring(t.tables, {centre: t.tables.length}) +
        '<div><h3>' + esc(t.label) + '</h3><p class="tables">' + t.tables.length + " of " + M.tables + " tables · " + tablesText(t.tables) + '</p></div>' +
        heard + linked + '</li>';
    }).join("");
    if (!themes.length && SLOTS){
      themeHtml = [0, 1, 2].map(function(i){
        return '<li class="theme is-slot">' + ring([]) + '<div>' + slot("Theme " + (i + 1), i ? "Grouped from Sheet 1." : FROM.theme) + '</div></li>';
      }).join("");
    }

    var cards = D.challenges.slice().sort(function(a, b){ return b.tables.length - a.tables.length; }).map(function(c){
      var th = themeById[c.theme];
      var acts = c.actions.length ? plural(c.actions.length, "action") + " to try" : (SLOTS ? "Actions to fill" : "");
      return '<li class="card' + (c.title ? "" : " is-empty") + '">' +
        (th ? '<p class="eyebrow">' + esc(th.label) + '</p>' : (SLOTS ? '<p class="eyebrow">' + inlineSlot("Theme to fill") + '</p>' : "")) +
        '<h3><a href="#' + esc(c.id) + '">' + esc(titleOf(c)) + '</a></h3>' +
        (c.summary ? '<p>' + esc(c.summary) + '</p>' : (SLOTS ? '<p class="muted">Title, summary and everything else on this page come from this table’s sheets.</p>' : "")) +
        '<p class="foot">' + ring(c.tables) + '<span>' + tablesText(c.tables) + (acts ? ' · ' + acts : "") + '</span></p>' +
        (c.title ? '<span class="go" aria-hidden="true">Explore this challenge' + ICON_ARROW + '</span>' : "") +
        '</li>';
    }).join("");

    // "Heard on the day": side-sheet quotes and things written in quotation marks on the main sheets, all in one place
    var cById = {};
    D.challenges.forEach(function(c){ cById[c.id] = c; });
    var heard = (D.quotes || []).map(function(q){
      var c = cById[q.challenge], t = q.tables || [];
      var where = t.length > 1 ? "Written at " + tablesText(t, true) : t.length ? tablesText(t) : "";
      var cap = [where, c ? '<a href="#' + esc(c.id) + '">' + esc(titleOf(c)) + '</a>' : ""].filter(Boolean).join(" · ") + srcTag(q);
      return '<li><figure class="quote"><blockquote><p>' + esc(q.text) + '</p></blockquote>' + (cap ? '<figcaption>' + cap + '</figcaption>' : "") + '</figure></li>';
    }).join("");

    var counts = [[D.themes.length, "themes"], [D.challenges.filter(function(c){ return c.title; }).length, "challenges"],
      [actionCount(), "actions"], [D.commitments.length, "commitments"]].filter(function(x){ return x[0] > 0; });

    // "Shared on the day": every resource in one place (general reading, then any tied to a challenge). One list
    // copes when only a few tables use a side sheet, where a page per challenge would be mostly empty.
    var shared = (D.resources || []).map(function(r){ return resCard(r); }).join("") + D.challenges.map(function(c){
      return (c.resources || []).map(function(r){ return resCard(r, c); }).join("");
    }).join("");

    var H_ = M.hero && M.hero.src ? M.hero : null;
    return '<section class="hero" aria-labelledby="hero-h">' +
      (H_ ? '<figure class="hero-photo"><img src="' + H_.src + '" alt="' + esc(H_.alt) + '" width="' + H_.width + '" height="' + H_.height + '"></figure>' : "") +
      '<div class="wrap"><div>' +
        '<p class="eyebrow">' + esc(M.series) + '</p>' +
        '<h1 id="hero-h" tabindex="-1">' + esc(M.title) + '</h1>' +
        '<p class="lede">Created from data collected during the ' + esc(O.forum || "community forum") + ' at ' + esc(M.event) + '.</p>' +
        (counts.length ? '<ul class="counts" aria-label="In this playbook">' + counts.map(function(x){ return '<li><b>' + x[0] + '</b> ' + x[1] + '</li>'; }).join("") + '</ul>' : "") +
        '<a class="btn" href="#challenges">Go to the challenges</a>' +
      '</div>' +
      '<div class="hero-ring">' + ring(range(Math.max(M.tables, 8)), {total: Math.max(M.tables, 8)}) + '</div>' +
      '</div></section>' +

      (themeHtml ? '<section class="section" aria-labelledby="themes-h"><div class="wrap">' +
        '<div class="section-head"><h2 id="themes-h">Where support gets stuck</h2>' +
        '<p>Every table listed the challenges its members face. These are the themes that came up, and which tables raised them. Each ring is the room: one arrow per table.</p></div>' +
        '<ul class="themes">' + themeHtml + '</ul>' +
      '</div></section>' : "") +

      '<section class="section" aria-labelledby="challenges-h"><div class="wrap">' +
        '<div class="section-head"><h2 id="challenges-h" tabindex="-1">The challenges</h2>' +
        '<p>Each table picked one challenge and worked through what has helped, what hasn’t, and what to try next. Where two tables picked the same challenge, their work is combined. Open any challenge to see the full detail.</p></div>' +
        '<ul class="cards' + (D.challenges.length % 2 ? " odd" : "") + '">' + cards + '</ul>' +
      '</div></section>' +

      (heard ? '<section class="section" aria-labelledby="heard-h"><div class="wrap">' +
        '<div class="section-head"><h2 id="heard-h">Heard on the day</h2>' +
        '<p>Things people said and wrote at the tables, word for word. No names: the forum ran under the Chatham House Rule.</p></div>' +
        '<ul class="quotes heard">' + heard + '</ul>' +
      '</div></section>' : "") +

      (shared ? '<section class="section" aria-labelledby="shared-h"><div class="wrap">' +
        '<div class="section-head"><h2 id="shared-h" tabindex="-1">Shared on the day</h2>' +
        '<p>Links, tools and reading people recommended to each other on the tables’ side sheets.</p></div>' +
        '<ul class="res-grid">' + shared + '</ul>' +
      '</div></section>' : "") +

      (JOIN ? '<section class="section join" aria-labelledby="join-h"><div class="wrap">' +
        '<h2 id="join-h">Join the conversation</h2>' +
        (O.about ? '<p>' + esc(O.about) + '</p>' : "") +
        '<a class="btn" href="' + safeUrl(JOIN.url) + '">' + esc(JOIN.label) + '</a>' +
      '</div></section>' : "");
  }

  function commitCard(c){
    var ch = c.challenge && byId[c.challenge];
    // name and organisation appear only when the person chose to write them on their card
    var by = [c.name, c.org].filter(Boolean).join(", ");
    return '<li class="commit"><p><q>' + esc(c.text) + '</q>' + srcTag(c) + '</p>' +
      (by ? '<p class="by">By ' + esc(by) + '</p>' : "") +
      (ch ? '<a href="#' + esc(ch.id) + '">' + esc(titleOf(ch)) + '</a>' : '<span class="tag">General</span>') + '</li>';
  }

  function viewChallenge(c){
    var idx = D.challenges.indexOf(c);
    var prev = D.challenges[idx - 1], next = D.challenges[idx + 1];
    var th = themeById[c.theme];
    var ctx = [].concat(c.context && c.context.sectors || [], c.context && c.context.sizes || []);

    var quotes = (c.quotes || []).map(function(q){
      var cap = (q.who ? esc(q.who) : "") + srcTag(q);
      return '<figure class="quote"><blockquote><p>' + esc(q.text) + '</p></blockquote>' + (cap ? '<figcaption>' + cap + '</figcaption>' : "") + '</figure>';
    }).join("");
    if (!quotes && SLOTS) quotes = slot("Quote", FROM.quote) + slot("Quote", FROM.quote);

    function triedList(items, label, from){
      if (!items.length) return SLOTS ? '<ul><li class="is-slot">' + slot(label, from) + '</li></ul>' : "";
      return '<ul>' + items.map(function(x){
        return '<li>' + esc(x.text) + srcTag(x) + '</li>';
      }).join("") + '</ul>';
    }

    var lessons = (c.lessons || []).length ? '<div class="learned"><h3>' + ICON_BULB + 'What we learned</h3><ul class="lessons">' +
      c.lessons.map(function(l){ return '<li>' + esc(textOf(l)) + srcTag(l) + '</li>'; }).join("") + '</ul></div>' : "";
    if (!lessons && SLOTS) lessons = '<div class="lesson-slot">' + slot("What we learned", FROM.lesson) + '</div>';

    var filter = c.actions.length ? '<fieldset class="filter"><legend>Show actions for</legend>' +
      [["all", "Any stage"]].concat(Object.keys(STAGES).map(function(k){ return [k, STAGES[k]]; })).map(function(o, i){
        // the pill text names the radio through aria-labelledby and is hidden itself, or VoiceOver stops on both
        return '<label for="stage-' + o[0] + '"><input type="radio" name="stage" id="stage-' + o[0] + '" value="' + o[0] + '" aria-labelledby="stage-' + o[0] + '-text"' + (i === 0 ? " checked" : "") + '>' +
          '<span id="stage-' + o[0] + '-text" aria-hidden="true">' + esc(o[1]) + '</span></label>';
      }).join("") + '</fieldset>' +
      '<p class="status" id="action-status" role="status" aria-live="polite">' + showing(c.actions.length, c.actions.length) + '</p>' : "";

    var actions = c.actions.map(function(a, i){
      return '<li class="action" data-stages="' + esc((a.stages || []).join(" ")) + '"><h3>' + esc(a.title) + srcTag(a) + '</h3><dl>' +
        '<dt>What to do</dt><dd>' + esc(a.what) + '</dd>' +
        '<dt>What you need</dt><dd>' + esc(a.needs) + '</dd>' +
        '<dt>How it sticks</dt><dd>' + esc(a.sticks) + '</dd></dl>' +
        ((a.stages || []).length ? '<div class="goodfor"><span id="gf-' + esc(c.id) + '-' + i + '">Good for</span><ul class="chips" aria-labelledby="gf-' + esc(c.id) + '-' + i + '">' + a.stages.map(function(s){ return '<li>' + esc(STAGES[s] || s) + '</li>'; }).join("") + '</ul></div>' : "") +
        '</li>';
    }).join("");
    if (!actions && SLOTS){
      // one empty card per action box on Sheet 3, so the page mirrors the paper
      actions = [1, 2, 3].map(function(n){
        return '<li class="action is-slot"><span class="slot-tag">To fill</span><h3>Action ' + n + '</h3><dl>' +
          '<dt>What to do</dt><dd>From Sheet 3, the action box.</dd>' +
          '<dt>What you need</dt><dd>From Sheet 3, “What you need”.</dd>' +
          '<dt>How it sticks</dt><dd>From Sheet 3, “How it sticks”.</dd></dl>' +
          '<div class="goodfor"><span>Good for</span>' + inlineSlot("The ticks on Sheet 3") + '</div></li>';
      }).join("");
    }

    var hasQ = (c.questions || []).length;
    var questions = hasQ || SLOTS ? '<section class="block" aria-labelledby="q-h"><h2 id="q-h">Still open</h2><p class="muted" style="margin:-8px 0 16px">Questions the table didn’t answer. If you have, tell ' + esc(O.short || TEAM) + '.</p>' +
      (hasQ ? '<ul class="qlist">' + c.questions.map(function(q){ return '<li>' + esc(textOf(q)) + srcTag(q) + '</li>'; }).join("") + '</ul>' : slot("Open questions", FROM.question)) + '</section>' : "";

    var hasR = (c.resources || []).length;
    var resources = hasR || SLOTS ? '<section class="block" aria-labelledby="r-h"><h2 id="r-h">Resources</h2>' +
      (hasR ? '<ul class="links">' + c.resources.map(linkItem).join("") + '</ul>' : slot("Resources", FROM.resource)) + '</section>' : "";

    return '<div class="wrap">' +
      '<div class="page-head">' +
        '<p class="crumb"><a href="#challenges">← All challenges</a></p>' +
        (th ? '<p class="eyebrow">' + esc(th.label) + '</p>' : (SLOTS ? '<p class="eyebrow">' + inlineSlot("Theme to fill") + '</p>' : "")) +
        '<h1 tabindex="-1">' + esc(titleOf(c)) + '</h1>' +
        (!c.title && SLOTS ? slot("Challenge title", FROM.title) : "") +
        '<div class="meta">' + ring(c.tables) + '<span>Worked on at ' + tablesText(c.tables, true) + '</span>' +
          (ctx.length ? chips(ctx) : (SLOTS ? inlineSlot("Sectors and sizes, from Sheet 2") : "")) + '</div>' +
        (c.summary ? '<p class="summary">' + esc(c.summary) + '</p>' : (SLOTS ? slot("Why it’s hard", FROM.summary) : "")) +
      '</div>' +
      (quotes ? '<div class="quotes' + ((c.quotes || []).length !== 1 ? " two" : "") + '">' + quotes + '</div>' : "") +
      '<section class="block" aria-labelledby="t-h"><h2 id="t-h">What’s been tried</h2>' +
        '<div class="tried">' +
          '<div class="ok"><h3>' + ICON_OK + 'Helped</h3>' + triedList(c.helped || [], "What helped", FROM.helped) + '</div>' +
          '<div class="no"><h3>' + ICON_NO + 'Got in the way</h3>' + triedList(c.hindered || [], "What got in the way", FROM.hindered) + '</div>' +
        '</div>' + lessons +
      '</section>' +
      '<section class="block" aria-labelledby="a-h"><h2 id="a-h">Actions to try</h2>' + filter +
        '<ul class="actions" id="action-list">' + actions + '</ul>' +
      '</section>' +
      questions + resources +
      '<nav class="pager" aria-label="Other challenges">' +
        (prev ? '<a class="prev" href="#' + esc(prev.id) + '"><span>Previous challenge</span><b>' + esc(titleOf(prev)) + '</b></a>' : "<span></span>") +
        (next ? '<a class="next" href="#' + esc(next.id) + '"><span>Next challenge</span><b>' + esc(titleOf(next)) + '</b></a>' : "") +
      '</nav>' +
    '</div>';
  }

  function viewCommitments(){
    var head = '<div class="wrap"><div class="page-head">' +
      '<p class="eyebrow">Commitments</p>' +
      '<h1 tabindex="-1">One thing I will try, adapt or explore</h1>' +
      '<p class="summary">At the end of the session, everyone wrote one commitment on a card. Some linked it to a challenge, and some added their name.</p></div>';
    if (!D.commitments.length){
      return head + (SLOTS ? '<ul class="commits">' + [0, 1, 2, 3].map(function(){ return '<li class="commit is-slot">' + slot("Commitment", FROM.commitment) + '</li>'; }).join("") + '</ul>' : "") + '</div>';
    }
    var opts = '<option value="all">All commitments (' + D.commitments.length + ')</option>' +
      D.challenges.map(function(c){
        var n = D.commitments.filter(function(x){ return x.challenge === c.id; }).length;
        return n ? '<option value="' + esc(c.id) + '">' + esc(titleOf(c)) + ' (' + n + ')</option>' : "";
      }).join("");
    var general = D.commitments.filter(function(x){ return !x.challenge; }).length;
    if (general) opts += '<option value="general">General (' + general + ')</option>';
    return head +
      '<div class="select"><label for="commit-filter">Show</label><select id="commit-filter">' + opts + '</select>' +
      '<span class="status" id="commit-status" role="status" aria-live="polite" style="margin:0"></span></div>' +
      '<ul class="commits" id="commit-list">' + D.commitments.map(function(c){
        return commitCard(c).replace('<li class="commit"', '<li class="commit" data-challenge="' + esc(c.challenge || "general") + '"');
      }).join("") + '</ul></div>';
  }

  var KIT_HOUR = [
    ["Before", "", "Set-up and arrivals", "Put a kit on every table: the four sheets, a commitment card per person, a table card, thick black markers and sticky notes. Test the slides and clicker. Table leads write their table number on every sheet."],
    ["0 to 10 minutes", "10 minutes", "Welcome", "Who you are, and the playbook you’ll make from the tables. How it gets made: sheets, photos, people check every line. Chatham House Rule, and nobody has to write."],
    ["10 to 22 minutes", "12 minutes", "Question 1: Where does support get stuck?", "7 minutes to list every challenge and star the top three, then pick one to tackle. 5 minutes with the table card up: tables share what they’re tackling, and anyone can move tables."],
    ["22 to 35 minutes", "13 minutes", "Question 2: What has helped, or not?", "What helped, what got in the way, and what you’d do next time, about the challenge on the table card."],
    ["35 to 50 minutes", "15 minutes", "Question 3: What could people try now, and how does it stick?", "Up to three actions: what to try, what you need, how it sticks. Tick who each one is good for."],
    ["50 to 55 minutes", "5 minutes", "Question 4: One thing I will try, adapt or explore", "Everyone writes a commitment on both halves of their card, tears it, keeps the half with the QR code and leaves the other half on the table."],
    ["55 to 60 minutes", "5 minutes", "Share-back and close", "Tables share an action each, as time allows. Skip it if you’re running late."],
    ["After", "About 30 minutes", "Capture", "Photograph every sheet with the table number in shot (sheets only, never people), and collect the card halves."]
  ];
  var KIT_SHEETS = [
    ["Sheet 1 · Question 1", "Where does support get stuck?", [
      ["Who’s at this table?", "Everyone puts one tally mark against their sector, and writes their country. Sectors: Public sector, Finance, Retail, Tech, Education, Charity, Health, Other. Then a line for Countries."],
      ["Every challenge at this table", "Write them all down. Budget, leadership, burnout, proving impact…"],
      ["Our top three", "Three numbered lines."],
      ["The one we’re tackling", "Copy it onto your table card too."]]],
    ["Sheet 2 · Question 2", "What has helped, or not?", [
      ["Helped", "What happened, and why did it work?"],
      ["Got in the way", "What would you change or avoid?"],
      ["If we did it again, we’d…", ""]]],
    ["Sheet 3 · Question 3", "What could people try now, and how does it stick?", [
      ["Action 1, Action 2 and Action 3", "Each has three columns, What to try, What you need and How it sticks, and tick boxes: Good for Just starting, Growing, Established."]]],
    ["Side sheet · All session", "Heard something good? Write it here.", [
      ["Quotes", "Exact words, no names"],
      ["Questions", "Things nobody could answer"],
      ["Resources", "Links, books, people, tools"],
      ["Best thing said today", "The table lead writes it in the last two minutes."]]],
    ["Commitment card · Question 4", "One thing I will try, adapt or explore is…", [
      ["Both halves", "The same prompt and writing lines on each half. People write their commitment on both, tear along the perforation and keep one."],
      ["The half you keep", "A QR code and “Scan for the " + SERIES + ": what every table came up with.”"],
      ["The half you leave", "Name (optional) and Organisation (optional): “Add these only if you’re happy for them to appear in the public playbook.”"]]],
    ["Table card", "Folds into a tent", [
      ["One side", "The table number."],
      ["The other side", "“We’re tackling:” with lines to write the table’s challenge, so the room can see it."]]]
  ];
  var KIT_PROMPTS = [
    ["Question 1", ["What would you fix first if you could?", "What makes support drop off after a good start?", "What does your boss ask that you can’t answer?"]],
    ["Question 2", ["Tell me about a time it worked. What was different?", "What would you never try again?", "What made the difference?"]],
    ["Question 3", ["What could someone do on Monday?", "What would they need to make it happen?", "What stops it fading after a month?"]],
    ["Question 4", ["Make it small enough to start this month. What’s one thing you heard today that you could try?"]]
  ];
  function viewKit(){
    function kitList(group){
      return (D.kit || []).filter(function(f){ return (f.group || "print") === group; }).map(function(f){
        // web pages open in the browser; PDFs and zips download
        var dl = f.kind === "web page" ? "" : " download";
        return '<li><a href="' + esc(f.href) + '"' + dl + '>' + esc(f.title) + ' (' + esc(f.kind) + ', ' + esc(f.size) + ')</a><span class="src">' + esc(f.note) + '</span></li>';
      }).join("");
    }
    var slides = kitList("slides"), webSheets = kitList("html"), files = kitList("print");
    // the kit and the tools that built this site, as an open-source project (kit.source in the settings, or meta.links.source)
    var SOURCE = M.links && M.links.source ? safeUrl(M.links.source) : "";
    var licence = M.kit_licence ? '<p class="summary">' + esc(M.kit_licence) + (SLOTS ? ' <span class="src-tag">Check the licence wording</span>' : "") + '</p>' : "";
    return '<div class="wrap"><div class="page-head">' +
      '<p class="eyebrow">Run your own</p>' +
      '<h1 tabindex="-1">Run your own forum</h1>' +
      '<p class="summary">Everything used to run this session: the plan for the hour, what’s on each sheet, prompts for when a table gets stuck, and the print files. Take it, change it, make it yours.</p>' + licence +
      (SOURCE ? '<p><a class="btn" href="' + SOURCE + '">Get the whole kit on GitHub</a></p>' : "") +
      '</div>' +
      '<section class="block" aria-labelledby="kit-hour"><h2 id="kit-hour">The hour, in seven parts</h2>' +
        '<ol class="kit-hour">' + KIT_HOUR.map(function(r){
          return '<li><h3>' + esc(r[2]) + '</h3><p class="when">' + esc(r[0]) + (r[1] ? " · " + esc(r[1]) : "") + '</p><p>' + esc(r[3]) + '</p></li>';
        }).join("") + '</ol></section>' +
      (slides ? '<section class="block" aria-labelledby="kit-slides"><h2 id="kit-slides">The slides</h2>' +
        '<p>The deck used on the day, with a slide and a timer for each question and the facilitator’s notes and prompts. Change anything you like.</p>' +
        '<ul class="links">' + slides + '</ul></section>' : "") +
      '<section class="block" aria-labelledby="kit-sheets"><h2 id="kit-sheets">What’s on each sheet</h2>' +
        '<p>The sheets are A1 posters, one per question, plus a side sheet that stays out all session. Here’s every word on them, to copy into your own versions.</p>' +
        '<div class="kit-sheets">' + KIT_SHEETS.map(function(sh){
          return '<section class="kit-sheet" aria-label="' + esc(sh[0]) + '"><p class="eyebrow">' + esc(sh[0]) + '</p><h3>' + esc(sh[1]) + '</h3><dl>' +
            sh[2].map(function(z){ return '<dt>' + esc(z[0]) + '</dt>' + (z[1] ? '<dd>' + esc(z[1]) + '</dd>' : ""); }).join("") + '</dl></section>';
        }).join("") + '</div>' +
        '<p class="note">Every sheet’s footer says: “All of this goes into the ' + esc(SERIES) + '. No names, please.”</p>' +
        (webSheets ? '<h3 class="kit-sub">Each sheet as a web page</h3><p>Every sheet and card as a page you can type into, print on A4, or save and change. They work with a screen reader, and suit an online table too.</p>' +
          '<ul class="links">' + webSheets + '</ul>' : "") +
      '</section>' +
      '<section class="block" aria-labelledby="kit-prompts"><h2 id="kit-prompts">If a table gets stuck</h2>' +
        '<div class="kit-prompts">' + KIT_PROMPTS.map(function(q){
          return '<div><h3>' + esc(q[0]) + '</h3><ul>' + q[1].map(function(x){ return '<li>' + esc(x) + '</li>'; }).join("") + '</ul></div>';
        }).join("") + '</div></section>' +
      '<section class="block" aria-labelledby="kit-files"><h2 id="kit-files">Print files</h2>' +
        (files ? '<ul class="links">' + files + '</ul>' : (SLOTS ? slot("Print files", "Added from print/out when the playbook is built.") : "<p>Ask " + esc(TEAM) + " for the print files.</p>")) +
        '<p class="note">These are ready for a professional printer: CMYK, with 3 mm bleed. The lettering is turned into outlines for the printer, so screen readers can’t read these PDFs: the text of every sheet is above. The commitment card’s QR code points to this playbook, so swap in your own.</p>' +
      '</section>' +
      '<section class="block" aria-labelledby="kit-after"><h2 id="kit-after">Turning the sheets into a playbook</h2>' +
        '<p>Photograph every sheet, transcribe it, and check every line against the photos before anything goes live. <a href="#about">How this playbook was made</a> describes how we did it.</p>' +
        (SOURCE ? '<p>The tools are free and open source: the paper kit, the slides, and the Claude Code skill that reads the photos and builds the site, with checks that stop it adding anything that wasn’t written down. You can rebrand all of it with your own name and colours. <a href="' + SOURCE + '">sheets-to-playbook on GitHub</a> has everything, with a guide to running it on the day.</p>' : "") +
        '</section>' +
      '</div>';
  }

  function viewAbout(){
    return '<div class="wrap"><div class="page-head">' +
      '<p class="eyebrow">About this playbook</p>' +
      '<h1 tabindex="-1">How this playbook was made</h1></div>' +
      '<div class="prose">' +
        '<p>This playbook was written by the people in the room at the ' + esc(O.forum || "community forum") + ' at ' + esc(M.event) + ' on ' + esc(M.date) + ', ' + esc(M.time) + '. People came from different organisations, sectors and stages: some just starting out, some working alone, some running established programmes.</p>' +
        '<h2>From the tables to this page</h2>' +
        '<ol class="steps">' +
          '<li>Each of the ' + M.tables + ' tables worked through four questions on large printed sheets: where support gets stuck, what has helped or not, what to try next, and one personal commitment.</li>' +
          '<li>A separate sheet on every table collected good quotes, open questions and resources as they came up.</li>' +
          '<li>After the session, ' + esc(TEAM) + ' photographed every sheet.</li>' +
          '<li>Claude, an AI model, transcribed the sheets and grouped the challenges into themes. It was told not to add anything that wasn’t written down, and to flag anything it couldn’t read.</li>' +
          '<li>' + esc(cap(TEAM)) + ' checked every entry against the original sheets before publishing.</li>' +
        '</ol>' +
        '<h2>Who said what</h2>' +
        '<p>The session ran under the Chatham House Rule. Nothing from the table discussions is linked to a named person or organisation. Commitments show a name only where someone chose to add one.</p>' +
        (O.about ? '<h2>About ' + esc(O.short || O.name) + '</h2><p>' + esc(O.about) + '</p>' : "") +
        '<h2>Keep a copy</h2>' +
        '<p>This playbook is a single web page that works offline, so you can keep it, share it or open it without an internet connection.</p>' +
        (canSave ? '<p><button type="button" class="save-btn" data-save>Download this playbook</button></p>' : "") +
      '</div></div>';
  }

  var VIEWS = {overview:[viewOverview, "Playbook"], commitments:[viewCommitments, "Commitments"], about:[viewAbout, "How it was made"], kit:[viewKit, "Run your own"]};
  // #challenges is the overview scrolled to its challenge list, so it can be linked to directly; the old Resources
  // page now lives on the overview too
  var ALIASES = {challenges: ["overview", "challenges-h"], resources: ["overview", "shared-h"]};
  // one page per challenge, at #<challenge id>
  function DETAIL(key){
    var c = byId[key];
    return c ? {html: viewChallenge(c), label: titleOf(c), nav: "overview", item: c} : null;
  }
