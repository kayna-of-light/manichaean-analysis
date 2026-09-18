# Browser Tool Recipes

These examples use Playwright via `run_playwright_code` with the provided `page` object. Prefer dedicated browser tools (`read_page`, `hover_element`, `click_element`, `type_in_page`, `screenshot_page`) for ordinary actions. Use Playwright for scoped reads, SVG coordinate transforms and precise drawing not exposed by the dedicated tools.

Always get page IDs from the current shared browser state. Do not copy old element refs, page IDs, array positions or source-image coordinates into a new review.

## Read one row and reveal its toolbar

```javascript
const displayedLine = '15'; // user's displayed row, not internal index
const selector = `button[aria-label="Open line editor for line ${displayedLine}"]`;
const card = page.locator('.line-card').filter({ has: page.locator(selector) });
await card.scrollIntoViewIfNeeded();
return {
  snapshot: await card.ariaSnapshot(),
  labels: await card.locator('[title^="blob"]').evaluateAll(es => es.map(e => e.title)),
  image: await card.getByRole('img').evaluate(s => ({
    viewBox: s.getAttribute('viewBox'),
    href: s.querySelector('image').getAttribute('href'),
  })),
};
```

Hover `card` before clicking its toolbar button. An invisible toolbar caused timeouts during the trial. Use a screenshot of the scoped card to compare image and transcription, rather than reading thousands of tokens from the whole page.

New/manual boxes may not use the base-token `title` pattern. Inspect their SVG rectangles and rendered labels separately; a query restricted to `[title^="blob"]` is not an inventory of all characters.

## Read warning reasons before targeted zoom

Yellow dots beneath labels are actionable inspection leads, even when they have no tooltip or accessibility label. On displayed line 15 of page 190, each warned token had a second child span styled as a 5-pixel yellow circle. An empty `[title]`/`[aria-label]` warning search did **not** mean there were no warnings. Inspect the label children's DOM when the accessibility snapshot omits the indicators; do not confuse these UI dots with printed underdots.

For the current app, read the same-origin warning endpoint through an in-page `fetch`. Confirm the internal line index from the chooser before filtering, then close the chooser without saving. The following uses the observed page-190 internal index only as an example:

```javascript
const pageNumber = page.url().match(/\/review\/(\d+)(?:[/?#]|$)/)?.[1];
if (!pageNumber) throw new Error('Not on a review page');
const internalLineIndex = 16; // EXAMPLE: verify for the requested displayed row
return await page.evaluate(async ({ pageNumber, internalLineIndex }) => {
  const response = await fetch(`/api/warnings/${pageNumber}`);
  if (!response.ok) throw new Error(`Warning read failed: ${response.status}`);
  const data = await response.json();
  return data.warnings.filter(w => w.lineIndex === internalLineIndex);
}, { pageNumber, internalLineIndex });
```

The response supplies `lineIndex`, `blobId`, `level` and `reasons`. Match these to the actual token, not its array position. In this browser bridge, `page.request.get` failed with an unsupported `Storage.getCookies` protocol method; the in-page read succeeded. Do not retry the unsupported request path or issue mutations to retrieve warnings.

Observed page-190 leads:
- Sha, blob 20: `confusion char`; `diacritic variant ϣ̣ more common here (2.0×)`. Targeted magnification then visually confirmed a separate printed underdot missing from the plain-sha label.
- Final eta, blob 40: `confusion char`; `rarely ends lines (<2%, possible missing successor)`. This did not by itself establish a missing letter.

Warnings direct attention; the scan determines the reading. Inspect unwarned tokens too, and never change a label merely to satisfy corpus frequency.

## Character chooser: changing a label

1. Read the target token's current title and locate it inside the verified card.
2. Click it. Inspect chooser state and preview. The chooser may show an internal line number different from the row label.
3. Use a palette button, or supported keyboard input, then `Save (Enter)`.
4. Re-read the card's saved label; do not trust only the textbox value.

Literal Latin example after opening the correct token:

```javascript
const literal = page.getByRole('button', { name: 'ABC', exact: true });
// Observed current MUI styling indicates the enabled literal mode.
// Reinspect the control if the UI changes.
if (!(await literal.getAttribute('class')).includes('MuiButton-contained')) {
  await literal.click();
}
await page.getByRole('textbox').press('l');
await page.getByRole('button', { name: 'Save (Enter)', exact: true }).click();
```

**Do not use `fill()` on this chooser's read-only proxy textbox.** Its `onChange` intentionally does not update application state. The initial attempted `fill('l')` on page 190 did not save the requested letter; the saved title exposed the failure. Keyboard input in ABC mode succeeded.

`Escape` cancels the chooser. If a magnified preview pushes footer buttons outside the viewport, Escape is safer than repeated clicks or force-clicks. Do not toggle ABC without checking its current mode.

## Inspect a printed mark with more context

The chooser preview is an SVG with an `<image>` element. Its `viewBox` gives the image-space crop. `Zoom out one step` includes surroundings; the control becomes `Zoom back to fit`. Tiny previews can exclude an overline or neighbour's descender, so do not diagnose the mark from the smallest crop alone.

For larger inspection, a temporary overlay can show a crop of the same displayed scan. Add it only to the review app tab, not to the native image-viewer tab, which can reset image layout automatically. This is a **display-only** helper, not a data edit or proof of persistence:

