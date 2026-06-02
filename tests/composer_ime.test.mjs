// tests/composer_ime.test.mjs
//
// Behavioral tests for the IME-safe composer controller. Uses Node's built-in
// test runner + JSDOM to dispatch synthetic composition / keydown events and
// assert the controller's submit gating. No browser binary, no Playwright.
//
// Run via: npm run test:composer
//      or: node --test tests/composer_ime.test.mjs

import { test, describe, beforeEach } from 'node:test';
import { strict as assert } from 'node:assert';
import { JSDOM } from 'jsdom';
import {
  createComposerController,
  IME_CONFIRM_ENTER_SUPPRESS_MS,
} from '../app/static/js/composer_controller.js';

function mountComposer() {
  const dom = new JSDOM(
    '<form><textarea></textarea><button type="submit"></button></form>'
  );
  const win = dom.window;
  const form = win.document.querySelector('form');
  const input = win.document.querySelector('textarea');
  const submit = win.document.querySelector('button');

  // The controller calls Date.now() — that's the host Date. JSDOM events
  // dispatch synchronously, so timing-sensitive tests use real setTimeout.

  let submitCount = 0;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitCount += 1;
  });

  const controller = createComposerController(input, submit, form, {
    hasContent: () => input.value.trim().length > 0,
  });

  // Production main.js syncs button.disabled with input content via an input
  // event listener. Mirror that here so disabled-state checks behave the same.
  input.addEventListener('input', () => {
    submit.disabled = input.value.trim().length === 0;
  });
  // Initial state: empty input => disabled.
  submit.disabled = true;

  return {
    dom, win, form, input, submit, controller,
    getSubmitCount: () => submitCount,
  };
}

function dispatchKey(input, key, opts = {}) {
  const win = input.ownerDocument.defaultView;
  const init = {
    key,
    shiftKey: !!opts.shiftKey,
    bubbles: true,
    cancelable: true,
  };
  const e = new win.KeyboardEvent('keydown', init);
  // JSDOM's KeyboardEvent constructor doesn't honor keyCode / isComposing —
  // patch them on the constructed event so the controller can read them.
  if ('keyCode' in opts) {
    Object.defineProperty(e, 'keyCode', { value: opts.keyCode });
  }
  if ('isComposing' in opts) {
    Object.defineProperty(e, 'isComposing', { value: opts.isComposing });
  }
  input.dispatchEvent(e);
  return e;
}

function dispatchComposition(input, type) {
  const win = input.ownerDocument.defaultView;
  input.dispatchEvent(new win.CompositionEvent(type, { bubbles: true }));
}

function setValue(input, value) {
  input.value = value;
  const win = input.ownerDocument.defaultView;
  input.dispatchEvent(new win.Event('input', { bubbles: true }));
}

describe('composer IME-safe Enter', () => {
  test('compositionstart blocks Enter', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchComposition(c.input, 'compositionstart');
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 0);
  });

  test('event.isComposing=true blocks Enter (no local compositionstart)', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchKey(c.input, 'Enter', { isComposing: true });
    assert.equal(c.getSubmitCount(), 0);
  });

  test('keyCode 229 blocks Enter', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchKey(c.input, 'Enter', { keyCode: 229 });
    assert.equal(c.getSubmitCount(), 0);
  });

  test('Enter within IME_CONFIRM_ENTER_SUPPRESS_MS of compositionend is suppressed (one-shot semantics)', () => {
    const c = mountComposer();
    setValue(c.input, 'LC');
    dispatchComposition(c.input, 'compositionstart');
    dispatchComposition(c.input, 'compositionend');
    // FIRST Enter inside the window: blocked.
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 0, 'first Enter inside window should be blocked');
    // SECOND Enter immediately after (still inside 80ms): now sends, because
    // the one-shot suppression was cleared by the first blocked Enter. This
    // protects deliberate rapid follow-up Enters from being eaten by the guard.
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 1, 'one-shot: 2nd Enter inside same window should send');
  });

  test('Enter after the suppression window sends normally', async () => {
    const c = mountComposer();
    setValue(c.input, 'LC200N');
    dispatchComposition(c.input, 'compositionstart');
    dispatchComposition(c.input, 'compositionend');
    await new Promise((r) => setTimeout(r, IME_CONFIRM_ENTER_SUPPRESS_MS + 20));
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 1);
  });

  test('Shift+Enter never sends', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchKey(c.input, 'Enter', { shiftKey: true });
    assert.equal(c.getSubmitCount(), 0);
  });

  test('plain English Enter sends immediately', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 1);
  });

  test('send button click submits through maybeSubmitComposer', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    c.submit.click();
    assert.equal(c.getSubmitCount(), 1);
  });

  test('send button click while composing also submits (explicit intent bypasses IME gate)', () => {
    const c = mountComposer();
    setValue(c.input, 'hello');
    dispatchComposition(c.input, 'compositionstart');
    c.submit.click();
    assert.equal(c.getSubmitCount(), 1);
  });

  test('empty input + Enter does not send', () => {
    const c = mountComposer();
    dispatchKey(c.input, 'Enter');
    assert.equal(c.getSubmitCount(), 0);
  });
});
