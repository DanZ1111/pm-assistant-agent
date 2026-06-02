// app/static/js/composer_controller.js
//
// ChatGPT-style composer controller with IME-safe Enter handling. Wires a
// <textarea> + send button + form into a unified send pipeline that survives
// Chinese / Japanese / Korean input-method composition. Used by both the
// bottom dock composer and the assistant side-panel composer.
//
// Defense in depth against IME-confirmation Enter (four layers):
//   1. Local isComposing flag (tracked via compositionstart / compositionend)
//   2. event.isComposing (W3C standard property)
//   3. event.keyCode === 229 (legacy Safari / older Edge IME signal)
//   4. One-shot suppressNextEnterUntil window after compositionend
//      Catches Chrome + Sogou Pinyin / Edge + Microsoft Pinyin where
//      compositionend fires BEFORE the Enter keydown that triggered it,
//      so all three other guards are already cleared by the time the
//      Enter handler runs. The window is one-shot — it self-clears after
//      blocking exactly one Enter, so a deliberate rapid follow-up Enter
//      still works.
//
// Submission paths:
//   - Keyboard Enter (IME-gated): keydown handler → maybeSubmitComposer
//   - Send-button click (NOT IME-gated, explicit user intent): click handler
//     intercepts, calls preventDefault, then maybeSubmitComposer
//   Both paths share trim / disabled / final-submit logic in one helper.

export const IME_CONFIRM_ENTER_SUPPRESS_MS = 80;

export function createComposerController(input, submit, form, hooks) {
  hooks = hooks || {};
  const hasContent = hooks.hasContent || (() => input.value.trim().length > 0);

  const state = {
    input: input,
    submit: submit,
    form: form,
    isComposing: false,
    suppressNextEnterUntil: 0,
  };

  function maybeSubmitComposer() {
    if (state.submit.disabled) return false;
    if (!hasContent()) return false;
    state.form.requestSubmit();
    return true;
  }

  function shouldSuppressEnterForIME(e) {
    if (state.isComposing) return true;
    if (e.isComposing) return true;
    if (e.keyCode === 229) return true;
    if (state.suppressNextEnterUntil && Date.now() < state.suppressNextEnterUntil) {
      // One-shot: clear the window after blocking exactly one Enter,
      // so a deliberate rapid follow-up Enter still works.
      state.suppressNextEnterUntil = 0;
      return true;
    }
    return false;
  }

  input.addEventListener('compositionstart', () => {
    state.isComposing = true;
    state.suppressNextEnterUntil = 0;
  });

  input.addEventListener('compositionend', () => {
    state.isComposing = false;
    state.suppressNextEnterUntil = Date.now() + IME_CONFIRM_ENTER_SUPPRESS_MS;
  });

  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    if (e.shiftKey) return;
    if (shouldSuppressEnterForIME(e)) return;
    e.preventDefault();
    maybeSubmitComposer();
  });

  // Send button: explicit click, bypasses IME gate, shares final-submit path.
  // We intercept the click and route through the helper so trim / disabled
  // checks stay consistent with the keyboard path. The button keeps
  // type="submit" for accessibility (screen readers, keyboard nav).
  submit.addEventListener('click', (e) => {
    e.preventDefault();
    maybeSubmitComposer();
  });

  return {
    state: state,
    maybeSubmitComposer: maybeSubmitComposer,
    shouldSuppressEnterForIME: shouldSuppressEnterForIME,
  };
}