```javascript
// Read the source URL from the selected card before this call.
const image = { href: '/api/image?root=textbody&p=p190_text_body.jpg', width: 936, height: 1304 };
const crop = [60, 590, 370, 57]; // example ONLY: derive from the actual target SVG
return await page.evaluate(({ image, crop }) => {
  document.getElementById('inspection-crop')?.remove();
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  const img = document.createElementNS(ns, 'image');
  svg.id = 'inspection-crop';
  svg.setAttribute('viewBox', crop.join(' '));
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Temporary enlarged scan crop');
  svg.style.cssText = 'position:fixed;left:8px;top:90px;width:760px;height:180px;z-index:9999;background:#ddd';
  img.setAttribute('href', image.href);
  img.setAttribute('width', String(image.width));
  img.setAttribute('height', String(image.height));
  svg.append(img);
  document.body.append(svg);
  return { viewBox: svg.getAttribute('viewBox') };
}, { image, crop });
```

Capture `#inspection-crop` with `screenshot_page`. Change only its `viewBox` to inspect another region. Remove the overlay before interacting with underlying controls and at task end:

```javascript
await page.locator('#inspection-crop').evaluateAll(es => es.forEach(e => e.remove()));
```

The ordinary chooser's SVG lives in a transformed popover; setting its CSS to `position:fixed` can still place the crop relative to that ancestor, clipping it. A top-level temporary overlay avoided this problem. Do not leave cosmetic DOM changes behind or report them as saved corrections.

## Draw using real SVG coordinates

1. Identify the printed glyph visually and read the SVG image/box coordinates.
2. Record the card's current array position and displayed number before enabling `Add bbox`.
3. Hover the card, click `Add bbox`, then reacquire by the verified position. The toolbar disappears in drawing mode, invalidating a locator that depends on its descendant button.
4. Convert source-image coordinates to pointer coordinates using the live SVG matrix.
5. Draw, label, save and inspect the new box. Exit draw mode with Escape.

```javascript
// cardIndex, displayedLine and box are established by prior inspection.
const card = page.locator('.line-card').nth(cardIndex);
if (await card.locator(':scope > span').innerText() !== displayedLine) {
  throw new Error('Row identity changed; reacquire before drawing');
}
const svg = card.getByRole('img');
const points = await svg.evaluate((s, b) => {
  return [[b.x0, b.y0], [b.x1, b.y1]].map(([x, y]) => {
    const p = s.createSVGPoint(); p.x = x; p.y = y;
    const q = p.matrixTransform(s.getScreenCTM());
    return { x: q.x, y: q.y };
  });
}, box);
await page.mouse.move(points[0].x, points[0].y);
await page.mouse.down();
await page.mouse.move(points[1].x, points[1].y, { steps: 5 });
await page.mouse.up();
await page.getByRole('textbox').waitFor({ state: 'visible' });
// Now select the verified label using its palette button and save.
```

Never reuse screen coordinates after scrolling, resizing, opening a dialog or changing zoom. Use source geometry and a freshly evaluated matrix. Distinguish `[x0,y0,x1,y1]` boxes from SVG `viewBox` `[x,y,width,height]`.

Ctrl+click creates a lacuna-dot box; do not use it for an underdot or a speck of unestablished meaning. Ordinary dragging creates a glyph box. Shift-drag can create an unlabelled box without opening the chooser; do not leave such boxes unresolved accidentally.

## Resize and retain only intended duplicate content

Within the line-editor dialog:

- Active original boxes: `<polygon>` in pointer-events-disabled groups. They are reference geometry, not editable rectangles.
- Saved/new boxes: `g > rect[style*="cursor: move"]`.
- Selected saved box: corner handles with styles such as `nw-resize` and `se-resize`.

Click the intended saved rectangle, inspect its coordinates and label, then drag the appropriate handle to a freshly transformed image point. Do not click the same selected rectangle unnecessarily: selection can toggle off and hide `Delete this box`.

When pruning a freshly duplicated row, remove only unwanted **copies** in its local editor. Use a bounded loop if helpful, with the candidates chosen from inspected geometry. Wait for each edit to be reflected before continuing. `Accept` saves the draft; removing a copied box from an unaccepted dialog does not remove the source token.

Do not use broad selectors such as `polygon:nth-of-type(1)` across many `<g>` groups: that matches many elements. Scope to an inspected group/coordinate or a verified locator index. Labels and toolbar identifiers must be reacquired after row insertion.

## Verification and asynchronous calls

- A browser timeout may occur after a mutation has already succeeded. Read the current state before retrying, especially for duplicate, draw, delete or move actions.
- If `run_playwright_code` returns `deferredResultId`, resume that execution with the same page ID and ID, without issuing another overlapping edit.
- Prefer specific state waits (`waitFor` for dialog closure or saved token title) over delays or repeated polling.
- Re-read character titles **and** manual/new-box labels and geometry.
- Reload only after all edits are saved; wait for the target rows to mount and check again.
- Inspect print and overlay again. Verify no duplicate character survived across rows and no existing uncertainty/overline association was lost.
- Leave no unsaved dialog, draw mode or temporary overlay open at completion.

No workflow step makes a missed character disappear as a limitation. Record unidentified errors explicitly and do not mark the page fully reviewed.