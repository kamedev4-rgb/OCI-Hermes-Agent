---
name: browser-hybrid
description: Route browser tasks between Hermes built-in browser tools and the external agent-browser CLI. Prefer built-in browser for navigation, snapshots, vision, and console debugging; use agent-browser only for fine-grained interactions like hover, upload, drag-and-drop, select, checkbox control, and rich DOM getters.
version: 1.0.0
author: MyKNOT
license: MIT
metadata:
  hermes:
    tags: [browser, browser-automation, cli, routing, agent-browser]
---

# Browser Hybrid Routing

Use this skill whenever a task needs browser automation and the built-in browser may be insufficient for advanced UI control.

## Core policy

1. Start with Hermes built-in browser tools.
2. Use `browser_snapshot`, `browser_console`, and `browser_vision` to understand the page.
3. Switch to `agent-browser` only when the required interaction is missing, awkward, or unreliable in built-in browser.
4. After a specialized `agent-browser` step, return to built-in browser if that makes the rest of the task simpler.
5. Prefer the smallest tool switch that solves the problem.

## Prefer built-in browser for

- page navigation
- accessibility-tree exploration
- ref-based click/type flows
- visual inspection of layout
- console and JS error debugging
- simple forms
- extracting page state with `browser_console(expression=...)`

## Prefer agent-browser for

Use `agent-browser` when the task requires one or more of:

- `hover`
- `dblclick`
- `focus`
- `select`
- `check` / `uncheck`
- `drag`
- `upload`
- `scrollintoview`
- semantic locators by role / text / label / placeholder / testid
- rich getters such as `get html`, `get attr`, `get value`, `get styles`, `get count`, `get box`

## Detection and verification

Before using `agent-browser`, verify it exists:

```bash
command -v agent-browser
agent-browser --version
```

If unavailable, do not assume it exists. Continue with built-in browser plus JS/vision fallbacks.

## Fallback order

1. built-in browser tools
2. `browser_console(expression=...)` for DOM inspection / JS extraction
3. `browser_vision` for layout or visual-state understanding
4. `agent-browser` only if confirmed installed

## Escalation rule

If built-in browser fails twice on the same interaction and the task maps to an `agent-browser` strength, check for `agent-browser` and switch.

Escalate earlier than that when the page appears to be a component-heavy app where the real controls are hidden behind framework internals, especially:

- Salesforce / Experience Cloud / LWR pages
- custom elements with shadow DOM
- pages where built-in snapshots expose controls but `browser_console(expression=...)` cannot reach matching DOM nodes directly

In those cases, prefer `agent-browser` for direct DOM inspection and scripted interaction instead of spending multiple turns fighting built-in browser abstractions.

## Extraction heuristics learned from use

- For X/Twitter article-style posts where the content is already expanded in the main tweet/article, built-in browser is usually enough. Navigate, then extract from the visible `article` content with `browser_console(expression=...)` rather than escalating to `agent-browser`.
- For Salesforce/LWR search portals with shadow-root components, `agent-browser eval` is often the fastest path: inspect the component's shadow root, set form values programmatically, click the search button, then parse the returned text for the target field.

## Communication policy

On Salesforce Experience Cloud / LWR / custom-element-heavy sites, built-in browser snapshots may expose visible controls while `browser_console` cannot reliably query them from the light DOM. If you see custom tags such as `c-*`, `community_*`, or `webruntime-*`, check whether the real controls live inside a component shadow root.

Preferred tactic:

1. Use built-in browser first to confirm the page and visible labels.
2. If DOM queries fail or return empty results, switch to `agent-browser eval`.
3. Query the host custom element, enter `shadowRoot`, then inspect or manipulate the inner controls there.
4. For search forms, set values, dispatch both `input` and `change`, click the search button, wait, then read `root.textContent` or extract result fields.

Example pattern:

```bash
agent-browser eval "(async () => {
  const root = document.querySelector('c-catalog-search-product')?.shadowRoot;
  const setVal = (sel, val) => {
    const el = root.querySelector(sel);
    if (!el) return false;
    el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
    return true;
  };
  setVal('select[name=CategoryName__c]', '自動倉庫');
  setVal('input[name=ProductName__c]', 'ISM3600');
  Array.from(root.querySelectorAll('button')).find(b => /検索/.test(b.textContent || ''))?.click();
  await new Promise(r => setTimeout(r, 5000));
  return (root.textContent || '').replace(/\s+/g, ' ');
})()"
```

Use this pattern when the page is visibly interactive but normal DOM inspection misses the real controls.

## Communication policy

- Keep tool-selection explanations short.
- If `agent-browser` is unavailable, say so briefly and continue with the best built-in path.
- Do not dump internal routing logic unless it affects the outcome.

## Typical `agent-browser` commands

```bash
agent-browser open https://example.com
agent-browser snapshot
agent-browser hover "#menu-button"
agent-browser select "#country" "JP"
agent-browser upload "input[type=file]" "/path/to/file.pdf"
agent-browser get attr "#submit" disabled
agent-browser close
```

## Notes

- Do not replace built-in browser wholesale.
- Use `agent-browser` only for the delta it uniquely solves.
- For destructive actions in a browser, make sure user intent is clear before proceeding.
