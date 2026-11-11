import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

test('slow data and review requests do not block the page heartbeat or proposal queue', async () => {
  const file = new URL('../desktop/plugin.js', import.meta.url);
  const code = (await readFile(file, 'utf8'))
    .replace(/^import .*;\n/gm, '')
    .replace('export default {', 'globalThis.plugin = {');
  let clock = 1000, cursor = 0, effectStarted = false, contribution, tick;
  const hooks = [], events = [], calls = [];
  let mounts = 0, holdData = false, releaseData, releaseReview;
  const packet = { id: 'feature', origin: 'http://127.0.0.1:8460', revision: 1, view: { widgets: [] } };
  const sandbox = {
    React: { createElement: (type, props, ...children) => ({ type, props: props || {}, children }) },
    useState(initial) {
      const index = cursor++;
      if (!(index in hooks)) hooks[index] = initial;
      return [hooks[index], next => { hooks[index] = next; }];
    },
    useEffect(fn) { if (!effectStarted) { effectStarted = true; fn(); } },
    host: { state: { focusedSessionId: { get: () => 'chat' }, focusedSessionProfile: { get: () => 'default' } } },
    gatewayActivationEpoch: () => 1,
    crypto: { randomUUID: () => 'client' },
    Date: { now: () => clock },
  };
  vm.runInNewContext(code, sandbox, { filename: 'graft-plugin.js' });
  const ctx = {
    storage: { get: () => '', set() {} },
    register(value) { contribution = value; },
    onEvent() {}, onDispose() {},
    setInterval(fn) { tick = fn; },
    rest(path) {
      calls.push(path);
      if (path === '/status') return Promise.resolve({ configured: true, features: [{ id: 'feature', title: 'Release room' }] });
      if (path === '/renderer') return Promise.resolve({ source: '/* renderer */' });
      if (path.endsWith('/packet')) return holdData ? new Promise(resolve => { releaseData = resolve; }) : Promise.resolve(packet);
      if (path === '/review') return new Promise(resolve => { releaseReview = resolve; });
      throw new Error('Unexpected route: ' + path);
    },
    preview: {
      isAvailable: () => true,
      executeJavaScript(script) {
        if (script.includes('.drain()')) return Promise.resolve(events.splice(0));
        mounts++;
        return Promise.resolve({ ok: true });
      },
    },
  };
  const flush = () => new Promise(resolve => setImmediate(resolve));
  const render = () => { cursor = 0; return contribution.render().type(); };
  function button(node, label) {
    if (!node || typeof node !== 'object') return null;
    if (node.type === 'button' && node.children.includes(label)) return node;
    for (const child of (node.children || []).flat(Infinity)) {
      const found = button(child, label); if (found) return found;
    }
    return null;
  }
  async function responsiveTick() {
    let timeout;
    const outcome = await Promise.race([
      tick().then(() => 'done'),
      new Promise(resolve => { timeout = setTimeout(() => resolve('blocked'), 100); }),
    ]);
    clearTimeout(timeout);
    assert.equal(outcome, 'done', 'network work blocked the heartbeat');
  }
  sandbox.plugin.register(ctx);
  render(); await flush();
  await button(render(), 'Attach to app').props.onClick();
  holdData = true; clock += 11000;
  await responsiveTick();
  assert.equal(typeof releaseData, 'function', 'background data refresh did not start');
  events.push({ clientId: 'client', feature_id: 'feature', task_id: 1, action: 'reassign', value: 2 });
  await responsiveTick();
  assert.equal(calls.filter(path => path === '/review').length, 1, 'proposal waited for the slow data request');
  await responsiveTick();
  assert.ok(mounts >= 4, 'heartbeat stopped while the review request was pending');
  releaseReview({ id: 'review', task_id: 1, title: 'Demo task' }); await flush();
  assert.equal(hooks[0].review.id, 'review', 'review did not reach the trusted pane');
  assert.equal(hooks[0].loading, false);
  releaseData(packet); await flush();
});
