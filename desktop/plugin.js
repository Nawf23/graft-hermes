import React, { useEffect, useState } from 'react';
import { host, gatewayActivationEpoch } from '@hermes/plugin-sdk';

const h = React.createElement;

export default {
  id: 'graft', name: 'Graft', defaultEnabled: false,
  capabilities: ['preview.executeJavaScript'],
  register(ctx) {
    let state = { features: [], selected: ctx.storage.get('selected', ''), active: false, loading: false, error: '', notice: '', review: null, configured: false };
    const listeners = new Set();
    const update = (patch) => { state = { ...state, ...patch }; listeners.forEach(fn => fn(state)); };
    const scope = () => [gatewayActivationEpoch(), host.state.focusedSessionProfile?.get(), host.state.focusedSessionId?.get()].join(':');
    let currentScope = scope(), source = '', packet = null, fetchedAt = 0, polling = false, disposed = false, wantsAttach = false, dataRefresh = null, reviewJob = null;
    const clientId = crypto.randomUUID();
    const errorText = e => String(e?.message || e).replace(/^Error: /, '');
    async function load() {
      const captured = scope();
      try {
        const status = await ctx.rest('/status');
        if (scope() !== captured || disposed) return;
        const selected = status.features.some(f => f.id === state.selected) ? state.selected : status.features[0]?.id || '';
        update({ ...status, selected, error: '' });
      } catch (e) { if (scope() === captured && !disposed) update({ error: 'Enable the Graft agent plugin, then retry. ' + errorText(e) }); }
    }
    function fetchPacket() {
      const captured = scope(), selected = state.selected, key = captured + ':' + selected;
      if (dataRefresh?.key === key) return dataRefresh.promise;
      const job = { key }; dataRefresh = job;
      job.promise = (async () => {
        const next = await ctx.rest('/features/' + encodeURIComponent(selected) + '/packet', { timeoutMs: 45000 });
        if (scope() !== captured || disposed || !state.active || state.selected !== selected || next.id !== selected) return;
        packet = next; fetchedAt = Date.now(); update({ error: '' });
      })().finally(() => { if (dataRefresh === job) dataRefresh = null; });
      return job.promise;
    }
    async function refresh(force = false) {
      if (!state.selected || !state.active || disposed) return;
      const captured = scope();
      if (force) {
        // A post-write refresh must follow any read that started before the write.
        if (dataRefresh) await dataRefresh.promise.catch(() => {});
        if (scope() !== captured || disposed || !state.active) return;
        await fetchPacket();
      } else if (!packet) return;
      if (!source) source = (await ctx.rest('/renderer')).source;
      if (scope() !== captured || disposed || !state.active || !packet) return;
      const result = await ctx.preview.executeJavaScript(source + '\n;graftMountV1(' + JSON.stringify(packet) + ',' + JSON.stringify({ clientId }) + ');');
      if (!result?.ok) throw new Error('Open the configured Kanboard address in the Browser pane, then attach again.');
    }
    async function attach() {
      if (!ctx.preview.isAvailable()) { update({ error: 'Open Kanboard in this chat’s Browser pane first.' }); return; }
      update({ active: true, loading: true, error: '' });
      try { await refresh(true); if (state.active && packet) update({ notice: 'Attached to ' + packet.origin, error: '' }); } catch (e) { update({ active: false, error: errorText(e) }); }
      finally { update({ loading: false }); }
    }
    async function pause() {
      update({ active: false, notice: 'Detached.', review: null }); packet = null;
      try { await ctx.preview.executeJavaScript('window.__graftV1?.clientId===' + JSON.stringify(clientId) + ' && window.__graftV1.remove()'); } catch {}
    }
    async function tick() {
      if (polling || disposed) return;
      if (scope() !== currentScope) {
        currentScope = scope(); packet = null; source = ''; fetchedAt = 0; wantsAttach = false; reviewJob = null;
        update({ active: false, loading: false, review: null, features: [], selected: '', notice: '', error: '' }); await load(); return;
      }
      if (!state.active || !packet) return;
      polling = true;
      try {
        await refresh();
        const captured = scope();
        const expected = packet?.origin;
        if (!expected) return;
        const events = await ctx.preview.executeJavaScript('location.origin===' + JSON.stringify(expected) + ' && window.__graftV1?.clientId===' + JSON.stringify(clientId) + ' ? window.__graftV1.drain() : []');
        if (scope() !== captured || disposed) return;
        for (const proposal of Array.isArray(events) ? events.slice(0, 1) : []) {
          if (state.review || reviewJob || proposal.clientId !== clientId || proposal.feature_id !== state.selected) continue;
          // Events from a website are untrusted proposals. Only this native pane can confirm.
          const job = { selected: state.selected }; reviewJob = job;
          update({ loading: true, notice: 'Preparing your review…', error: '' });
          ctx.rest('/review', { method: 'POST', timeoutMs: 45000, body: {
            feature_id: job.selected, task_id: proposal.task_id, action: proposal.action, value: proposal.value,
          }}).then(review => {
            if (scope() === captured && !disposed && state.selected === job.selected) update({ review, error: '', notice: 'Review the proposed change below.' });
          }).catch(e => {
            if (scope() === captured && !disposed && state.selected === job.selected) update({ error: errorText(e) });
          }).finally(() => { if (reviewJob === job) { reviewJob = null; update({ loading: false }); } });
        }
        // Renew the page lease and drain proposals independently of slow app reads.
        if (Date.now() - fetchedAt > 10000 && !dataRefresh && !reviewJob && !state.loading) {
          fetchPacket().catch(e => { if (scope() === captured && !disposed) update({ error: errorText(e) }); });
        }
      } catch (e) { update({ error: errorText(e), active: false }); }
      finally { polling = false; }
    }
    async function applyReview() {
      const review = state.review, captured = scope(); if (!review) return;
      update({ loading: true });
      try {
        const result = await ctx.rest('/review/' + encodeURIComponent(review.id) + '/apply', { method: 'POST', body: { confirmed: true }, timeoutMs: 45000 });
        if (scope() !== captured || disposed) return;
        update({ review: null, notice: result.message, error: '' }); await refresh(true);
      } catch (e) { if (scope() === captured) update({ review: null, error: errorText(e) }); }
      finally { if (scope() === captured) update({ loading: false }); }
    }
    function build(request) {
      const session = host.state.focusedSessionId.get() || 'new';
      if (!request.trim()) { update({ error: 'Describe the feature you want.' }); return; }
      wantsAttach = true;
      const sent = host.composer.submit(session, 'Use the Graft plugin for this feature. First call graft_capabilities and graft_data. ' +
        'If needed, use tool_search to find those tools. Read the builder skill with skill_view using the exact name graft:graft-builder. ' +
        'If any Graft tool or that skill is unavailable, stop and report what is missing. Do not search local files, run terminal commands, install software, or modify Mac apps. ' +
        (state.selected ? 'Revise feature ' + state.selected + ' if this request changes it; read its current blueprint with graft_list first. ' : '') +
        'Create this feature in the configured Kanboard app: ' + request.trim());
      if (!sent) { wantsAttach = false; update({ error: 'Could not submit to this chat. Try the same request in the normal chat box.' }); }
      else update({ notice: 'Hermes is designing your feature. Its result will appear here.', error: '' });
    }
    function Pane() {
      const [s, set] = useState(state), [request, setRequest] = useState('');
      useEffect(() => { listeners.add(set); load(); return () => listeners.delete(set); }, []);
      const example = 'Build a release room across all three projects. Show totals for open, overdue and unassigned tasks, estimated workload by owner, and a task table where I can change owners and due dates.';
      const createDisabled = !s.configured || s.loading || !request.trim();
      const border = '1px solid var(--ui-text-quaternary, #94a3b8)';
      const box = { padding: '16px', color: 'var(--ui-text-primary, #17212b)', fontSize: '13px', display: 'grid', gap: '12px' };
      const input = { display: 'block', boxSizing: 'border-box', width: '100%', padding: '10px', borderRadius: '8px', border, background: 'var(--ui-bg-tertiary, #f4f6fa)', color: 'var(--ui-text-primary, #17212b)', font: 'inherit', lineHeight: 1.5 };
      const btn = { padding: '9px 12px', borderRadius: '8px', border, background: 'var(--ui-bg-elevated, #f4f6fa)', color: 'var(--ui-text-primary, #17212b)', cursor: 'pointer' };
      return h('div', { style: box },
        h('div', null, h('strong', { style: { fontSize: '22px', letterSpacing: '-.8px' } }, '↗ graft'), h('p', { style: { opacity: .65, marginTop: '4px' } }, 'Ask your app for a missing feature.')),
        h('label', null, 'What would make this app better?', h('textarea', { value: request, onChange: e => { setRequest(e.target.value); if (state.error === 'Describe the feature you want.') update({ error: '' }); }, rows: 5, placeholder: 'Click here to type or paste your feature request…', style: { ...input, minHeight: '136px', border: '2px solid var(--ui-text-quaternary, #94a3b8)', marginTop: '8px', resize: 'vertical' } })),
        h('button', { type: 'button', onClick: () => { setRequest(example); if (state.error === 'Describe the feature you want.') update({ error: '' }); }, style: { ...btn, justifySelf: 'start', fontSize: '12px' } }, 'Fill with release-room example'),
        h('button', { onClick: () => build(request), style: { ...btn, background: '#195cff', border: '1px solid #195cff', color: '#fff', fontWeight: 600, opacity: createDisabled ? .5 : 1, cursor: createDisabled ? 'not-allowed' : 'pointer' }, disabled: createDisabled }, 'Create or revise feature'),
        !s.configured && h('p', null, 'Add the app address, username and personal API token in Settings → Plugins → Graft.'),
        h('label', null, 'Saved features', h('select', { style: { ...input, marginTop: '7px' }, value: s.selected, onChange: e => { packet = null; ctx.storage.set('selected', e.target.value); update({ selected: e.target.value, review: null }); } },
          !s.features.length && h('option', { value: '' }, 'Create your first feature'), ...s.features.map(f => h('option', { key: f.id, value: f.id }, f.title + ' · v' + f.revision)))),
        h('div', { style: { display: 'flex', gap: '8px' } },
          h('button', { style: btn, onClick: s.active ? pause : attach, disabled: !s.selected || s.loading }, s.loading ? 'Working…' : s.active ? 'Detach' : 'Attach to app'),
          h('button', { style: btn, onClick: () => load() }, 'Refresh')),
        s.error && h('p', { role: 'alert', style: { padding: '10px', border, borderRadius: '8px' } }, s.error),
        s.notice && h('p', { role: 'status', style: { opacity: .75 } }, s.notice),
        s.review && h('section', { style: { border, borderRadius: '10px', padding: '12px', display: 'grid', gap: '10px' } },
          h('strong', null, 'Review app change'), h('span', null, s.review.title), h('span', { style: { opacity: .7 } }, 'Task #' + s.review.task_id),
          h('span', null, s.review.label + ': ' + s.review.before + ' → ' + s.review.after),
          h('span', { style: { fontSize: '11px', opacity: .65 } }, 'This changes the original task in Kanboard.'),
          h('button', { style: btn, onClick: applyReview, disabled: s.loading }, s.loading ? 'Applying…' : 'Apply this change'),
          h('button', { style: btn, onClick: () => update({ review: null, notice: 'Change discarded.' }), disabled: s.loading }, 'Discard')),
        h('p', { style: { fontSize: '11px', opacity: .5 } }, 'Works with the configured Kanboard app. Record changes require your confirmation here.'));
    }
    ctx.register({ id: 'pane', area: 'panes', title: 'Graft', data: { placement: 'right', width: '310px' }, render: () => h(Pane) });
    ctx.onEvent('plugin.graft.feature.updated', async ({ payload }) => {
      await load(); if (disposed) return;
      if (payload?.id) { ctx.storage.set('selected', payload.id); packet = null; update({ selected: payload.id, review: null }); }
      if (wantsAttach) { wantsAttach = false; await attach(); }
    });
    ctx.onEvent('plugin.graft.data.updated', () => { fetchedAt = 0; });
    ctx.setInterval(tick, 1500);
    ctx.onDispose(() => { disposed = true; listeners.clear(); try { ctx.preview.executeJavaScript('window.__graftV1?.clientId===' + JSON.stringify(clientId) + ' && window.__graftV1.remove()').catch(() => {}); } catch {} });
  },
};
