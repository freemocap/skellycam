import {EventEmitter} from 'node:events';
import assert from 'node:assert/strict';
import test from 'node:test';
import {gracefulPythonShutdown} from '../electron/main/services/graceful-python-shutdown.ts';

class Backend extends EventEmitter {
    exitCode = null;
    signalCode = null;
    kill() { assert.fail('Shutdown must not kill a saving backend'); }
    finish() { this.exitCode = 0; this.emit('exit', 0); }
}

test('HTTP acknowledgement does not allow exit before video saves finish', async () => {
    const child = new Backend();
    let complete = false;
    const shutdown = gracefulPythonShutdown(child, 'http://localhost/shutdown', async () => ({ok: true}))
        .then(() => { complete = true; });
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(complete, false);
    child.finish();
    await shutdown;
    assert.equal(complete, true);
    assert.equal(child.listenerCount('exit'), 0);
});

for (const failure of ['network', 'http']) {
    test(`failed ${failure} request leaves backend running and permits retry`, async () => {
        const child = new Backend();
        await assert.rejects(gracefulPythonShutdown(child, 'http://localhost/shutdown', async () => {
            if (failure === 'network') throw new Error('unreachable');
            return {ok: false, status: 503};
        }), /left running to protect active video saves/);
        assert.equal(child.exitCode, null);
        assert.equal(child.listenerCount('exit'), 0);
        await gracefulPythonShutdown(child, 'http://localhost/shutdown', async () => {
            child.finish();
            return {ok: true};
        });
    });
}

test('backend exit racing a dropped HTTP response is still successful shutdown', async () => {
    const child = new Backend();
    await gracefulPythonShutdown(child, 'http://localhost/shutdown', async () => {
        child.finish();
        throw new Error('connection closed');
    });
    assert.equal(child.listenerCount('exit'), 0);
});

test('already exited backend needs no shutdown request', async () => {
    const child = new Backend();
    child.finish();
    await gracefulPythonShutdown(child, 'http://localhost/shutdown', async () => {
        assert.fail('No request is needed');
    });
});
