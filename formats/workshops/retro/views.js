  /* ---------- Retro: the views ----------
     Inserted into build/template-playbook.html at its views placeholder by build/build.py. One page of notes (how it
     went, ideas by votes, actions) and a page on how it was made. "#actions" is the notes scrolled to the actions. */

  // where each part comes from on the day, for the dashed boxes in a draft
  var FROM = {
    well: "From Sheet 1, Went well. One line each.",
    pain: "From Sheet 1, Got in the way. One line each.",
    question: "From Sheet 2, “How might we…”: each team’s question, word for word.",
    idea: "From Sheet 2, the idea boxes, with the dot votes each one got.",
    action: "From Sheet 3: what we’ll do, who and by when, as written."
  };

  var VIEW_BANNERS = {
    template: ["Template.", "Dashed boxes show where content from the session goes and which sheet it comes from."],
    draft: ["Draft for review.", "Dashed boxes are still empty, and tags like T01 · Sheet 2 show where each line came from. Both disappear when the notes are final."]
  };

  function teamTag(x){
    // which team said it, when more than one team was in the room
    if (!(M.tables > 1)) return "";
    var t = x.tables && x.tables.length ? x.tables : tablesOf(x);
    return t.length ? ' <span class="team-tag">' + esc(tablesText(t)) + '</span>' : "";
  }

  function lines(items, from){
    if (!items.length) return SLOTS ? '<ul><li class="is-slot">' + slot("To fill", from) + '</li></ul>' : '<p class="muted">Nothing written here.</p>';
    return '<ul>' + items.map(function(x){ return '<li>' + esc(textOf(x)) + teamTag(x) + srcTag(x) + '</li>'; }).join("") + '</ul>';
  }

  function votesText(n){ return plural(n || 0, "vote"); }

  function viewOverview(){
    var well = D.went_well || [], pain = D.got_in_way || [], ideas = (D.ideas || []).slice(), acts = D.actions || [], qs = D.questions || [];
    // most votes first; ties keep the order the teams wrote them in
    ideas = ideas.map(function(x, i){ return [x, i]; }).sort(function(a, b){ return (b[0].votes || 0) - (a[0].votes || 0) || a[1] - b[1]; })
                 .map(function(p){ return p[0]; });
    var counts = [[well.length, "went well"], [pain.length, "got in the way"], [ideas.length, plural(ideas.length, "idea").replace(/^\d+ /, "")],
                  [acts.length, plural(acts.length, "action").replace(/^\d+ /, "")]].filter(function(x){ return x[0]; });
    var who = M.tables > 1 ? plural(M.tables, GROUP) : "the " + GROUP;
    var hero = '<section class="hero" aria-labelledby="hero-h"><div class="wrap"><div>' +
      '<p class="eyebrow">' + esc(SERIES) + '</p>' +
      '<h1 id="hero-h" tabindex="-1">' + esc(M.title) + '</h1>' +
      '<p class="lede">What ' + esc(who) + ' wrote down' + (M.event ? ' at ' + esc(M.event) : "") + (M.date ? ', ' + esc(M.date) : "") + '.</p>' +
      (counts.length ? '<ul class="counts" aria-label="In these notes">' + counts.map(function(x){ return '<li><b>' + x[0] + '</b> ' + x[1] + '</li>'; }).join("") + '</ul>' : "") +
      '</div></div></section>';

    var looked = '<section class="section" aria-labelledby="look-h"><div class="wrap">' +
      '<div class="section-head"><h2 id="look-h">How did it go?</h2></div>' +
      '<div class="tried">' +
        '<div class="ok"><h3>' + ICON_OK + 'Went well</h3>' + lines(well, FROM.well) + '</div>' +
        '<div class="no"><h3>' + ICON_NO + 'Got in the way</h3>' + lines(pain, FROM.pain) + '</div>' +
      '</div></div></section>';

    var qHtml = qs.length ? '<ul class="hmw">' + qs.map(function(q){ return '<li><q>' + esc(textOf(q)) + '</q>' + teamTag(q) + srcTag(q) + '</li>'; }).join("") + '</ul>'
      : (SLOTS ? slot("How might we…", FROM.question) : "");
    var iHtml = ideas.length ? '<ol class="ideas-ranked">' + ideas.map(function(x){
        return '<li><span class="votes"><b>' + (x.votes || 0) + '</b> ' + (x.votes === 1 ? "vote" : "votes") + '</span>' +
          '<span class="idea-text">' + esc(textOf(x)) + teamTag(x) + srcTag(x) + '</span></li>';
      }).join("") + '</ol>' : (SLOTS ? slot("Ideas", FROM.idea) : '<p class="muted">No ideas written down.</p>');
    var tried = '<section class="section" aria-labelledby="ideas-h"><div class="wrap">' +
      '<div class="section-head"><h2 id="ideas-h">What could we try?</h2>' +
      (ideas.length ? '<p>Every idea, with the most dot votes first.</p>' : "") + '</div>' +
      qHtml + iHtml + '</div></section>';

    var aHtml = acts.length ? '<ul class="actions">' + acts.map(function(a){
        return '<li class="action"><h3>' + esc(a.what || textOf(a)) + '</h3><dl>' +
          '<dt>Who</dt><dd>' + (a.who ? esc(a.who) : '<span class="muted">Not given</span>') + '</dd>' +
          '<dt>By when</dt><dd>' + (a.when ? esc(a.when) : '<span class="muted">Not given</span>') + '</dd>' +
          '</dl>' + teamTag(a) + srcTag(a) + '</li>';
      }).join("") + '</ul>' : (SLOTS ? '<ul class="actions"><li class="action is-slot">' + slot("Actions", FROM.action) + '</li></ul>' : '<p class="muted">No actions agreed.</p>');
    var doing = '<section class="section" aria-labelledby="actions-h"><div class="wrap">' +
      '<div class="section-head"><h2 id="actions-h" tabindex="-1">What we’ll do</h2>' +
      (acts.length ? '<p>' + plural(acts.length, "action") + ', each with who and by when, as the ' + esc(GROUP) + ' wrote them.</p>' : "") + '</div>' +
      aHtml + '</div></section>';
    return hero + looked + tried + doing;
  }

  function viewAbout(){
    return '<div class="wrap"><div class="page-head">' +
      '<p class="eyebrow">How it was made</p>' +
      '<h1 tabindex="-1">How these notes were made</h1>' +
      '<p class="summary">Each ' + esc(GROUP) + ' wrote on three paper sheets during the session. Afterwards the sheets were photographed, the handwriting was read with the help of AI, and a person checked every uncertain word against the photos.</p>' +
      '</div>' +
      '<section class="block" aria-labelledby="ab-steps"><h2 id="ab-steps">Three questions</h2>' +
        '<ol class="steps-list">' +
          '<li><b>How did it go?</b> What went well, and what got in the way.</li>' +
          '<li><b>What could we try?</b> A “How might we…” question, ideas, and three dot votes each.</li>' +
          '<li><b>What we’ll do.</b> Actions, each with who and by when.</li>' +
        '</ol></section>' +
      '<section class="block" aria-labelledby="ab-rules"><h2 id="ab-rules">Nothing added</h2>' +
        '<p>Every line here traces back to a sheet: nothing was added, and quotes and questions are word for word. Vote counts are the dots on the paper. If a word couldn’t be read for certain, a person checked it against the photo.</p>' +
      '</section></div>';
  }

  var VIEWS = {overview:[viewOverview, "Notes"], about:[viewAbout, "How it was made"]};
  // the actions are a section of the notes, so the header can link straight to them
  var ALIASES = {actions: ["overview", "actions-h"]};
  function DETAIL(){ return null; }
