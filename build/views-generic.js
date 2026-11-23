  /* ---------- Any workshop: the generic views ----------
     Used when a workshop has no views.js of its own. The page is laid out from the "page" part of its output.json
     (D.page): a hero with counts, then one section per entry, each one of these types:

       lists    one to four lists side by side ({"parts": [{"path", "label", "icon": "ok"|"no"}]})
       ranked   items by votes, most first ({"path", "votes": "votes", "questions": "<path of How might we lines>"})
       cards    rows as cards: a title field, labelled parts and ticks ({"path", "title_field", "fields": [[key, label]],
                "ticks": {"key", "label", "labels": {value: label}}, "sort": {"field", "order": [values]}})
       scale    a 1 to N score per area ({"path", "area", "score", "note", "max": 5, "low", "high"})
       quotes   lines in quotation marks ({"path"})
       list     one list ({"path"})

     Every section can have an "intro" sentence and a "from" line, shown in a draft where the section is still empty.
     "nav": true gives the section its own link in the header, at #<section id> (the workshop's pages list it). The
     "How it was made" page comes from the agenda (D.agenda). */

  var P = D.page || {sections: []};

  function teamTag(x){
    if (!(M.tables > 1)) return "";
    var t = x.tables && x.tables.length ? x.tables : tablesOf(x);
    return t.length ? ' <span class="team-tag">' + esc(tablesText(t)) + '</span>' : "";
  }
  function itemsAt(path){ return (D[path] || []).filter(function(x){ return x != null; }); }
  function emptySlot(sec, label){ return SLOTS ? slot(label || sec.title, sec.from || "") : '<p class="muted">Nothing written here.</p>'; }
  function lineItem(x){ return '<li>' + esc(textOf(x)) + teamTag(x) + srcTag(x) + '</li>'; }

  var RENDER = {
    lists: function(sec){
      var n = sec.parts.length;
      return '<div class="lists cols-' + n + (n === 2 && sec.parts[0].icon ? ' tried' : '') + '">' + sec.parts.map(function(part){
        var items = itemsAt(part.path), icon = part.icon === "ok" ? ICON_OK : part.icon === "no" ? ICON_NO : "";
        return '<div class="' + (part.icon || "") + '"><h3>' + icon + esc(part.label) + '</h3>' +
          (items.length ? '<ul>' + items.map(lineItem).join("") + '</ul>' : (SLOTS ? slot("To fill", part.from || sec.from || "") : '<p class="muted">Nothing written here.</p>')) + '</div>';
      }).join("") + '</div>';
    },
    ranked: function(sec){
      var v = sec.votes || "votes";
      var items = itemsAt(sec.path).map(function(x, i){ return [x, i]; })
        .sort(function(a, b){ return (b[0][v] || 0) - (a[0][v] || 0) || a[1] - b[1]; }).map(function(p){ return p[0]; });
      var qs = sec.questions ? itemsAt(sec.questions) : [];
      var qHtml = qs.length ? '<ul class="hmw">' + qs.map(function(q){ return '<li><q>' + esc(textOf(q)) + '</q>' + teamTag(q) + srcTag(q) + '</li>'; }).join("") + '</ul>' : "";
      if (!items.length) return qHtml + emptySlot(sec);
      return qHtml + '<ol class="ideas-ranked">' + items.map(function(x){
        var n = x[v] || 0;
        return '<li><span class="votes"><b>' + n + '</b> ' + (n === 1 ? (sec.one || "vote") : (sec.many || "votes")) + '</span>' +
          '<span class="idea-text">' + esc(textOf(x)) + teamTag(x) + srcTag(x) + '</span></li>';
      }).join("") + '</ol>';
    },
    cards: function(sec){
      var items = itemsAt(sec.path);
      if (sec.sort){
        // e.g. risks with the most likely first: {"field": "likelihood", "order": ["high", "medium", "low"]}
        var rank = function(a){ var i = sec.sort.order.indexOf(String(a[sec.sort.field] || "")); return i < 0 ? 99 : i; };
        items = items.map(function(x, i){ return [x, i]; }).sort(function(a, b){ return rank(a[0]) - rank(b[0]) || a[1] - b[1]; }).map(function(p){ return p[0]; });
      }
      if (!items.length) return SLOTS ? '<ul class="actions"><li class="action is-slot">' + slot(sec.title, sec.from || "") + '</li></ul>' : '<p class="muted">Nothing written here.</p>';
      var tk = sec.ticks;
      return '<ul class="actions">' + items.map(function(a){
        var tv = tk ? a[tk.key] : null, picked = Array.isArray(tv) ? tv : (tv ? [tv] : []);
        var marks = picked.length ? chips(picked.map(function(k){ return (tk.labels || {})[k] || k; })) : "";
        return '<li class="action"><h3>' + esc(a[sec.title_field || "text"] || textOf(a)) + '</h3>' +
          ((sec.fields || []).length ? '<dl>' + sec.fields.map(function(f){
            return '<dt>' + esc(f[1]) + '</dt><dd>' + (a[f[0]] ? esc(a[f[0]]) : '<span class="muted">Not given</span>') + '</dd>';
          }).join("") + '</dl>' : "") +
          (marks ? '<div class="marks">' + (tk.label ? '<span class="marks-label">' + esc(tk.label) + '</span>' : "") + marks + '</div>' : "") +
          teamTag(a) + srcTag(a) + '</li>';
      }).join("") + '</ul>';
    },
    scale: function(sec){
      var items = itemsAt(sec.path), max = sec.max || 5;
      if (!items.length) return emptySlot(sec);
      return '<table class="scale"><caption class="visually-hidden">' + esc(sec.title) + ', scored 1 to ' + max + (sec.low ? ' (1 is ' + esc(sec.low) + ', ' + max + ' is ' + esc(sec.high) + ')' : "") + '</caption>' +
        '<thead><tr><th scope="col">' + esc(sec.area_label || "Area") + '</th><th scope="col">Score</th><th scope="col">' + esc(sec.note_label || "Why") + '</th></tr></thead><tbody>' +
        items.map(function(x){
          var s = parseInt(x[sec.score || "score"], 10), ok = s >= 1 && s <= max;
          var meter = '<span class="meter" aria-hidden="true">' + range(max).map(function(i){ return '<i' + (ok && i <= s ? ' class="on"' : "") + '></i>'; }).join("") + '</span>';
          return '<tr><th scope="row">' + esc(x[sec.area || "area"] || "") + teamTag(x) + '</th><td>' + meter +
            '<span class="score">' + (ok ? s + ' of ' + max : '<span class="muted">Not scored</span>') + '</span></td><td>' +
            (x[sec.note || "note"] ? esc(x[sec.note || "note"]) : '<span class="muted">Not given</span>') + srcTag(x) + '</td></tr>';
        }).join("") + '</tbody></table>' +
        (sec.low ? '<p class="scale-key">1 is ' + esc(sec.low) + '; ' + max + ' is ' + esc(sec.high) + '.</p>' : "");
    },
    quotes: function(sec){
      var items = itemsAt(sec.path);
      return items.length ? '<ul class="hmw">' + items.map(function(q){ return '<li><q>' + esc(textOf(q)) + '</q>' + teamTag(q) + srcTag(q) + '</li>'; }).join("") + '</ul>' : emptySlot(sec);
    },
    list: function(sec){
      var items = itemsAt(sec.path);
      return items.length ? '<ul class="plain-list">' + items.map(lineItem).join("") + '</ul>' : emptySlot(sec);
    }
  };

  function viewOverview(){
    var counts = (P.counts || []).map(function(c){
      var n = itemsAt(c[0]).length; return n ? [n, n === 1 ? c[1] : (c[2] || c[1] + "s")] : null;
    }).filter(Boolean);
    var who = M.tables > 1 ? plural(M.tables, GROUP) : "the " + GROUP;
    var hero = '<section class="hero" aria-labelledby="hero-h"><div class="wrap"><div>' +
      '<p class="eyebrow">' + esc(SERIES) + '</p>' +
      '<h1 id="hero-h" tabindex="-1">' + esc(M.title) + '</h1>' +
      '<p class="lede">What ' + esc(who) + ' wrote down' + (M.event ? ' at ' + esc(M.event) : "") + (M.date ? ', ' + esc(M.date) : "") + '.</p>' +
      (counts.length ? '<ul class="counts" aria-label="In these notes">' + counts.map(function(x){ return '<li><b>' + x[0] + '</b> ' + esc(x[1]) + '</li>'; }).join("") + '</ul>' : "") +
      '</div></div></section>';
    return hero + P.sections.map(function(sec){
      var body = (RENDER[sec.type] || RENDER.list)(sec);
      return '<section class="section" aria-labelledby="' + esc(sec.id) + '-h"><div class="wrap">' +
        '<div class="section-head"><h2 id="' + esc(sec.id) + '-h" tabindex="-1">' + esc(sec.title) + '</h2>' +
        (sec.intro ? '<p>' + esc(sec.intro) + '</p>' : "") + '</div>' + body + '</div></section>';
    }).join("");
  }

  function viewAbout(){
    var agenda = D.agenda || [];
    return '<div class="wrap"><div class="page-head">' +
      '<p class="eyebrow">How it was made</p>' +
      '<h1 tabindex="-1">How these notes were made</h1>' +
      '<p class="summary">Each ' + esc(GROUP) + ' wrote on ' + (agenda.length === 1 ? 'a paper sheet' : agenda.length + ' paper sheets') + ' during the session. Afterwards the sheets were photographed, the handwriting was read with the help of AI, and a person checked every uncertain word against the photos.</p>' +
      '</div>' +
      (agenda.length ? '<section class="block" aria-labelledby="ab-steps"><h2 id="ab-steps">' + (agenda.length === 1 ? "The question" : agenda.length + " questions") + '</h2>' +
        '<ol class="steps-list">' + agenda.map(function(a){ return '<li><b>' + esc(a.title) + '</b>' + (a.boxes && a.boxes.length ? ' ' + esc(a.boxes.join(", ")) + '.' : "") + '</li>'; }).join("") + '</ol></section>' : "") +
      '<section class="block" aria-labelledby="ab-rules"><h2 id="ab-rules">Nothing added</h2>' +
        '<p>Every line here traces back to a sheet: nothing was added, and anything quoted is word for word. Numbers, like votes or scores, are what was written on the paper. If a word couldn’t be read for certain, a person checked it against the photo.</p>' +
      '</section></div>';
  }

  var VIEW_BANNERS = {
    template: ["Template.", "Dashed boxes show where content from the session goes and which sheet it comes from."],
    draft: ["Draft for review.", "Dashed boxes are still empty, and tags like T01 · Sheet 2 show where each line came from. Both disappear when the notes are final."]
  };
  var VIEWS = {overview:[viewOverview, P.home_label || "Notes"], about:[viewAbout, "How it was made"]};
  // a section with "nav": true is the notes scrolled to it, with its own link in the header
  var ALIASES = {};
  P.sections.forEach(function(sec){ if (sec.nav) ALIASES[sec.id] = ["overview", sec.id + "-h"]; });
  function DETAIL(){ return null; }
